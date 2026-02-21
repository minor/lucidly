import type {
  Challenge,
  Session,
  PromptResponse,
  Scores,
  LeaderboardEntry,
  Agent,
  InterviewRoom,
  InterviewChallenge,
  InterviewConfig,
  InterviewSession,
  InterviewReport,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API request failed");
  }
  return res.json();
}

// ---- Challenges ----

export async function getChallenges(params?: {
  category?: string;
  difficulty?: string;
}): Promise<Challenge[]> {
  const searchParams = new URLSearchParams();
  if (params?.category) searchParams.set("category", params.category);
  if (params?.difficulty) searchParams.set("difficulty", params.difficulty);
  const query = searchParams.toString();
  return fetchJSON<Challenge[]>(`/api/challenges${query ? `?${query}` : ""}`);
}

export async function getChallenge(id: string): Promise<Challenge> {
  return fetchJSON<Challenge>(`/api/challenges/${id}`);
}

// ---- Sessions ----

export async function createSession(
  challengeId: string,
  model?: string,
  username?: string
): Promise<{ session_id: string; challenge: Challenge }> {
  return fetchJSON("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      challenge_id: challengeId,
      model,
      username: username || "anonymous",
    }),
  });
}

export async function getSession(sessionId: string): Promise<Session> {
  return fetchJSON<Session>(`/api/sessions/${sessionId}`);
}

/** Session event from SSE stream (agent runs): token_progress and session_update */
export type SessionEvent =
  | { type: "token_progress"; total_estimated_tokens: number }
  | { type: "session_update"; session: Session }
  | { type: "timer_paused" }
  | { type: "timer_resumed"; paused_seconds?: number }
  | { type: "ping" };

/**
 * Subscribe to server-sent events for an agent run session.
 * Call onMessage for each event; returns an abort function to close the stream.
 */
export function subscribeSessionEvents(
  sessionId: string,
  onMessage: (event: SessionEvent) => void,
  signal?: AbortSignal
): () => void {
  const url = `${API_BASE.replace(/^http/, "http")}/api/sessions/${sessionId}/events`;
  const controller = new AbortController();
  if (signal) {
    signal.addEventListener("abort", () => controller.abort());
  }

  const abort = () => controller.abort();

  fetch(url, { signal: controller.signal })
    .then((res) => {
      if (!res.ok || !res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const process = (): Promise<void> =>
        reader.read().then(({ done, value }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6)) as SessionEvent;
                onMessage(data);
              } catch {
                // ignore parse errors
              }
            }
          }
          return process();
        });
      return process();
    })
    .catch((err) => {
      if (err?.name === "AbortError") return;
      console.warn("Session events stream error:", err);
    });

  return abort;
}

export async function submitPrompt(
  sessionId: string,
  prompt: string,
  model?: string
): Promise<PromptResponse> {
  return fetchJSON<PromptResponse>(`/api/sessions/${sessionId}/prompt`, {
    method: "POST",
    body: JSON.stringify({ prompt, model }),
  });
}

export async function completeSession(
  sessionId: string
): Promise<{ session: Session; scores: Scores }> {
  return fetchJSON(`/api/sessions/${sessionId}/complete`, {
    method: "POST",
  });
}

// ---- Agents ----

export async function getAgents(): Promise<Agent[]> {
  return fetchJSON<Agent[]>("/api/agents");
}

export async function startAgentRun(agentId: string, challengeId: string): Promise<{
  session_id: string;
  challenge_id: string;
  agent_id: string;
}> {
  return fetchJSON("/api/agent-runs", {
    method: "POST",
    body: JSON.stringify({ agent_id: agentId, challenge_id: challengeId }),
  });
}

// ---- Leaderboard ----

