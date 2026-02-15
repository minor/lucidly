"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getInterviewRoom,
  listInterviewSessions,
  subscribeInterviewObserver,
} from "@/lib/api";
import type {
  InterviewRoom,
  InterviewSession,
} from "@/lib/types";
import {
  Loader2,
  ArrowLeft,
  Eye,
  Users,
  Clock,
  Copy,
  Check,
  FileText,
  Radio,
  Code,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types for live event tracking
// ---------------------------------------------------------------------------

interface LiveEvent {
  type: string;
  session_id?: string;
  candidate_name?: string;
  challenge_id?: string;
  prompt?: string;
  chunk?: string;
  turn_number?: number;
  generated_code?: string;
  total_tokens?: number;
  total_turns?: number;
  passed_count?: number;
  total_count?: number;
  scores?: Record<string, number>;
  timestamp?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ObserveDashboardPage() {
  const params = useParams();
  const router = useRouter();
  const roomId = params.roomId as string;

  const [room, setRoom] = useState<InterviewRoom | null>(null);
  const [sessions, setSessions] = useState<InterviewSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Live event feed
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [livePrompt, setLivePrompt] = useState<string | null>(null);
  const [liveCode, setLiveCode] = useState<string | null>(null);
  const [liveResponse, setLiveResponse] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [liveMetrics, setLiveMetrics] = useState<{
    total_tokens: number;
    total_turns: number;
  }>({ total_tokens: 0, total_turns: 0 });
  const [testResults, setTestResults] = useState<{
    passed_count: number;
    total_count: number;
  } | null>(null);

  const eventFeedRef = useRef<HTMLDivElement>(null);

  // ---- Fetch room and sessions ----
  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const [r, s] = await Promise.all([
          getInterviewRoom(roomId),
          listInterviewSessions(roomId),
        ]);
        if (ignore) return;
        setRoom(r);
        setSessions(s);
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

  // Poll sessions periodically
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const s = await listInterviewSessions(roomId);
        setSessions(s);
      } catch {}
    }, 5000);
    return () => clearInterval(interval);
  }, [roomId]);

  // ---- Subscribe to live events ----
  useEffect(() => {
    const abort = subscribeInterviewObserver(roomId, (event) => {
      const ev = event as unknown as LiveEvent;
      setEvents((prev) => [...prev.slice(-200), ev]); // keep last 200

      switch (ev.type) {
        case "session_started":
          // Refresh sessions
          listInterviewSessions(roomId)
            .then(setSessions)
            .catch(() => {});
          break;
        case "prompt_submitted":
          setLivePrompt(ev.prompt || null);
          setLiveResponse("");
          setIsStreaming(true);
          break;
        case "response_chunk":
          setLiveResponse((prev) => prev + (ev.chunk || ""));
          break;
        case "turn_complete":
          setLiveCode(ev.generated_code || null);
          setLiveMetrics({
            total_tokens: ev.total_tokens || 0,
            total_turns: ev.total_turns || 0,
          });
          setIsStreaming(false);
          break;
        case "test_results":
          setTestResults({
            passed_count: ev.passed_count || 0,
            total_count: ev.total_count || 0,
          });
          break;
        case "session_completed":
          listInterviewSessions(roomId)
            .then(setSessions)
            .catch(() => {});
          break;
      }
    });

    return () => abort();
  }, [roomId]);

  // Auto-scroll event feed
  useEffect(() => {
    eventFeedRef.current?.scrollTo({
      top: eventFeedRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [events]);

  const inviteUrl =
    typeof window !== "undefined" && room
      ? `${window.location.origin}/interview/${room.invite_code}`
      : "";

  const copyInviteLink = () => {
    navigator.clipboard.writeText(inviteUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeSessions = sessions.filter((s) => s.status === "active");
  const completedSessions = sessions.filter((s) => s.status === "completed");

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  if (error || !room) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-red-400">{error || "Room not found"}</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/interview/create")}
            className="text-muted hover:text-foreground transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold">{room.title}</h1>
              <div className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent">
                <Radio className="h-3 w-3" />
                Live
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted">
              {room.company_name && <span>{room.company_name}</span>}
              <span>·</span>
              <span>
                {room.challenges.length} challenge
                {room.challenges.length !== 1 ? "s" : ""}
              </span>
              <span>·</span>
              <span>{sessions.length} session{sessions.length !== 1 ? "s" : ""}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={copyInviteLink}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted hover:text-foreground hover:border-accent transition-colors cursor-pointer"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                Copy Invite
              </>
            )}
          </button>
          <button
            onClick={() => router.push(`/interview/report/${roomId}`)}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted hover:text-foreground hover:border-accent transition-colors cursor-pointer"
          >
            <FileText className="h-3.5 w-3.5" />
            Report
          </button>
        </div>
      </header>

      {/* Main grid */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Sessions + Metrics */}
        <div className="w-80 border-r border-border flex flex-col shrink-0">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">
              Sessions
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto">
            {sessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full px-4 text-center">
                <Users className="h-8 w-8 text-muted/40 mb-3" />
                <p className="text-sm text-muted mb-1">
                  Waiting for candidates
                </p>
                <p className="text-xs text-muted/60">
                  Share the invite link to get started
                </p>
              </div>
            ) : (
              <div className="p-3 space-y-2">
                {sessions.map((session) => {
                  const challenge = room.challenges.find(
                    (c) => c.id === session.challenge_id
                  );
                  const isActive = session.status === "active";
                  return (
                    <div
                      key={session.id}
                      className={`rounded-lg border p-3 ${
                        isActive
                          ? "border-accent/30 bg-accent/5"
                          : "border-border"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">
                          {session.candidate_name}
                        </span>
                        <span
                          className={`text-[10px] uppercase tracking-wider font-medium ${
                            isActive ? "text-accent" : "text-muted"
                          }`}
                        >
                          {isActive ? "Active" : "Done"}
                        </span>
                      </div>
                      <div className="text-xs text-muted space-y-0.5">
                        <div>
                          Challenge: {challenge?.title || "Unknown"}
                        </div>
                        <div>Turns: {session.total_turns}</div>
                        <div>
                          Tokens: {session.total_tokens.toLocaleString()}
                        </div>
                        {session.status === "completed" && (
                          <div className="font-medium text-foreground">
                            Score: {session.composite_score}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Live metrics */}
          {activeSessions.length > 0 && (
            <div className="border-t border-border px-4 py-3">
              <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                Live Metrics
              </h3>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-muted/10 px-3 py-2">
                  <div className="font-mono font-semibold">
                    {liveMetrics.total_turns}
                  </div>
                  <div className="text-muted">Turns</div>
                </div>
                <div className="rounded-lg bg-muted/10 px-3 py-2">
                  <div className="font-mono font-semibold">
                    {liveMetrics.total_tokens.toLocaleString()}
                  </div>
                  <div className="text-muted">Tokens</div>
                </div>
                {testResults && (
                  <div
                    className={`rounded-lg px-3 py-2 col-span-2 ${
                      testResults.passed_count === testResults.total_count
                        ? "bg-green-500/10"
                        : "bg-red-400/10"
                    }`}
                  >
                    <div className="font-mono font-semibold">
                      {testResults.passed_count}/{testResults.total_count}{" "}
                      tests passed
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Center: Live prompt + response */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <Eye className="h-4 w-4 text-muted" />
            <h3 className="text-sm font-medium">Live View</h3>
            {isStreaming && (
              <span className="flex items-center gap-1 text-xs text-accent">
                <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
                Streaming
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {!livePrompt && !liveResponse && events.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Eye className="h-8 w-8 text-muted/40 mb-3" />
                <p className="text-sm text-muted">
                  Candidate activity will appear here in real-time
                </p>
              </div>
            )}

            {livePrompt && (
              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-1">
                  Latest Prompt
                </div>
                <div className="bg-foreground/5 border border-border rounded-lg px-4 py-3 text-sm">
                  {livePrompt}
                </div>
              </div>
            )}

            {(liveResponse || isStreaming) && (
              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-1">
                  AI Response
                </div>
                <div className="text-sm leading-relaxed text-foreground whitespace-pre-wrap break-words">
                  {liveResponse}
                  {isStreaming && (
                    <span className="inline-block w-0.5 h-4 bg-foreground ml-1 align-middle animate-pulse" />
                  )}
                </div>
              </div>
            )}

            {liveCode && (
              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-1 flex items-center gap-1">
                  <Code className="h-3 w-3" />
                  Generated Code
                </div>
                <pre className="rounded-lg border border-border bg-code-bg p-4 text-xs font-mono overflow-x-auto max-h-[300px] overflow-y-auto">
                  <code>{liveCode}</code>
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* Right: Event feed */}
        <div className="w-72 border-l border-border flex flex-col shrink-0">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">
              Event Log
            </h3>
          </div>

          <div
            ref={eventFeedRef}
            className="flex-1 overflow-y-auto p-3 space-y-1.5"
          >
            {events
              .filter((e) => e.type !== "ping")
              .map((ev, i) => (
                <div
                  key={i}
                  className="rounded-md bg-muted/10 px-3 py-2 text-xs"
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="font-medium text-foreground capitalize">
                      {ev.type.replace(/_/g, " ")}
                    </span>
                    {ev.timestamp && (
                      <span className="text-muted font-mono">
                        {new Date(ev.timestamp * 1000).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                  {ev.candidate_name && (
                    <div className="text-muted">
                      Candidate: {ev.candidate_name}
                    </div>
                  )}
                  {ev.prompt && (
                    <div className="text-muted truncate">
                      &quot;{ev.prompt.slice(0, 80)}
                      {(ev.prompt?.length ?? 0) > 80 ? "…" : ""}&quot;
                    </div>
                  )}
                  {ev.total_turns !== undefined && (
                    <div className="text-muted">
                      Turn {ev.total_turns} · {ev.total_tokens?.toLocaleString()} tokens
                    </div>
                  )}
                  {ev.passed_count !== undefined && (
                    <div className="text-muted">
                      Tests: {ev.passed_count}/{ev.total_count}
                    </div>
                  )}
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
