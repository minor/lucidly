"use client";

import { useState, useEffect, useRef } from "react";
import { Search, X, Loader2, ExternalLink, AlertCircle } from "lucide-react";
import { searchLinearIssues, generateChallengeFromIssue } from "@/lib/api";
import { OAuthConnectButton } from "./OAuthConnectButton";
import type { LinearIssue, GeneratedChallenge } from "@/lib/types";
import { useIntegrationStatus } from "@/hooks/useIntegrationStatus";

interface Props {
  onImport: (challenge: GeneratedChallenge) => void;
  onClose: () => void;
}

export function LinearImportModal({ onImport, onClose }: Props) {
  const { status, loading: statusLoading, connectProvider } = useIntegrationStatus();
  const [query, setQuery] = useState("");
  const [issues, setIssues] = useState<LinearIssue[]>([]);
  const [searching, setSearching] = useState(false);
  const [generating, setGenerating] = useState<string | null>(null); // issue id being generated
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Auto-search when Linear is connected
  useEffect(() => {
    if (!status.linear) return;
    if (debounceRef.current !== undefined) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      setError(null);
      try {
        const results = await searchLinearIssues(query);
        setIssues(results);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => { if (debounceRef.current !== undefined) clearTimeout(debounceRef.current); };
  }, [query, status.linear]);

  const handleSelect = async (issue: LinearIssue) => {
    setGenerating(issue.id);
    setError(null);
    try {
      const challenge = await generateChallengeFromIssue(issue.id);
      onImport(challenge);
      onClose();
    } catch (e) {
      setError((e as Error).message);
      setGenerating(null);
    }
  };

  const needsLinear = !status.linear;
  const needsGitHub = status.linear && !status.github;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-xl border border-border bg-background shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">Import from Linear</h2>
          <button onClick={onClose} className="text-muted hover:text-foreground cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Connect prompts */}
          {!statusLoading && needsLinear && (
            <div className="rounded-lg border border-border p-4 space-y-3">
              <p className="text-sm text-muted">Connect your Linear account to browse issues.</p>
              <OAuthConnectButton
                provider="linear"
                connected={false}
                onConnect={() => connectProvider("linear")}
                label="Linear"
              />
            </div>
          )}

          {!statusLoading && needsGitHub && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                <p className="text-sm text-muted">
                  Connect GitHub to auto-import test cases from linked PRs. You can skip this and test cases will be AI-generated.
                </p>
              </div>
              <OAuthConnectButton
                provider="github"
                connected={false}
                onConnect={() => connectProvider("github")}
                label="GitHub"
              />
            </div>
          )}

          {/* Search */}
          {status.linear && (
            <>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search issues…"
                  className="w-full rounded-lg border border-input-border bg-input pl-9 pr-4 py-2.5 text-sm focus:border-accent focus:outline-none"
                  autoFocus
                />
              </div>

              {error && (
                <p className="text-xs text-red-400">{error}</p>
              )}

              {/* Issue list */}
              <div className="max-h-72 overflow-y-auto space-y-1">
                {searching && (
                  <div className="flex justify-center py-6">
                    <Loader2 className="h-5 w-5 animate-spin text-muted" />
                  </div>
                )}
                {!searching && issues.length === 0 && query && (
                  <p className="text-center text-sm text-muted py-6">No issues found</p>
                )}
                {!searching && issues.map((issue) => (
                  <button
                    key={issue.id}
                    onClick={() => handleSelect(issue)}
                    disabled={generating === issue.id}
                    className="w-full flex items-start gap-3 rounded-lg border border-border px-4 py-3 text-left hover:border-accent hover:bg-accent/5 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted font-mono shrink-0">{issue.identifier}</span>
                        <span className="text-sm font-medium truncate">{issue.title}</span>
                      </div>
                      {issue.description && (
                        <p className="text-xs text-muted mt-0.5 line-clamp-2">{issue.description}</p>
                      )}
                    </div>
                    {generating === issue.id ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted shrink-0 mt-0.5" />
                    ) : (
                      <ExternalLink className="h-3.5 w-3.5 text-muted shrink-0 mt-0.5" />
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
