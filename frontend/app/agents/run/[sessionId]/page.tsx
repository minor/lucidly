"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getSession, getChallenge } from "@/lib/api";
import { ChatMessage } from "@/components/ChatMessage";
import { ScoreBar } from "@/components/ScoreBar";
import type { Challenge, Session, Turn } from "@/lib/types";
import { Loader2, ArrowLeft, Trophy, Code, Eye } from "lucide-react";

const POLL_INTERVAL_MS = 1500;

export default function AgentRunWatchPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<Session | null>(null);
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [outputView, setOutputView] = useState<"preview" | "code">("preview");
  const [elapsed, setElapsed] = useState(0);
  const turnsEndRef = useRef<HTMLDivElement>(null);

  // Poll session
  useEffect(() => {
    let ignore = false;
    function poll() {
      getSession(sessionId)
        .then((data) => {
          if (!ignore) setSession(data);
        })
        .catch((err) => {
          if (!ignore) setError((err as Error).message);
        })
        .finally(() => {
          if (!ignore) setLoading(false);
        });
    }
    poll();
    const interval = setInterval(() => {
      if (ignore) return;
      getSession(sessionId)
        .then((data) => {
          if (!ignore) setSession(data);
        })
        .catch(() => {});
    }, POLL_INTERVAL_MS);
    return () => {
      ignore = true;
      clearInterval(interval);
    };
  }, [sessionId]);

  // Load challenge when session is available (once per challenge_id)
  const fetchedChallengeIdRef = useRef<string | null>(null);
  useEffect(() => {
    fetchedChallengeIdRef.current = null;
  }, [sessionId]);
  useEffect(() => {
    if (!session?.challenge_id) return;
    if (fetchedChallengeIdRef.current === session.challenge_id) return;
    fetchedChallengeIdRef.current = session.challenge_id;
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

  // Elapsed time: live when active, fixed when completed
  useEffect(() => {
    if (!session?.started_at) return;
    if (session.status === "completed" && session.completed_at != null) {
      setElapsed(session.completed_at - session.started_at);
      return;
    }
    const start = session.started_at * 1000;
    const tick = () => setElapsed((Date.now() - start) / 1000);
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [session?.started_at, session?.status, session?.completed_at]);

  useEffect(() => {
    turnsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.turns?.length]);

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
        <Link
          href="/agents"
          className="mt-4 inline-block text-sm text-muted hover:text-foreground"
        >
          Back to Agents
        </Link>
      </div>
    );
  }

  const isActive = session?.status === "active";
  const latestCode =
    session?.final_code ||
    (session?.turns?.length
      ? session.turns[session.turns.length - 1]?.generated_code
      : "") ||
    "";

  return (
    <div className="flex h-screen flex-col">
      {/* Header — same style as play page */}
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
              {challenge?.title ?? session?.challenge_id}
            </h1>
            <div className="flex items-center gap-2 text-xs text-muted">
              <span>{session?.username ?? "Agent run"}</span>
              <span>·</span>
              <span className="capitalize">{challenge?.category ?? "—"}</span>
              <span>·</span>
              <span>{isActive ? "Running…" : "Completed"}</span>
            </div>
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
          tokens={session?.total_tokens ?? 0}
          elapsedSec={elapsed}
          accuracy={
            session?.turns?.length
              ? session.turns[session.turns.length - 1].accuracy_at_turn
              : undefined
          }
          compositeScore={session?.composite_score ?? undefined}
        />
        {isActive && (
          <span className="text-xs text-muted">Watching agent run…</span>
        )}
      </div>

      {/* Main content — same two-column layout as play: left = challenge + output, right = chat */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Challenge description + Your output (live-updating) */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border overflow-hidden">
          <div className="flex-1 overflow-y-auto">
            <div className="p-6">
              <h2 className="text-sm font-semibold mb-3">Challenge</h2>
              <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap mb-4">
                {challenge?.description ?? "Loading…"}
              </p>
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
              {challenge?.embed_url && (
                <div className="rounded-lg border border-border overflow-hidden bg-muted/20 mb-4 h-[320px]">
                  <iframe
                    src={challenge.embed_url}
                    title="Challenge reference"
                    className="w-full h-full border-0 rounded-lg pointer-events-none"
                    sandbox="allow-scripts allow-same-origin"
                  />
                </div>
              )}
              {challenge?.image_url && !challenge?.embed_url && (
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

              {/* Your output — same panel as play page, live-updating from session */}
              <div className="mt-8 pt-6 border-t border-border">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold">Your output</h2>
                  <div className="inline-flex rounded-lg border border-border bg-muted/30 p-0.5">
                    <button
                      type="button"
                      onClick={() => setOutputView("preview")}
                      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                        outputView === "preview"
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted hover:text-foreground"
                      }`}
                    >
                      <Eye className="h-3 w-3" />
                      Preview
                    </button>
                    <button
                      type="button"
                      onClick={() => setOutputView("code")}
                      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
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
                <div className="rounded-xl border border-border overflow-hidden bg-code-bg">
                  {outputView === "preview" ? (
                    latestCode ? (
                      <iframe
                        title="Agent output preview"
                        sandbox="allow-scripts"
                        srcDoc={latestCode}
                        className="w-full h-[320px] border-0 rounded-none"
                      />
                    ) : (
                      <div className="h-[200px] flex items-center justify-center bg-muted/20 text-sm text-muted">
                        {isActive
                          ? "Output will appear here as the agent generates code…"
                          : "No code generated."}
                      </div>
                    )
                  ) : (
                    <pre className="p-4 overflow-auto max-h-[320px] m-0 text-xs font-mono text-foreground/90 whitespace-pre">
                      <code>{latestCode || "No code yet."}</code>
                    </pre>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Chat (turns) — read-only, same structure as play */}
        <div className="w-1/2 shrink-0 flex flex-col border-l border-border overflow-hidden">
          <div className="border-b border-border px-6 py-3">
            <h2 className="text-sm font-medium text-foreground">Chat</h2>
            <p className="text-xs text-muted">Agent prompts and assistant replies</p>
          </div>
          <div className="flex-1 overflow-y-auto">
            <div className="px-6 py-4">
              {session?.turns?.length ? (
                <div className="space-y-0">
                  {session.turns.map((turn: Turn) => (
                    <div key={turn.turn_number} className="space-y-0">
                      <ChatMessage
                        role="user"
                        content={turn.prompt_text}
                        userLabel="Agent"
                      />
                      <ChatMessage
                        role="assistant"
                        content={turn.response_text}
                        generatedCode={turn.generated_code || undefined}
                        accuracy={turn.accuracy_at_turn}
                        turnNumber={turn.turn_number}
                        tokens={turn.prompt_tokens + turn.response_tokens}
                      />
                    </div>
                  ))}
                  <div ref={turnsEndRef} />
                </div>
              ) : (
                <p className="text-sm text-muted">
                  {isActive
                    ? "Waiting for agent to submit first prompt…"
                    : "No turns yet."}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
