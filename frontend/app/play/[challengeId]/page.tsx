"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { getChallenge } from "@/lib/api";
import { PromptInput } from "@/components/PromptInput";
import { streamChat, type ChatMessage } from "@/lib/api";
import type { Challenge } from "@/lib/types";
import {
  Loader2,
  ArrowLeft,
  Sparkles,
  Eye,
  Code,
} from "lucide-react";

/**
 * Extract code blocks from a markdown-formatted LLM response.
 * Returns the content inside ``` fences, or the full text if no fences.
 */
function extractCode(text: string): string {
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

  // Rendered output state
  const [renderedCode, setRenderedCode] = useState<string>("");
  const [previewTab, setPreviewTab] = useState<"preview" | "code">("preview");

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

  // Extract renderable code from the latest assistant message
  useEffect(() => {
    const assistantMessages = messages.filter((m) => m.role === "assistant");
    if (assistantMessages.length === 0) return;

    const latest = assistantMessages[assistantMessages.length - 1];
    const code = extractCode(latest.content);
    if (code && isHtmlCode(code)) {
      setRenderedCode(code);
    }
  }, [messages]);

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
        {/* Left panel: Challenge description + rendered output */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border">
          {/* Top: Challenge description (scrollable) */}
          <div className={`${isUiChallenge && renderedCode ? "h-1/2" : "flex-1"} overflow-y-auto border-b border-border`}>
            <div className="p-6">
              <h2 className="text-sm font-semibold mb-3">Challenge</h2>
              <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap mb-4">
                {challenge?.description}
              </p>
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

          {/* Bottom: Rendered output (only for UI challenges) */}
          {isUiChallenge && (
            <div className={`${renderedCode ? "h-1/2" : "h-0"} flex flex-col transition-all duration-300`}>
              {renderedCode && (
                <>
                  {/* Preview header with tabs */}
                  <div className="flex items-center justify-between border-b border-border px-4 py-2 shrink-0">
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

                  {/* Preview / Code content */}
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
