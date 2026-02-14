"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { getChallenge, runTests, createSandbox, terminateSandbox } from "@/lib/api";
import { PromptInput } from "@/components/PromptInput";
import { streamChat, type ChatMessage, type TestCaseResult, type RunTestsResponse } from "@/lib/api";
import type { Challenge } from "@/lib/types";
import {
  Loader2,
  ArrowLeft,
  Sparkles,
  Eye,
  Code,
  CheckCircle2,
  XCircle,
  FlaskConical,
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

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // UI preview state
  const [renderedCode, setRenderedCode] = useState<string>("");
  const [previewTab, setPreviewTab] = useState<"preview" | "code">("preview");

  // Test results state
  const [testResults, setTestResults] = useState<RunTestsResponse | null>(null);
  const [testTab, setTestTab] = useState<"results" | "code">("results");
  const [latestCode, setLatestCode] = useState<string>("");
  const [runningTests, setRunningTests] = useState(false);

  // Sandbox state
  const [sandboxId, setSandboxId] = useState<string | null>(null);
  const [sandboxError, setSandboxError] = useState<string | null>(null);
  const sandboxIdRef = useRef<string | null>(null);

  // Initialize challenge
  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const challengeData = await getChallenge(challengeId);
        if (ignore) return;
        setChallenge(challengeData);
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  // Create sandbox when challenge loads (for function challenges with tests)
  useEffect(() => {
    if (!challenge) return;
    const hasFunctionTests = challenge.test_suite && challenge.test_suite.length > 0;
    if (!hasFunctionTests) return;

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

  // Extract code and run tests when messages change
  useEffect(() => {
    const assistantMessages = messages.filter((m) => m.role === "assistant");
    if (assistantMessages.length === 0) return;

    const latest = assistantMessages[assistantMessages.length - 1];
    const isUi = challenge?.category === "ui";
    const hasFunctionTests = challenge?.test_suite && challenge.test_suite.length > 0;

    if (isUi) {
      const code = extractAllCode(latest.content);
      if (code && isHtmlCode(code)) {
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
    }
  }, [messages, challenge, challengeId, sandboxId]);

  const handleSubmit = async (prompt: string) => {
    if (!prompt.trim() || isStreaming) return;

    const userMessage: ChatMessage = { role: "user", content: prompt };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsStreaming(true);
    setCurrentStreamingMessage("");

    await streamChat(
      updatedMessages,
      undefined,
      (chunk) => {
        setCurrentStreamingMessage((prev) => prev + chunk);
      },
      (fullResponse) => {
        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: fullResponse,
        };
        setMessages([...updatedMessages, assistantMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
      },
      (error) => {
        console.error("Chat error:", error);
        const errorMessage: ChatMessage = {
          role: "assistant",
          content: `Error: ${error}`,
        };
        setMessages([...updatedMessages, errorMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
      }
    );
  };

  const isUiChallenge = challenge?.category === "ui";
  const hasFunctionTests =
    challenge?.test_suite && challenge.test_suite.length > 0;
  const hasBottomPanel =
    (isUiChallenge && renderedCode) || (hasFunctionTests && (testResults || runningTests));

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
            className="text-muted hover:text-foreground transition-colors"
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

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Left panel: Challenge description + output */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border">
          {/* Top: Challenge description (scrollable) */}
          <div
            className={`${
              hasBottomPanel ? "h-1/2" : "flex-1"
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
              {challenge?.image_url && (
                <div className="rounded-lg border border-border overflow-hidden bg-muted/20 mb-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={challenge.image_url}
                    alt="Challenge reference"
                    className="w-full max-h-[280px] object-contain object-top"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Bottom: Output panel */}
          {hasBottomPanel && (
            <div className="h-1/2 flex flex-col">
              {/* ---- UI Preview ---- */}
              {isUiChallenge && renderedCode && (
                <>
                  <div className="flex items-center border-b border-border px-4 py-2 shrink-0">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setPreviewTab("preview")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                          previewTab === "preview"
                            ? "bg-accent/10 text-accent"
                            : "text-muted hover:text-foreground"
                        }`}
                      >
                        <Eye className="h-3 w-3" />
                        Preview
                      </button>
                      <button
                        onClick={() => setPreviewTab("code")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                          previewTab === "code"
                            ? "bg-accent/10 text-accent"
                            : "text-muted hover:text-foreground"
                        }`}
                      >
                        <Code className="h-3 w-3" />
                        Code
                      </button>
                    </div>
                  </div>
                  <div className="flex-1 min-h-0 overflow-hidden">
                    {previewTab === "preview" ? (
                      <iframe
                        srcDoc={renderedCode}
                        className="h-full w-full border-0 bg-white"
                        sandbox="allow-scripts"
                        title="Rendered output"
                      />
                    ) : (
                      <pre className="h-full overflow-auto p-4 bg-code-bg text-xs font-mono">
                        <code>{renderedCode}</code>
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
              <PromptInput
                onSubmit={handleSubmit}
                loading={isStreaming}
                placeholder="Ask anything..."
                disabled={isStreaming}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
