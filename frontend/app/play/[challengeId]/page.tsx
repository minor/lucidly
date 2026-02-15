"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { getChallenge, runTests, runCode, createSandbox, terminateSandbox, MODEL_PRICING, MODELS, calculateScore, evaluateUI } from "@/lib/api";
import { PromptInput } from "@/components/PromptInput";
import { ScoreBar } from "@/components/ScoreBar";
import { streamChat, type ChatMessage, type TestCaseResult, type RunTestsResponse, type StreamDoneData, type RunCodeResponse } from "@/lib/api";
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
} from "lucide-react";

// ---------------------------------------------------------------------------
// Code extraction helpers
// ---------------------------------------------------------------------------

/**
 * Extract the best Python code block from a markdown-formatted LLM response.
 * Strategy:
 *   1. Collect all code blocks from the response
 *   2. Among python-tagged blocks, prefer the one containing `def ` or `class `
 *      (the actual implementation, not a usage example)
 *   3. If multiple contain `def`, take the largest one
 *   4. Fall back to the last python block, then the last block overall
 */
function extractPythonCode(text: string): string {
  const pattern = /```(\w*)\s*\n([\s\S]*?)```/g;
  const blocks: { lang: string; code: string }[] = [];
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    blocks.push({ lang: m[1].toLowerCase(), code: m[2].trim() });
  }
  if (blocks.length === 0) return "";

  // Filter to python blocks
  const pythonBlocks = blocks.filter(
    (b) => b.lang === "python" || b.lang === "py" || b.lang === ""
  );
  const candidates = pythonBlocks.length > 0 ? pythonBlocks : blocks;

  // Prefer blocks that contain function/class definitions (actual implementations)
  const withDef = candidates.filter(
    (b) => /\bdef\s+\w+/.test(b.code) || /\bclass\s+\w+/.test(b.code)
  );

  if (withDef.length > 0) {
    // Take the largest implementation block
    return withDef.reduce((a, b) =>
      a.code.length >= b.code.length ? a : b
    ).code;
  }

  // Fall back to last candidate
  return candidates[candidates.length - 1].code;
}

/**
 * Extract all code blocks concatenated (for HTML).
 */
function extractAllCode(text: string): string {
  const pattern = /```(?:\w+)?\s*\n([\s\S]*?)```/g;
  const matches: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    matches.push(m[1].trim());
  }
  return matches.length > 0 ? matches.join("\n\n") : "";
}

/**
 * Check if code looks like renderable HTML.
 */
