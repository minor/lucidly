"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getInterviewReport } from "@/lib/api";
import type { InterviewReport, InterviewSessionReport } from "@/lib/types";
import {
  Loader2,
  ArrowLeft,
  FileText,
  Clock,
  Coins,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Code,
  User,
  Zap,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function InterviewReportPage() {
  const params = useParams();
  const router = useRouter();
  const roomId = params.roomId as string;

  const [report, setReport] = useState<InterviewReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(
    new Set()
  );

  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const r = await getInterviewReport(roomId);
        if (ignore) return;
        setReport(r);
        // Expand all sessions by default
        setExpandedSessions(
          new Set(r.sessions.map((s: InterviewSessionReport) => s.session.id))
        );
      } catch (err) {
        if (!ignore) setError((err as Error).message);
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    init();
    return () => {
      ignore = true;
    };
  }, [roomId]);

  const toggleSession = (sessionId: string) => {
    setExpandedSessions((prev) => {
      const next = new Set(prev);
      if (next.has(sessionId)) {
        next.delete(sessionId);
      } else {
        next.add(sessionId);
      }
      return next;
    });
  };

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-red-400">{error || "Report not found"}</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/interview/observe/${roomId}`)}
            className="text-muted hover:text-foreground transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-accent" />
              <h1 className="text-sm font-semibold">Assessment Report</h1>
            </div>
            <p className="text-xs text-muted">{report.room.title}</p>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-6 py-8 space-y-8">
          {/* Summary card */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-lg font-semibold mb-4">Interview Summary</h2>
            <div className="grid grid-cols-4 gap-4">
              <div className="rounded-lg bg-muted/10 p-4 text-center">
                <div className="text-2xl font-bold font-mono">
                  {report.sessions.length}
                </div>
                <div className="text-xs text-muted mt-1">Sessions</div>
              </div>
              <div className="rounded-lg bg-muted/10 p-4 text-center">
                <div className="text-2xl font-bold font-mono">
                  {report.room.challenges.length}
                </div>
                <div className="text-xs text-muted mt-1">Challenges</div>
              </div>
              <div className="rounded-lg bg-muted/10 p-4 text-center">
                <div className="text-2xl font-bold font-mono">
                  {report.sessions.filter(
                    (s) => s.session.status === "completed"
                  ).length}
                </div>
                <div className="text-xs text-muted mt-1">Completed</div>
              </div>
              <div className="rounded-lg bg-muted/10 p-4 text-center">
                <div className="text-2xl font-bold font-mono text-accent">
                  {report.sessions.length > 0
                    ? Math.round(
                        report.sessions.reduce(
                          (sum, s) => sum + s.metrics.composite_score,
                          0
                        ) / report.sessions.length
                      )
                    : 0}
                </div>
                <div className="text-xs text-muted mt-1">Avg Score</div>
              </div>
            </div>
          </div>

          {/* Session reports */}
          {report.sessions.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-muted">
                No sessions have been completed yet.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {report.sessions.map((sessionReport) => {
                const { session, challenge_title, challenge_category, elapsed_sec, metrics, turns } = sessionReport;
                const isExpanded = expandedSessions.has(session.id);

                return (
                  <div
                    key={session.id}
                    className="rounded-xl border border-border bg-card overflow-hidden"
                  >
                    {/* Session header */}
                    <button
                      onClick={() => toggleSession(session.id)}
                      className="w-full flex items-center justify-between px-6 py-4 hover:bg-muted/5 transition-colors cursor-pointer"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-muted" />
                          <span className="text-sm font-semibold">
                            {session.candidate_name}
                          </span>
                        </div>
                        <span className="text-xs text-muted">
                          {challenge_title}
                        </span>
                        <span
                          className={`text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full ${
                            session.status === "completed"
                              ? "bg-green-500/10 text-green-500"
                              : "bg-accent/10 text-accent"
                          }`}
                        >
                          {session.status}
                        </span>
                      </div>

                      <div className="flex items-center gap-6">
                        {/* Quick metrics */}
                        <div className="flex items-center gap-4 text-xs text-muted">
                          <span className="flex items-center gap-1">
                            <Zap className="h-3 w-3" />
                            {metrics.composite_score}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatTime(elapsed_sec)}
                          </span>
                          <span className="flex items-center gap-1">
                            <RefreshCw className="h-3 w-3" />
                            {metrics.total_turns}
                          </span>
                          <span className="flex items-center gap-1">
                            <Coins className="h-3 w-3" />
                            {metrics.total_tokens.toLocaleString()}
                          </span>
                        </div>
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-muted" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-muted" />
                        )}
                      </div>
                    </button>

                    {/* Expanded content */}
                    {isExpanded && (
                      <div className="border-t border-border">
                        {/* Metrics bar */}
                        <div className="px-6 py-4 border-b border-border bg-muted/5">
                          <div className="grid grid-cols-5 gap-4">
                            <div>
                              <div className="text-xs text-muted mb-1">
                                Score
                              </div>
                              <div className="text-lg font-bold font-mono">
                                {metrics.composite_score}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1">
                                Accuracy
                              </div>
                              <div className="text-lg font-bold font-mono">
                                {Math.round(metrics.accuracy * 100)}%
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1">
                                Time
                              </div>
                              <div className="text-lg font-bold font-mono">
                                {formatTime(elapsed_sec)}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1">
                                Turns
                              </div>
                              <div className="text-lg font-bold font-mono">
                                {metrics.total_turns}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1">
                                Tokens
                              </div>
                              <div className="text-lg font-bold font-mono">
                                {metrics.total_tokens.toLocaleString()}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Turn-by-turn replay */}
                        <div className="px-6 py-4">
                          <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-4">
                            Turn-by-Turn Replay
                          </h4>
                          <div className="space-y-4">
                            {turns.map((turn, i) => (
                              <div
                                key={i}
                                className="space-y-2"
                              >
                                <div className="flex items-center gap-2 text-xs text-muted">
                                  <span className="font-mono font-medium">
                                    Turn {turn.turn_number}
                                  </span>
                                  <span>·</span>
                                  <span>
                                    {turn.prompt_tokens + turn.response_tokens}{" "}
                                    tokens
                                  </span>
                                </div>

                                {/* User prompt */}
                                <div className="bg-foreground/5 border border-border rounded-lg px-4 py-3 text-sm">
                                  <div className="text-xs text-muted mb-1 font-medium">
                                    Candidate
                                  </div>
                                  <div className="whitespace-pre-wrap break-words">
                                    {turn.prompt_text}
                                  </div>
                                </div>

                                {/* AI response */}
                                <div className="text-sm pl-4 border-l-2 border-border">
                                  <div className="text-xs text-muted mb-1 font-medium">
                                    AI Response
                                  </div>
                                  <div className="whitespace-pre-wrap break-words text-foreground/80 max-h-[200px] overflow-y-auto">
                                    {turn.response_text.slice(0, 500)}
                                    {turn.response_text.length > 500 && "…"}
                                  </div>
                                </div>

                                {/* Generated code */}
                                {turn.generated_code && (
                                  <div>
                                    <div className="flex items-center gap-1 text-xs text-muted mb-1">
                                      <Code className="h-3 w-3" />
                                      Generated Code
                                    </div>
                                    <pre className="rounded-lg border border-border bg-code-bg p-3 text-xs font-mono overflow-x-auto max-h-[150px] overflow-y-auto">
                                      <code>
                                        {turn.generated_code.slice(0, 800)}
                                        {turn.generated_code.length > 800 &&
                                          "\n// ... truncated"}
                                      </code>
                                    </pre>
                                  </div>
                                )}

                                {i < turns.length - 1 && (
                                  <div className="border-b border-border" />
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
