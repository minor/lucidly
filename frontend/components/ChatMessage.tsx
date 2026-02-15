"use client";

import { CheckCircle, XCircle, Code, Eye, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";

interface CodePreviewTabsProps {
  code: string;
}

function CodePreviewTabs({ code }: CodePreviewTabsProps) {
  const [activeTab, setActiveTab] = useState<"code" | "preview">("preview");

  return (
    <div className="flex flex-col">
      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab("preview")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2 text-xs font-medium transition-colors cursor-pointer ${
            activeTab === "preview"
              ? "border-accent text-accent"
              : "border-transparent text-muted hover:text-foreground"
          }`}
        >
          <Eye className="h-3.5 w-3.5" />
          Preview
        </button>
        <button
          onClick={() => setActiveTab("code")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2 text-xs font-medium transition-colors cursor-pointer ${
            activeTab === "code"
              ? "border-accent text-accent"
              : "border-transparent text-muted hover:text-foreground"
          }`}
        >
          <Code className="h-3.5 w-3.5" />
          Code
        </button>
      </div>

      {activeTab === "preview" ? (
        <div className="relative aspect-video w-full bg-white">
          <iframe
            srcDoc={code}
            className="absolute inset-0 h-full w-full border-0"
            sandbox="allow-scripts"
            title="Preview"
          />
        </div>
      ) : (
        <pre className="border-0 rounded-none m-0 p-4 overflow-x-auto">
          <code className="text-xs">{code}</code>
        </pre>
      )}
    </div>
  );
}

/** Derive a short summary from generated code for the chat bubble (no full code in chat). */
function deriveSummary(generatedCode: string): string {
  const trimmed = generatedCode.trim();
  const lower = trimmed.toLowerCase();
  if (lower.startsWith("<!doctype html") || lower.startsWith("<html")) {
    return "Generated a full HTML page for the output panel.";
  }
  if (trimmed.length > 0) {
    return "Generated code for the output panel.";
  }
  return "Response ready.";
}

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  generatedCode?: string;
  accuracy?: number;
  testResults?: boolean[];
  turnNumber?: number;
  tokens?: number;
  /** Override label for user role (e.g. "Agent" on benchmark watch page) */
  userLabel?: string;
  /** When true, show thinking trace (Planning → Generating code) with spinner */
  isAssistantLoading?: boolean;
  /** Optional one-line summary when assistant is done; otherwise derived from generatedCode */
  summary?: string;
  /** When true, do not render the Generated Output block (e.g. code lives only in main output panel) */
  hideGeneratedOutput?: boolean;
}

export function ChatMessage({
  role,
  content,
  generatedCode,
  accuracy,
  testResults,
  turnNumber,
  tokens,
  userLabel,
  isAssistantLoading,
  summary,
  hideGeneratedOutput,
}: ChatMessageProps) {
  const isUser = role === "user";

  // Assistant loading: "Planning steps" for ~20s, then "Generating code" for the rest (no cycling)
  const [loadingPhase, setLoadingPhase] = useState<0 | 1>(0);
  useEffect(() => {
    if (!isAssistantLoading) return;
    setLoadingPhase(0);
    const id = window.setTimeout(() => setLoadingPhase(1), 20_000);
    return () => clearTimeout(id);
  }, [isAssistantLoading]);

  const loadingTrace =
    loadingPhase === 0
      ? "Planning steps..."
      : "Generating code...";

  // Assistant done: show summary (or derive from code); never full code in chat
  const doneSummary =
    summary ?? (generatedCode ? deriveSummary(generatedCode) : "Response ready.");

  const messageContent = isUser
    ? content
    : isAssistantLoading
      ? loadingTrace
      : content
        ? doneSummary
        : "";

  return (
    <div className="py-3 border-b border-border/50 last:border-b-0">
      {/* Role label — IDE-style */}
      <div className="flex items-center gap-2 text-xs text-muted mb-1.5">
        {isUser ? (
          <span>{userLabel ?? "You"}</span>
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

      {/* Message text — user prompt, or assistant: loading trace then summary (no full code) */}
      <div
        className={`text-sm leading-relaxed ${
          isUser ? "text-foreground" : "text-muted-foreground"
        }`}
      >
        <div className="flex items-start gap-2">
          {!isUser && isAssistantLoading && (
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-accent mt-0.5" />
          )}
          <p className="whitespace-pre-wrap">{messageContent}</p>
        </div>
      </div>

      {/* Code output (hidden when code is shown in main output panel, e.g. agent run) */}
      {generatedCode && !hideGeneratedOutput && (
        <div className="mt-3 rounded-lg border border-border bg-code-bg overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
            <span className="text-xs font-medium text-muted">
              Generated Output
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

          {/* Toggle between Code and Preview if it looks like HTML */}
          {generatedCode.trim().toLowerCase().startsWith("<!doctype html") ||
          generatedCode.trim().toLowerCase().startsWith("<html") ? (
            <CodePreviewTabs code={generatedCode} />
          ) : (
            <pre className="border-0 rounded-none m-0 p-3">
              <code className="text-xs">{generatedCode}</code>
            </pre>
          )}
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
