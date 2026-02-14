"use client";

import { User, Bot, CheckCircle, XCircle } from "lucide-react";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  generatedCode?: string;
  accuracy?: number;
  testResults?: boolean[];
  turnNumber?: number;
  tokens?: number;
}

export function ChatMessage({
  role,
  content,
  generatedCode,
  accuracy,
  testResults,
  turnNumber,
  tokens,
}: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3 py-4 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-foreground text-background" : "bg-accent/20 text-accent"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div
        className={`flex-1 space-y-3 ${isUser ? "text-right" : "text-left"}`}
      >
        {/* Role label */}
        <div className="flex items-center gap-2 text-xs text-muted">
          {isUser ? (
            <span className="ml-auto">You</span>
          ) : (
            <>
              <span>Lucidly AI</span>
              {turnNumber && (
                <span className="text-muted/50">Turn {turnNumber}</span>
              )}
              {tokens !== undefined && (
                <span className="text-muted/50">{tokens} tokens</span>
              )}
            </>
          )}
        </div>

        {/* Message text */}
        <div
          className={`inline-block rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-foreground text-background"
              : "bg-card border border-border"
          }`}
        >
          <p className="whitespace-pre-wrap">{content}</p>
        </div>

        {/* Code output */}
        {generatedCode && (
          <div className="rounded-xl border border-border bg-code-bg overflow-hidden">
            <div className="flex items-center justify-between border-b border-border px-4 py-2">
              <span className="text-xs font-medium text-muted">
                Generated Code
              </span>
              {accuracy !== undefined && (
                <span
                  className={`text-xs font-medium ${
                    accuracy >= 0.8
                      ? "text-success"
                      : accuracy >= 0.5
                        ? "text-accent"
                        : "text-error"
                  }`}
                >
                  {Math.round(accuracy * 100)}% accuracy
                </span>
              )}
            </div>
            <pre className="border-0 rounded-none m-0">
              <code className="text-xs">{generatedCode}</code>
            </pre>
          </div>
        )}

        {/* Test results */}
        {testResults && testResults.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {testResults.map((passed, i) => (
              <div
                key={i}
                className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${
                  passed
                    ? "bg-success/10 text-success"
                    : "bg-error/10 text-error"
                }`}
              >
                {passed ? (
                  <CheckCircle className="h-3 w-3" />
                ) : (
                  <XCircle className="h-3 w-3" />
                )}
                Test {i + 1}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