function isHtmlCode(code: string): boolean {
  const trimmed = code.trim().toLowerCase();
  return (
    trimmed.startsWith("<!doctype html") ||
    trimmed.startsWith("<html") ||
    trimmed.startsWith("<head") ||
    trimmed.startsWith("<body") ||
    (trimmed.includes("<div") && trimmed.includes("</div>")) ||
    (trimmed.includes("<style") && trimmed.includes("</style>"))
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ChallengePage() {
  const params = useParams();
  const router = useRouter();
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

  // Your output panel: resizable height (small initially), Preview | Code toggle
  const OUTPUT_PANEL_MIN = 120;
  const OUTPUT_PANEL_INITIAL = 200;
  const [outputPanelHeight, setOutputPanelHeight] = useState(OUTPUT_PANEL_INITIAL);
  const resizeStartYRef = useRef<number>(0);
  const resizeStartHeightRef = useRef<number>(OUTPUT_PANEL_INITIAL);

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
  
  // Abort controller for cancelling generation
  const abortControllerRef = useRef<AbortController | null>(null);

  // Submit solution state
  const [submitState, setSubmitState] = useState<"idle" | "pending" | "completed">("idle");
  const [finalScores, setFinalScores] = useState<Scores | null>(null);
  const [scoreBarFrozen, setScoreBarFrozen] = useState(false);
  const [scoreLoading, setScoreLoading] = useState(false);
  const frozenStatsRef = useRef<{
    elapsed: number;
    turns: number;
    tokens: number;
    accuracy: number | undefined;
    score: number | undefined;
    cost: number;
  } | null>(null);

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

  // Timer for efficiency stats (freeze when pending or completed)
  useEffect(() => {
    const interval = setInterval(() => {
      // Don't update timer when pending or completed (frozen)
      if (submitState === "idle") {
        setElapsed((Date.now() - startTimeRef.current) / 1000);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [submitState]);

  // Draggable resize for "Your output" panel (drag up = expand)
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  // Ensure selectedModel is valid (handles removal of old models)
  useEffect(() => {
    const isValid = MODELS.some((m) => m.id === selectedModel);
    if (!isValid) {
      setSelectedModel(MODELS[0].id);
    }
  }, [selectedModel]);

  // Create sandbox when challenge loads (for function challenges with tests OR data challenges)
  useEffect(() => {
    if (!challenge) return;
    const hasFunctionTests = challenge.test_suite && challenge.test_suite.length > 0;
    const isDataChallenge = challenge.category === "data";
    // Only create sandbox for function/data challenges
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

    // Terminate sandbox on cleanup (navigation away or close)
    return () => {
      ignore = true;
      if (sandboxIdRef.current) {
        terminateSandbox(sandboxIdRef.current).catch(() => {});
        sandboxIdRef.current = null;
      }
    };
  }, [challenge]);

  // Also terminate sandbox on page close/refresh
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (sandboxIdRef.current) {
        // Use sendBeacon for reliable cleanup on page close
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        navigator.sendBeacon(
          `${API_BASE}/api/sandbox/${sandboxIdRef.current}/terminate`,
          ""
        );
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  // Extract code and run tests when messages change (ONLY after streaming is done)
  useEffect(() => {
    if (isStreaming) return;

    const assistantMessages = messages.filter((m) => m.role === "assistant");
    if (assistantMessages.length === 0) return;

    const latest = assistantMessages[assistantMessages.length - 1];
    const isUi = challenge?.category === "ui";
    const hasFunctionTests = challenge?.test_suite && challenge.test_suite.length > 0;

    if (isUi) {
      const code = extractAllCode(latest.content);
      if (code && isHtmlCode(code)) {
        // Just render the code, don't automatically evaluate
        setRenderedCode(code);
      }
    }

    if (hasFunctionTests && sandboxId) {
      const code = extractPythonCode(latest.content);
      if (code) {
        setLatestCode(code);
        // Auto-run tests in persistent sandbox
        setRunningTests(true);
        runTests(code, challengeId, sandboxId)
          .then((results) => {
            setTestResults(results);
            setRunningTests(false);
          })
          .catch((err) => {
            console.error("Test run failed:", err);
            setRunningTests(false);
          });
      }
    } else if (isDataChallenge && sandboxId) {
      // Auto-run code for data challenges
      const code = extractPythonCode(latest.content);
      if (code) {
        setRenderedCode(code); // Reuse renderedCode for data challenges to show in "Code" tab if needed
        setRunningCode(true);
        setCodeResult(null);
        
        runCode(sandboxId, code)
          .then((result) => {
            setCodeResult(result);
            setRunningCode(false);
          })
          .catch((e) => {
            console.error("Failed to run code:", e);
            setCodeResult({ stdout: "", stderr: `Error running code: ${e}`, returncode: 1 });
            setRunningCode(false);
          });
      }
    }
  }, [messages, challenge, challengeId, sandboxId]);

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
      // Persist estimated tokens and cost so far
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

  const handleSubmitSolution = async () => {
    if (submitState !== "idle") return;

    // Calculate accuracy based on challenge type
    let accuracy = 0.0;
    let evaluatedUiScore: number | undefined = undefined;
    
    // Freeze the score bar stats first
    const currentElapsed = elapsed;
    const currentTurns = totalTurns;
    const currentTokens = Math.round(totalTokens + totalInputTokens + estimatedTokens);
    const currentCost = totalCost + inputCost + ((estimatedTokens * (MODEL_PRICING[selectedModel]?.output || MODEL_PRICING["gpt-5.2"].output)) / 1_000_000);
    
    setScoreBarFrozen(true);
    setSubmitState("pending");
    setScoreLoading(true);
    
    try {
      // Calculate accuracy based on challenge type
      let accuracy = 0.0;
      let evaluatedUiScore: number | undefined = undefined;
      
      if (isUiChallenge) {
        // For UI challenges, evaluate the rendered code to get the score
        if (renderedCode) {
          const result = await evaluateUI(challengeId, renderedCode);
          accuracy = result.score / 100; // Convert percentage to 0-1
          evaluatedUiScore = result.score; // Store for display
          setUiScore(result.score);
        }
      } else if (hasFunctionTests && testResults) {
        accuracy = testResults.passed_count / testResults.total_count;
      } else if (isDataChallenge && codeResult) {
        // For data challenges, accuracy is based on return code (0 = success)
        accuracy = codeResult.returncode === 0 ? 1.0 : 0.0;
      }
      
      // Update frozen stats with calculated values
      frozenStatsRef.current = {
        elapsed: currentElapsed,
        turns: currentTurns,
        tokens: currentTokens,
        accuracy: isUiChallenge ? accuracy : (testResults ? testResults.passed_count / testResults.total_count : undefined),
        score: isUiChallenge ? evaluatedUiScore : (testResults ? (testResults.passed_count / testResults.total_count) * 100 : undefined),
        cost: currentCost,
      };
      
      // Calculate composite score
      const scores = await calculateScore({
        accuracy,
        elapsed_sec: currentElapsed,
        total_tokens: currentTokens,
        total_turns: currentTurns,
      });
      
      setFinalScores(scores);
      setScoreLoading(false);
      setSubmitState("completed");
    } catch (err) {
      console.error("Failed to calculate score:", err);
      setScoreBarFrozen(false);
      setScoreLoading(false);
      frozenStatsRef.current = null;
      setSubmitState("idle");
    }
  };

  const handleRetry = () => {
    // Reset all state to restart the challenge
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
    frozenStatsRef.current = null;
    startTimeRef.current = Date.now();
    setElapsed(0);
  };

  const handleSubmit = async (prompt: string, model: string) => {
    if (!prompt.trim() || isStreaming) return;
    setSelectedModel(model);

    const userMessage: ChatMessage = { role: "user", content: prompt };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsStreaming(true);
    setCurrentStreamingMessage("");
    setTotalTurns((t) => t + 1);

    // Create new abort controller
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    await streamChat(
      updatedMessages,
      model,
      (chunk) => {
        setCurrentStreamingMessage((prev) => prev + chunk);
        // Estimate tokens: roughly 1 token per 4 chars
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
        setEstimatedTokens(0);
        abortControllerRef.current = null;
      },
      (error) => {
        if (error === "AbortError") return; // Ignore aborts
        console.error("Chat error:", error);
        const errorMessage: ChatMessage = {
          role: "assistant",
          content: `Error: ${error}`,
        };
        setMessages([...updatedMessages, errorMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
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
          // Input cost: dynamic pricing based on selected model
          const pricing = MODEL_PRICING[model] || MODEL_PRICING["gpt-5.2"];
          setInputCost((usage.input_tokens * pricing.input) / 1_000_000);
          setTotalInputTokens((t) => t + usage.input_tokens);
        }
      },
      abortControllerRef.current?.signal
    );
  };

  const isUiChallenge = challenge?.category === "ui";
  const hasFunctionTests =
    challenge?.test_suite && challenge.test_suite.length > 0;
  const isDataChallenge = challenge?.category === "data";

  const hasBottomPanel =

    isUiChallenge ||
    (hasFunctionTests && (testResults || runningTests)) ||
    (isDataChallenge && (codeResult || runningCode));

  // Placeholder for "Your output" when no code generated yet (UI challenges)
  const OUTPUT_PLACEHOLDER_IMAGE =
    "https://placehold.co/800x400/f8fafc/94a3b8?text=Your+rendered+page";
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

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
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
          onClick={submitState === "completed" ? handleRetry : handleSubmitSolution}
          disabled={submitState === "pending"}
          className={`shrink-0 rounded-lg px-4 py-2 text-xs font-medium transition-opacity ${
            submitState === "pending"
              ? "bg-muted text-muted-foreground cursor-not-allowed italic"
              : submitState === "completed"
                ? "bg-foreground text-background hover:opacity-90 cursor-pointer"
                : "bg-foreground text-background hover:opacity-90 cursor-pointer"
          }`}
        >
          {submitState === "pending" ? "Pending" : submitState === "completed" ? "Retry" : "Submit solution"}
        </button>
      </div>

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Left panel: Challenge description + output */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border">
          {/* Top: Challenge description (scrollable); flexes to fill space above output panel */}
          <div
            className={`${
              hasBottomPanel ? "min-h-0 flex-1" : "flex-1"
            } overflow-y-auto border-b border-border`}
          >
            <div className="p-6">
              <h2 className="text-sm font-semibold mb-3">Challenge</h2>
              <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap mb-4">
                {challenge?.description}
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
              {challenge?.html_url && referenceHtml && (
                <div className="rounded-lg border border-border overflow-hidden bg-muted/20 mb-4 h-[680px]">
                  <iframe
                    srcDoc={referenceHtml}
                    title="Challenge reference (top of page only)"
                    className="w-full h-[900px] border-0 rounded-lg pointer-events-none"
                    sandbox="allow-scripts allow-same-origin"
                  />
                </div>
              )}
              {challenge?.image_url && !challenge?.html_url && (
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

          {/* Resize handle (drag up to expand output panel) */}
          {hasBottomPanel && (
            <button
              type="button"
              onMouseDown={handleResizeStart}
              className="flex w-full cursor-n-resize items-center justify-center border-t border-border bg-muted/10 py-1.5 text-muted hover:bg-muted/20 hover:text-foreground focus:outline-none"
              aria-label="Resize output panel"
            >
              <GripHorizontal className="h-4 w-4" />
            </button>
          )}

          {/* Bottom: Output panel (resizable height) */}
          {hasBottomPanel && (
            <div
              className="flex shrink-0 flex-col border-t border-border bg-muted/5 overflow-hidden"
              style={{ height: outputPanelHeight }}
            >
              {/* ---- Data Challenge Execution Output ---- */}
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

              {/* ---- UI Preview (always shown for UI challenges; placeholder until code is generated) ---- */}
              {isUiChallenge && (
                <>
                  <div className="flex items-center justify-between border-b border-border px-4 py-2.5 shrink-0 bg-background/80">
                    <h3 className="text-sm font-semibold text-foreground">
                      Your output
                    </h3>
                    <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/30 p-0.5">
                      <button
                        onClick={() => setPreviewTab("preview")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
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
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
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
                            alt="Your rendered output"
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

              {/* ---- Function Test Results ---- */}
              {hasFunctionTests && !isUiChallenge && (
                <>
                  <div className="flex items-center justify-between border-b border-border px-4 py-2 shrink-0">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setTestTab("results")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
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
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
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

        {/* Right: Chat panel with streaming */}
        <div className="flex flex-col w-1/2 shrink-0 border-l border-border">
          {/* Chat Header */}
          <div className="border-b border-border px-6 py-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted" />
            <h2 className="text-sm font-medium text-foreground">Chat</h2>
          </div>

          {/* Messages Container */}
          <div
            ref={chatContainerRef}
            className="flex-1 overflow-y-auto"
          >
            <div className="px-6 py-8">
              {messages.length === 0 && !isStreaming && (
                <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
                  <div className="text-center max-w-md">
                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent/10 mb-4">
                      <Sparkles className="h-6 w-6 text-accent" />
                    </div>
                    <h3 className="text-lg font-medium text-foreground mb-2">
                      Start a conversation
                    </h3>
                    <p className="text-sm text-muted">
                      Describe what you want built for this challenge
                    </p>
                  </div>
                </div>
              )}

              {/* Messages */}
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

                {/* Streaming Message */}
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

          {/* Input Area */}
          <div className="border-t border-border bg-background">
            <div className="px-6 py-4">
              <div className="flex justify-between items-center mb-2">
                <div></div>
              </div>
              <PromptInput
                onSubmit={handleSubmit}
                onStop={handleStop}
                loading={isStreaming}
                placeholder="Ask anything..."
                disabled={isStreaming || submitState === "pending" || submitState === "completed"}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}