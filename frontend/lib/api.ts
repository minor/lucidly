import type {
  Challenge,
  Session,
  PromptResponse,
  Scores,
  LeaderboardEntry,
  Agent,
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
  signal?: AbortSignal
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, model }),
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
  accuracy: number;
  elapsed_sec: number;
  total_tokens: number;
  total_turns: number;
  difficulty?: string;
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
};

export const MODELS = [
  { id: "gpt-5.2", name: "GPT-5.2" },
  { id: "gpt-5-mini", name: "GPT-5 Mini" },
  { id: "gpt-5-nano", name: "GPT-5 Nano" },
  { id: "claude-opus-4-6", name: "Claude Opus 4.6" },
  { id: "claude-sonnet-4-5", name: "Claude Sonnet 4.5" },
  { id: "claude-haiku-4-5", name: "Claude Haiku 4.5" },
];

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
