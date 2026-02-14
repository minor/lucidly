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
  Info,
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
  const [showInfo, setShowInfo] = useState(true);

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

      // Add user message
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
          <button
            onClick={() => setShowInfo(!showInfo)}
            className={`rounded-lg p-2 transition-colors ${
              showInfo
                ? "bg-accent/10 text-accent"
                : "text-muted hover:text-foreground"
            }`}
          >
            <Info className="h-4 w-4" />
          </button>
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

      {/* Score bar */}
      <div className="border-b border-border px-6 py-2">
        <ScoreBar
          accuracy={lastAccuracy}
          turns={totalTurns}
          tokens={totalTokens}
          elapsedSec={elapsed}
          compositeScore={scores?.composite_score}
        />
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat area */}
        <div className="flex flex-1 flex-col">
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {/* Challenge info card */}
            {showInfo && challenge && (
              <div className="mb-6 rounded-xl border border-border bg-card p-5">
                <h2 className="text-sm font-semibold mb-2">
                  Challenge Description
                </h2>
                <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap">
                  {challenge.description}
                </p>
                {challenge.test_suite && challenge.test_suite.length > 0 && (
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
                          <span className="text-muted">Input:</span>{" "}
                          {tc.input}
                          <br />
                          <span className="text-muted">Expected:</span>{" "}
                          {tc.expected_output}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Chat messages */}
            {chat.map((entry, i) => (
              <ChatMessage key={i} {...entry} />
            ))}

            {/* Loading indicator */}
            {loading && (
              <div className="flex items-center gap-2 py-4 text-sm text-muted">
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </div>
            )}

            {/* Completion card */}
            {completed && scores && (
              <div className="my-6 rounded-xl border border-accent/30 bg-accent/5 p-6 text-center">
                <Trophy className="mx-auto h-8 w-8 text-accent mb-3" />
                <h2 className="text-xl font-serif font-semibold mb-1">
                  Challenge Complete!
                </h2>
                <p className="text-3xl font-bold font-mono text-accent">
                  {scores.composite_score}
                  <span className="text-sm font-normal text-muted">
                    {" "}
                    / 1000
                  </span>
                </p>
                <div className="mt-4 flex justify-center gap-6 text-sm">
                  <div>
                    <p className="font-semibold font-mono">
                      {scores.accuracy_score}
                    </p>
                    <p className="text-xs text-muted">Accuracy</p>
                  </div>
                  <div>
                    <p className="font-semibold font-mono">
                      {scores.speed_score}
                    </p>
                    <p className="text-xs text-muted">Speed</p>
                  </div>
                  <div>
                    <p className="font-semibold font-mono">
                      {scores.token_score}
                    </p>
                    <p className="text-xs text-muted">Tokens</p>
                  </div>
                  <div>
                    <p className="font-semibold font-mono">
                      {scores.turn_score}
                    </p>
                    <p className="text-xs text-muted">Turns</p>
                  </div>
                </div>
                <button
                  onClick={() => router.push("/play")}
                  className="mt-6 rounded-lg bg-foreground px-6 py-2 text-sm font-medium text-background transition-opacity hover:opacity-80"
                >
                  Try Another Challenge
                </button>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="my-4 rounded-xl border border-error/20 bg-error/5 p-4 text-center">
                <p className="text-sm text-error">{error}</p>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Prompt input */}
          {!completed && (
            <div className="border-t border-border px-6 py-4">
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
