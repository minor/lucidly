"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { getChallenge, runTests, runCode, createSandbox, terminateSandbox, MODEL_PRICING, MODELS, createVercelSandbox, updateVercelSandboxCode, stopVercelSandbox, streamPromptFeedback, createScoringSession, submitScore, freezeScoringTimer, unfreezeScoringTimer } from "@/lib/api";
import { PromptInput } from "@/components/PromptInput";
import { ScoreBar } from "@/components/ScoreBar";
import { SimpleMarkdown } from "@/components/SimpleMarkdown";
import { streamChat, type ChatMessage, type TestCaseResult, type RunTestsResponse, type StreamDoneData, type RunCodeResponse } from "@/lib/api";
import { extractPythonCode, extractRenderableUI } from "@/lib/codeExtract";
import type { Challenge, Scores } from "@/lib/types";
import {
  Loader2,
  ArrowLeft,
  Sparkles,
  Eye,
  Code,
  CheckCircle2,
  XCircle,
  FlaskConical,
  GripHorizontal,
  GripVertical,
  Trophy,
  X,
  MessageCircle,
  Lightbulb,
  FileText,
  LogIn,
  UserPlus,
  HelpCircle,
} from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import { useUsername } from "@/hooks/useUsername";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ChallengePage() {
  const params = useParams();
  const router = useRouter();
  const { user, isAuthenticated, loginWithRedirect } = useAuth0();
  const { username, loading: usernameLoading } = useUsername(user);
  const [showAuthOverlay, setShowAuthOverlay] = useState(false);
  const challengeId = params.challengeId as string;

  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Efficiency stats (timer, turns, tokens)
  const startTimeRef = useRef<number>(Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [totalTurns, setTotalTurns] = useState(0);
  const [totalTokens, setTotalTokens] = useState(0);
  const [totalInputTokens, setTotalInputTokens] = useState(0);
  const [estimatedTokens, setEstimatedTokens] = useState(0);
  const [totalCost, setTotalCost] = useState(0);
  const [inputCost, setInputCost] = useState(0);

  // Output panel state
  const OUTPUT_PANEL_MIN = 120;
  const OUTPUT_PANEL_INITIAL = 200;
  const [outputPanelHeight, setOutputPanelHeight] = useState(OUTPUT_PANEL_INITIAL);
  const resizeStartYRef = useRef<number>(0);
  const resizeStartHeightRef = useRef<number>(OUTPUT_PANEL_INITIAL);

  // Product challenge: resizable Notepad/PRD panel (like coding output panel)
  const PRODUCT_PANEL_MIN = 120;
  const PRODUCT_PANEL_INITIAL = 220;
  const [productPanelHeight, setProductPanelHeight] = useState(PRODUCT_PANEL_INITIAL);
  const productResizeStartYRef = useRef<number>(0);
  const productResizeStartHeightRef = useRef<number>(PRODUCT_PANEL_INITIAL);

  // Workspace horizontal resize state (default 50%, range 30%–70%)
  const WORKSPACE_WIDTH_DEFAULT = 50;
  const WORKSPACE_WIDTH_MIN = 30;
  const WORKSPACE_WIDTH_MAX = 70;
  const [workspaceWidth, setWorkspaceWidth] = useState(WORKSPACE_WIDTH_DEFAULT);
  const workspaceResizeStartXRef = useRef<number>(0);
  const workspaceResizeStartWidthRef = useRef<number>(WORKSPACE_WIDTH_DEFAULT);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // UI preview state
  const [renderedCode, setRenderedCode] = useState<string>("");
  const [previewTab, setPreviewTab] = useState<"preview" | "code">("preview");
  
  // Reference HTML state (for html_url)
  const [referenceHtml, setReferenceHtml] = useState<string>("");

  // Test results state
  const [testResults, setTestResults] = useState<RunTestsResponse | null>(null);
  const [testTab, setTestTab] = useState<"results" | "code">("results");
  const [latestCode, setLatestCode] = useState<string>("");
  const [runningTests, setRunningTests] = useState(false);

  // UI evaluation score state
  const [uiScore, setUiScore] = useState<number | undefined>(undefined);

  // Code execution state (data challenges)
  const [codeResult, setCodeResult] = useState<RunCodeResponse | null>(null);
  const [runningCode, setRunningCode] = useState(false);

  // Model selection state
  const [selectedModel, setSelectedModel] = useState("gpt-5.2");

  // Sandbox state
  const [sandboxId, setSandboxId] = useState<string | null>(null);
  const [sandboxError, setSandboxError] = useState<string | null>(null);
  const sandboxIdRef = useRef<string | null>(null);
  
  // Vercel Sandbox state (for UI challenges)
  const [vercelSandboxId, setVercelSandboxId] = useState<string | null>(null);
  const [vercelPreviewUrl, setVercelPreviewUrl] = useState<string | null>(null);
  const [vercelSandboxReady, setVercelSandboxReady] = useState(false);
  const [vercelSandboxLoading, setVercelSandboxLoading] = useState(false);
  const vercelSandboxIdRef = useRef<string | null>(null);
  const [iframeKey, setIframeKey] = useState(0); // bump to force iframe reload

  // Scoring session (server-side tamper-proof stat tracking)
  const scoringSessionIdRef = useRef<string | null>(null);

  // Abort controller
  const abortControllerRef = useRef<AbortController | null>(null);

  // Submit solution state (Merged from HEAD and Leaderboard)
  const [submitState, setSubmitState] = useState<"idle" | "pending" | "completed">("idle");
  const [finalScores, setFinalScores] = useState<Scores | null>(null);
  const [scoreBarFrozen, setScoreBarFrozen] = useState(false);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [showScoreExplainer, setShowScoreExplainer] = useState(false);

  // Prompt feedback state
  const [workspaceTab, setWorkspaceTab] = useState<"chat" | "feedback">("chat");
  const [feedbackContent, setFeedbackContent] = useState("");
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const feedbackAbortRef = useRef<AbortController | null>(null);
  
  // Ref to hold stats when frozen (pending/completed)
  const frozenStatsRef = useRef<{
    elapsed: number;
    turns: number;
    tokens: number;
    accuracy: number | undefined;
    score: number | undefined;
    cost: number;
  }>(null);

  // Timer pause refs (from Leaderboard)
  const totalPausedTimeRef = useRef(0);
  const pauseStartTimeRef = useRef<number | null>(null);
  
  // Execution state (from Leaderboard - allows pausing during tests)
  const [isExecuting, setIsExecuting] = useState(false);
  
  // True from prompt submission until first LLM token arrives (pause timer during latency)
  const [isWaitingForFirstToken, setIsWaitingForFirstToken] = useState(false);

  // Product challenge state (Part 1: discovery chat, Part 2: PRD)
  const [productPart, setProductPart] = useState<1 | 2>(1);
  const [notes, setNotes] = useState("");
  const [prdContent, setPrdContent] = useState("");
  const [productBottomTab, setProductBottomTab] = useState<"notepad" | "prd">("notepad");

  // Initialize challenge
  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const challengeData = await getChallenge(challengeId);
        if (ignore) return;
        setChallenge(challengeData);
        startTimeRef.current = Date.now();
        
        // Fetch HTML content if html_url exists
        if (challengeData.html_url) {
          try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const response = await fetch(`${API_BASE}/api/challenges/${challengeId}/html`);
            if (!ignore && response.ok) {
              const htmlContent = await response.text();
              setReferenceHtml(htmlContent);
            }
          } catch (err) {
            console.error("Failed to fetch reference HTML:", err);
          }
        }
      } catch (err) {
        if (!ignore) setError((err as Error).message);
      } finally {
        if (!ignore) setInitializing(false);
      }
    }
    init();
    return () => {
      ignore = true;
    };
  }, [challengeId]);

  // Create scoring session once when challenge + username are ready
  useEffect(() => {
    if (!challenge || !isAuthenticated || usernameLoading) return;
    if (scoringSessionIdRef.current) return;
    const authUsername = username || user?.nickname || user?.name || "anonymous";
    let ignore = false;
    createScoringSession({
      challenge_id: challengeId,
      username: authUsername,
    })
      .then((res) => {
        if (!ignore) scoringSessionIdRef.current = res.session_id;
      })
      .catch((err) => console.error("Failed to create scoring session:", err));
    return () => {
      ignore = true;
    };
  }, [challenge, challengeId, isAuthenticated, usernameLoading, username, user]);

  // Timer Logic (Merged)
  useEffect(() => {
    // Check for 100% accuracy to auto-pause timer
    const isPerfect = testResults && testResults.total_count > 0 && testResults.passed_count === testResults.total_count;
    
    // Pause conditions:
    // 1. Waiting for first LLM token (network/inference latency after prompt submit)
    // 2. Running tests or code (executing but not streaming chat)
    // 3. Submitting or Finished (submitState !== 'idle')
    // 4. 100% Accuracy achieved
    const shouldPause = isWaitingForFirstToken || (isExecuting && !isStreaming) || submitState !== 'idle' || (isPerfect && submitState === 'idle');

    if (shouldPause) {
      if (!pauseStartTimeRef.current) {
        pauseStartTimeRef.current = Date.now();
      }
    } else {
      if (pauseStartTimeRef.current) {
        const duration = Date.now() - pauseStartTimeRef.current;
        totalPausedTimeRef.current += duration;
        pauseStartTimeRef.current = null;
      }
    }
  }, [isWaitingForFirstToken, isExecuting, isStreaming, submitState, testResults]);

  useEffect(() => {
    const interval = setInterval(() => {
      const isPerfect = testResults && testResults.total_count > 0 && testResults.passed_count === testResults.total_count;
      const shouldPause = isWaitingForFirstToken || (isExecuting && !isStreaming) || submitState !== 'idle' || (isPerfect && submitState === 'idle');

      if (!shouldPause) {
        const now = Date.now();
        const totalPaused = totalPausedTimeRef.current;
        setElapsed((now - startTimeRef.current - totalPaused) / 1000);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [isWaitingForFirstToken, isExecuting, isStreaming, submitState, testResults]);

  // Freeze/unfreeze server-side timer when 100% accuracy is achieved or lost
  const wasPerfectRef = useRef(false);
  useEffect(() => {
    const sessionId = scoringSessionIdRef.current;
    if (!sessionId) return;
    const isPerfect = !!(testResults && testResults.total_count > 0 && testResults.passed_count === testResults.total_count);
    if (isPerfect && !wasPerfectRef.current) {
      freezeScoringTimer(sessionId).catch(() => {});
    } else if (!isPerfect && wasPerfectRef.current) {
      unfreezeScoringTimer(sessionId).catch(() => {});
    }
    wasPerfectRef.current = isPerfect;
  }, [testResults]);

  // Resize handler
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

  // Product panel resize (Notepad/PRD)
  const handleProductPanelResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    productResizeStartYRef.current = e.clientY;
    productResizeStartHeightRef.current = productPanelHeight;
    const onMove = (moveEvent: MouseEvent) => {
      const delta = productResizeStartYRef.current - moveEvent.clientY;
      const next = productResizeStartHeightRef.current + delta;
      const max = typeof window !== "undefined" ? Math.max(400, window.innerHeight * 0.7) : 600;
      setProductPanelHeight(Math.min(max, Math.max(PRODUCT_PANEL_MIN, next)));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [productPanelHeight]);

  // Workspace horizontal resize
  const handleWorkspaceResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    workspaceResizeStartXRef.current = e.clientX;
    workspaceResizeStartWidthRef.current = workspaceWidth;
    const onMove = (moveEvent: MouseEvent) => {
      const vw = window.innerWidth;
      const deltaPx = workspaceResizeStartXRef.current - moveEvent.clientX;
      const deltaPct = (deltaPx / vw) * 100;
      const next = workspaceResizeStartWidthRef.current + deltaPct;
      setWorkspaceWidth(Math.min(WORKSPACE_WIDTH_MAX, Math.max(WORKSPACE_WIDTH_MIN, next)));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [workspaceWidth]);

  const scrollToBottom = () => {
    const container = chatContainerRef.current;
    if (!container) return;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    if (isNearBottom) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  // Ensure selectedModel is valid
  useEffect(() => {
    const isValid = MODELS.some((m) => m.id === selectedModel);
    if (!isValid) {
      setSelectedModel(MODELS[0].id);
    }
  }, [selectedModel]);

  // Modal Sandbox lifecycle (for Python/C++ code execution)
  useEffect(() => {
    if (!challenge) return;
    const hasFunctionTests = challenge.test_suite && challenge.test_suite.length > 0;
    const isDataChallenge = challenge.category === "data";
    if (!hasFunctionTests && !isDataChallenge) return;

    let ignore = false;
    async function initSandbox() {
      try {
        const { sandbox_id } = await createSandbox();
        if (ignore) return;
        setSandboxId(sandbox_id);
        sandboxIdRef.current = sandbox_id;
      } catch (err) {
        if (!ignore) setSandboxError((err as Error).message);
      }
    }
    initSandbox();

    return () => {
      ignore = true;
      if (sandboxIdRef.current) {
        terminateSandbox(sandboxIdRef.current).catch(() => {});
        sandboxIdRef.current = null;
      }
    };
  }, [challenge]);

  // Vercel Sandbox lifecycle (for UI challenges — live preview)
  // DISABLED: using plain srcDoc HTML rendering instead. Re-enable this
  // useEffect (and the code-push effect below) to restore Vercel Sandbox.
  // useEffect(() => {
  //   if (!challenge || challenge.category !== "ui") return;
  //
  //   let ignore = false;
  //   setVercelSandboxLoading(true);
  //
  //   async function initVercelSandbox() {
  //     try {
  //       const { sandboxId: sbId, previewUrl } = await createVercelSandbox();
  //       if (ignore) return;
  //       setVercelSandboxId(sbId);
  //       setVercelPreviewUrl(previewUrl);
  //       setVercelSandboxReady(true);
  //       vercelSandboxIdRef.current = sbId;
  //     } catch (err) {
  //       console.error("Failed to create Vercel sandbox:", err);
  //     } finally {
  //       if (!ignore) setVercelSandboxLoading(false);
  //     }
  //   }
  //   initVercelSandbox();
  //
  //   return () => {
  //     ignore = true;
  //     if (vercelSandboxIdRef.current) {
  //       stopVercelSandbox(vercelSandboxIdRef.current).catch(() => {});
  //       vercelSandboxIdRef.current = null;
  //     }
  //   };
  // }, [challenge]);

  useEffect(() => {
    const handleBeforeUnload = () => {
      if (sandboxIdRef.current) {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        navigator.sendBeacon(
          `${API_BASE}/api/sandbox/${sandboxIdRef.current}/terminate`,
          ""
        );
      }
      // Vercel sandbox cleanup (disabled — not in use)
      // if (vercelSandboxIdRef.current) {
      //   navigator.sendBeacon(
      //     `/api/sandbox/${vercelSandboxIdRef.current}`,
      //     ""
      //   );
      // }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  // Push rendered code to Vercel Sandbox when it changes
  // DISABLED: Vercel Sandbox not in use — srcDoc rendering handles updates.
  // useEffect(() => {
  //   if (!renderedCode || !vercelSandboxId || !vercelSandboxReady) return;
  //
  //   updateVercelSandboxCode(vercelSandboxId, renderedCode)
  //     .then(() => {
  //       setIframeKey((k) => k + 1);
  //     })
  //     .catch((err) => {
  //       console.error("Failed to update sandbox code:", err);
  //     });
  // }, [renderedCode, vercelSandboxId, vercelSandboxReady]);

  // Auto-run tests/code after streaming
  useEffect(() => {
    if (isStreaming) return;

    const assistantMessages = messages.filter((m) => m.role === "assistant");
    if (assistantMessages.length === 0) return;

    const latest = assistantMessages[assistantMessages.length - 1];
    const isUi = challenge?.category === "ui";
    const hasFunctionTests = challenge?.test_suite && challenge.test_suite.length > 0;

    if (isUi) {
      const extracted = extractRenderableUI(latest.content);
      if (extracted) {
        setRenderedCode(extracted.html);
      }
    }

    if (hasFunctionTests && sandboxId) {
      const code = extractPythonCode(latest.content);
      if (code) {
        setLatestCode(code);
        setRunningTests(true);
        setIsExecuting(true);
        runTests(code, challengeId, sandboxId, scoringSessionIdRef.current ?? undefined)
          .then((results) => {
            setTestResults(results);
            setRunningTests(false);
            setIsExecuting(false);
          })
          .catch((err) => {
            console.error("Test run failed:", err);
            setRunningTests(false);
            setIsExecuting(false);
          });
      } else {
        setIsExecuting(false);
      }
    } else if (isDataChallenge && sandboxId) {
      const code = extractPythonCode(latest.content);
      if (code) {
        setRenderedCode(code);
        setRunningCode(true);
        setIsExecuting(true);
        setCodeResult(null);
        
        runCode(sandboxId, code)
          .then((result) => {
            setCodeResult(result);
            setRunningCode(false);
            setIsExecuting(false);
          })
          .catch((e) => {
            console.error("Failed to run code:", e);
            setCodeResult({ stdout: "", stderr: `Error running code: ${e}`, returncode: 1 });
            setRunningCode(false);
            setIsExecuting(false);
          });
      } else {
        setIsExecuting(false);
      }
    } else {
      setIsExecuting(false);
    }
  }, [messages, challenge, challengeId, sandboxId, isStreaming]);

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
      setIsWaitingForFirstToken(false);
      if (estimatedTokens > 0 || inputCost > 0) {
        setTotalTokens((t) => t + Math.round(estimatedTokens));
        // Calculate estimated output cost dynamically
        const pricing = MODEL_PRICING[selectedModel] || MODEL_PRICING["gpt-5.2"];
        const outputCost = (estimatedTokens * pricing.output) / 1_000_000;
        setTotalCost((c) => c + inputCost + outputCost);
        setEstimatedTokens(0);
        setInputCost(0);
      }
    }
  };

  const isUiChallenge = challenge?.category === "ui";
  const hasFunctionTests = challenge?.test_suite && challenge.test_suite.length > 0;
  const isDataChallenge = challenge?.category === "data";
  const isProductChallenge = challenge?.category === "product";
  const productParts = challenge?.product_parts ?? [];

  const handleSubmitSolution = async () => {
    if (submitState !== "idle") return;

    // Freeze the score bar stats for display (informational only)
    const currentElapsed = elapsed;
    const currentTurns = totalTurns;
    const currentTokens = Math.round(totalTokens + totalInputTokens + estimatedTokens);
    const currentCost = totalCost + inputCost + ((estimatedTokens * (MODEL_PRICING[selectedModel]?.output || MODEL_PRICING["gpt-5.2"].output)) / 1_000_000);

    setScoreBarFrozen(true);
    setSubmitState("pending");
    setScoreLoading(true);

    // Client-side accuracy preview for the frozen stats display
    let previewAccuracy: number | undefined;
    let previewScore: number | undefined;
    if (isProductChallenge) {
      previewAccuracy = undefined;
      previewScore = undefined;
    } else if (isUiChallenge) {
      previewAccuracy = uiScore != null ? uiScore / 100 : undefined;
      previewScore = uiScore;
    } else if (hasFunctionTests && testResults) {
      previewAccuracy = testResults.passed_count / testResults.total_count;
      previewScore = previewAccuracy * 100;
    } else if (isDataChallenge && codeResult) {
      previewAccuracy = codeResult.returncode === 0 ? 1.0 : 0.0;
      previewScore = previewAccuracy * 100;
    }

    frozenStatsRef.current = {
      elapsed: currentElapsed,
      turns: currentTurns,
      tokens: currentTokens,
      accuracy: previewAccuracy,
      score: previewScore,
      cost: currentCost,
    };

    try {
      const sessionId = scoringSessionIdRef.current;
      if (!sessionId) {
        throw new Error("No scoring session — please refresh the page");
      }

      const scores = await submitScore(sessionId, {
        code: latestCode || undefined,
        sandbox_id: sandboxId ?? undefined,
        generated_html: isUiChallenge ? renderedCode || undefined : undefined,
        prd_content: isProductChallenge && prdContent.trim() ? prdContent : undefined,
      });

      setFinalScores(scores);
      setScoreLoading(false);
      setSubmitState("completed");
      setShowCompletionModal(true);

      triggerPromptFeedback();
    } catch (err) {
      console.error("Failed to submit score:", err);
      setScoreBarFrozen(false);
      setScoreLoading(false);
      frozenStatsRef.current = null;
      setSubmitState("idle");
    }
  };

  const handleRetry = () => {
    // Reset all state to restart
    setMessages([]);
    setRenderedCode("");
    setTestResults(null);
    setLatestCode("");
    setUiScore(undefined);
    setCodeResult(null);
    setTotalTurns(0);
    setTotalTokens(0);
    setTotalInputTokens(0);
    setEstimatedTokens(0);
    setTotalCost(0);
    setInputCost(0);
    setSubmitState("idle");
    setFinalScores(null);
    setScoreBarFrozen(false);
    setScoreLoading(false);
    setShowCompletionModal(false);
    setIsWaitingForFirstToken(false);
    frozenStatsRef.current = null;
    startTimeRef.current = Date.now();
    setElapsed(0);
    totalPausedTimeRef.current = 0;
    pauseStartTimeRef.current = null;
    setProductPart(1);
    setNotes("");
    setPrdContent("");
    setProductBottomTab("notepad");
    setProductPanelHeight(PRODUCT_PANEL_INITIAL);
    setFeedbackContent("");
    setFeedbackLoading(false);
    setWorkspaceTab("chat");
    if (feedbackAbortRef.current) feedbackAbortRef.current.abort();

    // Create a fresh scoring session for the new attempt
    const authUsername = username || user?.nickname || user?.name || "anonymous";
    scoringSessionIdRef.current = null;
    createScoringSession({ challenge_id: challengeId, username: authUsername })
      .then((res) => {
        scoringSessionIdRef.current = res.session_id;
      })
      .catch((err) => console.error("Failed to create scoring session:", err));
  };

  const triggerPromptFeedback = async () => {
    if (feedbackLoading || !challenge || !frozenStatsRef.current) return;

    setFeedbackLoading(true);
    setFeedbackContent("");
    setWorkspaceTab("feedback");

    // Abort any previous feedback stream
    if (feedbackAbortRef.current) feedbackAbortRef.current.abort();
    feedbackAbortRef.current = new AbortController();

    try {
      await streamPromptFeedback(
        {
          messages: messages,
          challenge_id: challengeId,
          challenge_description: challenge.description || "",
          challenge_category: challenge.category || "",
          challenge_difficulty: challenge.difficulty || "",
          reference_html: referenceHtml || "",
          ...(isProductChallenge && prdContent.trim() ? { prd_content: prdContent } : {}),
          accuracy: frozenStatsRef.current.accuracy || 0,
          total_turns: frozenStatsRef.current.turns,
          total_tokens: frozenStatsRef.current.tokens,
          elapsed_sec: frozenStatsRef.current.elapsed,
        },
        (chunk) => setFeedbackContent((prev) => prev + chunk),
        () => setFeedbackLoading(false),
        (error) => {
          console.error("Prompt feedback error:", error);
          setFeedbackContent((prev) => prev + `\n\n**Error:** ${error}`);
          setFeedbackLoading(false);
        },
        feedbackAbortRef.current.signal
      );
    } catch (err) {
      console.error("Failed to stream feedback:", err);
      setFeedbackLoading(false);
    }
  };

  const handleSubmit = async (prompt: string, model: string) => {
    if (!prompt.trim() || isStreaming || isExecuting || submitState !== "idle") return;

    // Require auth before prompting
    if (!isAuthenticated) {
      setShowAuthOverlay(true);
      return;
    }

    setSelectedModel(model);

    const userMessage: ChatMessage = { role: "user", content: prompt };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsStreaming(true);
    setIsExecuting(true); // Start execution state (stops timer for chat duration + execution)
    setIsWaitingForFirstToken(true); // Pause timer during LLM latency
    setCurrentStreamingMessage("");
    setTotalTurns((t) => t + 1);

    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    let firstTokenReceived = false;
    await streamChat(
      updatedMessages,
      model,
      (chunk) => {
        // Resume timer on first token — latency period is over
        if (!firstTokenReceived) {
          firstTokenReceived = true;
          setIsWaitingForFirstToken(false);
        }
        setCurrentStreamingMessage((prev) => prev + chunk);
        setEstimatedTokens((prev) => prev + chunk.length / 4);
      },
      (fullResponse) => {
        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: fullResponse,
        };
        setMessages([...updatedMessages, assistantMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
        setIsWaitingForFirstToken(false); // Ensure cleared
        setEstimatedTokens(0);
        abortControllerRef.current = null;
      },
      (error) => {
        if (error === "AbortError") return;
        console.error("Chat error:", error);
        const errorMessage: ChatMessage = {
          role: "assistant",
          content: `Error: ${error}`,
        };
        setMessages([...updatedMessages, errorMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
        setIsWaitingForFirstToken(false); // Ensure cleared
        setEstimatedTokens(0);
        abortControllerRef.current = null;
      },
      (data: StreamDoneData) => {
        if (data.output_tokens) {
          setTotalTokens((t) => t + data.output_tokens!);
        }
        if (data.cost) {
          setTotalCost((c) => c + data.cost!);
        }
        setEstimatedTokens(0);
        setInputCost(0);
      },
      (usage) => {
        if (usage.input_tokens) {
          const pricing = MODEL_PRICING[model] || MODEL_PRICING["gpt-5.2"];
          setInputCost((usage.input_tokens * pricing.input) / 1_000_000);
          setTotalInputTokens((t) => t + usage.input_tokens);
        }
      },
      abortControllerRef.current?.signal,
      isProductChallenge && productPart === 1 ? challengeId : undefined,
      scoringSessionIdRef.current ?? undefined
    );
  };

  const hasBottomPanel =
    !isProductChallenge &&
    (isUiChallenge ||
      (hasFunctionTests && (testResults || runningTests)) ||
      (isDataChallenge && (codeResult || runningCode)));

  const OUTPUT_PLACEHOLDER_IMAGE =
    "https://placehold.co/800x400/f8fafc/94a3b8?text=Waiting+for+code...";
  const OUTPUT_PLACEHOLDER_CODE = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>My Page</title>
</head>
<body>
  <header>...</header>
  <main>...</main>
</body>
</html>`;

  if (initializing || (isAuthenticated && usernameLoading)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen sm:h-screen flex-col relative">
      {/* Auth overlay — shown when unauthenticated user tries to prompt */}
      {showAuthOverlay && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md animate-in fade-in duration-200">
          <h2 className="text-xl font-semibold tracking-tight mb-2">Sign in to start prompting</h2>
          <p className="text-sm text-muted mb-6">Create an account to interact with challenges</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => loginWithRedirect({ appState: { returnTo: window.location.pathname } })}
              className="flex items-center gap-1.5 rounded-lg border border-border bg-card/80 backdrop-blur-sm px-3 py-2 text-xs font-medium text-muted hover:text-foreground hover:border-foreground/20 shadow-sm transition-colors cursor-pointer"
            >
              <LogIn className="h-3.5 w-3.5" />
              Log in
            </button>
            <button
              type="button"
              onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: "signup" }, appState: { returnTo: window.location.pathname } })}
              className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-medium text-accent-foreground hover:bg-accent/90 shadow-sm transition-colors cursor-pointer"
            >
              <UserPlus className="h-3.5 w-3.5" />
              Sign up
            </button>
          </div>
        </div>
      )}

      {/* Score Overlay */}
      {submitState === "completed" && finalScores && showCompletionModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/95 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-2xl rounded-2xl border border-border bg-card p-12 shadow-2xl text-center relative">
            {/* Close button */}
            <button
              onClick={() => {
                setShowCompletionModal(false);
                // Keep submitState as "completed" to maintain frozen state
                // Timer will stay frozen, chat disabled, button shows "Retry"
              }}
              className="absolute top-4 right-4 text-muted hover:text-foreground transition-colors cursor-pointer p-1 rounded-md hover:bg-muted/10"
              aria-label="Close modal"
            >
              <X className="h-5 w-5" />
            </button>
            
            <div className="mb-8 flex justify-center">
              <div className="rounded-full bg-accent/10 p-4">
                <Trophy className="h-12 w-12 text-accent" />
              </div>
            </div>
            
            <h2 className="mb-2 text-3xl font-bold tracking-tight">Challenge Complete!</h2>
            <p className="mb-8 text-muted">Great job! Here&apos;s how you performed.</p>

            <div className="mb-10 flex justify-center">
              <div className="relative">
                <div className="text-center">
                  <div className="text-6xl font-black text-foreground font-mono tracking-tighter">
                    {finalScores.composite_score}
                  </div>
                  <div className="mt-2 text-sm font-medium text-muted uppercase tracking-widest flex items-center justify-center gap-1">
                    Final Score
                    <button
                      onClick={() => setShowScoreExplainer((v) => !v)}
                      className="inline-flex items-center justify-center rounded-full text-muted hover:text-foreground transition-colors cursor-pointer"
                      aria-label="How is the score calculated?"
                    >
                      <HelpCircle className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
                {showScoreExplainer && (
                  <div className="absolute left-full top-0 ml-4 w-52 rounded-lg border border-border bg-background p-3 text-left text-xs text-muted leading-relaxed shadow-lg animate-in fade-in slide-in-from-left-1 duration-150">
                    <p className="mb-1 font-semibold text-foreground text-[11px] uppercase tracking-wider">Scoring</p>
                    <p>
                      ELO-style rating (0–1000) weighted by{" "}
                      <span className="text-foreground font-medium">Accuracy 70%</span>,{" "}
                      <span className="text-foreground font-medium">Speed 15%</span>, and{" "}
                      <span className="text-foreground font-medium">Cost 15%</span>.
                    </p>
                  </div>
                )}
              </div>
            </div>

            <div className="mb-10 flex justify-center">
              <ScoreBar 
                accuracy={isProductChallenge ? undefined : finalScores.accuracy_score / 1000}
                score={isProductChallenge ? undefined : (frozenStatsRef.current?.score)}
                compositeScore={finalScores.composite_score}
                turns={frozenStatsRef.current?.turns || 0}
                tokens={frozenStatsRef.current?.tokens || 0}
                elapsedSec={frozenStatsRef.current?.elapsed || 0}
                cost={frozenStatsRef.current?.cost || 0}
              />
            </div>

            <div className="mx-auto max-w-sm space-y-4">
              <div className="rounded-lg bg-green-500/10 border border-green-500/20 p-3 text-green-500 flex items-center justify-center gap-2 animate-in fade-in duration-300">
                <CheckCircle2 className="h-4 w-4" />
                <span className="text-sm font-medium">Score submitted as {username || user?.nickname || user?.name || "anonymous"}</span>
              </div>
              
              <div className="flex gap-2 mt-2">
                <button 
                  onClick={() => {
                    setShowCompletionModal(false);
                    setWorkspaceTab("feedback");
                  }}
                  className="flex-1 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent/90 transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <Lightbulb className="h-3.5 w-3.5" />
                  {isProductChallenge ? "View PRD Feedback" : "View Prompt Feedback"}
                </button>
              </div>
              <div className="flex gap-2 mt-2">
                <button 
                  onClick={() => {
                    setShowCompletionModal(false);
                    setWorkspaceTab("chat");
                  }}
                  className="flex-1 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-accent/10 hover:border-accent/40 transition-colors cursor-pointer"
                >
                  View My Response
                </button>
                <button 
                  onClick={handleRetry}
                  className="flex-1 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-accent/10 hover:border-accent/40 transition-colors cursor-pointer"
                >
                  Retry Challenge
                </button>
              </div>
              <button 
                onClick={() => router.push("/play")}
                className="text-sm text-muted hover:text-foreground underline underline-offset-4 cursor-pointer"
              >
                Return to All Challenges
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/play")}
            className="text-muted hover:text-foreground transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-sm font-semibold">{challenge?.title}</h1>
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="capitalize">{challenge?.category}</span>
              <span>·</span>
              <span className="capitalize">{challenge?.difficulty}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Efficiency stats + Submit solution */}
      <div className="flex items-center justify-between gap-4 border-b border-border px-6 py-2">
        <ScoreBar
          turns={scoreBarFrozen && frozenStatsRef.current ? frozenStatsRef.current.turns : totalTurns}
          tokens={scoreBarFrozen && frozenStatsRef.current ? frozenStatsRef.current.tokens : Math.round(totalTokens + totalInputTokens + estimatedTokens)}
          elapsedSec={scoreBarFrozen && frozenStatsRef.current ? frozenStatsRef.current.elapsed : elapsed}
          accuracy={scoreBarFrozen && frozenStatsRef.current ? frozenStatsRef.current.accuracy : (testResults ? testResults.passed_count / testResults.total_count : undefined)}
          score={
            scoreBarFrozen && frozenStatsRef.current
              ? frozenStatsRef.current.score
              : isUiChallenge && uiScore !== undefined
                ? uiScore
                : testResults
                  ? (testResults.passed_count / testResults.total_count) * 100
                  : undefined
          }
          scoreLoading={scoreLoading && !scoreBarFrozen}
          compositeScore={finalScores ? finalScores.composite_score : undefined}
          cost={
            scoreBarFrozen && frozenStatsRef.current
              ? frozenStatsRef.current.cost
              : totalCost +
                inputCost +
                ((estimatedTokens * (MODEL_PRICING[selectedModel]?.output || MODEL_PRICING["gpt-5.2"].output)) / 1_000_000)
          }
        />
        <button
            type="button"
            onClick={submitState === 'completed' ? handleRetry : handleSubmitSolution}
            disabled={
                submitState === "pending" ||
                isExecuting ||
                isStreaming ||
                (isProductChallenge
                  ? productPart !== 2 || !prdContent.trim()
                  : !testResults && !codeResult && !renderedCode)
            }
            className={`hidden sm:inline-flex shrink-0 rounded-lg bg-foreground text-background px-4 py-2 text-xs font-medium transition-opacity ${
                submitState === "pending" ||
                (submitState === "idle" &&
                  (isExecuting ||
                    isStreaming ||
                    (isProductChallenge ? productPart !== 2 || !prdContent.trim() : !testResults && !codeResult && !renderedCode)))
                ? "opacity-50 cursor-not-allowed"
                : "hover:opacity-90 cursor-pointer"
            }`}
        >
            {submitState === "pending" ? "Pending" : submitState === "completed" ? "Retry" : isProductChallenge && productPart === 2 ? "Submit PRD" : "Submit"}
        </button>
      </div>

      {/* Main content */}
      <div className="flex flex-col sm:flex-row sm:overflow-hidden sm:flex-1 sm:min-h-0">
        <div className="contents sm:flex sm:flex-1 sm:flex-col sm:min-w-0 sm:border-r sm:border-border">
          {/* Top: Challenge description (or product Part 1/2 + notepad) */}
          <div
            className={`${
              hasBottomPanel ? "sm:min-h-0 sm:flex-1" : "sm:flex-1"
            } sm:overflow-y-auto border-b border-border flex flex-col sm:min-h-0 order-1 sm:order-none`}
          >
            <div className="p-6 flex-1 min-h-0">
              <h2 className="text-sm font-semibold mb-3">Challenge</h2>
              <SimpleMarkdown content={challenge?.description || ""} className="text-sm leading-relaxed mb-4" />

              {isProductChallenge && productParts.length > 0 && (
                <div className="mb-10 pb-4 space-y-3">
                  <div className="rounded-lg border border-border bg-muted/10 p-4 pb-5 flex flex-col">
                    <span className="text-sm font-semibold text-foreground mb-2">
                      {productParts[productPart - 1]?.title ?? `Part ${productPart}`}
                    </span>
                    <SimpleMarkdown
                      content={productParts[productPart - 1]?.description ?? ""}
                      className="text-sm leading-relaxed text-muted-foreground"
                    />
                    {productPart === 1 && (
                      <div className="mt-2 flex justify-start">
                        <button
                          type="button"
                          onClick={() => {
                            setProductPart(2);
                            setMessages([]);
                            setSelectedModel("sonar-pro");
                          }}
                          className="rounded-lg bg-foreground text-background px-3 py-1.5 text-xs font-medium hover:opacity-90 cursor-pointer"
                        >
                          Next → Part 2
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {!isProductChallenge && challenge?.starter_code && (
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
              {!isProductChallenge && challenge?.html_url && referenceHtml && (
                <div className="rounded-lg border border-border overflow-hidden bg-muted/20 mb-4 h-[680px]">
                  <iframe
                    srcDoc={referenceHtml}
                    title="Challenge reference (top of page only)"
                    className="w-full h-[900px] border-0 rounded-lg pointer-events-none"
                    sandbox="allow-scripts allow-same-origin"
                  />
                </div>
              )}
              {!isProductChallenge && challenge?.image_url && !challenge?.html_url && (
                <div className="rounded-lg border border-border overflow-hidden bg-muted/20 mb-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={challenge.image_url}
                    alt="Challenge reference"
                    className="w-full max-h-[280px] object-contain object-top"
                  />
                </div>
              )}
              {!isProductChallenge && challenge?.test_suite && challenge.test_suite.length > 0 && (
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

          {/* Product challenge: resizable Notepad | PRD panel */}
          {isProductChallenge && (
            <>
              <button
                type="button"
                onMouseDown={handleProductPanelResizeStart}
                className="hidden sm:flex order-1 sm:order-none w-full cursor-n-resize items-center justify-center border-t border-border bg-muted/10 py-1.5 text-muted hover:bg-muted/20 hover:text-foreground focus:outline-none shrink-0"
                aria-label="Resize notepad panel"
              >
                <GripHorizontal className="h-4 w-4" />
              </button>
              <div
                className="flex shrink-0 flex-col border-t border-border overflow-hidden order-1 sm:order-none mobile-auto-height"
                style={{ height: productPanelHeight }}
              >
                <div className="flex items-center justify-between border-b border-border px-4 py-2.5 shrink-0 bg-background/80">
                <span className="text-sm font-semibold text-foreground">
                  {productBottomTab === "notepad" ? "Notepad" : "PRD"}
                </span>
                <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/30 p-0.5">
                  <button
                    type="button"
                    onClick={() => setProductBottomTab("notepad")}
                    className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                      productBottomTab === "notepad"
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted hover:text-foreground"
                    }`}
                  >
                    Notepad
                  </button>
                  <button
                    type="button"
                    onClick={() => setProductBottomTab("prd")}
                    className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                      productBottomTab === "prd"
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted hover:text-foreground"
                    }`}
                  >
                    <FileText className="h-3 w-3" />
                    PRD
                  </button>
                </div>
              </div>
              <div className="flex-1 min-h-0 overflow-hidden rounded-b-lg border-x border-b border-border bg-code-bg/50 flex flex-col">
                {productBottomTab === "notepad" ? (
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Take notes from your conversation with the CRO..."
                    className="flex-1 min-h-0 w-full resize-none p-4 text-sm font-mono text-foreground bg-transparent border-0 focus:outline-none focus:ring-0 placeholder:text-muted"
                  />
                ) : (
                  <textarea
                    value={prdContent}
                    onChange={(e) => setPrdContent(e.target.value)}
                    placeholder="Write your PRD here. Use the right panel to chat with the assistant as you draft..."
                    className="flex-1 min-h-0 w-full resize-none p-4 text-sm leading-relaxed text-foreground bg-transparent border-0 focus:outline-none focus:ring-0 placeholder:text-muted"
                  />
                )}
              </div>
              </div>
            </>
          )}

          {/* Resize handle */}
          {hasBottomPanel && (
            <button
              type="button"
              onMouseDown={handleResizeStart}
              className="hidden sm:flex order-3 sm:order-none w-full cursor-n-resize items-center justify-center border-t border-border bg-muted/10 py-1.5 text-muted hover:bg-muted/20 hover:text-foreground focus:outline-none"
              aria-label="Resize output panel"
            >
              <GripHorizontal className="h-4 w-4" />
            </button>
          )}

          {/* Bottom: Output panel */}
          {hasBottomPanel && (
            <div
              className="flex shrink-0 flex-col border-t border-border bg-muted/5 overflow-hidden order-3 sm:order-none mobile-auto-height"
              style={{ height: outputPanelHeight }}
            >
              {isDataChallenge && (
                <div className="flex flex-col h-full bg-card">
                  <div className="px-4 py-2 border-b border-border bg-muted/30 flex justify-between items-center">
                    <span className="text-sm font-medium">Execution Output</span>
                    {codeResult && (
                      <span className={`text-xs ${codeResult.returncode === 0 ? "text-green-500" : "text-red-400"}`}>
                        {codeResult.returncode === 0 ? "Success" : "Failed"}
                      </span>
                    )}
                  </div>
                  <div className="flex-1 p-4 overflow-auto font-mono text-xs">
                    {runningCode ? (
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Running code...
                      </div>
                    ) : codeResult ? (
                      <div className="space-y-4">
                        {codeResult.stdout && (
                          <div>
                            <div className="text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Stdout</div>
                            <pre className="whitespace-pre-wrap text-foreground bg-muted/30 p-2 rounded">{codeResult.stdout}</pre>
                          </div>
                        )}
                        {codeResult.stderr && (
                          <div>
                            <div className="text-[10px] text-error mb-1 uppercase tracking-wider text-red-400">Stderr</div>
                            <pre className="whitespace-pre-wrap text-red-400 bg-red-400/10 p-2 rounded">{codeResult.stderr}</pre>
                          </div>
                        )}
                        {!codeResult.stdout && !codeResult.stderr && (
                          <div className="text-muted-foreground italic">No output</div>
                        )}
                      </div>
                    ) : (
                      <div className="text-muted-foreground italic">Run your code to see output here</div>
                    )}
                  </div>
                </div>
              )}

              {isUiChallenge && (
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
                          title="Rendered output"
                        />
                      ) : (
                        <div className="h-full flex items-center justify-center bg-muted/20">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={OUTPUT_PLACEHOLDER_IMAGE}
                            alt="Waiting for code..."
                            className="max-h-full w-full object-contain object-top"
                          />
                        </div>
                      )
                    ) : (
                      <pre className="h-full overflow-auto p-4 bg-code-bg text-xs font-mono">
                        <code>{renderedCode || OUTPUT_PLACEHOLDER_CODE}</code>
                      </pre>
                    )}
                  </div>
                </>
              )}

              {hasFunctionTests && !isUiChallenge && (
                <>
                  <div className="flex items-center justify-between border-b border-border px-4 py-2 shrink-0">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setTestTab("results")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                          testTab === "results"
                            ? "bg-accent/10 text-accent"
                            : "text-muted hover:text-foreground"
                        }`}
                      >
                        <FlaskConical className="h-3 w-3" />
                        Tests
                      </button>
                      <button
                        onClick={() => setTestTab("code")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                          testTab === "code"
                            ? "bg-accent/10 text-accent"
                            : "text-muted hover:text-foreground"
                        }`}
                      >
                        <Code className="h-3 w-3" />
                        Code
                      </button>
                    </div>
                    {testResults && (
                      <span
                        className={`text-xs font-medium ${
                          testResults.all_passed
                            ? "text-green-500"
                            : "text-red-400"
                        }`}
                      >
                        {testResults.passed_count}/{testResults.total_count}{" "}
                        passed
                      </span>
                    )}
                  </div>

                  <div className="flex-1 min-h-0 overflow-y-auto">
                    {runningTests ? (
                      <div className="flex items-center justify-center h-full gap-2">
                        <Loader2 className="h-4 w-4 animate-spin text-muted" />
                        <span className="text-sm text-muted">
                          Running tests…
                        </span>
                      </div>
                    ) : testTab === "results" && testResults ? (
                      <div className="p-4 space-y-2">
                        {/* Summary banner */}
                        <div
                          className={`rounded-lg px-3 py-2 text-xs font-medium ${
                            testResults.all_passed
                              ? "bg-green-500/10 text-green-500"
                              : "bg-red-400/10 text-red-400"
                          }`}
                        >
                          {testResults.all_passed
                            ? "✓ All tests passed!"
                            : `✗ ${testResults.total_count - testResults.passed_count} test(s) failed`}
                        </div>

                        {/* Individual results */}
                        {testResults.results.map((tc, i) => (
                          <div
                            key={i}
                            className={`rounded-lg border px-3 py-2 text-xs ${
                              tc.passed
                                ? "border-green-500/20 bg-green-500/5"
                                : "border-red-400/20 bg-red-400/5"
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              {tc.passed ? (
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                              ) : (
                                <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                              )}
                              <span className="font-mono text-foreground truncate">
                                {tc.input}
                              </span>
                            </div>
                            {!tc.passed && (
                              <div className="ml-5.5 mt-1 space-y-0.5 text-xs font-mono">
                                {tc.error ? (
                                  <div className="text-red-400">
                                    Error: {tc.error}
                                  </div>
                                ) : (
                                  <>
                                    <div className="text-muted">
                                      Expected:{" "}
                                      <span className="text-green-500">
                                        {tc.expected}
                                      </span>
                                    </div>
                                    <div className="text-muted">
                                      Got:{" "}
                                      <span className="text-red-400">
                                        {tc.actual}
                                      </span>
                                    </div>
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : testTab === "code" && latestCode ? (
                      <pre className="h-full overflow-auto p-4 bg-code-bg text-xs font-mono">
                        <code>{latestCode}</code>
                      </pre>
                    ) : (
                      <div className="flex items-center justify-center h-full">
                        <span className="text-sm text-muted">
                          No test results yet
                        </span>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Vertical resize handle between left panel and workspace */}
        <button
          type="button"
          onMouseDown={handleWorkspaceResizeStart}
          className="hidden sm:flex items-center justify-center cursor-col-resize w-1.5 shrink-0 bg-muted/10 hover:bg-muted/20 text-muted hover:text-foreground transition-colors focus:outline-none"
          aria-label="Resize workspace width"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        {/* Right: Chat panel (CRO in Part 1, general assistant in Part 2 for PRD help) */}
        <div
          className="flex flex-col order-2 sm:order-none h-[80vh] sm:h-auto mobile-full-width sm:shrink-0 border-t sm:border-t-0 border-border"
          style={{ width: `${workspaceWidth}%` }}
        >
          <div className="border-b border-border px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-muted" />
              <h2 className="text-sm font-medium text-foreground">
                {isProductChallenge && productPart === 1 ? "Chat with the CRO" : isProductChallenge && productPart === 2 ? "General AI" : "Workspace"}
              </h2>
            </div>
            {submitState === "completed" && (
              <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/30 p-0.5">
                <button
                  onClick={() => setWorkspaceTab("chat")}
                  className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                    workspaceTab === "chat"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  <MessageCircle className="h-3 w-3" />
                  Chat
                </button>
                <button
                  onClick={() => setWorkspaceTab("feedback")}
                  className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                    workspaceTab === "feedback"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  <Lightbulb className="h-3 w-3" />
                  Feedback
                  {feedbackLoading && (
                    <Loader2 className="h-3 w-3 animate-spin ml-0.5" />
                  )}
                </button>
              </div>
            )}
          </div>

          {workspaceTab === "chat" ? (
          <div
            ref={chatContainerRef}
            className="flex-1 overflow-y-auto"
          >
            <div className="px-6 py-8">
              {messages.length === 0 && !isStreaming && (
                <div className="flex flex-col items-center justify-center h-full min-h-[200px] sm:min-h-[400px]">
                  <div className="text-center max-w-md">
                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent/10 mb-4">
                      <Sparkles className="h-6 w-6 text-accent" />
                    </div>
                    <h3 className="text-lg font-medium text-foreground mb-2">
                      {isProductChallenge && productPart === 1 ? "Ask the CRO questions" : "Start a conversation"}
                    </h3>
                    <p className="text-sm text-muted">
                      {isProductChallenge && productPart === 1
                        ? "Ask clarifying questions to understand the problem, pain points, and constraints. Take notes in the notepad."
                        : isProductChallenge && productPart === 2
                          ? "Chat with the assistant to draft your PRD. Use the Notepad / PRD tabs on the left to write."
                          : "Describe what you want built for this challenge"}
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
          ) : (
            <div className="flex-1 overflow-y-auto">
              <div className="px-6 py-8">
                {feedbackLoading && !feedbackContent && (
                  <div className="flex flex-col items-center justify-center min-h-[400px]">
                    <Loader2 className="h-6 w-6 animate-spin text-accent mb-3" />
                    <p className="text-sm text-muted">Analyzing your prompts…</p>
                  </div>
                )}
                {feedbackContent && (
                  <div className="prose-sm">
                    <SimpleMarkdown content={feedbackContent} className="text-sm leading-relaxed" />
                    {feedbackLoading && (
                      <span className="inline-block w-0.5 h-4 bg-foreground ml-1 align-middle animate-pulse" />
                    )}
                  </div>
                )}
                {!feedbackLoading && !feedbackContent && (
                  <div className="flex flex-col items-center justify-center min-h-[400px]">
                    <div className="text-center max-w-md">
                      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent/10 mb-4">
                        <Lightbulb className="h-6 w-6 text-accent" />
                      </div>
                      <h3 className="text-lg font-medium text-foreground mb-2">
                        {isProductChallenge ? "PRD Feedback" : "Prompt Feedback"}
                      </h3>
                      <p className="text-sm text-muted">
                        {isProductChallenge
                          ? "Submit your PRD to get AI-powered feedback on feasibility, expertise, clarity, and alignment with discovery."
                          : "Submit your solution to get AI-powered feedback on your prompting strategy."}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="border-t border-border bg-background">
            <div className="px-6 py-4">
              <div className="flex justify-between items-center mb-2">
                <div></div>
              </div>
              <PromptInput
                onSubmit={handleSubmit}
                onStop={handleStop}
                isStreaming={isStreaming}
                selectedModel={selectedModel}
                onModelChange={setSelectedModel}
                fixedModel={isProductChallenge && productPart === 1 ? "gpt-5.2" : undefined}
                placeholder={isProductChallenge && productPart === 1 ? "Ask the CRO..." : "Ask anything..."}
                disabled={isStreaming || isExecuting || submitState === "pending" || submitState === "completed"}
                extraButton={
                  <button
                    type="button"
                    onClick={submitState === "completed" ? handleRetry : handleSubmitSolution}
                    disabled={
                      submitState === "pending" ||
                      isExecuting ||
                      isStreaming ||
                      (isProductChallenge
                        ? productPart !== 2 || !prdContent.trim()
                        : !testResults && !codeResult && !renderedCode)
                    }
                    className={`sm:hidden shrink-0 rounded-lg bg-foreground text-background px-3 h-7 text-xs font-medium transition-opacity ${
                      submitState === "pending" ||
                      (submitState === "idle" &&
                        (isExecuting ||
                          isStreaming ||
                          (isProductChallenge ? productPart !== 2 || !prdContent.trim() : !testResults && !codeResult && !renderedCode)))
                        ? "opacity-50 cursor-not-allowed"
                        : "hover:opacity-90 cursor-pointer"
                    }`}
                  >
                    {submitState === "pending" ? "Pending" : submitState === "completed" ? "Retry" : isProductChallenge && productPart === 2 ? "Submit PRD" : "Submit"}
                  </button>
                }
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}