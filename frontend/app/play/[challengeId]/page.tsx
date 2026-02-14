"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  createSession,
  submitPrompt,
  completeSession,
  getChallenge,
} from "@/lib/api";
import { PromptInput } from "@/components/PromptInput";
import { ChatMessage } from "@/components/ChatMessage";
import { ScoreBar } from "@/components/ScoreBar";
import type { Challenge, PromptResponse, Scores } from "@/lib/types";
import {
  Loader2,
  CheckCircle,
  ArrowLeft,
  Trophy,
} from "lucide-react";

interface ChatEntry {
  role: "user" | "assistant";
  content: string;
  generatedCode?: string;
  accuracy?: number;
  testResults?: boolean[];
  turnNumber?: number;
  tokens?: number;
}

export default function ChallengePage() {
  const params = useParams();
  const router = useRouter();
  const challengeId = params.challengeId as string;

  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [chat, setChat] = useState<ChatEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const [scores, setScores] = useState<Scores | null>(null);

  // Metrics
  const [totalTokens, setTotalTokens] = useState(0);
  const [totalTurns, setTotalTurns] = useState(0);
  const [lastAccuracy, setLastAccuracy] = useState(0);
  const startTimeRef = useRef<number>(Date.now());
  const [elapsed, setElapsed] = useState(0);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Timer
  useEffect(() => {
    if (completed) return;
    const interval = setInterval(() => {
      setElapsed((Date.now() - startTimeRef.current) / 1000);
    }, 1000);
    return () => clearInterval(interval);
  }, [completed]);

  // Initialize session
  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const challengeData = await getChallenge(challengeId);
        if (ignore) return;
        setChallenge(challengeData);

        const { session_id } = await createSession(challengeId);
        if (ignore) return;
        setSessionId(session_id);
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

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  const handleSubmit = useCallback(
    async (prompt: string) => {
      if (!sessionId || loading || completed) return;

      setChat((prev) => [...prev, { role: "user", content: prompt }]);
      setLoading(true);
      setError(null);

      try {
        const response: PromptResponse = await submitPrompt(
          sessionId,
          prompt
        );

        setChat((prev) => [
          ...prev,
          {
            role: "assistant",
            content: response.response_text,
            generatedCode: response.generated_code,
            accuracy: response.accuracy,
            testResults: response.test_results ?? undefined,
            turnNumber: response.turn_number,
            tokens: response.prompt_tokens + response.response_tokens,
          },
        ]);

        setTotalTokens(
          (prev) =>
            prev + response.prompt_tokens + response.response_tokens
        );
        setTotalTurns((prev) => prev + 1);
        setLastAccuracy(response.accuracy);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [sessionId, loading, completed]
  );

  const handleComplete = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await completeSession(sessionId);
      setScores(result.scores);
      setCompleted(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

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
        <div className="flex items-center gap-3">
          {!completed && totalTurns > 0 && (
            <button
              onClick={handleComplete}
              disabled={loading}
              className="flex items-center gap-1.5 rounded-lg bg-foreground px-4 py-2 text-xs font-medium text-background transition-opacity hover:opacity-80 disabled:opacity-50"
            >
              <CheckCircle className="h-3.5 w-3.5" />
              Complete
            </button>
          )}
        </div>
      </header>

      {/* Efficiency stats at top */}
      <div className="border-b border-border px-6 py-2">
        <ScoreBar
          accuracy={lastAccuracy}
          turns={totalTurns}
          tokens={totalTokens}
          elapsedSec={elapsed}
          compositeScore={scores?.composite_score}
        />
      </div>

      {/* Main content: left = description + output, right = chat */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Challenge description and output */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border">
          {/* Top left: Challenge description and image/visual */}
          <div className="border-b border-border p-5 overflow-y-auto">
            <h2 className="text-sm font-semibold mb-2">Challenge</h2>
            <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap mb-4">
              {challenge?.description}
            </p>
            {challenge?.image_url && (
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
          </div>

          {/* Bottom left: Output (hard-coded for now) */}
          <div className="flex-1 min-h-0 flex flex-col p-5 overflow-hidden">
            <h2 className="text-sm font-semibold mb-2">Output</h2>
            <div className="flex-1 rounded-lg border border-border bg-code-bg p-4 overflow-auto">
              <pre className="text-xs font-mono text-muted whitespace-pre-wrap">
                {`// Your generated output will appear here.
// For now this is a placeholder.

// Example (landing page):
// <!DOCTYPE html>
// <html>...</html>

// Example (snake game):
// Canvas + JS game loop

// Example (NYT scraper):
// [{"title": "...", "url": "..."}, ...]`}
              </pre>
            </div>
          </div>
        </div>

        {/* Right: Chat panel (IDE-style, no avatars) */}
        <div className="flex flex-col w-[420px] shrink-0">
          <div className="flex-1 overflow-y-auto px-4 py-4">
            {chat.map((entry, i) => (
              <ChatMessage key={i} {...entry} />
            ))}
            {loading && (
              <div className="flex items-center gap-2 py-4 text-sm text-muted">
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </div>
            )}
            {error && (
              <div className="my-4 rounded-lg border border-error/20 bg-error/5 p-3">
                <p className="text-sm text-error">{error}</p>
              </div>
            )}
            {completed && scores && (
              <div className="my-4 rounded-xl border border-accent/30 bg-accent/5 p-4 text-center">
                <Trophy className="mx-auto h-6 w-6 text-accent mb-2" />
                <p className="text-lg font-bold font-mono text-accent">
                  {scores.composite_score}
                  <span className="text-xs font-normal text-muted"> / 1000</span>
                </p>
                <button
                  onClick={() => router.push("/play")}
                  className="mt-3 rounded-lg bg-foreground px-4 py-1.5 text-xs font-medium text-background hover:opacity-80"
                >
                  Try Another Challenge
                </button>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          {!completed && (
            <div className="border-t border-border p-4">
              <PromptInput
                onSubmit={handleSubmit}
                loading={loading}
                placeholder="Write your prompt..."
                disabled={!sessionId}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
