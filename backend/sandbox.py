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
    # Install Python dependencies
    .pip_install("pandas", "requests", "beautifulsoup4", "numpy", "lxml")
    # Install System dependencies (g++ for C++, sanitizers for testing)
    .apt_install("g++", "libtsan0", "libasan5")
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
    # Detect Language
    is_cpp = "#include" in code or "int main" in code
    
    if is_cpp:
        return await _run_cpp_tests(sandbox_id, code, test_suite)

    # Python Execution (default)
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


async def _run_cpp_tests(sandbox_id: str, code: str, test_suite: list[dict]) -> list[dict]:
    """Compile and run C++ code against test suite."""
    sb = _sandboxes.get(sandbox_id)
    if not sb:
        raise RuntimeError(f"Sandbox {sandbox_id} not found.")

    # 1. Write Code to File
    # We can write via a small python script
    write_script = f"with open('solution.cpp', 'w') as f: f.write({json.dumps(code)})"
    await sb.exec.aio("python", "-c", write_script)

    # 2. Compile (only if main exists, otherwise wait for test harness)
    # If the user code is a library (no main), we skip this step to avoid "undefined reference to main".
    
    has_main = "int main" in code
    if has_main:
        compile_proc = await sb.exec.aio("g++", "-o", "solution", "solution.cpp", timeout=30)
        await compile_proc.wait.aio()
        
        # If main exists but compilation fails, report it immediately
        if compile_proc.returncode != 0:
            stderr = await compile_proc.stderr.read.aio()
            return [
                {
                    "input": tc["input"],
                    "expected": tc["expected_output"],
                    "actual": None,
                    "passed": False,
                    "error": f"Compilation Error: {stderr.strip()}",
                }
                for tc in test_suite
            ]
    else:
        # No main found. Proceed to test harnesses.
        pass

    # 3. Configure Sanitizers based on inputs
    # If the input is a special flag like "TEST_CONCURRENT_PUSH_POP", we inject a specific main function wrapper.
    # Otherwise, we assume standard stdin/stdout.

    results = []
    
    for tc in test_suite:
        inp = tc["input"]
        expected = tc["expected_output"]
        
        # Custom handling for specific C++ concurrency tests
        if inp.startswith("TEST_"):
             # We need to compile with the specific test harness appended
            wrapper_code = code + "\n" + _get_cpp_test_harness(inp)
            
            # Write wrapper
            write_script = f"with open('test_wrapper.cpp', 'w') as f: f.write({json.dumps(wrapper_code)})"
            await sb.exec.aio("python", "-c", write_script)
            
            # Compile with Sanitizers for these tests
            # -fsanitize=thread for race detection
            # -fsanitize=address for leaks/use-after-free
            # We can't run both at once easily. Let's pick based on input or run twice?
            # TSan is usually incompatible with ASan.
            
            compile_cmd = ["g++", "-o", "test_runner", "test_wrapper.cpp", "-pthread", "-O2", "-g"]
            if "LEAK" in inp or "RECLAMATION" in inp:
                compile_cmd.append("-fsanitize=address")
            else:
                compile_cmd.append("-fsanitize=thread")

            compile_proc = await sb.exec.aio(*compile_cmd, timeout=30)
            await compile_proc.wait.aio()
            
            if compile_proc.returncode != 0:
                stderr = await compile_proc.stderr.read.aio()
                results.append({
                    "input": inp,
                    "expected": expected,
                    "actual": "Compilation Failed",
                    "passed": False,
                    "error": stderr.strip()
                })
                continue

            # Run
            run_proc = await sb.exec.aio("./test_runner", timeout=10)
            stdout = await run_proc.stdout.read.aio()
            stderr = await run_proc.stderr.read.aio()
            await run_proc.wait.aio()
            
            # Check for sanitizer errors in stderr
            err_output = stderr.strip()
            actual_out = stdout.strip()
            
            # If sanitizer caught something, it prints to stderr
            passed = (run_proc.returncode == 0) and ("ThreadSanitizer" not in err_output) and ("AddressSanitizer" not in err_output)
            
            if passed and actual_out == expected:
                results.append({
                    "input": inp,
                    "expected": expected,
                    "actual": actual_out,
                    "passed": True,
                    "error": None
                })
            else:
                results.append({
                    "input": inp,
                    "expected": expected,
                    "actual": actual_out if not err_output else "Check Error Log",
                    "passed": False,
                    "error": err_output or "Runtime Error"
                })

        else:
            # Standard Stdin/Stdout flow
            # If we didn't compile 'solution' yet (because main was missing but this is a standard test?),
            # that's a user error or mismatch. Assume 'solution' binary exists from step 2.
            
            if not has_main:
                # User tried to run standard test but code has no main
                 results.append({
                    "input": inp,
                    "expected": expected,
                    "actual": "Missing main function",
                    "passed": False,
                    "error": "Standard tests require int main()"
                })
                 continue

            # Run existing 'solution' binary
            run_proc = await sb.exec.aio("./solution", stdin=inp.encode(), timeout=5)
            stdout = await run_proc.stdout.read.aio()
            stderr = await run_proc.stderr.read.aio()
            await run_proc.wait.aio()
            
            actual = stdout.strip()
            # Strict equality check
            passed = actual == expected.strip()
            
            results.append({
                "input": inp,
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "error": stderr.strip() if run_proc.returncode != 0 else None
            })
             
    return results

def _get_cpp_test_harness(test_name: str) -> str:
    """Return the C++ main function wrapper for a specific test case."""
    if test_name == "TEST_CONCURRENT_PUSH_POP":
        return """
#include <vector>
#include <thread>
#include <iostream>

void test_concurrent_push_pop() {
    LockFreeStack stack;
    std::vector<std::thread> threads;
    for (int i = 0; i < 10; ++i) {
        threads.push_back(std::thread([&, i]() {
            for (int j = 0; j < 100; ++j) {
                stack.push(j);
                int val;
                stack.pop(val, i);
            }
        }));
    }
    for (auto& t : threads) t.join();
    std::cout << "PASS" << std::endl;
}

int main() {
    try {
        test_concurrent_push_pop();
    } catch (...) {
        return 1;
    }
    return 0;
}
"""
    elif test_name == "TEST_RECLAMATION_LEAKS":
        return """
#include <vector>
#include <thread>
#include <iostream>
#include <atomic>

void stress_test_reclamation() {
    LockFreeStack stack;
    std::atomic<int> pops{0};
    
    std::thread w1([&]{ for(int i=0; i<10000; ++i) stack.push(i); });
    std::thread w2([&]{ for(int i=0; i<10000; ++i) stack.push(i); });

    auto reader = [&](int id) {
        int val;
        while(pops < 20000) {
            if (stack.pop(val, id)) pops++;
        }
    };

    std::vector<std::thread> readers;
    for(int i=0; i<4; ++i) readers.emplace_back(reader, i);

    w1.join(); w2.join();
    for(auto& t : readers) t.join();
    
    std::cout << "PASS" << std::endl;
}

int main() {
    stress_test_reclamation();
    return 0;
}
"""
    return "int main() { return 1; }"


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
