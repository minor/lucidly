# No Shot

**Master the art of prompting.** Like Leetcode, but for the age of AI.

No Shot is a competitive learning platform that benchmarks and gamifies your ability to prompt AI models to write code. Solve challenges, climb leaderboards, and sharpen your prompting skills.

🔗 **Live at [noshot-ai.vercel.app](https://noshot-ai.vercel.app/)**

---

## Features

### ⚡ Arena Mode
- **10 challenges** across 5 categories (UI, function, debug, data, system) and 3 difficulty levels
- **Multi-model support** — GPT-5.2, GPT-5 Mini, GPT-5 Nano, Claude Opus 4.6, Claude Sonnet 4.5, Claude Haiku 4.5, Grok 4.1 Fast Reasoning, Grok Code Fast
- **Streaming chat** — Real-time LLM responses with live code generation
- **Live sandboxed preview** — UI challenges render in a Vercel Sandbox; function challenges run automated tests
- **ELO-style scoring** (0–1000) — Composite score based on accuracy (70%), speed (15%), and cost efficiency (15%)
- **Prompt feedback** — AI-generated tips to improve your prompting technique
- **Leaderboards** — Per-challenge rankings with sortable metrics

### 🤖 Agent Benchmarks
- Run autonomous AI agents (Claude Agent SDK, OpenAI Assistant, and more) against any challenge
- Watch agent thinking traces update live in the UI

### 📋 Interview Mode
- Create custom interview rooms with coding, frontend, and system design challenges
- Share invite codes with candidates
- Observe candidates solving challenges in real time
- View detailed post-interview reports with turn-by-turn transcripts and metrics

---

## Tech Stack

| Layer | Technologies |
| --- | --- |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Zustand, Auth0 |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| **LLM Providers** | OpenAI, Anthropic, xAI (Grok) |
| **Database** | Supabase (PostgreSQL) |
| **Sandboxing** | Vercel Sandbox (UI), Modal (agents) |
| **Testing** | Playwright (E2E) |

---

## Prerequisites

- **[Bun](https://bun.sh)** (recommended) or Node.js 18+
- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

---

## Getting Started

### 1. Install root dependencies

From the project root:

```bash
bun install
```

This installs `concurrently` to run both servers with a single command.

### 2. Install frontend dependencies

```bash
cd frontend
bun install
```

### 3. Install backend dependencies

```bash
cd backend
uv sync
```

### 4. Configure API keys

Create a `backend/.env` file with your LLM provider keys. **At minimum, you need one provider:**

```env
# ── Required (at least one) ────────────────────────────────────────

# OpenAI (powers GPT models)
OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=https://api.openai.com/v1        # default; change for OpenRouter etc.

# Anthropic (powers Claude models)
ANTHROPIC_API_KEY=sk-ant-...

# xAI (powers Grok models)
XAI_API_KEY=xai-...
```

**Where to get keys:**
- OpenAI → [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Anthropic → [console.anthropic.com](https://console.anthropic.com/)
- xAI → [console.x.ai](https://console.x.ai/)

<details>
<summary><strong>Optional environment variables</strong></summary>

```env
# ── Database ───────────────────────────────────────────────────────
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# ── Auth ───────────────────────────────────────────────────────────
# Set these in frontend/.env.local
# NEXT_PUBLIC_AUTH0_DOMAIN=your-tenant.auth0.com
# NEXT_PUBLIC_AUTH0_CLIENT_ID=...

# ── Agent benchmarks ──────────────────────────────────────────────
USE_INPROCESS_AGENT=true               # default; runs agent inside backend process
AGENT_INTERNAL_SECRET=                  # only needed for Modal-based agents
BACKEND_PUBLIC_URL=http://localhost:8000

# ── Modal (cloud agent execution) ─────────────────────────────────
# MODAL_TOKEN_ID=...
# MODAL_TOKEN_SECRET=...

# ── Browserbase / Stagehand (agent web scraping) ──────────────────
# BROWSERBASE_API_KEY=...
# BROWSERBASE_PROJECT_ID=...

# ── Server ────────────────────────────────────────────────────────
# HOST=0.0.0.0
# PORT=8000
# CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

</details>

### 5. Start the dev server

From the project root:

```bash
bun run dev
```

This starts both servers concurrently:

| Service | URL |
| --- | --- |
| Backend (FastAPI) | `http://localhost:8000` |
| Frontend (Next.js) | `http://localhost:3000` |

---

## Project Structure

```
lucidly/
├── frontend/               # Next.js app (see frontend/README.md)
│   ├── app/                # App Router pages & API routes
│   ├── components/         # Shared React components
│   ├── lib/                # API client, types, utilities
│   └── hooks/              # Custom React hooks
├── backend/                # FastAPI server
│   ├── main.py             # App entry point & API routes
│   ├── config.py           # Settings & model pricing
│   ├── llm.py              # LLM client (OpenAI-compatible + Anthropic + xAI)
│   ├── challenges.py       # Challenge loader
│   ├── challenges.json     # Challenge definitions
│   ├── sessions.py         # Session & leaderboard management
│   ├── agents.py           # Agent definitions
│   ├── agent_runner.py     # Agent execution loop
│   ├── sandbox.py          # Code sandbox execution
│   ├── evaluation/         # Scoring engine, test runner, evaluator
│   └── interviews/         # Interview mode (rooms, sessions, realtime)
├── modal_agent/            # Modal cloud agent deployment
│   └── app.py
└── package.json            # Root scripts (concurrently)
```

---

## Agent Benchmarks (Optional)

The **Agents** page lets you run autonomous AI agents against challenges and watch them work.

### In-process (default)

No extra setup needed. The agent runs inside the backend process. Just open **Agents**, pick an agent and challenge, and click **Run**.

### With Modal (cloud)

For cloud-based agent execution:

1. Authenticate: `modal token set`
2. Deploy: `cd modal_agent && modal deploy app.py`
3. In `backend/.env`:
   ```env
   USE_INPROCESS_AGENT=false
   BACKEND_PUBLIC_URL=<url-reachable-from-Modal>   # e.g. ngrok URL
   AGENT_INTERNAL_SECRET=<shared-secret>
   ```

### Supported agents

| Agent | SDK | Required Key |
| --- | --- | --- |
| Claude Agent SDK | `claude-agent-sdk` | `ANTHROPIC_API_KEY` |
| OpenAI Assistant | OpenAI Assistants API | `OPENAI_API_KEY` |

> **Tip:** Tail the debug log for agent traces: `tail -f .cursor/debug.log`

---

## License

Private — all rights reserved.
