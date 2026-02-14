"use client";

import { User, Bot, CheckCircle, XCircle, Code, Eye } from "lucide-react";
import { useState } from "react";

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
          className={`flex items-center gap-2 border-b-2 px-4 py-2 text-xs font-medium transition-colors ${
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
          className={`flex items-center gap-2 border-b-2 px-4 py-2 text-xs font-medium transition-colors ${
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
              <span className="text-xs font-medium text-muted">Generated Output</span>
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
            {generatedCode.trim().startsWith("<!DOCTYPE html") || generatedCode.trim().startsWith("<html") ? (
               <CodePreviewTabs code={generatedCode} />
            ) : (
                <pre className="border-0 rounded-none m-0 p-4 overflow-x-auto">
                  <code className="text-xs">{generatedCode}</code>
                </pre>
            )}
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
