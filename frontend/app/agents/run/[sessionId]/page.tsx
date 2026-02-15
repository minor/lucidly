"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getSession, getChallenge, subscribeSessionEvents } from "@/lib/api";
import { ScoreBar } from "@/components/ScoreBar";
import { SimpleMarkdown } from "@/components/SimpleMarkdown";
import type { Challenge, Session, ThinkingTraceEntry } from "@/lib/types";
import { Loader2, ArrowLeft, Trophy, Code, ImageIcon, GripHorizontal } from "lucide-react";
import { MODEL_PRICING } from "@/lib/api";

const OUTPUT_PANEL_MIN = 120;
const OUTPUT_PANEL_INITIAL = 240;

const OUTPUT_PLACEHOLDER_IMAGE =
  "https://placehold.co/800x400/f8fafc/94a3b8?text=Agent+output";
const OUTPUT_PLACEHOLDER_CODE = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8" /><title>Output</title></head>
<body><header>...</header><main>...</main></body>
</html>`;

const POLL_INTERVAL_MS = 1500;
const POLL_INTERVAL_ACTIVE_MS = 500; // Faster polling while run is active so tokens/stats update in near real time

/** Format trace entry kwargs into a short, user-facing detail string. */
function formatTraceDetail(entry: ThinkingTraceEntry): string | null {
  const parts: string[] = [];
  if (typeof entry.prompt_len === "number") {
    parts.push(`${entry.prompt_len.toLocaleString()} characters`);
  }
  if (typeof entry.response_tokens === "number") {
    parts.push(`${entry.response_tokens.toLocaleString()} tokens`);
  }
  if (typeof entry.total_turns === "number") {
    parts.push(entry.total_turns === 1 ? "1 turn" : `${entry.total_turns} turns`);
  }
  if (typeof entry.accuracy === "number") {
    const pct = Math.round(entry.accuracy * 100);
    parts.push(`${pct}% match`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

export default function AgentRunWatchPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<Session | null>(null);
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [outputView, setOutputView] = useState<"preview" | "code">("preview");
  const [elapsed, setElapsed] = useState(0);
  const [outputPanelHeight, setOutputPanelHeight] = useState(OUTPUT_PANEL_INITIAL);
  const [sessionNotFound, setSessionNotFound] = useState(false);
  /** Reference HTML for challenges with html_url (same as user challenge page) */
  const [referenceHtml, setReferenceHtml] = useState<string>("");
  /** Live token count during LLM stream (from SSE); null when using session.total_tokens */
  const [liveEstimatedTokens, setLiveEstimatedTokens] = useState<number | null>(null);
  const resizeStartYRef = useRef<number>(0);
  const resizeStartHeightRef = useRef<number>(OUTPUT_PANEL_INITIAL);
  const traceEndRef = useRef<HTMLDivElement>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let ignore = false;
    setSessionNotFound(false);
    function poll() {
      getSession(sessionId)
        .then((data) => {
          if (!ignore) setSession(data);
        })
        .catch((err) => {
          if (!ignore) {
            const msg = (err as Error).message ?? "";
            if (msg.toLowerCase().includes("session") && msg.toLowerCase().includes("not found")) {
              setSessionNotFound(true);
              if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
              }
            }
            setError((err as Error).message);
          }
        })
        .finally(() => {
          if (!ignore) setLoading(false);
        });
    }
    poll();
    return () => {
      ignore = true;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [sessionId]);

  // Poll at a faster rate when run is active so tokens and trace update in near real time
  useEffect(() => {
    if (!session || session.status !== "active") return;
    const intervalMs = POLL_INTERVAL_ACTIVE_MS;
    pollIntervalRef.current = setInterval(() => {
      getSession(sessionId)
        .then((data) => setSession(data))
        .catch((err) => {
          const msg = (err as Error).message ?? "";
          if (msg.toLowerCase().includes("session") && msg.toLowerCase().includes("not found")) {
            setSessionNotFound(true);
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
          }
        });
    }, intervalMs);
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [sessionId, session?.status]);

  // Slower poll when completed (or before first session load) to catch completion
  useEffect(() => {
    if (session?.status === "active") return; // Handled by faster poll above
    const intervalMs = POLL_INTERVAL_MS;
    const id = setInterval(() => {
      getSession(sessionId)
        .then((data) => setSession(data))
        .catch(() => {});
    }, intervalMs);
    return () => clearInterval(id);
  }, [sessionId, session?.status]);

  // Subscribe to SSE for real-time token progress (and session updates) during agent run
  useEffect(() => {
    if (!sessionId) return;
    const abort = subscribeSessionEvents(sessionId, (event) => {
      if (event.type === "token_progress") {
        setLiveEstimatedTokens(event.total_estimated_tokens);
      } else if (event.type === "session_update") {
        setSession(event.session as Session);
        setLiveEstimatedTokens(null); // use real total_tokens from session now
      }
    });
    return () => abort();
  }, [sessionId]);

  // Fetch challenge when session is available (same as user challenge page)
  useEffect(() => {
    if (!session?.challenge_id) return;
    let ignore = false;
    getChallenge(session.challenge_id)
      .then((c) => {
        if (!ignore) setChallenge(c);
      })
      .catch(() => {});
    return () => {
      ignore = true;
    };
  }, [session?.challenge_id]);

  // Fetch reference HTML when challenge has html_url (match play page so agent benchmark = user challenge)
  useEffect(() => {
    if (!challenge?.html_url) return;
    let ignore = false;
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${API_BASE}/api/challenges/${challenge.id}/html`)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error("Failed to fetch"))))
      .then((html) => {
        if (!ignore) setReferenceHtml(html);
      })
      .catch(() => {});
    return () => {
      ignore = true;
    };
  }, [challenge?.id, challenge?.html_url]);

  // Auto-scroll thinking trace to bottom when new entries appear
  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.thinking_trace?.length]);

  // Elapsed time: when completed, use final duration and stop; otherwise tick every second
  useEffect(() => {
    if (!session?.started_at) return;
    if (session.status === "completed" && session.completed_at != null) {
      setElapsed(Math.max(0, session.completed_at - session.started_at));
      return;
    }
    const updateElapsed = () => {
      setElapsed(Math.max(0, Date.now() / 1000 - session.started_at));
    };
    updateElapsed();
    const interval = setInterval(updateElapsed, 1000);
    return () => clearInterval(interval);
  }, [session?.started_at, session?.status, session?.completed_at]);

  // Resize handle for "Your output" panel (drag up to expand)
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    resizeStartYRef.current = e.clientY;
    resizeStartHeightRef.current = outputPanelHeight;
    const onMove = (moveEvent: MouseEvent) => {
      const delta = resizeStartYRef.current - moveEvent.clientY;
      const next = resizeStartHeightRef.current + delta;
      const max = typeof window !== "undefined" ? Math.max(400, window.innerHeight * 0.7) : 600;
      setOutputPanelHeight(Math.min(max, Math.max(OUTPUT_PANEL_MIN, next)));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [outputPanelHeight]);

  if (sessionNotFound) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6">
        <p className="text-center text-sm text-muted">
          This run is no longer available (e.g. the server was restarted). Sessions are stored in memory and are lost on restart.
        </p>
        <Link
          href="/agents"
          className="rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-muted/50"
        >
          Start a new run
        </Link>
      </div>
    );
  }

  if (loading && !session) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  if (error && !session) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-10">
        <p className="text-sm text-error">{error}</p>
        <button
          type="button"
          onClick={() => router.push("/agents")}
          className="mt-4 text-sm text-muted hover:text-foreground"
        >
          Back to Agents
        </button>
      </div>
    );
  }

  const isActive = session?.status === "active";
  const latestCode = session?.final_code || (session?.turns?.length ? session?.turns[session.turns.length - 1]?.generated_code : "") || "";

  // Calculate total cost from turns (use fallback pricing if model not in MODEL_PRICING, e.g. openai-cot uses gpt-4o)
  const defaultPricing = { input: 0, output: 0 };
  const totalCost = session?.turns?.reduce((acc, turn) => {
    const model = session.model_used || "gpt-5.2";
    const pricing = MODEL_PRICING[model] ?? MODEL_PRICING["gpt-5.2"] ?? defaultPricing;
    const inputCost = (turn.prompt_tokens * pricing.input) / 1_000_000;
    const outputCost = (turn.response_tokens * pricing.output) / 1_000_000;
    return acc + inputCost + outputCost;
  }, 0) ?? 0;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-3">
          <Link
            href="/agents"
            className="text-muted hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-sm font-semibold">
              {session?.username ?? "Agent run"}
            </h1>
            <p className="text-xs text-muted">
              {session?.challenge_id} — {isActive ? "Running…" : "Completed"}
            </p>
          </div>
        </div>
        {session?.status === "completed" && (
          <Link
            href="/leaderboard"
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-accent-bg"
          >
            <Trophy className="h-3.5 w-3.5" />
            View leaderboard
          </Link>
        )}
      </header>

      {/* Stats bar — same as play page (read-only) */}
      <div className="flex items-center justify-between gap-4 border-b border-border px-6 py-2">
        <ScoreBar
          turns={session?.total_turns ?? 0}
          tokens={liveEstimatedTokens ?? session?.total_tokens ?? 0}
          elapsedSec={elapsed}
          accuracy={
            session?.turns?.length
              ? session.turns[session.turns.length - 1].accuracy_at_turn
              : undefined
          }
          compositeScore={session?.composite_score ?? undefined}
          cost={totalCost}
          hideTurns
        />
        {isActive && (
          <span className="text-xs text-muted">Watching agent run…</span>
        )}
      </div>

      {/* Main content — left = task (narrow), right = thinking trace + source/output */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Challenge description — same structure as user play page */}
        <div className="w-[340px] shrink-0 border-r border-border overflow-y-auto">
          <div className="p-6">
            <h2 className="text-sm font-semibold mb-3">Challenge</h2>
            <SimpleMarkdown content={challenge?.description ?? ""} className="text-sm leading-relaxed mb-4" />
            {challenge?.starter_code && (
              <div className="rounded-lg border border-border bg-code-bg overflow-hidden mb-4">
                <div className="px-3 py-1.5 border-b border-border">
                  <span className="text-xs font-medium text-muted">
                    Buggy Code
                  </span>
                </div>
                <pre className="p-3 overflow-x-auto">
                  <code className="text-xs font-mono">
                    {challenge.starter_code}
                  </code>
                </pre>
              </div>
            )}
            {challenge?.html_url && referenceHtml && (
              <div className="rounded-lg border border-border overflow-hidden bg-muted/20 mb-4 h-[320px]">
                <iframe
                  srcDoc={referenceHtml}
                  title="Challenge reference (top of page only)"
                  className="w-full h-[500px] border-0 rounded-lg pointer-events-none"
                  sandbox="allow-scripts allow-same-origin"
                />
              </div>
            )}
            {challenge?.embed_url && !challenge?.html_url && (
              <div className="rounded-lg border border-border overflow-hidden bg-muted/20 mb-4 h-[320px]">
                <iframe
                  src={challenge.embed_url}
                  title="Challenge reference"
                  className="w-full h-[500px] border-0 rounded-lg pointer-events-none"
                  sandbox="allow-scripts allow-same-origin"
                />
              </div>
            )}
            {challenge?.image_url && !challenge?.html_url && !challenge?.embed_url && (
              <div className="rounded-lg border border-border overflow-hidden bg-muted/20 mb-4">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={challenge.image_url}
                  alt="Challenge reference"
                  className="w-full max-h-[280px] object-contain object-top"
                />
              </div>
            )}
            {challenge?.test_suite && challenge.test_suite.length > 0 && (
              <div className="mt-4">
                <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                  Test Cases
                </h3>
                <div className="space-y-1.5">
                  {challenge.test_suite.map((tc, i) => (
                    <div
                      key={i}
                      className="rounded-lg bg-code-bg px-3 py-2 text-xs font-mono"
                    >
                      <span className="text-muted">Input:</span> {tc.input}
                      <br />
                      <span className="text-muted">Expected:</span>{" "}
                      {tc.expected_output}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Thinking trace (top) + Source code & output (bottom) — flex so both get space */}
        <div className="flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden border-l border-border">
          {/* Thinking trace — flex-1 so it shares space with output below */}
          <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
            <div className="p-6 pb-0 shrink-0">
              <h2 className="text-sm font-semibold mb-3">Thinking trace</h2>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-3 space-y-2">
              {(session?.thinking_trace?.length ?? 0) > 0 ? (
                <>
                  {(session?.thinking_trace ?? []).map((entry: ThinkingTraceEntry, i: number) => {
                    const detail = formatTraceDetail(entry);
                    return (
                      <div
                        key={i}
                        className="flex flex-col gap-0.5 text-sm text-foreground/90"
                      >
                        <div className="flex items-baseline gap-2">
                          <span className="shrink-0 tabular-nums text-muted-foreground text-xs">
                            +{entry.elapsed_ms}ms
                          </span>
                          <span>{entry.step}</span>
                        </div>
                        {detail && (
                          <div className="pl-6 text-xs text-muted-foreground">
                            {detail}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {isActive && (
                    <div className="flex items-center gap-2 text-xs text-muted">
                      <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
                      <span>Working…</span>
                    </div>
                  )}
                  <div ref={traceEndRef} />
                </>
              ) : (
                <div className="flex items-center gap-2 text-sm text-muted">
                  {isActive ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                      <span>Starting…</span>
                    </>
                  ) : (
                    <span>No trace entries.</span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Resize handle — drag to give more space to trace or output */}
          <button
            type="button"
            onMouseDown={handleResizeStart}
            className="flex w-full cursor-n-resize items-center justify-center border-t border-border bg-muted/10 py-1.5 text-muted hover:bg-muted/20 hover:text-foreground focus:outline-none shrink-0"
            aria-label="Resize output panel"
          >
            <GripHorizontal className="h-4 w-4" />
          </button>

          {/* Source code & rendered output — fixed height so trace gets the rest; resize handle adjusts this */}
          <div
            className="shrink-0 flex flex-col border-t border-border bg-muted/5 overflow-hidden"
            style={{ height: outputPanelHeight }}
          >
            <div className="flex items-center justify-between border-b border-border px-4 py-2.5 shrink-0 bg-background/80">
              <h3 className="text-sm font-semibold text-foreground">
                Your output
              </h3>
              <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/30 p-0.5">
                <button
                  type="button"
                  onClick={() => setOutputView("preview")}
                  className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                    outputView === "preview"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  <ImageIcon className="h-3 w-3" />
                  Preview
                </button>
                <button
                  type="button"
                  onClick={() => setOutputView("code")}
                  className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                    outputView === "code"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  <Code className="h-3 w-3" />
                  Code
                </button>
              </div>
            </div>
            <div className="flex-1 min-h-0 overflow-hidden rounded-b-lg mx-2 mb-2 border border-border bg-code-bg/50">
              {outputView === "preview" ? (
                latestCode ? (
                  <iframe
                    title="Agent output"
                    sandbox="allow-scripts"
                    srcDoc={latestCode}
                    className="w-full h-full border-0 bg-white"
                  />
                ) : (
                  <div className="h-full flex items-center justify-center bg-muted/20">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={OUTPUT_PLACEHOLDER_IMAGE}
                      alt="Agent output"
                      className="max-h-full w-full object-contain object-top"
                    />
                  </div>
                )
              ) : (
                <pre className="h-full overflow-auto p-4 text-xs font-mono whitespace-pre">
                  <code>{latestCode || OUTPUT_PLACEHOLDER_CODE}</code>
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
