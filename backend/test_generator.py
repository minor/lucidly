"""Automatic test generation for challenges based on their description and category."""

import json
from typing import Any
from pydantic import BaseModel
import httpx

from challenges import Challenge, TestCase
from llm import LLM, LLMResponse
from config import settings


class AnthropicLLM:
    """
    Anthropic API client that mimics the LLM interface.
    Uses Anthropic's native API directly (not OpenAI-compatible).
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-6",
        system_prompt: str = "You are a test generation expert. Generate comprehensive test suites for coding challenges. Return only valid JSON.",
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ):
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
    
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
        """Generate a response using Anthropic's API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            
            # Build messages
            messages = []
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model or self.model,
                "max_tokens": max_tokens or self.max_tokens,
                "messages": messages,
                "system": system_prompt or self.system_prompt,
                "temperature": temperature if temperature is not None else self.temperature,
            }
            
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                error_text = response.text
                raise Exception(f"Anthropic API error ({response.status_code}): {error_text}")
            
            data = response.json()
            content = data.get("content", [])
            response_text = ""
            for block in content:
                if block.get("type") == "text":
                    response_text += block.get("text", "")
            
            usage = data.get("usage", {})
            
            return LLMResponse(
                response_text=response_text,
                generated_code=LLM.extract_code_blocks(response_text),
                prompt_tokens=usage.get("input_tokens", 0),
                response_tokens=usage.get("output_tokens", 0),
                model=data.get("model", self.model),
            )


def create_claude_llm() -> LLM | AnthropicLLM:
    """
    Create an LLM instance configured to use Claude API.
    
    Uses Anthropic's native API if ANTHROPIC_API_KEY is available,
    otherwise falls back to OpenRouter (if OPENAI_API_KEY is set).
    """
    # Prefer Anthropic API directly if key is available
    if settings.anthropic_api_key:
        return AnthropicLLM(
            api_key=settings.anthropic_api_key,
            model="claude-opus-4-6",
            system_prompt="You are a test generation expert. Generate comprehensive test suites for coding challenges. Return only valid JSON.",
            temperature=0.3,
        )
    
    # Fall back to OpenRouter if OpenAI key is available
    if settings.openai_api_key:
        return LLM(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openai_api_key,
            model="gpt-5.2-2025-12-11",
            system_prompt="You are a test generation expert. Generate comprehensive test suites for coding challenges. Return only valid JSON.",
            temperature=0.3,
        )
    
    # No API keys - return default (will fail when used)
    raise ValueError(
        "No API key configured. Please set ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file."
    )


class GeneratedTestSuite(BaseModel):
    """A generated test suite for a challenge."""
    test_cases: list[TestCase]
    test_metadata: dict[str, Any]  # Additional metadata about the tests
    execution_type: str  # "function", "ui", "api", "scraping", etc.


