# No Shot — Frontend

The frontend for **No Shot**, a competitive platform that benchmarks and gamifies your ability to prompt AI to write code. Like [Monkeytype](https://monkeytype.com) for the age of AI.

## Tech Stack

- **[Next.js](https://nextjs.org) 16** — App Router, server components, API routes
- **[React](https://react.dev) 19** — UI library
- **[TypeScript](https://www.typescriptlang.org) 5** — Type safety
- **[Tailwind CSS](https://tailwindcss.com) 4** — Utility-first styling
- **[Auth0](https://auth0.com)** — Authentication
- **[Zustand](https://zustand-demo.pmnd.rs)** — Lightweight state management
- **[Lucide](https://lucide.dev)** — Icon system
- **[Vercel Sandbox](https://vercel.com/docs/sandbox)** — Sandboxed execution for UI challenges
- **[Playwright](https://playwright.dev)** — End-to-end testing

## Features

### Arena Mode

- **Challenge Browser** — Browse and filter challenges by category (UI, function, debug, data, system) and difficulty (easy, medium, hard)
- **Interactive Prompting Sessions** — Chat with an LLM in real time, watch code generate via streaming, and iterate across multiple turns
- **Live Preview** — Sandboxed preview for UI challenges powered by Vercel Sandbox; automated test execution for function challenges
- **ELO-style Scoring** — Composite score (0–1000) based on accuracy, speed, and cost efficiency
- **Model Selection** — Choose between supported LLMs (GPT, Claude, etc.)
- **Prompt Feedback** — Get AI-generated feedback on how to improve your prompts
- **Leaderboard** — Per-challenge rankings with sortable metrics (score, accuracy, time, turns, tokens, cost)
- **Agent Benchmarks** — Run autonomous AI agents against challenges and watch their thinking trace live

### Interview Mode

- **Create Interviews** — Build interview rooms with custom coding, frontend, and system design challenges
- **Invite Candidates** — Share an invite code for candidates to join
- **Live Observation** — Watch candidates solve challenges in real time
- **Reports** — Review detailed post-interview reports with metrics and turn-by-turn transcripts

## Project Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── page.tsx            # Landing page
│   ├── layout.tsx          # Root layout (sidebar, auth, fonts)
│   ├── globals.css         # Design system & theme variables
│   ├── play/               # Arena: challenge browser & sessions
│   ├── leaderboard/        # Per-challenge leaderboards
│   ├── agents/             # Agent benchmark runner & live viewer
│   ├── interview/          # Interview mode (create, take, observe, report)
│   └── api/                # API routes (sandbox proxy)
├── components/             # Shared React components
│   ├── Sidebar.tsx         # Collapsible sidebar with mode switching
│   ├── PromptInput.tsx     # Chat input component
│   ├── ScoreBar.tsx        # Live score display
│   ├── ChallengeCard.tsx   # Challenge grid card
│   ├── SimpleMarkdown.tsx  # Lightweight markdown renderer
│   ├── Auth0Provider.tsx   # Auth0 context wrapper
│   └── ...
├── lib/                    # Utilities & shared logic
│   ├── api.ts              # Backend API client & streaming helpers
│   ├── types.ts            # TypeScript interfaces
│   └── codeExtract.ts      # Code extraction from LLM responses
├── hooks/                  # Custom React hooks
│   └── useUsername.ts      # Username resolution hook
└── public/                 # Static assets (logo, icons)
```

## Getting Started

### Prerequisites

- **[Bun](https://bun.sh)** (recommended) or Node.js 18+
- The backend server running on `http://localhost:8000` (see the [root README](../README.md))

### Install Dependencies

```bash
cd frontend
bun install
```

Or with npm:

```bash
npm install
```

### Environment Variables

Create a `.env.local` file in the `frontend/` directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_AUTH0_DOMAIN=your-auth0-domain
NEXT_PUBLIC_AUTH0_CLIENT_ID=your-auth0-client-id
```

### Run the Dev Server

```bash
bun dev
```

Or with npm:

```bash
npm run dev
```

The app will be available at **[http://localhost:3000](http://localhost:3000)**.

> **Tip:** You can also start both the frontend and backend together from the project root with `bun run dev` — see the [root README](../README.md) for details.

## Scripts

| Command | Description |
| --- | --- |
| `bun dev` | Start the Next.js dev server |
| `bun run build` | Create a production build |
| `bun start` | Serve the production build |
| `bun run lint` | Run ESLint |

## Deployment

The frontend is configured for deployment on **[Vercel](https://vercel.com)**. See `vercel.json` for the build configuration.
