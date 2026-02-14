"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { getChallenge } from "@/lib/api";
import { PromptInput } from "@/components/PromptInput";
import { ScoreBar } from "@/components/ScoreBar";
import { streamChat, type ChatMessage } from "@/lib/api";
import type { Challenge } from "@/lib/types";
import {
  Loader2,
  ArrowLeft,
  Sparkles,
  ImageIcon,
  Code,
} from "lucide-react";

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

  // Your output panel: Preview | Code (v0-style toggle)
  const [outputView, setOutputView] = useState<"preview" | "code">("preview");

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Hardcoded placeholder for "Your output" (preview image + source)
  const OUTPUT_PREVIEW_IMAGE =
    "https://placehold.co/800x500/f8fafc/64748b?text=Your+rendered+page";
  const OUTPUT_SOURCE_PLACEHOLDER = `<!DOCTYPE html>
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

  // Initialize challenge
  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const challengeData = await getChallenge(challengeId);
        if (ignore) return;
        setChallenge(challengeData);
        startTimeRef.current = Date.now();
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

  // Timer for efficiency stats
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed((Date.now() - startTimeRef.current) / 1000);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  const handleSubmit = async (prompt: string) => {
    if (!prompt.trim() || isStreaming) return;

    // Add user message
    const userMessage: ChatMessage = { role: "user", content: prompt };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsStreaming(true);
    setCurrentStreamingMessage("");

    // Stream response
    await streamChat(
      updatedMessages,
      undefined, // Use default model
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
        setTotalTurns((t) => t + 1);
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
              <span>-</span>
              <span className="capitalize">{challenge?.difficulty}</span>
            </div>
          </div>
        </div>
        <button
          type="button"
          className="rounded-lg bg-foreground px-4 py-2 text-xs font-medium text-background transition-opacity hover:opacity-90"
        >
          Submit solution
        </button>
      </header>

      {/* Efficiency stats */}
      <div className="border-b border-border px-6 py-2">
        <ScoreBar
          turns={totalTurns}
          tokens={totalTokens}
          elapsedSec={elapsed}
        />
      </div>

      {/* Main content: left = description, right = chat */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Challenge description */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border overflow-y-auto">
          <div className="p-6">
            <h2 className="text-sm font-semibold mb-3">Challenge</h2>
            <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap mb-4">
              {challenge?.description}
            </p>
            {challenge?.embed_url && (
              <div className="rounded-lg border border-border overflow-hidden bg-muted/20">
                <iframe
                  src={challenge.embed_url}
                  title="Challenge reference"
                  className="w-full h-[320px] border-0 rounded-lg"
                  sandbox="allow-scripts allow-same-origin"
                />
              </div>
            )}
            {challenge?.image_url && !challenge?.embed_url && (
              <div className="rounded-lg border border-border overflow-hidden bg-muted/20">
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

            {/* Your output — v0-style panel with Preview / Code toggle */}
            <div className="mt-8 pt-6 border-t border-border">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold">Your output</h2>
                <div
                  className="inline-flex rounded-lg border border-border bg-muted/30 p-0.5"
                  role="tablist"
                >
                  <button
                    type="button"
                    onClick={() => setOutputView("preview")}
                    className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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
                    className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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
                  <div className="min-h-[200px] bg-muted/20 flex items-center justify-center">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={OUTPUT_PREVIEW_IMAGE}
                      alt="Your rendered output"
                      className="w-full max-h-[400px] object-contain object-top"
                    />
                  </div>
                ) : (
                  <pre className="p-4 overflow-auto max-h-[400px] m-0 text-xs font-mono text-foreground/90 whitespace-pre">
                    <code>{OUTPUT_SOURCE_PLACEHOLDER}</code>
                  </pre>
                )}
              </div>
            </div>
          </div>
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
                      Ask Claude Code for help with this challenge
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
                    {/* Message Content */}
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