export async function getLeaderboard(params?: {
  limit?: number;
  category?: string;
  challenge_id?: string;
}): Promise<LeaderboardEntry[]> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.category) searchParams.set("category", params.category);
  if (params?.challenge_id) searchParams.set("challenge_id", params.challenge_id);
  const query = searchParams.toString();
  return fetchJSON<LeaderboardEntry[]>(
    `/api/leaderboard${query ? `?${query}` : ""}`
  );
}

// ---- WebSocket ----

export function createSessionWebSocket(sessionId: string): WebSocket {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return new WebSocket(`${wsBase}/ws/session/${sessionId}`);
}

// ---- Chat ----

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface StreamDoneData {
  content: string;
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
}

export async function streamChat(
  messages: ChatMessage[],
  model?: string,
  onChunk?: (chunk: string) => void,
  onComplete?: (fullResponse: string) => void,
  onError?: (error: string) => void,
  onDone?: (data: StreamDoneData) => void,
  onUsage?: (usage: { input_tokens: number }) => void,
  signal?: AbortSignal,
  challengeId?: string
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, model, challenge_id: challengeId ?? undefined }),
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      onError?.("AbortError");
      return;
    }
    throw err;
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    onError?.(error.detail || "Failed to stream chat");
    return;
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    onError?.("No response body");
    return;
  }

  let buffer = "";
  let fullResponse = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "chunk") {
              fullResponse += data.content;
              onChunk?.(data.content);
            } else if (data.type === "usage") {
              onUsage?.({ input_tokens: data.input_tokens });
            } else if (data.type === "done") {
              onComplete?.(data.content || fullResponse);
              onDone?.({
                content: data.content || fullResponse,
                input_tokens: data.input_tokens,
                output_tokens: data.output_tokens,
                cost: data.cost,
              });
            } else if (data.type === "error") {
              onError?.(data.message || "Unknown error");
              return;
            }
          } catch (e) {
            // Skip invalid JSON
          }
        }
      }
    }
  } catch (err: unknown) {
    // AbortError is expected when the user stops the stream early
    if (err instanceof DOMException && err.name === "AbortError") {
      onComplete?.(fullResponse);
      onError?.("AbortError");
      return;
    }
    throw err;
  } finally {
    reader.releaseLock();
  }
}

// ---- Sandbox Lifecycle ----

export async function createSandbox(): Promise<{ sandbox_id: string }> {
  return fetchJSON<{ sandbox_id: string }>("/api/sandbox/create", {
    method: "POST",
  });
}

export async function terminateSandbox(sandboxId: string): Promise<void> {
  await fetchJSON(`/api/sandbox/${sandboxId}/terminate`, {
    method: "POST",
  });
}

// ---- Run Tests ----

export interface TestCaseResult {
  input: string;
  expected: string;
  actual: string | null;
  passed: boolean;
  error: string | null;
}

export interface RunTestsResponse {
  results: TestCaseResult[];
  all_passed: boolean;
  passed_count: number;
  total_count: number;
}

export interface RunCodeResponse {
  stdout: string;
  stderr: string;
  returncode: number;
}

export async function runTests(
  code: string,
  challengeId: string,
  sandboxId: string
): Promise<RunTestsResponse> {
  return fetchJSON<RunTestsResponse>("/api/run-tests", {
    method: "POST",
    body: JSON.stringify({ code, challenge_id: challengeId, sandbox_id: sandboxId }),
  });
}

export async function runCode(
  sandboxId: string,
  code: string
): Promise<RunCodeResponse> {
  return fetchJSON<RunCodeResponse>("/api/run-code", {
    method: "POST",
    body: JSON.stringify({ sandbox_id: sandboxId, code }),
  });
}

// ---- UI Evaluation ----

export interface EvaluateUIResponse {
  score: number; // 0-100
  similarity_score: number; // 0-1
  detailed_feedback?: string;
}

export async function evaluateUI(
  challengeId: string,
  generatedHtml: string
): Promise<EvaluateUIResponse> {
  return fetchJSON<EvaluateUIResponse>("/api/evaluate-ui", {
    method: "POST",
    body: JSON.stringify({
      challenge_id: challengeId,
      generated_html: generatedHtml,
    }),
  });
}

