"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getInterviewRoom,
  getInterviewSession,
  listInterviewSessions,
  cancelInterviewSession,
  subscribeInterviewObserver,
} from "@/lib/api";
import type {
  InterviewRoom,
  InterviewSession,
  InterviewTurn,
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
  X,
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

  const [liveSessionId, setLiveSessionId] = useState<string | null>(null);

  // Selected session for full turn history in Live View
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedTurns, setSelectedTurns] = useState<InterviewTurn[]>([]);

  const eventFeedRef = useRef<HTMLDivElement>(null);
  const liveViewRef = useRef<HTMLDivElement>(null);

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
      // Don't log response_chunk events – the response is visible in the live view
      if (ev.type !== "response_chunk") {
        setEvents((prev) => [...prev.slice(-200), ev]); // keep last 200
      }

      switch (ev.type) {
        case "session_started":
          // Refresh sessions
          listInterviewSessions(roomId)
            .then(setSessions)
            .catch(() => {});
          break;
        case "prompt_submitted":
          setLiveSessionId(ev.session_id || null);
          // Auto-select this session if none selected
          setSelectedSessionId((prev) => prev || ev.session_id || null);
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
        case "session_cancelled":
          listInterviewSessions(roomId)
            .then(setSessions)
            .catch(() => {});
          break;
      }
    });

    return () => abort();
  }, [roomId]);

  // (Event feed is newest-first, no auto-scroll needed)

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

  // Sort: Active (top) → Done → Cancelled (bottom), most recent first within each group
  const sortedSessions = [...sessions].sort((a, b) => {
    const statusOrder = (s: string) =>
      s === "active" ? 0 : s === "completed" ? 1 : 2;
    const diff = statusOrder(a.status) - statusOrder(b.status);
    if (diff !== 0) return diff;
    // Most recently active at top: use last turn timestamp, then completed_at, then started_at
    const lastActivity = (s: InterviewSession) => {
      if (s.turns.length > 0) return s.turns[s.turns.length - 1].timestamp;
      return s.completed_at || s.started_at;
    };
    return lastActivity(b) - lastActivity(a);
  });

  // ---- Select session to view full history ----
  const handleSelectSession = async (sessionId: string) => {
    if (selectedSessionId === sessionId) {
      // Deselect
      setSelectedSessionId(null);
      setSelectedTurns([]);
      return;
    }
    setSelectedSessionId(sessionId);
    try {
      const sess = await getInterviewSession(roomId, sessionId);
      setSelectedTurns(sess.turns || []);
    } catch {
      setSelectedTurns([]);
    }
  };

  // When SSE brings in a new turn for the selected session, refresh turns
  useEffect(() => {
    if (!selectedSessionId) return;
    const sess = sessions.find((s) => s.id === selectedSessionId);
    if (!sess) return;
    // Refresh turns when total_turns changes (session polling picks this up)
    getInterviewSession(roomId, selectedSessionId)
      .then((s) => setSelectedTurns(s.turns || []))
      .catch(() => {});
  }, [selectedSessionId, sessions, roomId]);

  // Auto-scroll live view only while streaming
  useEffect(() => {
    if (!isStreaming) return;
    liveViewRef.current?.scrollTo({
      top: liveViewRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [liveResponse, isStreaming]);

  // ---- Cancel session ----
  const [confirmCancelId, setConfirmCancelId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const handleCancelSession = async (sessionId: string) => {
    setCancelling(true);
    try {
      await cancelInterviewSession(roomId, sessionId);
      const s = await listInterviewSessions(roomId);
      setSessions(s);
    } catch {}
    setCancelling(false);
    setConfirmCancelId(null);
  };

  // ---- Resizable sessions column ----
  const [sessionsWidth, setSessionsWidth] = useState(320);
  const sessionsResizeRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const handleSessionsResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      sessionsResizeRef.current = { startX: e.clientX, startWidth: sessionsWidth };
      const onMove = (moveEvent: MouseEvent) => {
        if (!sessionsResizeRef.current) return;
        const delta = moveEvent.clientX - sessionsResizeRef.current.startX;
        const next = sessionsResizeRef.current.startWidth + delta;
        setSessionsWidth(Math.min(600, Math.max(200, next)));
      };
      const onUp = () => {
        sessionsResizeRef.current = null;
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [sessionsWidth]
  );

  // ---- Resizable event log column ----
  const [eventLogWidth, setEventLogWidth] = useState(288);
  const eventLogResizeRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const handleEventLogResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      eventLogResizeRef.current = { startX: e.clientX, startWidth: eventLogWidth };
      const onMove = (moveEvent: MouseEvent) => {
        if (!eventLogResizeRef.current) return;
        // Dragging left = growing the panel (panel is on the right side)
        const delta = eventLogResizeRef.current.startX - moveEvent.clientX;
        const next = eventLogResizeRef.current.startWidth + delta;
        setEventLogWidth(Math.min(600, Math.max(180, next)));
      };
      const onUp = () => {
        eventLogResizeRef.current = null;
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [eventLogWidth]
  );

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
        <div className="flex flex-col shrink-0" style={{ width: sessionsWidth }}>
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
                {sortedSessions.map((session) => {
                  const challenge = room.challenges.find(
                    (c) => c.id === session.challenge_id
                  );
                  const isActive = session.status === "active";
                  const isCancelled = session.status === "cancelled";
                  return (
                    <div
                      key={session.id}
                      onClick={() => handleSelectSession(session.id)}
                      className={`rounded-lg border p-3 cursor-pointer transition-colors ${
                        selectedSessionId === session.id
                          ? "border-accent bg-accent/10 ring-1 ring-accent/30"
                          : isActive
                          ? "border-accent/30 bg-accent/5 hover:bg-accent/10"
                          : isCancelled
                          ? "border-border opacity-50 hover:opacity-70"
                          : "border-border hover:bg-muted/10"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className={`text-sm font-medium ${isCancelled ? "line-through text-muted" : ""}`}>
                          {session.candidate_name}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`text-[10px] uppercase tracking-wider font-medium ${
                              isActive ? "text-accent" : isCancelled ? "text-red-400" : "text-muted"
                            }`}
                          >
                            {isActive ? "Active" : isCancelled ? "Cancelled" : "Done"}
                          </span>
                          {isActive && confirmCancelId !== session.id && (
                            <button
                              onClick={() => setConfirmCancelId(session.id)}
                              className="text-muted hover:text-red-400 transition-colors cursor-pointer p-0.5"
                              title="Cancel session"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Cancel confirmation */}
                      {confirmCancelId === session.id && (
                        <div className="mb-2 rounded-md bg-red-400/10 border border-red-400/20 px-3 py-2">
                          <p className="text-xs text-red-400 mb-2">Cancel this session?</p>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleCancelSession(session.id)}
                              disabled={cancelling}
                              className="text-xs font-medium text-red-400 hover:text-red-300 cursor-pointer disabled:opacity-50"
                            >
                              {cancelling ? "Cancelling…" : "Yes, cancel"}
                            </button>
                            <button
                              onClick={() => setConfirmCancelId(null)}
                              className="text-xs text-muted hover:text-foreground cursor-pointer"
                            >
                              No
                            </button>
                          </div>
                        </div>
                      )}

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

        {/* Resize handle */}
        <div
          onMouseDown={handleSessionsResizeStart}
          className="w-1 cursor-col-resize bg-border hover:bg-accent/40 transition-colors shrink-0"
        />

        {/* Center: Live prompt + response */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <Eye className="h-4 w-4 text-muted" />
            <h3 className="text-sm font-medium">
              {selectedSessionId ? "Session View" : "Live View"}
            </h3>
            {(() => {
              const viewSessionId = selectedSessionId || liveSessionId;
              const viewSession = viewSessionId ? sessions.find((s) => s.id === viewSessionId) : null;
              const viewChallenge = viewSession
                ? room.challenges.find((c) => c.id === viewSession.challenge_id)
                : null;
              return viewSession ? (
                <>
                  <span className="text-xs text-muted">—</span>
                  <span className="text-xs text-foreground font-medium">
                    {viewSession.candidate_name}
                  </span>
                  {viewChallenge && (
                    <span className="text-xs text-muted">
                      · {viewChallenge.title}
                    </span>
                  )}
                  <span className="text-xs text-muted">
                    · {selectedTurns.length} turn{selectedTurns.length !== 1 ? "s" : ""}
                  </span>
                </>
              ) : null;
            })()}
            {isStreaming && liveSessionId === (selectedSessionId || liveSessionId) && (
              <span className="flex items-center gap-1 text-xs text-accent ml-auto">
                <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
                Streaming
              </span>
            )}
          </div>

          <div ref={liveViewRef} className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* No session selected and no live activity */}
            {!selectedSessionId && !livePrompt && !liveResponse && events.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Eye className="h-8 w-8 text-muted/40 mb-3" />
                <p className="text-sm text-muted">
                  Select a session or wait for candidate activity
                </p>
              </div>
            )}

            {/* Full turn history from selected session */}
            {selectedSessionId && selectedTurns.map((turn, i) => (
              <div key={i} className="space-y-3">
                <div>
                  <div className="text-xs text-muted uppercase tracking-wider mb-1">
                    Turn {turn.turn_number} — Prompt
                  </div>
                  <div className="bg-foreground/5 border border-border rounded-lg px-4 py-3 text-sm">
                    {turn.prompt_text}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted uppercase tracking-wider mb-1">
                    Response
                    {turn.accuracy_at_turn > 0 && (
                      <span className="ml-2 text-accent">
                        {Math.round(turn.accuracy_at_turn * 100)}% accuracy
                      </span>
                    )}
                  </div>
                  <div className="text-sm leading-relaxed text-foreground whitespace-pre-wrap break-words">
                    {turn.response_text}
                  </div>
                </div>
                {turn.generated_code && (
                  <div>
                    <div className="text-xs text-muted uppercase tracking-wider mb-1 flex items-center gap-1">
                      <Code className="h-3 w-3" />
                      Generated Code
                    </div>
                    <pre className="rounded-lg border border-border bg-code-bg p-4 text-xs font-mono overflow-x-auto max-h-[200px] overflow-y-auto">
                      <code>{turn.generated_code}</code>
                    </pre>
                  </div>
                )}
                {i < selectedTurns.length - 1 && (
                  <hr className="border-border" />
                )}
              </div>
            ))}

            {/* Live streaming for the selected (or any) session */}
            {liveSessionId === selectedSessionId && livePrompt && (
              <div className="space-y-3">
                {selectedTurns.length > 0 && <hr className="border-border" />}
                <div>
                  <div className="text-xs text-muted uppercase tracking-wider mb-1">
                    Turn {selectedTurns.length + 1} — Prompt
                    {isStreaming && (
                      <span className="ml-2 text-accent text-[10px]">LIVE</span>
                    )}
                  </div>
                  <div className="bg-foreground/5 border border-border rounded-lg px-4 py-3 text-sm">
                    {livePrompt}
                  </div>
                </div>
                {(liveResponse || isStreaming) && (
                  <div>
                    <div className="text-xs text-muted uppercase tracking-wider mb-1">
                      Response
                    </div>
                    <div className="text-sm leading-relaxed text-foreground whitespace-pre-wrap break-words">
                      {liveResponse}
                      {isStreaming && (
                        <span className="inline-block w-0.5 h-4 bg-foreground ml-1 align-middle animate-pulse" />
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Fallback: live view when no session is selected */}
            {!selectedSessionId && livePrompt && (
              <>
                <div>
                  <div className="text-xs text-muted uppercase tracking-wider mb-1">
                    Latest Prompt
                  </div>
                  <div className="bg-foreground/5 border border-border rounded-lg px-4 py-3 text-sm">
                    {livePrompt}
                  </div>
                </div>
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
              </>
            )}
          </div>
        </div>

        {/* Event log resize handle */}
        <div
          onMouseDown={handleEventLogResizeStart}
          className="w-1 cursor-col-resize bg-border hover:bg-accent/40 transition-colors shrink-0"
        />

        {/* Right: Event feed */}
        <div className="flex flex-col shrink-0" style={{ width: eventLogWidth }}>
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
              .slice()
              .reverse()
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
