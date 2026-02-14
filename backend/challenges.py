"""In-memory challenge store seeded with 10 challenges from the PRD."""

from pydantic import BaseModel


class TestCase(BaseModel):
    input: str
    expected_output: str


class Challenge(BaseModel):
    id: str
    title: str
    description: str
    category: str  # ui, function, debug, system, data
    difficulty: str  # easy, medium, hard
    target_code: str | None = None
    test_suite: list[TestCase] | None = None
    starter_code: str | None = None


# ---------------------------------------------------------------------------
# Seed library — 10 challenges from PRD Section 8
# ---------------------------------------------------------------------------

SEED_CHALLENGES: list[Challenge] = [
    # 1 — Easy UI
    Challenge(
        id="center-a-div",
        title="Center a Div",
        description=(
            "Create an HTML page with a centered card. The card should have "
            "a shadow, rounded corners, and contain the text 'Hello, World!'. "
            "Use CSS flexbox or grid to center the card both horizontally and vertically."
        ),
        category="ui",
        difficulty="easy",
        target_code="""<!DOCTYPE html>
<html>
<head><style>
  body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f5f5; font-family: sans-serif; }
  .card { padding: 2rem 3rem; background: white; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.10); }
</style></head>
<body><div class="card">Hello, World!</div></body>
</html>""",
    ),
    # 2 — Easy Function
    Challenge(
        id="fizzbuzz",
        title="FizzBuzz",
        description=(
            "Write a Python function `fizzbuzz(n: int) -> list[str]` that returns "
            "a list of strings from 1 to n. For multiples of 3, use 'Fizz'; for "
            "multiples of 5, use 'Buzz'; for multiples of both, use 'FizzBuzz'; "
            "otherwise, use the string representation of the number."
        ),
        category="function",
        difficulty="easy",
        target_code="""def fizzbuzz(n: int) -> list[str]:
    result = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            result.append("FizzBuzz")
        elif i % 3 == 0:
            result.append("Fizz")
        elif i % 5 == 0:
            result.append("Buzz")
        else:
            result.append(str(i))
    return result""",
        test_suite=[
            TestCase(input="fizzbuzz(1)", expected_output="['1']"),
            TestCase(input="fizzbuzz(3)", expected_output="['1', '2', 'Fizz']"),
            TestCase(input="fizzbuzz(5)", expected_output="['1', '2', 'Fizz', '4', 'Buzz']"),
            TestCase(
                input="fizzbuzz(15)",
                expected_output=(
                    "['1', '2', 'Fizz', '4', 'Buzz', 'Fizz', '7', '8', 'Fizz', "
                    "'Buzz', '11', 'Fizz', '13', '14', 'FizzBuzz']"
                ),
            ),
            TestCase(input="fizzbuzz(0)", expected_output="[]"),
        ],
    ),
    # 3 — Easy Function
    Challenge(
        id="reverse-linked-list",
        title="Reverse a Linked List",
        description=(
            "Write a Python solution with a class `ListNode` (val, next) and a "
            "function `reverse_list(head: ListNode | None) -> ListNode | None` "
            "that reverses a singly linked list in-place."
        ),
        category="function",
        difficulty="easy",
        target_code="""class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def reverse_list(head):
    prev = None
    curr = head
    while curr:
        next_node = curr.next
        curr.next = prev
        prev = curr
        curr = next_node
    return prev""",
        test_suite=[
            TestCase(input="list_to_arr(reverse_list(arr_to_list([1,2,3,4,5])))", expected_output="[5, 4, 3, 2, 1]"),
            TestCase(input="list_to_arr(reverse_list(arr_to_list([1])))", expected_output="[1]"),
            TestCase(input="list_to_arr(reverse_list(arr_to_list([])))", expected_output="[]"),
            TestCase(input="list_to_arr(reverse_list(arr_to_list([1,2])))", expected_output="[2, 1]"),
        ],
    ),
    # 4 — Medium UI
    Challenge(
        id="responsive-navbar",
        title="Responsive Nav Bar",
        description=(
            "Create an HTML page with a responsive navigation bar. On desktop "
            "(>768px), show a horizontal nav with links: Home, About, Services, "
            "Contact. On mobile (<=768px), collapse into a hamburger menu that "
            "toggles a vertical dropdown. Use vanilla HTML/CSS/JS."
        ),
        category="ui",
        difficulty="medium",
        target_code="""<!DOCTYPE html>
<html>
<head><style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  nav { background: #1a1a2e; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
  nav .brand { color: white; font-size: 1.5rem; font-weight: bold; }
  nav ul { list-style: none; display: flex; gap: 2rem; }
  nav ul li a { color: #eee; text-decoration: none; }
  .hamburger { display: none; cursor: pointer; color: white; font-size: 1.5rem; }
  @media (max-width: 768px) {
    .hamburger { display: block; }
    nav ul { display: none; flex-direction: column; width: 100%; position: absolute; top: 60px; left: 0; background: #1a1a2e; padding: 1rem 2rem; }
    nav ul.active { display: flex; }
  }
</style></head>
<body>
<nav>
  <span class="brand">Brand</span>
  <span class="hamburger" onclick="document.querySelector('ul').classList.toggle('active')">☰</span>
  <ul><li><a href="#">Home</a></li><li><a href="#">About</a></li><li><a href="#">Services</a></li><li><a href="#">Contact</a></li></ul>
</nav>
</body></html>""",
    ),
    # 5 — Medium UI
    Challenge(
        id="todo-app",
        title="Todo App Component",
        description=(
            "Create a single-file HTML page with a Todo app. Features: add a "
            "new todo via input + button, toggle completion (strikethrough), "
            "delete todos. Use vanilla JS with local state (no framework)."
        ),
        category="ui",
        difficulty="medium",
        target_code="""<!DOCTYPE html>
<html>
<head><style>
  body { font-family: sans-serif; max-width: 500px; margin: 2rem auto; }
  .todo { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0; border-bottom: 1px solid #eee; }
  .todo.done span { text-decoration: line-through; color: #999; }
  input[type=text] { flex: 1; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
  button { padding: 0.5rem 1rem; cursor: pointer; border: none; border-radius: 4px; background: #333; color: white; }
</style></head>
<body>
<h1>Todos</h1>
<div style="display:flex;gap:0.5rem;margin-bottom:1rem">
  <input type="text" id="inp" placeholder="Add a todo..." />
  <button onclick="addTodo()">Add</button>
</div>
<div id="list"></div>
<script>
let todos = [];
function render() {
  const list = document.getElementById('list');
  list.innerHTML = todos.map((t, i) => `<div class="todo ${t.done?'done':''}"><input type="checkbox" ${t.done?'checked':''} onchange="toggle(${i})"><span>${t.text}</span><button onclick="remove(${i})">×</button></div>`).join('');
}
function addTodo() { const inp = document.getElementById('inp'); if(inp.value.trim()) { todos.push({text:inp.value.trim(),done:false}); inp.value=''; render(); } }
function toggle(i) { todos[i].done = !todos[i].done; render(); }
function remove(i) { todos.splice(i,1); render(); }
document.getElementById('inp').addEventListener('keydown', e => { if(e.key==='Enter') addTodo(); });
render();
</script>
</body></html>""",
    ),
    # 6 — Medium Function
    Challenge(
        id="debounce",
        title="Debounce Utility",
        description=(
            "Write a Python function `debounce(func, wait_ms)` that returns a "
            "debounced version of `func`. The debounced function delays invoking "
            "`func` until after `wait_ms` milliseconds have elapsed since the last "
            "invocation. It should also have a `.cancel()` method."
        ),
        category="function",
        difficulty="medium",
        target_code="""import threading

def debounce(func, wait_ms):
    timer = [None]
    def debounced(*args, **kwargs):
        if timer[0] is not None:
            timer[0].cancel()
        timer[0] = threading.Timer(wait_ms / 1000.0, func, args, kwargs)
        timer[0].start()
    def cancel():
        if timer[0] is not None:
            timer[0].cancel()
            timer[0] = None
    debounced.cancel = cancel
    return debounced""",
        test_suite=[
            TestCase(input="callable(debounce(lambda: None, 100))", expected_output="True"),
            TestCase(input="hasattr(debounce(lambda: None, 100), 'cancel')", expected_output="True"),
            TestCase(input="callable(debounce(lambda: None, 100).cancel)", expected_output="True"),
        ],
    ),
    # 7 — Medium Debug
    Challenge(
        id="fix-memory-leak",
        title="Fix the Memory Leak",
        description=(
            "The following React component has a memory leak caused by a missing "
            "cleanup in useEffect. Fix the code so the interval is properly cleaned "
            "up when the component unmounts.\n\n"
            "```jsx\n"
            "import { useState, useEffect } from 'react';\n"
            "export default function Timer() {\n"
            "  const [count, setCount] = useState(0);\n"
            "  useEffect(() => {\n"
            "    setInterval(() => setCount(c => c + 1), 1000);\n"
            "  }, []);\n"
            "  return <div>Count: {count}</div>;\n"
            "}\n"
            "```"
        ),
        category="debug",
        difficulty="medium",
        target_code="""import { useState, useEffect } from 'react';
export default function Timer() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setCount(c => c + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return <div>Count: {count}</div>;
}""",
        test_suite=[
            TestCase(input="'clearInterval' in code", expected_output="True"),
            TestCase(input="'return' in code.split('setInterval')[1]", expected_output="True"),
        ],
    ),
    # 8 — Hard UI
    Challenge(
        id="kanban-board",
        title="Kanban Board",
        description=(
            "Create a single-file HTML/CSS/JS Kanban board with three columns: "
            "'To Do', 'In Progress', 'Done'. Users should be able to add cards "
            "to any column and drag-and-drop cards between columns. Use the "
            "HTML5 Drag and Drop API."
        ),
        category="ui",
        difficulty="hard",
    ),
    # 9 — Hard Function
    Challenge(
        id="rate-limiter",
        title="Rate Limiter",
        description=(
            "Write a Python class `RateLimiter` that implements a sliding window "
            "rate limiter. Constructor takes `max_requests: int` and `window_sec: float`. "
            "Method `allow(identifier: str) -> bool` returns True if the request is "
            "allowed, False if rate-limited. Each identifier has its own window."
        ),
        category="function",
        difficulty="hard",
        target_code="""import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests: int, window_sec: float):
        self.max_requests = max_requests
        self.window_sec = window_sec
        self.requests = defaultdict(list)

    def allow(self, identifier: str) -> bool:
        now = time.time()
        window_start = now - self.window_sec
        self.requests[identifier] = [t for t in self.requests[identifier] if t > window_start]
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(now)
            return True
        return False""",
        test_suite=[
            TestCase(input="RateLimiter(2, 1.0).allow('a')", expected_output="True"),
            TestCase(input="r = RateLimiter(1, 1.0); r.allow('a'); r.allow('a')", expected_output="False"),
            TestCase(input="r = RateLimiter(2, 1.0); r.allow('a'); r.allow('b')", expected_output="True"),
        ],
    ),
    # 10 — Medium Data
    Challenge(
        id="csv-to-json",
        title="CSV to JSON Transformer",
        description=(
            "Write a Python function `csv_to_json(csv_string: str) -> list[dict]` "
            "that parses a CSV string (with headers in the first row) into a list "
            "of dictionaries. Handle edge cases: quoted fields with commas, "
            "trailing newlines, and empty fields."
        ),
        category="data",
        difficulty="medium",
        target_code="""import csv
import io

def csv_to_json(csv_string: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_string.strip()))
    return [dict(row) for row in reader]""",
        test_suite=[
            TestCase(
                input='csv_to_json("name,age\\nAlice,30\\nBob,25")',
                expected_output="[{'name': 'Alice', 'age': '30'}, {'name': 'Bob', 'age': '25'}]",
            ),
            TestCase(
                input='csv_to_json("a,b\\n1,2\\n")',
                expected_output="[{'a': '1', 'b': '2'}]",
            ),
            TestCase(
                input='csv_to_json("name,city\\n\\"Doe, John\\",\\"New York\\"\\n")',
                expected_output="[{'name': 'Doe, John', 'city': 'New York'}]",
            ),
        ],
    ),
]


def get_all_challenges() -> list[Challenge]:
    return SEED_CHALLENGES


def get_challenge_by_id(challenge_id: str) -> Challenge | None:
    for c in SEED_CHALLENGES:
        if c.id == challenge_id:
            return c
    return None
