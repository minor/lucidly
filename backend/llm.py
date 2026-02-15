import re
from dataclasses import dataclass, field
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from config import settings


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

        return ""