// ---- Score Calculation ----

export interface CalculateScoreRequest {
  challenge_id: string;
  accuracy: number;
  elapsed_sec: number;
  total_tokens: number;
  total_turns: number;
  difficulty?: string;
  model?: string;
  category?: string;
  prd_content?: string;
  username?: string;
  messages?: ChatMessage[];
  total_cost?: number;
}

export async function calculateScore(
  req: CalculateScoreRequest
): Promise<Scores> {
  return fetchJSON<Scores>("/api/calculate-score", {
    method: "POST",
    body: JSON.stringify(req),
  });
}


export const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  "claude-opus-4-6": { input: 5.0, output: 25.0 },
  "claude-sonnet-4-5": { input: 3.0, output: 15.0 },
  "claude-haiku-4-5": { input: 1.0, output: 5.0 },
  "gpt-5.2": { input: 1.75, output: 14.0 },
  "gpt-5-nano": { input: 0.05, output: 0.40 },
  "gpt-5-mini": { input: 0.25, output: 2.00 },
  "gpt-4o": { input: 2.5, output: 10.0 },
  "grok-4-1-fast-reasoning": { input: 0.20, output: 0.50 },
  "grok-code-fast-1": { input: 0.20, output: 1.50 },
  "sonar": { input: 0.20, output: 1.0 },
  "sonar-pro": { input: 3.0, output: 15.0 },
};

export const MODELS = [
  { id: "gpt-5.2", name: "GPT-5.2" },
  { id: "gpt-5-mini", name: "GPT-5 Mini" },
  { id: "gpt-5-nano", name: "GPT-5 Nano" },
  // DISABLED: Claude models hidden until re-enabled
  // { id: "claude-opus-4-6", name: "Claude Opus 4.6" },
  // { id: "claude-sonnet-4-5", name: "Claude Sonnet 4.5" },
  // { id: "claude-haiku-4-5", name: "Claude Haiku 4.5" },
  { id: "grok-4-1-fast-reasoning", name: "Grok 4.1 Fast Reasoning" },
  { id: "grok-code-fast-1", name: "Grok Code Fast" },
  { id: "sonar-pro", name: "Perplexity Sonar Pro" },
];

// ---- Prompt Feedback (AI analysis) ----

export interface PromptFeedbackRequest {
  messages: ChatMessage[];
  challenge_id: string;
  challenge_description: string;
  challenge_category: string;
  challenge_difficulty: string;
  reference_html?: string;
  /** For product challenges: the submitted PRD text to grade */
  prd_content?: string;
  accuracy: number;
  total_turns: number;
  total_tokens: number;
  elapsed_sec: number;
  db_session_id?: string;
}

/**
 * Stream AI-powered feedback on the user's prompt engineering.
 * Uses SSE to progressively deliver the analysis.
 */
export async function streamPromptFeedback(
  req: PromptFeedbackRequest,
  onChunk?: (chunk: string) => void,
  onComplete?: (fullResponse: string) => void,
  onError?: (error: string) => void,
  signal?: AbortSignal
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/prompt-feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return;
    }
    throw err;
  }

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    onError?.(error.detail || "Failed to get prompt feedback");
    return;
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    onError?.("No response body");
    return;
  }

  let buffer = "";
  let fullResponse = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "chunk") {
              fullResponse += data.content;
              onChunk?.(data.content);
            } else if (data.type === "done") {
              onComplete?.(data.content || fullResponse);
            } else if (data.type === "error") {
              onError?.(data.message || "Unknown error");
              return;
            }
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      onComplete?.(fullResponse);
      return;
    }
    throw err;
  } finally {
    reader.releaseLock();
  }
}

// ---- Interview Mode ----

