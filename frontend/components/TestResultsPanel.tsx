"use client";

import { Loader2, FlaskConical, Code, CheckCircle2, XCircle } from "lucide-react";
import type { TestCaseResult } from "@/lib/api";

interface Props {
  results: TestCaseResult[] | null;
  running: boolean;
  tab: "results" | "code";
  onTabChange: (tab: "results" | "code") => void;
  latestCode?: string;
}

export function TestResultsPanel({ results, running, tab, onTabChange, latestCode }: Props) {
  const passedCount = results?.filter((r) => r.passed).length ?? 0;
  const totalCount = results?.length ?? 0;
  const allPassed = totalCount > 0 && passedCount === totalCount;

  return (
    <>
      {/* Tab bar */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2 shrink-0">
        <div className="flex items-center gap-1">
          <button
            onClick={() => onTabChange("results")}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
              tab === "results" ? "bg-accent/10 text-accent" : "text-muted hover:text-foreground"
            }`}
          >
            <FlaskConical className="h-3 w-3" />
            Tests
          </button>
          <button
            onClick={() => onTabChange("code")}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
              tab === "code" ? "bg-accent/10 text-accent" : "text-muted hover:text-foreground"
            }`}
          >
            <Code className="h-3 w-3" />
            Code
          </button>
        </div>
        {results && (
          <span className={`text-xs font-medium ${allPassed ? "text-green-500" : "text-red-400"}`}>
            {passedCount}/{totalCount} passed
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {running ? (
          <div className="flex items-center justify-center h-full gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-muted" />
            <span className="text-sm text-muted">Running tests…</span>
          </div>
        ) : tab === "results" && results ? (
          <div className="p-4 space-y-2">
            {/* Summary banner */}
            <div
              className={`rounded-lg px-3 py-2 text-xs font-medium ${
                allPassed ? "bg-green-500/10 text-green-500" : "bg-red-400/10 text-red-400"
              }`}
            >
              {allPassed ? "✓ All tests passed!" : `✗ ${totalCount - passedCount} test(s) failed`}
            </div>

            {/* Individual results */}
            {results.map((tc, i) => (
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
                  <span className="font-mono text-foreground truncate">{tc.name ?? tc.input}</span>
                </div>
                {!tc.passed && (
                  <div className="ml-5 mt-1 space-y-0.5 text-xs font-mono">
                    {tc.error ? (
                      <div className="text-red-400">Error: {tc.error}</div>
                    ) : (
                      <>
                        <div className="text-muted">
                          Expected: <span className="text-green-500">{tc.expected}</span>
                        </div>
                        <div className="text-muted">
                          Got: <span className="text-red-400">{tc.actual}</span>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : tab === "code" && latestCode ? (
          <pre className="h-full overflow-auto p-4 bg-code-bg text-xs font-mono">
            <code>{latestCode}</code>
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full">
            <span className="text-sm text-muted">No test results yet</span>
          </div>
        )}
      </div>
    </>
  );
}
