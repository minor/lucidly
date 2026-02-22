"""Set dummy env vars before any application module is imported.

The app initialization (main.py -> TestGenerator -> create_claude_llm) requires
at least one LLM API key to be present. Providing a dummy value lets the app
load without real credentials; the key is never used because tests don't hit
live LLM endpoints.
"""

import os

os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY") or "test-dummy-key"
