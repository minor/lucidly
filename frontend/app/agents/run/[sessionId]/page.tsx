"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getSession, getChallenge } from "@/lib/api";
import { ChatMessage } from "@/components/ChatMessage";
import { ScoreBar } from "@/components/ScoreBar";
import type { Challenge, Session, Turn } from "@/lib/types";
import { Loader2, ArrowLeft, Trophy, Code, ImageIcon } from "lucide-react";
import { MODEL_PRICING } from "@/lib/api";

const OUTPUT_PLACEHOLDER_IMAGE =
  "https://placehold.co/800x400/f8fafc/94a3b8?text=Agent+output";
const OUTPUT_PLACEHOLDER_CODE = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8" /><title>Output</title></head>
<body><header>...</header><main>...</main></body>
</html>`;

const POLL_INTERVAL_MS = 1500;

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
  const turnsEndRef = useRef<HTMLDivElement>(null);

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

  // Fetch challenge when session is available
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

  useEffect(() => {
    turnsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.turns?.length]);

  // Calculate elapsed time
  useEffect(() => {
    if (!session?.started_at) return;
    const updateElapsed = () => {
      const elapsedSec = (Date.now() / 1000 - session.started_at);
      setElapsed(Math.max(0, elapsedSec));
    };
    updateElapsed();
    const interval = setInterval(updateElapsed, 1000);
    return () => clearInterval(interval);
  }, [session?.started_at]);

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

  // Calculate total cost from turns
  const totalCost = session?.turns?.reduce((acc, turn) => {
    const model = session.model_used || "claude-3-opus-20240229";
    const pricing = MODEL_PRICING[model] || MODEL_PRICING["claude-3-opus-20240229"];
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
          tokens={session?.total_tokens ?? 0}
          elapsedSec={elapsed}
          accuracy={
            session?.turns?.length
              ? session.turns[session.turns.length - 1].accuracy_at_turn
              : undefined
          }
          compositeScore={session?.composite_score ?? undefined}
          cost={totalCost}
        />
        {isActive && (
          <span className="text-xs text-muted">Watching agent run…</span>
        )}
      </div>

      {/* Main content — left = challenge + output (same as play), right = agent chat */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Challenge description + Your output (same as play page) */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border overflow-hidden">
          {/* Challenge description (scrollable) */}
          <div className="flex-1 min-h-0 overflow-y-auto border-b border-border">
            <div className="p-6">
              <h2 className="text-sm font-semibold mb-3">Challenge</h2>
              <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap mb-4">
                {challenge?.description ?? "Loading challenge…"}
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
                    className="w-full h-[500px] border-0 rounded-lg pointer-events-none"
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
            </div>
          </div>

          {/* Your output panel (same styling as play page) */}
          <div className="shrink-0 h-[240px] flex flex-col border-t border-border bg-muted/5">
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

        {/* Right: Agent chat (turns) + final score when completed */}
        <div className="flex flex-col w-[480px] shrink-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6">
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
          {session?.status === "completed" && (
            <div className="shrink-0 border-t border-border p-4 bg-muted/5">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
                Final score
              </h2>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                <div>
                  <span className="text-muted">Composite </span>
                  <span className="font-mono font-semibold text-accent">
                    {session.composite_score ?? "—"}
                  </span>
                </div>
                <div>
                  <span className="text-muted">Accuracy </span>
                  <span className="font-mono">{session.accuracy_score ?? "—"}</span>
                </div>
                <div>
                  <span className="text-muted">Turns </span>
                  <span className="font-mono">{session.total_turns}</span>
                </div>
                <div>
                  <span className="text-muted">Tokens </span>
                  <span className="font-mono">{session.total_tokens}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