export async function createInterviewRoom(params: {
  created_by: string;
  title: string;
  company_name?: string;
  config?: Partial<InterviewConfig>;
}): Promise<InterviewRoom> {
  return fetchJSON<InterviewRoom>("/api/interviews", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function listInterviewRooms(
  created_by?: string
): Promise<InterviewRoom[]> {
  const query = created_by ? `?created_by=${encodeURIComponent(created_by)}` : "";
  return fetchJSON<InterviewRoom[]>(`/api/interviews${query}`);
}

export async function getInterviewRoom(roomId: string): Promise<InterviewRoom> {
  return fetchJSON<InterviewRoom>(`/api/interviews/${roomId}`);
}

export async function getInterviewRoomByInvite(
  inviteCode: string
): Promise<InterviewRoom> {
  return fetchJSON<InterviewRoom>(`/api/interviews/invite/${inviteCode}`);
}

export async function updateInterviewRoom(
  roomId: string,
  params: { title?: string; company_name?: string; config?: InterviewConfig }
): Promise<InterviewRoom> {
  return fetchJSON<InterviewRoom>(`/api/interviews/${roomId}`, {
    method: "PATCH",
    body: JSON.stringify(params),
  });
}

export async function addInterviewChallenge(
  roomId: string,
  params: {
    title: string;
    description: string;
    category: string;
    starter_code?: string;
    solution_code?: string;
    test_cases?: { input: string; expected_output: string }[];
    reference_html?: string;
  }
): Promise<InterviewChallenge> {
  return fetchJSON<InterviewChallenge>(
    `/api/interviews/${roomId}/challenges`,
    {
      method: "POST",
      body: JSON.stringify(params),
    }
  );
}

export async function removeInterviewChallenge(
  roomId: string,
  challengeId: string
): Promise<void> {
  await fetchJSON(`/api/interviews/${roomId}/challenges/${challengeId}`, {
    method: "DELETE",
  });
}

export async function startInterviewSession(
  roomId: string,
  params: { candidate_name: string; challenge_id: string }
): Promise<InterviewSession> {
  return fetchJSON<InterviewSession>(
    `/api/interviews/${roomId}/sessions`,
    {
      method: "POST",
      body: JSON.stringify(params),
    }
  );
}

export async function getInterviewSession(
  roomId: string,
  sessionId: string
): Promise<InterviewSession> {
  return fetchJSON<InterviewSession>(
    `/api/interviews/${roomId}/sessions/${sessionId}`
  );
}

export async function listInterviewSessions(
  roomId: string
): Promise<InterviewSession[]> {
  return fetchJSON<InterviewSession[]>(
    `/api/interviews/${roomId}/sessions`
  );
}

export async function completeInterviewSession(
  roomId: string,
  sessionId: string
): Promise<{ session: InterviewSession; scores: Scores }> {
  return fetchJSON(`/api/interviews/${roomId}/sessions/${sessionId}/complete`, {
    method: "POST",
  });
}

export async function getInterviewReport(
  roomId: string
): Promise<InterviewReport> {
  return fetchJSON<InterviewReport>(`/api/interviews/${roomId}/report`);
}

/**
 * Stream a prompt to an interview session. Uses SSE like the chat endpoint.
 */
export async function streamInterviewPrompt(
  roomId: string,
  sessionId: string,
  prompt: string,
  model?: string,
  onChunk?: (chunk: string) => void,
  onComplete?: (data: {
    content: string;
    generated_code: string;
    input_tokens: number;
    output_tokens: number;
    cost: number;
    total_tokens: number;
    total_turns: number;
  }) => void,
  onError?: (error: string) => void,
  signal?: AbortSignal
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE}/api/interviews/${roomId}/sessions/${sessionId}/prompt`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, model }),
        signal,
      }
    );
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      onError?.("AbortError");
      return;
    }
    throw err;
  }

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    onError?.(error.detail || "Failed to stream prompt");
    return;
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    onError?.("No response body");
    return;
  }

  let buffer = "";
  let fullResponse = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "chunk") {
              fullResponse += data.content;
              onChunk?.(data.content);
            } else if (data.type === "done") {
              onComplete?.({
                content: data.content || fullResponse,
                generated_code: data.generated_code || "",
                input_tokens: data.input_tokens || 0,
                output_tokens: data.output_tokens || 0,
                cost: data.cost || 0,
                total_tokens: data.total_tokens || 0,
                total_turns: data.total_turns || 0,
              });
            } else if (data.type === "error") {
              onError?.(data.message || "Unknown error");
              return;
            }
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      onComplete?.({
        content: fullResponse,
        generated_code: "",
        input_tokens: 0,
        output_tokens: 0,
        cost: 0,
        total_tokens: 0,
        total_turns: 0,
      });
      return;
    }
    throw err;
  } finally {
    reader.releaseLock();
  }
}

/**
 * Subscribe to interview room observation events (SSE).
 */
export function subscribeInterviewObserver(
  roomId: string,
  onMessage: (event: Record<string, unknown>) => void,
  signal?: AbortSignal
): () => void {
  const url = `${API_BASE}/api/interviews/${roomId}/observe`;
  const controller = new AbortController();
  if (signal) {
    signal.addEventListener("abort", () => controller.abort());
  }

  const abort = () => controller.abort();

  fetch(url, { signal: controller.signal })
    .then((res) => {
      if (!res.ok || !res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const process = (): Promise<void> =>
        reader.read().then(({ done, value }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                onMessage(data);
              } catch {
                // ignore parse errors
              }
            }
          }
          return process();
        });
      return process();
    })
    .catch((err) => {
      if (err?.name === "AbortError") return;
      console.warn("Interview observer stream error:", err);
    });

  return abort;
}

// ---- Vercel Sandbox (UI preview) ----

export interface VercelSandboxInfo {
  sandboxId: string;
  previewUrl: string;
}

/**
 * Create a Vercel Sandbox with an HTTP server for live UI preview.
 * Returns the sandbox ID and a publicly accessible preview URL.
 */
export async function createVercelSandbox(): Promise<VercelSandboxInfo> {
  const res = await fetch("/api/sandbox", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || "Failed to create Vercel sandbox");
  }
  return res.json();
}

/**
 * Write HTML code to a Vercel Sandbox. The sandbox's HTTP server will
 * serve the updated HTML on the next request / iframe refresh.
 */
export async function updateVercelSandboxCode(
  sandboxId: string,
  code: string
): Promise<void> {
  const res = await fetch(`/api/sandbox/${sandboxId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || "Failed to update sandbox code");
  }
}

/**
 * Stop and clean up a Vercel Sandbox.
 */
export async function stopVercelSandbox(sandboxId: string): Promise<void> {
  await fetch(`/api/sandbox/${sandboxId}`, { method: "DELETE" }).catch(
    () => {}
  );
}

// ---------------------------------------------------------------------------
// Username management
// ---------------------------------------------------------------------------

/**
 * Fetch the stored username for an Auth0 user.
 * Returns the username string or null if not yet set.
 */
export async function getUsername(auth0Id: string): Promise<string | null> {
  const res = await fetch(`${API_BASE}/api/username/${encodeURIComponent(auth0Id)}`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.username ?? null;
}

/**
 * Check if a username is available (case-insensitive).
 */
export async function checkUsernameAvailable(username: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/username-available/${encodeURIComponent(username)}`);
  if (!res.ok) return false;
  const data = await res.json();
  return data.available;
}

/**
 * Claim a username for the given Auth0 user.
 * Throws an error with the detail message if the name is taken or invalid.
 */
export async function setUsername(auth0Id: string, username: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/username`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ auth0_id: auth0Id, username }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Failed to set username." }));
    throw new Error(data.detail || "Failed to set username.");
  }
  const data = await res.json();
  return data.username;
}
