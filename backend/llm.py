import re
from dataclasses import dataclass, field
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from config import settings


CODING_SYSTEM_PROMPT = (
    "You are a code generation assistant in a competitive prompting challenge. "
    "The user will describe what they want built. Generate ONLY the code — no "
    "explanations, no markdown fences unless specifically asked. The code should "
    "be complete, runnable, and match the user's requirements exactly."
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
    ) -> LLMResponse:
        """
        Non-streaming generation. Returns the full response with token counts
        and extracted code blocks.
        """
        messages = self._build_messages(
            prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
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
    ) -> AsyncGenerator[str, None]:
        """
        Streaming generation. Yields text chunks as they arrive.
        Useful for WebSocket-based real-time updates.
        """
        messages = self._build_messages(
            prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
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
    ) -> list[dict]:
        """Build the messages array for the API call."""
        messages: list[dict] = [
            {"role": "system", "content": system_prompt or self.system_prompt}
        ]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def extract_code_blocks(text: str) -> str:
        """
        Extract code from markdown fenced code blocks.
        If no fences found, return the full text (assuming it's raw code).
        """
        pattern = r"```(?:\w+)?\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)

        if matches:
            return "\n\n".join(match.strip() for match in matches)

        # No fences found — the response might already be raw code
        return text.strip()
