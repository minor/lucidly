"""
Unit tests for PR-fixed file selection and function extraction in generate.py.
These test the logic that will be added to build_challenge_from_issue.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from integrations.generate import (
    _select_source_file,
    _extract_functions_for_tests,
)


# ---------------------------------------------------------------------------
# _select_source_file(pr_fixed_test_ids, base_source_files) -> dict
# ---------------------------------------------------------------------------

BASE_SOURCE_FILES = [
    {"filename": "src/parser.py", "content": "def tokenize(s): pass"},
    {"filename": "src/validator.py", "content": "def is_valid(s): pass"},
]


def test_select_by_matching_stem():
    """test_parser.py → stem 'parser' matches src/parser.py."""
    test_ids = ["tests/test_parser.py::test_tokenize"]
    result = _select_source_file(test_ids, BASE_SOURCE_FILES)
    assert result["filename"] == "src/parser.py"


def test_select_higher_score_wins():
    """More test IDs referencing parser than validator → parser wins."""
    test_ids = [
        "tests/test_parser.py::test_tokenize",
        "tests/test_parser.py::test_numbers",
        "tests/test_validator.py::test_email",
    ]
    result = _select_source_file(test_ids, BASE_SOURCE_FILES)
    assert result["filename"] == "src/parser.py"


def test_select_tie_falls_back_to_first():
    """On tie, use base_source_files[0]."""
    test_ids = [
        "tests/test_parser.py::test_tokenize",
        "tests/test_validator.py::test_email",
    ]
    result = _select_source_file(test_ids, BASE_SOURCE_FILES)
    assert result["filename"] == BASE_SOURCE_FILES[0]["filename"]


def test_select_no_match_falls_back_to_first():
    """No test file stem matches any source file → use base_source_files[0]."""
    test_ids = ["tests/test_unrelated.py::test_foo"]
    result = _select_source_file(test_ids, BASE_SOURCE_FILES)
    assert result["filename"] == BASE_SOURCE_FILES[0]["filename"]


def test_select_empty_test_ids_falls_back_to_first():
    result = _select_source_file([], BASE_SOURCE_FILES)
    assert result["filename"] == BASE_SOURCE_FILES[0]["filename"]


# ---------------------------------------------------------------------------
# _extract_functions_for_tests(pr_fixed_test_ids, source_content) -> str | None
# ---------------------------------------------------------------------------

SOURCE_WITH_TWO_FUNCS = """\
def tokenize(s: str) -> list[str]:
    return s.split()

def extract_numbers(text: str) -> list[int]:
    return []

def helper():
    return 42
"""

SOURCE_WITH_DECORATOR = """\
@staticmethod
def tokenize(s: str) -> list[str]:
    return s.split()
"""


def test_extract_single_function():
    test_ids = ["tests/test_parser.py::test_tokenize_basic"]
    result = _extract_functions_for_tests(test_ids, SOURCE_WITH_TWO_FUNCS)
    assert result is not None
    assert "def tokenize" in result
    assert "def extract_numbers" not in result
    assert "def helper" not in result


def test_extract_multiple_functions():
    test_ids = [
        "tests/test_parser.py::test_tokenize",
        "tests/test_parser.py::test_extract_numbers",
    ]
    result = _extract_functions_for_tests(test_ids, SOURCE_WITH_TWO_FUNCS)
    assert result is not None
    assert "def tokenize" in result
    assert "def extract_numbers" in result


def test_extract_includes_decorator():
    test_ids = ["tests/test_parser.py::test_tokenize"]
    result = _extract_functions_for_tests(test_ids, SOURCE_WITH_DECORATOR)
    assert result is not None
    assert "@staticmethod" in result
    assert "def tokenize" in result


def test_extract_returns_none_when_no_names_found():
    """Test IDs with no recognizable function names → return None (caller falls back)."""
    test_ids = ["tests/test_parser.py::test_setup_module"]
    result = _extract_functions_for_tests(test_ids, SOURCE_WITH_TWO_FUNCS)
    # 'setup_module' not in source → None
    assert result is None


def test_extract_returns_none_on_syntax_error():
    test_ids = ["tests/test_parser.py::test_tokenize"]
    result = _extract_functions_for_tests(test_ids, "def foo(: broken")
    assert result is None


def test_extract_returns_none_when_matched_names_not_in_source():
    test_ids = ["tests/test_parser.py::test_completely_missing_fn"]
    result = _extract_functions_for_tests(test_ids, SOURCE_WITH_TWO_FUNCS)
    assert result is None


def test_extract_uses_test_case_inputs_as_secondary_source():
    """Function names extracted from test_cases inputs when test_ids have no match."""
    test_ids = []  # No test IDs — names come entirely from test_cases
    test_cases = [{"input": "extract_numbers('abc 1 2')", "expected_output": "[1, 2]"}]
    result = _extract_functions_for_tests(test_ids, SOURCE_WITH_TWO_FUNCS, test_cases)
    assert result is not None
    assert "def extract_numbers" in result
    assert "def tokenize" not in result


def test_extract_regex_on_inputs_does_not_match_method_calls():
    """Method calls like obj.method(x) should NOT extract 'obj' as a function name.

    re.match(r'^([A-Za-z_]\\w*)\\s*\\(', 'obj.method(x)') fails because 'obj' is
    followed by '.' not '(' — so the regex correctly excludes method calls.
    """
    test_ids = []
    test_cases = [{"input": "obj.method(x)", "expected_output": "something"}]
    result = _extract_functions_for_tests(test_ids, SOURCE_WITH_TWO_FUNCS, test_cases)
    # 'obj' is not a function name in source (and wouldn't match regex anyway)
    assert result is None
