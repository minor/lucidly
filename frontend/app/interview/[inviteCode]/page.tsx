"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  getInterviewRoomByInvite,
  startInterviewSession,
  streamInterviewPrompt,
  completeInterviewSession,
  createVercelSandbox,
  updateVercelSandboxCode,
  stopVercelSandbox,
} from "@/lib/api";
import { PromptInput } from "@/components/PromptInput";
import { ScoreBar } from "@/components/ScoreBar";
import { SimpleMarkdown } from "@/components/SimpleMarkdown";
import { extractRenderableUI, extractPythonCode } from "@/lib/codeExtract";
import type {
  InterviewRoom,
  InterviewSession,
  InterviewChallenge,
} from "@/lib/types";
import type { ChatMessage } from "@/lib/api";
import {
  Loader2,
  Sparkles,
  Clock,
  Eye,
  Code,
  GripHorizontal,
  Trophy,
  AlertTriangle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CandidateInterviewPage() {
  const params = useParams();
  const inviteCode = params.inviteCode as string;

  // Room & session state
  const [room, setRoom] = useState<InterviewRoom | null>(null);
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [activeChallenge, setActiveChallenge] =
    useState<InterviewChallenge | null>(null);
  const [activeChallengeIdx, setActiveChallengeIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Join form
  const [candidateName, setCandidateName] = useState("");
  const [joined, setJoined] = useState(false);
  const [joining, setJoining] = useState(false);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Metrics
  const startTimeRef = useRef<number>(Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [totalTurns, setTotalTurns] = useState(0);
  const [totalTokens, setTotalTokens] = useState(0);
  const [totalCost, setTotalCost] = useState(0);
  const [estimatedTokens, setEstimatedTokens] = useState(0);

  // Model
  const [selectedModel, setSelectedModel] = useState("gpt-5.2");

  // Output panel
  const OUTPUT_PANEL_MIN = 120;
  const OUTPUT_PANEL_INITIAL = 220;
  const [outputPanelHeight, setOutputPanelHeight] = useState(OUTPUT_PANEL_INITIAL);
  const resizeStartYRef = useRef<number>(0);
  const resizeStartHeightRef = useRef<number>(OUTPUT_PANEL_INITIAL);

  // UI preview
  const [renderedCode, setRenderedCode] = useState("");
  const [previewTab, setPreviewTab] = useState<"preview" | "code">("preview");
  const [vercelSandboxId, setVercelSandboxId] = useState<string | null>(null);
  const [vercelPreviewUrl, setVercelPreviewUrl] = useState<string | null>(null);
  const [vercelSandboxReady, setVercelSandboxReady] = useState(false);
  const vercelSandboxIdRef = useRef<string | null>(null);
  const [iframeKey, setIframeKey] = useState(0);

  // Test results (for coding challenges — shown if interviewer allows)
  const [latestCode, setLatestCode] = useState("");

  // Submission
  const [submitState, setSubmitState] = useState<"idle" | "pending" | "completed">("idle");
  const [finalScores, setFinalScores] = useState<{ composite_score: number } | null>(null);

  // Timer expired
  const [timeExpired, setTimeExpired] = useState(false);

  // Abort
  const abortControllerRef = useRef<AbortController | null>(null);

  // ---- Fetch room ----
  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const r = await getInterviewRoomByInvite(inviteCode);
        if (ignore) return;
        setRoom(r);
        if (r.challenges.length > 0) {
          setActiveChallenge(r.challenges[0]);
        }
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
  }, [inviteCode]);

  // ---- Timer ----
  useEffect(() => {
    if (!joined || submitState !== "idle") return;
    const interval = setInterval(() => {
      const now = Date.now();
      const sec = (now - startTimeRef.current) / 1000;
      setElapsed(sec);

      // Check time limit
      if (room?.config.time_limit_minutes) {
        const limitSec = room.config.time_limit_minutes * 60;
        if (sec >= limitSec) {
          setTimeExpired(true);
          clearInterval(interval);
        }
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [joined, submitState, room]);

  // ---- Auto-scroll chat ----
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStreamingMessage]);

  // ---- Vercel Sandbox for frontend challenges ----
  // DISABLED: using plain srcDoc HTML rendering instead. Re-enable these
  // useEffects to restore Vercel Sandbox.
  // useEffect(() => {
  //   if (!activeChallenge || activeChallenge.category !== "frontend") return;
  //
  //   let ignore = false;
  //   async function initSandbox() {
  //     try {
  //       const { sandboxId, previewUrl } = await createVercelSandbox();
  //       if (ignore) return;
  //       setVercelSandboxId(sandboxId);
  //       setVercelPreviewUrl(previewUrl);
  //       setVercelSandboxReady(true);
  //       vercelSandboxIdRef.current = sandboxId;
  //     } catch {
  //       // fallback to srcDoc
  //     }
  //   }
  //   initSandbox();
  //   return () => {
  //     ignore = true;
  //     if (vercelSandboxIdRef.current) {
  //       stopVercelSandbox(vercelSandboxIdRef.current).catch(() => {});
  //       vercelSandboxIdRef.current = null;
  //     }
  //   };
  // }, [activeChallenge]);

  // Push code to sandbox (disabled — srcDoc rendering handles updates)
  // useEffect(() => {
  //   if (!renderedCode || !vercelSandboxId || !vercelSandboxReady) return;
  //   updateVercelSandboxCode(vercelSandboxId, renderedCode)
  //     .then(() => setIframeKey((k) => k + 1))
  //     .catch(() => {});
  // }, [renderedCode, vercelSandboxId, vercelSandboxReady]);

  // ---- Extract code from latest assistant message ----
  useEffect(() => {
    if (isStreaming) return;
    const assistantMessages = messages.filter((m) => m.role === "assistant");
    if (assistantMessages.length === 0) return;
    const latest = assistantMessages[assistantMessages.length - 1];

    if (activeChallenge?.category === "frontend") {
      const extracted = extractRenderableUI(latest.content);
      if (extracted) setRenderedCode(extracted.html);
    } else if (activeChallenge?.category === "coding") {
      const code = extractPythonCode(latest.content);
      if (code) setLatestCode(code);
    }
  }, [messages, isStreaming, activeChallenge]);

  // ---- Resize handler ----
  const handleResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      resizeStartYRef.current = e.clientY;
      resizeStartHeightRef.current = outputPanelHeight;
      const onMove = (moveEvent: MouseEvent) => {
        const delta = resizeStartYRef.current - moveEvent.clientY;
        const next = resizeStartHeightRef.current + delta;
        const max =
          typeof window !== "undefined"
            ? Math.max(400, window.innerHeight * 0.7)
            : 600;
        setOutputPanelHeight(Math.min(max, Math.max(OUTPUT_PANEL_MIN, next)));
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [outputPanelHeight]
  );

  // ---- Join ----
  const handleJoin = async () => {
    if (!candidateName.trim() || !room || !activeChallenge) return;
    setJoining(true);
    try {
      const sess = await startInterviewSession(room.id, {
        candidate_name: candidateName,
        challenge_id: activeChallenge.id,
      });
      setSession(sess);
      setJoined(true);
      startTimeRef.current = Date.now();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setJoining(false);
    }
  };

  // ---- Submit prompt ----
  const handleSubmit = async (prompt: string, model: string) => {
    if (!prompt.trim() || isStreaming || !session || !room || submitState !== "idle") return;
    if (timeExpired) return;
    setSelectedModel(model);

    const userMessage: ChatMessage = { role: "user", content: prompt };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsStreaming(true);
    setCurrentStreamingMessage("");
    setTotalTurns((t) => t + 1);

    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    await streamInterviewPrompt(
      room.id,
      session.id,
      prompt,
      model,
      (chunk) => {
        setCurrentStreamingMessage((prev) => prev + chunk);
        setEstimatedTokens((prev) => prev + chunk.length / 4);
      },
      (data) => {
        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: data.content,
        };
        setMessages([...updatedMessages, assistantMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
        setTotalTokens(data.total_tokens || 0);
        setTotalTurns(data.total_turns || 0);
        if (data.cost) setTotalCost((c) => c + data.cost);
        setEstimatedTokens(0);
        abortControllerRef.current = null;
      },
      (err) => {
        if (err === "AbortError") return;
        const errorMessage: ChatMessage = {
          role: "assistant",
          content: `Error: ${err}`,
        };
        setMessages([...updatedMessages, errorMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
        setEstimatedTokens(0);
        abortControllerRef.current = null;
      },
      abortControllerRef.current?.signal
    );
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  };

  // ---- Submit solution ----
  const handleSubmitSolution = async () => {
    if (submitState !== "idle" || !session || !room) return;
    setSubmitState("pending");
    try {
      const result = await completeInterviewSession(room.id, session.id);
      setFinalScores(result.scores);
      setSubmitState("completed");
    } catch {
      setSubmitState("idle");
    }
  };

  // ---- Switch challenge ----
  const handleSwitchChallenge = async (idx: number) => {
    if (!room || idx === activeChallengeIdx) return;
    const ch = room.challenges[idx];
    setActiveChallengeIdx(idx);
    setActiveChallenge(ch);
    setMessages([]);
    setRenderedCode("");
    setLatestCode("");
    setCurrentStreamingMessage("");
    setSubmitState("idle");
    setFinalScores(null);

    // Start a new session for the new challenge
    if (joined && candidateName) {
      try {
        const sess = await startInterviewSession(room.id, {
          candidate_name: candidateName,
          challenge_id: ch.id,
        });
        setSession(sess);
      } catch {}
    }
  };

  // ---- Derived ----
  const isFrontend = activeChallenge?.category === "frontend";
  const isCoding = activeChallenge?.category === "coding";
  const hasOutput = isFrontend || (isCoding && latestCode);
  const timeLimitSec = (room?.config.time_limit_minutes ?? 45) * 60;
  const timeRemaining = Math.max(0, timeLimitSec - elapsed);

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  // ---- Loading / Error ----
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
        <div className="text-center">
          <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-3" />
          <h2 className="text-lg font-semibold mb-1">
            {error || "Interview not found"}
          </h2>
          <p className="text-sm text-muted">
            Check that the invite link is correct.
          </p>
        </div>
      </div>
    );
  }

  // ---- Join screen ----
  if (!joined) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md rounded-2xl border border-border bg-card p-10 shadow-lg text-center">
          <div className="mb-6">
            <h1 className="text-2xl font-bold mb-1">{room.title}</h1>
            {room.company_name && (
              <p className="text-sm text-muted">{room.company_name}</p>
            )}
          </div>

          <div className="mb-6 text-left space-y-2">
            <div className="flex items-center gap-2 text-sm text-muted">
              <Clock className="h-4 w-4" />
              <span>
                Time limit: {room.config.time_limit_minutes} minutes
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted">
              <Code className="h-4 w-4" />
              <span>
                {room.challenges.length} challenge
                {room.challenges.length !== 1 ? "s" : ""}
              </span>
            </div>
          </div>

          <div className="space-y-3">
            <input
              type="text"
              value={candidateName}
              onChange={(e) => setCandidateName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleJoin()}
              placeholder="Enter your name"
              className="w-full rounded-lg border border-input-border bg-input px-4 py-2.5 text-sm focus:border-accent focus:outline-none text-center"
            />
            <button
              onClick={handleJoin}
              disabled={!candidateName.trim() || joining}
              className="w-full rounded-lg bg-foreground px-4 py-2.5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              {joining ? "Joining…" : "Start Interview"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---- Main interview UI ----
  return (
    <div className="flex h-screen flex-col relative">
      {/* Completion overlay */}
      {submitState === "completed" && finalScores && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/95 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl border border-border bg-card p-10 shadow-2xl text-center">
            <div className="mb-6 flex justify-center">
              <div className="rounded-full bg-accent/10 p-4">
                <Trophy className="h-10 w-10 text-accent" />
              </div>
            </div>
            <h2 className="text-2xl font-bold mb-2">Submitted!</h2>
            <p className="text-sm text-muted mb-6">
              Your interview has been submitted. The interviewer will review
              your performance.
            </p>
            <div className="text-4xl font-black font-mono mb-1">
              {finalScores.composite_score}
            </div>
            <div className="text-xs text-muted uppercase tracking-widest mb-6">
              Score
            </div>
            <ScoreBar
              turns={totalTurns}
              tokens={totalTokens}
              elapsedSec={elapsed}
              cost={totalCost}
            />
          </div>
        </div>
      )}

      {/* Time expired overlay */}
      {timeExpired && submitState === "idle" && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-background/90 backdrop-blur-sm">
          <div className="text-center">
            <AlertTriangle className="h-10 w-10 text-red-400 mx-auto mb-3" />
            <h2 className="text-xl font-bold mb-2">Time&apos;s Up</h2>
            <p className="text-sm text-muted mb-4">
              The time limit has been reached.
            </p>
            <button
              onClick={handleSubmitSolution}
              className="rounded-lg bg-foreground px-6 py-2.5 text-sm font-medium text-background hover:opacity-90 cursor-pointer"
            >
              Submit Solution
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-sm font-semibold">{room.title}</h1>
            <div className="flex items-center gap-2 text-xs text-muted">
              {room.company_name && <span>{room.company_name}</span>}
              {room.company_name && <span>·</span>}
              <span>{candidateName}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Time remaining */}
          <div
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-mono ${
              timeRemaining < 300
                ? "border-red-400/30 text-red-400"
                : "border-border text-foreground"
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            {formatTime(timeRemaining)}
          </div>
        </div>
      </header>

      {/* Stats bar */}
      <div className="flex items-center justify-between gap-4 border-b border-border px-6 py-2">
        <ScoreBar
          turns={totalTurns}
          tokens={totalTokens}
          elapsedSec={elapsed}
          cost={totalCost}
        />
        <button
          type="button"
          onClick={handleSubmitSolution}
          disabled={
            submitState !== "idle" ||
            isStreaming ||
            (!renderedCode && !latestCode && messages.length === 0)
          }
          className={`shrink-0 rounded-lg bg-foreground text-background px-4 py-2 text-xs font-medium transition-opacity ${
            submitState !== "idle" ||
            isStreaming ||
            (!renderedCode && !latestCode && messages.length === 0)
              ? "opacity-50 cursor-not-allowed"
              : "hover:opacity-90 cursor-pointer"
          }`}
        >
          {submitState === "pending"
            ? "Submitting…"
            : submitState === "completed"
            ? "Submitted"
            : "Submit Solution"}
        </button>
      </div>

      {/* Challenge tabs (if multiple) */}
      {room.challenges.length > 1 && (
        <div className="flex items-center gap-2 border-b border-border px-6 py-2 overflow-x-auto">
          {room.challenges.map((ch, i) => (
            <button
              key={ch.id}
              onClick={() => handleSwitchChallenge(i)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                i === activeChallengeIdx
                  ? "border-accent bg-accent/10 text-foreground"
                  : "border-border text-muted hover:text-foreground"
              }`}
            >
              Q{i + 1}: {ch.title}
            </button>
          ))}
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Challenge + Output */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border">
          <div
            className={`${
              hasOutput ? "min-h-0 flex-1" : "flex-1"
            } overflow-y-auto border-b border-border flex flex-col min-h-0`}
          >
            <div className="p-6 flex-1 min-h-0">
              <h2 className="text-sm font-semibold mb-3">
                {activeChallenge?.title}
              </h2>
              <SimpleMarkdown
                content={activeChallenge?.description || ""}
                className="text-sm leading-relaxed mb-4"
              />

              {activeChallenge?.starter_code && (
                <div className="rounded-lg border border-border bg-code-bg overflow-hidden mb-4">
                  <div className="px-3 py-1.5 border-b border-border">
                    <span className="text-xs font-medium text-muted">
                      Starter Code
                    </span>
                  </div>
                  <pre className="p-3 overflow-x-auto">
                    <code className="text-xs font-mono">
                      {activeChallenge.starter_code}
                    </code>
                  </pre>
                </div>
              )}

              {/* Show test cases if interviewer allows */}
              {activeChallenge?.category === "coding" &&
                room.config.show_test_results_to_candidate &&
                activeChallenge.test_cases &&
                activeChallenge.test_cases.length > 0 && (
                  <div className="mt-4">
                    <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                      Test Cases
                    </h3>
                    <div className="space-y-1.5">
                      {activeChallenge.test_cases.map((tc, i) => (
                        <div
                          key={i}
                          className="rounded-lg bg-code-bg px-3 py-2 text-xs font-mono"
                        >
                          <span className="text-muted">Input:</span>{" "}
                          {typeof tc === "object" && "input" in tc
                            ? tc.input
                            : String(tc)}
                          <br />
                          <span className="text-muted">Expected:</span>{" "}
                          {typeof tc === "object" && "expected_output" in tc
                            ? tc.expected_output
                            : ""}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          </div>

          {/* Output panel */}
          {hasOutput && (
            <>
              <button
                type="button"
                onMouseDown={handleResizeStart}
                className="flex w-full cursor-n-resize items-center justify-center border-t border-border bg-muted/10 py-1.5 text-muted hover:bg-muted/20 hover:text-foreground focus:outline-none"
                aria-label="Resize output panel"
              >
                <GripHorizontal className="h-4 w-4" />
              </button>
              <div
                className="flex shrink-0 flex-col border-t border-border bg-muted/5 overflow-hidden"
                style={{ height: outputPanelHeight }}
              >
                {isFrontend && (
                  <>
                    <div className="flex items-center justify-between border-b border-border px-4 py-2.5 shrink-0 bg-background/80">
                      <h3 className="text-sm font-semibold text-foreground">
                        Your output
                      </h3>
                      <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/30 p-0.5">
                        <button
                          onClick={() => setPreviewTab("preview")}
                          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                            previewTab === "preview"
                              ? "bg-background text-foreground shadow-sm"
                              : "text-muted hover:text-foreground"
                          }`}
                        >
                          <Eye className="h-3 w-3" />
                          Preview
                        </button>
                        <button
                          onClick={() => setPreviewTab("code")}
                          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                            previewTab === "code"
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
                      {previewTab === "preview" ? (
                        renderedCode ? (
                          <iframe
                            srcDoc={renderedCode}
                            className="h-full w-full border-0 bg-white"
                            sandbox="allow-scripts"
                            title="Preview"
                          />
                        ) : (
                          <div className="h-full flex items-center justify-center text-sm text-muted">
                            Preview will appear here
                          </div>
                        )
                      ) : (
                        <pre className="h-full overflow-auto p-4 bg-code-bg text-xs font-mono">
                          <code>{renderedCode || "// No code yet"}</code>
                        </pre>
                      )}
                    </div>
                  </>
                )}

                {isCoding && latestCode && (
                  <>
                    <div className="flex items-center justify-between border-b border-border px-4 py-2.5 shrink-0 bg-background/80">
                      <h3 className="text-sm font-semibold text-foreground">
                        Generated Code
                      </h3>
                    </div>
                    <pre className="flex-1 min-h-0 overflow-auto p-4 bg-code-bg text-xs font-mono">
                      <code>{latestCode}</code>
                    </pre>
                  </>
                )}
              </div>
            </>
          )}
        </div>

        {/* Right: Chat */}
        <div className="flex flex-col w-1/2 shrink-0">
          <div className="border-b border-border px-6 py-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted" />
            <h2 className="text-sm font-medium text-foreground">
              Workspace
            </h2>
          </div>

          <div className="flex-1 overflow-y-auto">
            <div className="px-6 py-8">
              {messages.length === 0 && !isStreaming && (
                <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
                  <div className="text-center max-w-md">
                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent/10 mb-4">
                      <Sparkles className="h-6 w-6 text-accent" />
                    </div>
                    <h3 className="text-lg font-medium text-foreground mb-2">
                      Start prompting
                    </h3>
                    <p className="text-sm text-muted">
                      Describe what you want to build. The AI will generate
                      code based on your prompt.
                    </p>
                  </div>
                </div>
              )}

              <div className="space-y-8">
                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={`flex gap-4 group ${
                      message.role === "user" ? "flex-row-reverse" : ""
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm leading-relaxed">
                        {message.role === "user" ? (
                          <div className="bg-foreground/5 border border-border rounded-lg px-4 py-3 text-foreground">
                            <div className="whitespace-pre-wrap break-words">
                              {message.content}
                            </div>
                          </div>
                        ) : (
                          <div className="text-foreground">
                            <div className="whitespace-pre-wrap break-words">
                              {message.content}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {isStreaming && (
                  <div className="flex gap-4 group">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm leading-relaxed text-foreground">
                        <div className="whitespace-pre-wrap break-words">
                          {currentStreamingMessage}
                          <span className="inline-block w-0.5 h-4 bg-foreground ml-1 align-middle animate-pulse" />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="border-t border-border bg-background">
            <div className="px-6 py-4">
              <PromptInput
                onSubmit={handleSubmit}
                onStop={handleStop}
                isStreaming={isStreaming}
                selectedModel={selectedModel}
                onModelChange={setSelectedModel}
                placeholder="Describe what you want to build…"
                disabled={
                  isStreaming ||
                  submitState !== "idle" ||
                  timeExpired
                }
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
