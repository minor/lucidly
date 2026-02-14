"use client";

import { CheckCircle, XCircle } from "lucide-react";

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
    <div className="py-3 border-b border-border/50 last:border-b-0">
      {/* Role label only (no avatar) — IDE-style */}
      <div className="flex items-center gap-2 text-xs text-muted mb-1.5">
        {isUser ? (
          <span>You</span>
        ) : (
          <>
            <span>Assistant</span>
            {turnNumber != null && (
              <span className="text-muted/70">Turn {turnNumber}</span>
            )}
            {tokens != null && (
              <span className="text-muted/70">{tokens} tokens</span>
            )}
          </>
        )}
      </div>

      {/* Message text — plain block, no bubble */}
      <div
        className={`text-sm leading-relaxed ${
          isUser ? "text-foreground" : "text-muted-foreground"
        }`}
      >
        <p className="whitespace-pre-wrap">{content}</p>
      </div>

      {/* Code output */}
      {generatedCode && (
        <div className="mt-3 rounded-lg border border-border bg-code-bg overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
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
                {Math.round(accuracy * 100)}%
              </span>
            )}
          </div>
          <pre className="border-0 rounded-none m-0 p-3">
            <code className="text-xs">{generatedCode}</code>
          </pre>
        </div>
      )}

      {/* Test results */}
      {testResults && testResults.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {testResults.map((passed, i) => (
            <div
              key={i}
              className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
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
  );
}
