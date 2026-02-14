"use client";

import { useEffect, useState } from "react";
import { getLeaderboard } from "@/lib/api";
import type { LeaderboardEntry } from "@/lib/types";
import { Loader2, Trophy, Medal, Bot } from "lucide-react";

export default function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    getLeaderboard({ limit: 50 })
      .then((data) => {
        if (!ignore) setEntries(data);
      })
      .catch((err) => {
        if (!ignore) setError(err.message);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, []);

  const getRankIcon = (rank: number) => {
    if (rank === 1)
      return <Trophy className="h-4 w-4 text-accent" />;
    if (rank <= 3)
      return <Medal className="h-4 w-4 text-muted" />;
    return (
      <span className="text-sm font-mono text-muted w-4 text-center">
        {rank}
      </span>
    );
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-3xl font-semibold tracking-tight">
          Leaderboard
        </h1>
        <p className="mt-2 text-sm text-muted">
          Top performers across all challenges.
        </p>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-muted" />
        </div>
      ) : error ? (
        <div className="rounded-xl border border-error/20 bg-error/5 p-6 text-center">
          <p className="text-sm text-error">{error}</p>
          <p className="mt-1 text-xs text-muted">
            Make sure the backend server is running on port 8000.
          </p>
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-10 text-center">
          <Trophy className="mx-auto h-10 w-10 text-muted/30 mb-4" />
          <p className="text-sm text-muted">
            No completed sessions yet. Be the first on the leaderboard!
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[3rem_1fr_10rem_5rem_5rem_5rem_5rem] gap-2 border-b border-border bg-background/50 px-4 py-3 text-xs font-medium uppercase tracking-wider text-muted">
            <span>#</span>
            <span>Player</span>
            <span>Challenge</span>
            <span className="text-right">Score</span>
            <span className="text-right">Accuracy</span>
            <span className="text-right">Turns</span>
            <span className="text-right">Tokens</span>
          </div>

          {/* Rows */}
          {entries.map((entry, i) => (
            <div
              key={i}
              className={`grid grid-cols-[3rem_1fr_10rem_5rem_5rem_5rem_5rem] gap-2 items-center px-4 py-3 text-sm ${
                i !== entries.length - 1 ? "border-b border-border" : ""
              } ${i < 3 ? "bg-accent/[0.03]" : ""}`}
            >
              <div className="flex items-center">{getRankIcon(i + 1)}</div>
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-medium truncate">{entry.username}</span>
                {entry.username.startsWith("agent:") && (
                  <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent">
                    <Bot className="h-2.5 w-2.5" />
                    Agent
                  </span>
                )}
              </div>
              <span className="text-muted truncate text-xs">
                {entry.challenge_title}
              </span>
              <span className="text-right font-mono font-semibold text-accent">
                {entry.composite_score}
              </span>
              <span className="text-right font-mono text-xs">
                {entry.accuracy_score}
              </span>
              <span className="text-right font-mono text-xs text-muted">
                {entry.total_turns}
              </span>
              <span className="text-right font-mono text-xs text-muted">
                {entry.total_tokens}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
