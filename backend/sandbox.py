"""Modal sandbox manager — persistent sandbox lifecycle.

Creates a Modal sandbox when a challenge is loaded, reuses it for test runs,
and terminates it when the challenge is submitted or the page is closed.
"""

import json
import modal

# In-memory store: sandbox_id -> modal.Sandbox
_sandboxes: dict[str, modal.Sandbox] = {}

# Define the image with necessary dependencies for data challenges
_sandbox_image = (
    modal.Image.debian_slim()
    .pip_install("pandas", "requests", "beautifulsoup4", "numpy", "lxml")
)


async def create_sandbox() -> str:
    """Create a new persistent Modal sandbox. Returns the sandbox_id."""
    app = await modal.App.lookup.aio("lucidly-sandbox", create_if_missing=True)
    sb = await modal.Sandbox.create.aio(
        image=_sandbox_image,
        app=app,
        timeout=3600,  # 1 hour idle timeout
    )
    _sandboxes[sb.object_id] = sb
    return sb.object_id


async def run_tests_in_sandbox(
    sandbox_id: str,
    code: str,
    test_suite: list[dict],
) -> list[dict]:
    """Execute code + test suite inside an existing sandbox.

    Returns list of dicts with: input, expected, actual, passed, error.
    """
    # Build a self-contained test runner script
    runner_script = _build_test_runner(code, test_suite)

    # Execute in sandbox using the helper
    result = await run_code_in_sandbox(sandbox_id, runner_script)
    
    stdout = result["stdout"]
    stderr = result["stderr"]
    returncode = result["returncode"]

    if returncode != 0:
        return [
            {
                "input": tc["input"],
                "expected": tc["expected_output"],
                "actual": None,
                "passed": False,
                "error": f"Sandbox execution error: {stderr.strip() or 'unknown error'}",
            }
            for tc in test_suite
        ]

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return [
            {
                "input": tc["input"],
                "expected": tc["expected_output"],
                "actual": None,
                "passed": False,
                "error": f"Failed to parse sandbox output: {stdout[:200]}",
            }
            for tc in test_suite
        ]


async def run_code_in_sandbox(
    sandbox_id: str,
    code: str,
) -> dict:
    """Execute arbitrary code in the sandbox and return stdout/stderr."""
    sb = _sandboxes.get(sandbox_id)
    if sb is None:
        raise RuntimeError(f"Sandbox {sandbox_id} not found. It may have been terminated.")

    # Execute in sandbox
    process = await sb.exec.aio("python", "-c", code, timeout=30)
    stdout = await process.stdout.read.aio()
    stderr = await process.stderr.read.aio()
    await process.wait.aio()

    return {
        "stdout": stdout,
        "stderr": stderr,
        "returncode": process.returncode,
    }


async def terminate_sandbox(sandbox_id: str) -> bool:
    """Terminate a sandbox and clean up. Returns True if found and terminated."""
    sb = _sandboxes.pop(sandbox_id, None)
    if sb is None:
        return False
    try:
        await sb.terminate.aio()
    except Exception:
        pass  # Already terminated
    return True


async def terminate_all() -> int:
    """Terminate all active sandboxes. Returns count terminated."""
    count = 0
    for sid in list(_sandboxes.keys()):
        await terminate_sandbox(sid)
        count += 1
    return count


def _build_test_runner(code: str, test_suite: list[dict]) -> str:
    """Build a Python script that runs all tests and outputs JSON results."""
    # Escape the code and test suite for embedding in a Python string
    code_escaped = json.dumps(code)
    tests_escaped = json.dumps(test_suite)

    return f"""
import json
import sys

# Helper functions
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def arr_to_list(arr):
    head = None
    for v in reversed(arr):
        head = ListNode(v, head)
    return head

def list_to_arr(node):
    result = []
    while node:
        result.append(node.val)
        node = node.next
    return result

code = {code_escaped}
test_suite = {tests_escaped}

namespace = {{"ListNode": ListNode, "arr_to_list": arr_to_list, "list_to_arr": list_to_arr}}
code_error = None
try:
    exec(code, namespace)
except Exception as e:
    code_error = str(e)

results = []
for test in test_suite:
    if code_error:
        results.append({{
            "input": test["input"],
            "expected": test["expected_output"],
            "actual": None,
            "passed": False,
            "error": f"Code failed to execute: {{code_error}}",
        }})
        continue

    try:
        actual = eval(test["input"], namespace)
        expected = eval(test["expected_output"], namespace)
        passed = actual == expected
        results.append({{
            "input": test["input"],
            "expected": repr(expected),
            "actual": repr(actual),
            "passed": passed,
            "error": None,
        }})
    except Exception as e:
        results.append({{
            "input": test["input"],
            "expected": test["expected_output"],
            "actual": None,
            "passed": False,
            "error": str(e),
        }})

print(json.dumps(results))
"""
