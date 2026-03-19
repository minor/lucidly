"""Unit tests for LLM-based test case generation (LLM calls mocked)."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from integrations.generate import parse_test_cases_from_file, generate_test_cases_from_diff


SAMPLE_PYTEST = """
def test_paginate_first_page():
    assert paginate([1,2,3,4,5], 1, 2) == [1, 2]

def test_paginate_last_page():
    assert paginate([1,2,3,4,5], 3, 2) == [5]

def test_paginate_returns_none_side_effect():
    result = set_flag(True)
    assert result is None
"""

MOCK_LLM_PARSE_RESPONSE = """
[
  {"input": "paginate([1,2,3,4,5], 1, 2)", "expected_output": "[1, 2]"},
  {"input": "paginate([1,2,3,4,5], 3, 2)", "expected_output": "[5]"},
  {"input": "set_flag(True)", "expected_output": "None"}
]
"""


def _make_llm_response(text: str):
    """Create a mock LLMResponse-like object with .response_text."""
    mock_resp = MagicMock()
    mock_resp.response_text = text
    return mock_resp


@pytest.mark.asyncio
async def test_parse_test_cases_from_file():
    with patch("integrations.generate.LLM") as MockLLM:
        instance = MockLLM.return_value
        instance.generate = AsyncMock(return_value=_make_llm_response(MOCK_LLM_PARSE_RESPONSE))
        result = await parse_test_cases_from_file(SAMPLE_PYTEST)

    assert len(result) == 3
    assert result[0]["input"] == "paginate([1,2,3,4,5], 1, 2)"
    assert result[0]["expected_output"] == "[1, 2]"
    assert result[2]["expected_output"] == "None"


MOCK_LLM_GEN_RESPONSE = """
[
  {"input": "fix_pagination([1,2,3], 1, 2)", "expected_output": "[1, 2]"}
]
"""


@pytest.mark.asyncio
async def test_generate_test_cases_from_diff():
    with patch("integrations.generate.LLM") as MockLLM:
        instance = MockLLM.return_value
        instance.generate = AsyncMock(return_value=_make_llm_response(MOCK_LLM_GEN_RESPONSE))
        result = await generate_test_cases_from_diff(
            title="Fix pagination",
            description="Off by one error",
            diff_text="@@ def paginate",
        )

    assert len(result) == 1
    assert result[0]["input"] == "fix_pagination([1,2,3], 1, 2)"
