import modal

app = modal.App("lucidly-sandbox")

@app.function(sandbox=True, timeout=60)
def run_python_tests_in_sandbox(code: str, test_suite: list[dict]) -> list[bool]:
    """
    Executes the generated code + tests in a Modal sandbox.
    Returns a list of booleans indicating pass/fail for each test case.
    """
    results = []

    # Helper functions available in test context
    helpers = """
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
"""

    namespace = {}
    try:
        # Execute the user's code
        exec(helpers + "\n" + code, namespace)
    except Exception:
        # If the code itself fails to run (syntax error, etc.), all tests fail
        return [False] * len(test_suite)

    for test in test_suite:
        try:
            # Evaluate input and expected output in the same namespace
            actual = eval(test["input"], namespace)
            expected = eval(test["expected_output"], namespace)
            results.append(actual == expected)
        except Exception:
            results.append(False)

    return results