class TestGenerator:
    """Generates test suites automatically for challenges."""

    def __init__(self, llm: LLM | AnthropicLLM | None = None):
        # Use Claude by default for test generation
        # Will use Anthropic API directly if ANTHROPIC_API_KEY is set
        self.llm = llm or create_claude_llm()

    async def generate_tests(self, challenge: Challenge) -> GeneratedTestSuite:
        """
        Generate appropriate tests for a challenge based on its category and description.
        
        Returns a GeneratedTestSuite with test cases tailored to the challenge type.
        """
        if challenge.category == "ui":
            return await self._generate_ui_tests(challenge)
        elif challenge.category == "data" or "scraper" in challenge.description.lower() or "scraping" in challenge.description.lower():
            return await self._generate_scraping_tests(challenge)
        elif challenge.category == "function":
            return await self._generate_function_tests(challenge)
        elif "api" in challenge.description.lower() or challenge.category == "api":
            return await self._generate_api_tests(challenge)
        else:
            # Default: try to infer from description
            return await self._generate_generic_tests(challenge)

    async def _generate_ui_tests(self, challenge: Challenge) -> GeneratedTestSuite:
        """Generate visual/UI tests for web development challenges."""
        prompt = f"""You are a test generator for UI/web development challenges.

Challenge: {challenge.title}
Description: {challenge.description}
Image URL: {challenge.image_url or "None"}

Generate a comprehensive test suite for evaluating if a generated HTML/CSS/JS implementation matches the challenge requirements. Focus on:

1. Visual elements (colors, fonts, layout structure)
2. DOM structure (key elements, classes, IDs)
3. Interactive behavior (if applicable)
4. Responsive design (if mentioned)

Return a JSON object with this structure:
{{
  "test_cases": [
    {{
      "input": "description of what to check (e.g., 'check if header exists with class hero')",
      "expected_output": "expected result (e.g., 'header element with class hero found')"
    }}
  ],
  "visual_checks": [
    "List of visual elements to verify (e.g., 'background color is #1a1a2e')"
  ],
  "dom_checks": [
    "List of DOM structure checks (e.g., 'main element contains section with class features')"
  ]
}}

Focus on semantic checks rather than exact code matching. The tests should verify that the output achieves the same visual and functional result as described.
"""

        response = await self.llm.generate(
            prompt,
            system_prompt="You are a test generation expert. Return only valid JSON.",
            temperature=0.3,
        )

        # Parse the response
        import json
        import re
        try:
            # Extract JSON from response
            content = response.response_text
            # Try to find JSON in the response (could be in code blocks or raw)
            code_blocks = LLM.extract_code_blocks(content)
            if code_blocks:
                json_match = json.loads(code_blocks)
            else:
                # Try to find JSON object in the text
                json_match = json.loads(content)
            if isinstance(json_match, str):
                json_match = json.loads(json_match)
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: create basic tests
            json_match = {
                "test_cases": [
                    {
                        "input": "Check if HTML structure matches requirements",
                        "expected_output": "Valid HTML with required elements"
                    }
                ],
                "visual_checks": ["Visual layout matches description"],
                "dom_checks": ["Key DOM elements present"]
            }

        test_cases = [
            TestCase(input=tc.get("input", ""), expected_output=tc.get("expected_output", ""))
            for tc in json_match.get("test_cases", [])
        ]

        return GeneratedTestSuite(
            test_cases=test_cases,
            test_metadata={
                "visual_checks": json_match.get("visual_checks", []),
                "dom_checks": json_match.get("dom_checks", []),
                "image_url": challenge.image_url,
            },
            execution_type="ui",
        )

    async def _generate_scraping_tests(self, challenge: Challenge) -> GeneratedTestSuite:
        """Generate tests for web scraping challenges."""
        prompt = f"""You are a test generator for web scraping challenges.

Challenge: {challenge.title}
Description: {challenge.description}

Generate test cases that verify:
1. The scraper successfully fetches the target page
2. The output structure matches expected format (JSON/list of dicts)
3. Required fields are present (titles, URLs, etc.)
4. Data quality (non-empty, valid URLs, etc.)

Return a JSON object with this structure:
{{
  "test_cases": [
    {{
      "input": "test description (e.g., 'run scraper and check output structure')",
      "expected_output": "expected result (e.g., 'list of dicts with keys: title, url')"
    }}
  ],
  "required_fields": ["title", "url"],
  "validation_rules": ["output is list", "each item has title and url", "urls are valid"]
}}
"""

        response = await self.llm.generate(
            prompt,
            system_prompt="You are a test generation expert. Return only valid JSON.",
            temperature=0.3,
        )

        import json
        try:
            content = response.response_text
            code_blocks = LLM.extract_code_blocks(content)
            if code_blocks:
                json_match = json.loads(code_blocks)
            else:
                json_match = json.loads(content)
            if isinstance(json_match, str):
                json_match = json.loads(json_match)
        except (json.JSONDecodeError, ValueError):
            json_match = {
                "test_cases": [
                    {
                        "input": "Run scraper and validate output",
                        "expected_output": "Valid structured output with required fields"
                    }
                ],
                "required_fields": [],
                "validation_rules": []
            }

        test_cases = [
            TestCase(input=tc.get("input", ""), expected_output=tc.get("expected_output", ""))
            for tc in json_match.get("test_cases", [])
        ]

        return GeneratedTestSuite(
            test_cases=test_cases,
            test_metadata={
                "required_fields": json_match.get("required_fields", []),
                "validation_rules": json_match.get("validation_rules", []),
            },
            execution_type="scraping",
        )

    async def _generate_function_tests(self, challenge: Challenge) -> GeneratedTestSuite:
        """Generate function/algorithm tests."""
        prompt = f"""You are a test generator for function/algorithm challenges.

Challenge: {challenge.title}
Description: {challenge.description}

Generate test cases with input/output pairs. Return a JSON object:
{{
  "test_cases": [
    {{
      "input": "function call expression (e.g., 'add(2, 3)')",
      "expected_output": "expected result expression (e.g., '5')"
    }}
  ]
}}
"""

        response = await self.llm.generate(
            prompt,
            system_prompt="You are a test generation expert. Return only valid JSON.",
            temperature=0.3,
        )

        import json
        try:
            content = response.response_text
            code_blocks = LLM.extract_code_blocks(content)
            if code_blocks:
                json_match = json.loads(code_blocks)
            else:
                json_match = json.loads(content)
            if isinstance(json_match, str):
                json_match = json.loads(json_match)
        except (json.JSONDecodeError, ValueError):
            json_match = {"test_cases": []}

        test_cases = [
            TestCase(input=tc.get("input", ""), expected_output=tc.get("expected_output", ""))
            for tc in json_match.get("test_cases", [])
        ]

        return GeneratedTestSuite(
            test_cases=test_cases,
            test_metadata={},
            execution_type="function",
        )

    async def _generate_api_tests(self, challenge: Challenge) -> GeneratedTestSuite:
        """Generate tests for API-related challenges."""
        prompt = f"""You are a test generator for API challenges.

Challenge: {challenge.title}
Description: {challenge.description}

Generate test cases that verify:
1. API calls are made correctly
2. Responses are handled properly
3. Error cases are handled
4. Output format matches requirements

Return a JSON object with test cases.
"""

        response = await self.llm.generate(
            prompt,
            system_prompt="You are a test generation expert. Return only valid JSON.",
            temperature=0.3,
        )

        import json
        try:
            content = response.response_text
            code_blocks = LLM.extract_code_blocks(content)
            if code_blocks:
                json_match = json.loads(code_blocks)
            else:
                json_match = json.loads(content)
            if isinstance(json_match, str):
                json_match = json.loads(json_match)
        except (json.JSONDecodeError, ValueError):
            json_match = {"test_cases": []}

        test_cases = [
            TestCase(input=tc.get("input", ""), expected_output=tc.get("expected_output", ""))
            for tc in json_match.get("test_cases", [])
        ]

        return GeneratedTestSuite(
            test_cases=test_cases,
            test_metadata={},
            execution_type="api",
        )

    async def _generate_generic_tests(self, challenge: Challenge) -> GeneratedTestSuite:
        """Generate generic tests when category is unclear."""
        prompt = f"""Analyze this challenge and generate appropriate test cases.

Challenge: {challenge.title}
Description: {challenge.description}
Category: {challenge.category}

Generate test cases that verify the challenge requirements are met.
Return JSON with test_cases array.
"""

        response = await self.llm.generate(
            prompt,
            system_prompt="You are a test generation expert. Return only valid JSON.",
            temperature=0.3,
        )

        import json
        try:
            content = response.response_text
            code_blocks = LLM.extract_code_blocks(content)
            if code_blocks:
                json_match = json.loads(code_blocks)
            else:
                json_match = json.loads(content)
            if isinstance(json_match, str):
                json_match = json.loads(json_match)
        except (json.JSONDecodeError, ValueError):
            json_match = {"test_cases": []}

        test_cases = [
            TestCase(input=tc.get("input", ""), expected_output=tc.get("expected_output", ""))
            for tc in json_match.get("test_cases", [])
        ]

        return GeneratedTestSuite(
            test_cases=test_cases,
            test_metadata={},
            execution_type="generic",
        )

