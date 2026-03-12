# Linear + GitHub Integration for Interview Mode — Design

**Date:** 2026-03-11
**Status:** Approved

---

## Goal

Allow interviewers to import Linear issues directly into interview mode challenge creation. The issue title and description auto-populate the challenge form; existing GitHub test files (from linked PRs) are parsed into test cases, or LLM-generated if none exist.

---

## Architecture

### New backend module: `backend/integrations/`

- `router.py` — FastAPI router mounted at `/api/integrations`
- `linear.py` — Linear OAuth client + issue/PR attachment fetching
- `github.py` — GitHub OAuth client + PR diff + test file fetching
- `generate.py` — LLM logic for parsing/generating test cases

### New Supabase table: `user_integrations`

```sql
CREATE TABLE user_integrations (
  id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     TEXT    NOT NULL,                     -- Auth0 sub claim
  provider    TEXT    NOT NULL,                     -- 'linear' | 'github'
  access_token  TEXT  NOT NULL,
  refresh_token TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, provider)
);
```

### New config keys (`.env`)

```
LINEAR_CLIENT_ID=
LINEAR_CLIENT_SECRET=
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
INTEGRATION_REDIRECT_BASE_URL=https://app.lucidly.com   # used to build OAuth callback URLs
```

---

## API Endpoints

### OAuth

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/integrations/linear/connect` | Redirect to Linear OAuth consent screen |
| GET | `/api/integrations/linear/callback` | Linear OAuth callback — stores token, closes popup |
| GET | `/api/integrations/github/connect` | Redirect to GitHub OAuth consent screen |
| GET | `/api/integrations/github/callback` | GitHub OAuth callback — stores token, closes popup |

Both callbacks return a small HTML page that calls `window.opener.postMessage` and closes itself, so the popup flow resolves cleanly in the frontend.

### Status + Data

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/integrations/status` | `{ linear: bool, github: bool }` for the current user |
| GET | `/api/integrations/linear/issues?query=` | Search/list issues from Linear workspace |
| POST | `/api/integrations/generate-challenge` | Given a Linear issue ID, return populated challenge fields |

### `POST /api/integrations/generate-challenge` request/response

```json
// Request
{ "issue_id": "ABC-123" }

// Response
{
  "title": "Fix off-by-one in pagination",
  "description": "...",
  "starter_code": "def paginate(items, page, size):\n    pass",
  "test_cases": [
    { "input": "paginate([1,2,3,4,5], 1, 2)", "expected_output": "[1, 2]" },
    { "input": "paginate([1,2,3,4,5], 3, 2)", "expected_output": "[5]" }
  ],
  "source": "existing_tests"  // or "llm_generated"
}
```

---

## Data Flow

```
1. User clicks "Import from Linear" in Step 2
2. Frontend checks GET /api/integrations/status
3. If Linear not connected → open /api/integrations/linear/connect in popup → postMessage on success → recheck status
4. If GitHub not connected → same popup flow for GitHub
5. Open Linear issue picker modal → GET /api/integrations/linear/issues?query=
6. User selects issue → POST /api/integrations/generate-challenge { issue_id }
   a. Fetch issue title + description from Linear API
   b. Fetch issue attachments → find linked GitHub PRs
   c. Fetch PR changed files from GitHub API
   d. For each changed file, look for corresponding test file in repo (e.g. src/foo.py → tests/test_foo.py)
   e. If test files found: fetch content → LLM parses into {input, expected_output} pairs
   f. If no test files: LLM generates test cases from issue description + diff
7. Auto-populate challenge form; user can edit before saving
```

---

## Test Case Generation Logic

**Existing tests path:**
- Identify test files by convention: `tests/test_<module>.py`, `__tests__/<module>.test.ts`, etc.
- Fetch file content via GitHub API
- LLM prompt: "Given these test functions, extract each as a `{input, expected_output}` pair where input is a function call expression and expected_output is a Python literal. For void tests that pass with no return value, use `None` as expected_output."

**LLM generation path (no existing tests):**
- Inputs: issue title, issue description, PR diff (changed functions/signatures)
- LLM prompt: "Generate N test cases for the described bug fix as `{input, expected_output}` pairs..."

---

## Frontend Changes

### `frontend/app/interview/create/page.tsx`

- Add "Import from Linear" button in Step 2, above the manual challenge form
- Add `LinearImportModal` component: search input + issue list + connect prompts
- Add `useIntegrationStatus` hook: polls `/api/integrations/status`, triggers OAuth popups

### New components

- `frontend/components/interview/LinearImportModal.tsx` — issue picker + OAuth inline prompts
- `frontend/components/interview/OAuthConnectButton.tsx` — reusable popup OAuth button

### `frontend/lib/api.ts`

- `getIntegrationStatus()`
- `searchLinearIssues(query)`
- `generateChallenge(issueId)`

---

## Auth

All `/api/integrations/*` endpoints (except OAuth callbacks) require the Auth0 JWT via `Depends(get_current_user)`. The OAuth callbacks use a `state` param (signed with a short-lived HMAC using the user's session) to bind the callback to the initiating user.

---

## Out of Scope

- Refreshing expired OAuth tokens automatically (Linear tokens don't expire; GitHub tokens don't expire unless revoked)
- Syncing Linear issue updates back after import
- Support for non-Python test files generating test cases (JS/TS deferred)
