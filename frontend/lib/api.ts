import type {
  Challenge,
  Session,
  PromptResponse,
  Scores,
  LeaderboardEntry,
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

// ---- Leaderboard ----

export async function getLeaderboard(params?: {
  limit?: number;
  category?: string;
}): Promise<LeaderboardEntry[]> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.category) searchParams.set("category", params.category);
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
