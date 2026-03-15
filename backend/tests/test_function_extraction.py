"""
Unit tests for file selection and function extraction logic in generate.py.
Tests call _select_source_file and _extract_functions_for_tests directly.
"""
import pytest
from integrations.generate import _select_source_file, _extract_functions_for_tests


# ---------------------------------------------------------------------------
# _select_source_file
# ---------------------------------------------------------------------------

def test_select_source_file_prefers_changed_files():
    """If a changed file is exercised by fixed tests, pick it."""
    test_ids = ["tests/test_parser.py::test_tokenize", "tests/test_parser.py::test_parse"]
    changed_files = [
        {"filename": "src/parser.py", "patch": "@@ ... @@"},
        {"filename": "src/utils.py", "patch": "@@ ... @@"},
    ]
    result = _select_source_file(test_ids, changed_files)
    assert result == "src/parser.py"


def test_select_source_file_skips_test_files():
    """Never picks a test file as the source."""
    test_ids = ["tests/test_parser.py::test_tokenize"]
    changed_files = [{"filename": "tests/test_parser.py", "patch": ""}]
    result = _select_source_file(test_ids, changed_files)
    assert result is None


def test_select_source_file_returns_none_when_no_match():
    """Returns None when no changed files match test module names."""
    test_ids = ["tests/test_parser.py::test_tokenize"]
    changed_files = [{"filename": "src/unrelated.py", "patch": ""}]
    result = _select_source_file(test_ids, changed_files)
    assert result is None


# ---------------------------------------------------------------------------
# _extract_functions_for_tests
# ---------------------------------------------------------------------------

SAMPLE_SOURCE = """
def tokenize(s):
    return s.split()

def parse(tokens):
    return {"tokens": tokens}

def _helper():
    pass
"""

def test_extract_functions_finds_names_from_test_ids():
    """Extracts functions whose names appear in test node IDs."""
    test_ids = [
        "tests/test_parser.py::test_tokenize",
        "tests/test_parser.py::test_parse",
    ]
    result = _extract_functions_for_tests(SAMPLE_SOURCE, test_ids)
    assert "def tokenize" in result
    assert "def parse" in result
    assert "_helper" not in result


def test_extract_functions_deduplicates():
    """Same function name in multiple test IDs is only extracted once."""
    test_ids = [
        "tests/test_parser.py::test_tokenize",
        "tests/test_parser.py::test_tokenize_edge",
    ]
    result = _extract_functions_for_tests(SAMPLE_SOURCE, test_ids)
    assert result.count("def tokenize") == 1


def test_extract_functions_returns_full_source_when_no_match():
    """Falls back to full source when no function names can be extracted."""
    test_ids = ["tests/test_parser.py::test_nonexistent"]
    result = _extract_functions_for_tests(SAMPLE_SOURCE, test_ids)
    assert result == SAMPLE_SOURCE


def test_extract_uses_test_case_inputs_as_secondary_source():
    """When test_ids alone don't match, inputs from test_cases are used as secondary names."""
    test_ids = ["tests/test_parser.py::test_it"]
    test_cases = [{"input": "tokenize('hello')", "expected_output": "['hello']"}]
    result = _extract_functions_for_tests(SAMPLE_SOURCE, test_ids, test_cases=test_cases)
    assert "def tokenize" in result


def test_extract_regex_on_inputs_does_not_match_method_calls():
    """obj.method() in inputs should not match 'method' as a top-level function."""
    source = """
def method(x): return x
def other(x): return x
"""
    test_ids = ["tests/test_foo.py::test_it"]
    test_cases = [{"input": "obj.method()", "expected_output": "1"}]
    result = _extract_functions_for_tests(source, test_ids, test_cases=test_cases)
    # method() is a method call on obj, not a standalone call — should fall back to full source
    assert result == source
