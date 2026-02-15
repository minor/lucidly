import ast
import re
import logging
from dataclasses import dataclass, field
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from config import settings

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AST-based code filtering utilities
# ---------------------------------------------------------------------------


def strip_main_block(code: str) -> str:
    """Remove ``if __name__ == "__main__":`` blocks and bare ``main()`` calls
    from Python source using AST so that only function/class definitions and
    top-level assignments remain.  This is critical for test-suite evaluation
    where the test harness needs to call the defined functions directly.

    If the code cannot be parsed, returns the original string unchanged.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    new_body: list[ast.stmt] = []
    for node in tree.body:
        # Skip ``if __name__ == "__main__": …``
        if isinstance(node, ast.If):
            try:
                test = node.test
                if (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"
                    and len(test.comparators) == 1
                    and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value == "__main__"
                ):
                    continue
            except Exception:
                pass

        # Skip bare ``main()`` expression-statements
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name) and func.id == "main":
                continue

        new_body.append(node)

    tree.body = new_body
    return ast.unparse(tree)


def extract_python_via_ast(text: str) -> str:
    """Try to find valid Python function/class definitions inside *text* by
    attempting ``ast.parse`` on progressively smaller slices.  Useful when an
    LLM returns code without markdown fences.

    Returns the extracted code string, or ``""`` if nothing useful found.
    """
    # First, try parsing the whole text as Python
    stripped = text.strip()
    try:
        tree = ast.parse(stripped)
        # Accept if it has at least one function/class, or is valid script-style code (no def/class)
        has_def = any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in ast.walk(tree))
        if has_def or len(tree.body) > 0:
            return stripped
    except SyntaxError:
        pass

    # Try to find a contiguous block that starts with "def " or "class "
    lines = stripped.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        lstripped = line.lstrip()
        if lstripped.startswith("def ") or lstripped.startswith("class ") or lstripped.startswith("async def "):
            start_idx = i
            break

    if start_idx is None:
        return ""

    # Try parsing from the found start through the end
    candidate = "\n".join(lines[start_idx:])
    try:
        tree = ast.parse(candidate)
        has_def = any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in ast.walk(tree))
        if has_def:
            return candidate
    except SyntaxError:
        # Try trimming from the end line-by-line
        for end in range(len(lines) - 1, start_idx, -1):
            candidate = "\n".join(lines[start_idx:end])
            try:
                tree = ast.parse(candidate)
                has_def = any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in ast.walk(tree))
                if has_def:
                    return candidate
            except SyntaxError:
                continue

    return ""


def run_function_tests_local(code: str, test_suite: list[dict]) -> tuple[float, list[bool]]:
    """Execute Python *code* (typically function definitions) and evaluate it
    against *test_suite* (list of ``{input, expected_output}`` dicts) **in-process**.

    Returns ``(accuracy, results_list)`` where *accuracy* is 0.0–1.0 and
    *results_list* is per-test-case booleans.

    The code is first run through :func:`strip_main_block` to remove
    ``if __name__`` guards before ``exec``-ing.
    """
    if not test_suite:
        return 0.0, []

    # Prepare a clean namespace with common helpers
    namespace: dict = {}

    # Strip main block so exec only defines functions
    clean_code = strip_main_block(code)

    try:
        exec(clean_code, namespace)
    except Exception as exc:
        _log.warning("run_function_tests_local: exec failed: %s", exc)
        return 0.0, [False] * len(test_suite)

    results: list[bool] = []
    for tc in test_suite:
        try:
            actual = eval(tc["input"], namespace)
            expected = eval(tc["expected_output"], namespace)
            results.append(actual == expected)
        except Exception as exc:
            _log.debug("run_function_tests_local: test %s failed: %s", tc["input"], exc)
            results.append(False)

    accuracy = sum(results) / len(results) if results else 0.0
    return accuracy, results


CODING_SYSTEM_PROMPT = (
    "You are a code generation assistant. The user will describe what they want built. "
    "You must output the code inside a single markdown code block (e.g. ```html then newline then your code then ```). "
    "The code should be complete, runnable, and match the user's requirements. "
    "For UI challenges, output one complete HTML document (inline CSS/JS is fine). "
)

REPLICATE_UI_SYSTEM_PROMPT = (
    "You are an expert at replicating landing pages and UIs from a reference screenshot. "
    "You will receive an image of a reference page. Your job is to produce one complete HTML document (with inline CSS and minimal JS if needed) that recreates it as closely as possible. "
    "Match: layout and structure, typography (font families and sizes), colors (backgrounds, text, buttons, links), spacing, borders, and all visible copy. "
    "Output only the HTML inside a single markdown code block (e.g. ```html then newline then your code then ```). "
    "Do not add placeholder content—use the exact text and structure you see. One complete pass; no explanations outside the code block."
)


@dataclass
class LLMResponse:
    """Structured response from an LLM call."""

    response_text: str
    generated_code: str
    prompt_tokens: int
    response_tokens: int
    model: str


class LLM:
    """
    Flexible LLM client that works with any OpenAI-compatible API.

    Swap the base_url to point at different providers:
      - OpenAI:      https://api.openai.com/v1
      - OpenRouter:  https://openrouter.ai/api/v1
      - Anthropic:   https://openrouter.ai/api/v1  (via OpenRouter)
      - Google:      https://generativelanguage.googleapis.com/v1beta/openai
      - xAI:         https://api.x.ai/v1
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        system_prompt: str = CODING_SYSTEM_PROMPT,
        max_tokens: int = settings.max_tokens,
        temperature: float = 0.2,
    ) -> None:
        self.base_url = base_url or settings.openai_base_url
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.default_model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        conversation_history: list[dict] | None = None,
        image_data_url: str | None = None,
    ) -> LLMResponse:
        """
        Non-streaming generation. Returns the full response with token counts
        and extracted code blocks. If image_data_url is provided (e.g. reference screenshot),
        the message includes the image for vision models.
        """
        messages = self._build_messages(
            prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            image_data_url=image_data_url,
        )

        response = await self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            max_completion_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
        )

        choice = response.choices[0]
        response_text = choice.message.content or ""
        usage = response.usage

        return LLMResponse(
            response_text=response_text,
            generated_code=self.extract_code_blocks(response_text),
            prompt_tokens=usage.prompt_tokens if usage else 0,
            response_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
        )

    async def stream(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        conversation_history: list[dict] | None = None,
        image_data_url: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming generation. Yields text chunks as they arrive.
        If image_data_url is provided, the message includes the image for vision models.
        """
        messages = self._build_messages(
            prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            image_data_url=image_data_url,
        )

        stream = await self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            max_completion_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _build_messages(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        conversation_history: list[dict] | None = None,
        image_data_url: str | None = None,
    ) -> list[dict]:
        """Build the messages array for the API call. Supports vision via image_data_url (data URL)."""
        messages: list[dict] = [
            {"role": "system", "content": system_prompt or self.system_prompt}
        ]

        if conversation_history:
            messages.extend(conversation_history)

        if image_data_url:
            user_content: list[dict] = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]
            messages.append({"role": "user", "content": user_content})
            import logging
            logging.getLogger(__name__).info(
                "LLM vision: attaching image to user message, data_url len=%d",
                len(image_data_url),
            )
        else:
            messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def extract_code_blocks(text: str) -> str:
        """
        Extract code from markdown fenced code blocks.
        Allows optional newline after opening fence. If response is truncated
        (e.g. hit max_tokens) and has no closing ```, treat rest of text as code.

        Falls back to AST-based extraction for Python code when no fenced blocks
        or HTML are found (handles responses without code tags).
        """
        if not (text or "").strip():
            return ""

        # Fenced blocks: allow optional newline after ```language
        pattern = r"```(?:\w+)?\s*\n?(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return "\n\n".join(match.strip() for match in matches if match.strip())

        # Truncated response: opening ``` but no closing ``` (e.g. hit token limit)
        open_match = re.search(r"```(?:\w+)?\s*\n?(.*)", text, re.DOTALL)
        if open_match:
            code = open_match.group(1).strip()
            if len(code) > 50:  # avoid treating a short stub as code
                return code

        # No fences: try to extract HTML so we don't put refusal text in iframe
        html_match = re.search(
            r"(<!DOCTYPE\s+html[^>]*>.*?</html>|<html[\s\S]*?</html>)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if html_match:
            return html_match.group(1).strip()

        # If the whole response looks like raw HTML (starts with <), use it
        stripped = text.strip()
        if stripped.startswith("<"):
            return stripped

        # No fences and no HTML: try to find Python code via AST parsing
        ast_code = extract_python_via_ast(text)
        if ast_code:
            return ast_code

        return ""
