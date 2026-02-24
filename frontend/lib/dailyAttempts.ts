/**
 * Local tracking of in-progress challenge attempts.
 *
 * The backend only records a session in challenge_sessions on *submission*,
 * so the daily-attempts endpoint lags by one for the current in-progress
 * attempt. This module writes to localStorage when the user enters a challenge
 * so the challenge list can show the accurate remaining count immediately.
 *
 * Key format: lucidly_attempts_{date}
 * Value: JSON object { [challengeId_username]: count }
 */

const PREFIX = "lucidly_attempts_";

function todayKey(): string {
  return PREFIX + new Date().toISOString().slice(0, 10);
}

function readLocal(): Record<string, number> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(todayKey());
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeLocal(data: Record<string, number>): void {
  if (typeof window === "undefined") return;
  try {
    // Prune stale days while we're here
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(PREFIX) && key !== todayKey()) {
        localStorage.removeItem(key);
      }
    }
    localStorage.setItem(todayKey(), JSON.stringify(data));
  } catch {}
}

/** Record that the user started an attempt for a challenge. */
export function recordLocalAttempt(challengeId: string, username: string): void {
  const key = `${challengeId}_${username}`;
  const data = readLocal();
  data[key] = (data[key] ?? 0) + 1;
  writeLocal(data);
}

/**
 * Merge local in-progress counts into the backend counts.
 * Use the higher of the two for each challenge, so we never show
 * an optimistic count lower than what the server knows.
 */
export function mergeWithLocalAttempts(
  backendCounts: Record<string, number>,
  username: string
): Record<string, number> {
  const local = readLocal();
  const merged = { ...backendCounts };
  for (const [key, localCount] of Object.entries(local)) {
    const [challengeId] = key.split(`_${username}`);
    if (!challengeId || !key.endsWith(`_${username}`)) continue;
    merged[challengeId] = Math.max(merged[challengeId] ?? 0, localCount);
  }
  return merged;
}
