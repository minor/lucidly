"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getSession } from "@/lib/api";
import { ChatMessage } from "@/components/ChatMessage";
import { ScoreBar } from "@/components/ScoreBar";
import type { Challenge, Session, Turn } from "@/lib/types";
import { Loader2, ArrowLeft, Trophy, Code, ImageIcon, Eye } from "lucide-react";
import { MODEL_PRICING } from "@/lib/api";

const POLL_INTERVAL_MS = 1500;

export default function AgentRunWatchPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<Session | null>(null);
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

      {/* Main content — same two-column layout as play: left = challenge + output, right = chat */}
      <div className="flex flex-1 min-h-0">
        {/* Left: turns + output */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border overflow-hidden">
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
          {/* Output panel */}
          {latestCode && (
            <div className="border-t border-border p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-muted">
                  Generated output
                </span>
                <div className="inline-flex rounded-lg border border-border bg-muted/30 p-0.5">
                  <button
                    type="button"
                    onClick={() => setOutputView("preview")}
                    className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium ${
                      outputView === "preview"
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted hover:text-foreground"
                    }`}
                  >
                    <ImageIcon className="h-3.5 w-3.5" />
                    Preview
                  </button>
                  <button
                    type="button"
                    onClick={() => setOutputView("code")}
                    className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium ${
                      outputView === "code"
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted hover:text-foreground"
                    }`}
                  >
                    <Code className="h-3.5 w-3.5" />
                    Code
                  </button>
                </div>
              </div>
              <div className="rounded-xl border border-border overflow-hidden bg-code-bg">
                {outputView === "preview" ? (
                  <div className="min-h-[160px] bg-muted/20">
                    <iframe
                      title="Preview"
                      sandbox="allow-scripts"
                      srcDoc={latestCode}
                      className="w-full h-[240px] border-0 rounded-none"
                    />
                  </div>
                ) : (
                  <pre className="p-4 overflow-auto max-h-[240px] m-0 text-xs font-mono text-foreground/90 whitespace-pre">
                    <code>{latestCode}</code>
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>
        {/* Right: score when completed */}
        {session?.status === "completed" && (
          <div className="w-72 shrink-0 border-l border-border p-6">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">
              Final score
            </h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted">Composite</span>
                <span className="font-mono font-semibold text-accent">
                  {session.composite_score ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Accuracy</span>
                <span className="font-mono">{session.accuracy_score ?? "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Turns</span>
                <span className="font-mono">{session.total_turns}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Tokens</span>
                <span className="font-mono">{session.total_tokens}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
