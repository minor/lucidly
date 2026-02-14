## Setup Steps

### 1. Install root dependencies
From the root directory (`/Users/emily/Documents/Github/lucidly`), install the root dependency:

```bash
bun install
```

Or if you prefer npm:
```bash
npm install
```

This installs `concurrently` to run both the backend and frontend.

### 2. Install frontend dependencies
Navigate to the frontend directory and install dependencies:

```bash
cd frontend
bun install
```

### 3. Install backend dependencies
The backend uses Python with `uv`. From the backend directory:

```bash
cd backend
uv sync
```

This installs Python dependencies (FastAPI, uvicorn, OpenAI, etc.).

### 3.5. Configure API keys
Create a `.env` file in the `backend` directory with your API keys:

```bash
cd backend
touch .env
```

Add your Anthropic API key to the `.env` file:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

You can get your Anthropic API key from: https://console.anthropic.com/

**Note:** If you prefer to use OpenRouter or another OpenAI-compatible API instead, you can set:

```env
OPENAI_API_KEY=your_openrouter_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

### 3.6. Agent benchmark (optional)
To run **agent benchmark runs** (Agents page: select agent + challenge, Run):

- **In-process (default, no Modal):** Use `USE_INPROCESS_AGENT=true` (default). The agent runs inside the backend process. Open **Agents**, pick an agent and challenge, click **Run**, then watch the same challenge UI update live. No `AGENT_INTERNAL_SECRET` needed for in-process.

- **With Modal (cloud):** To run agents in Modal instead:
  1. Run `modal token` (or set `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` in env).
  2. Deploy: `cd modal_agent && modal deploy app.py`.
  3. In `backend/.env`: set `USE_INPROCESS_AGENT=false`, `BACKEND_PUBLIC_URL=<url-reachable-from-Modal>` (e.g. ngrok URL for local backend), and `AGENT_INTERNAL_SECRET=<same-secret>`.

**Agent types:** The app supports several agents. Two use **real SDKs**:
- **Claude Agent SDK** (`claude-sdk`): Uses the `claude-agent-sdk` package with a custom `submit_prompt` tool that calls your backend. Set `ANTHROPIC_API_KEY` for the SDK to call Claude.
- **OpenAI Assistant** (`openai-assistant`): Uses the OpenAI Assistants API with a `submit_prompt` function tool. Uses `OPENAI_API_KEY` and `OPENAI_BASE_URL`.

See `backend/.env.example` for all optional variables (OpenAI, Anthropic, agent secret, Modal).

### 4. Start the development server
From the root directory, run:

```bash
bun run dev
```

Or:
```bash
npm run dev
```

This starts:
- Backend server on `http://0.0.0.0:8000` (FastAPI/uvicorn)
- Frontend server (Next.js) on `http://localhost:3000` (default)

### Prerequisites
- Bun (for frontend and root scripts)
- Python 3.11+ (for backend)
- `uv` (Python package manager) — install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`

If you don't have `uv` installed, install it first, then run `uv sync` in the backend directory.

The server should be running after these steps.

```shellscript
bun install
```

```shellscript
npm install
```

```shellscript
cd frontend
bun install
```

```shellscript
cd backend
uv sync
```

```shellscript
bun run dev
```

```shellscript
npm run dev
```