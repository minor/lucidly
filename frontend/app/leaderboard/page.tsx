"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  ArrowLeft, 
  ArrowUpDown, 
  ArrowUp, 
  ArrowDown,
  Trophy,
  Zap,
  Clock,
  RefreshCw,
  Coins,
  DollarSign,
  Activity
} from "lucide-react";

// Removed dummy data generator and hardcoded CHALLENGES

import { getChallenges, getLeaderboard } from "@/lib/api";
import type { Challenge, LeaderboardEntry as ApiLeaderboardEntry } from "@/lib/types";

type SortKey = "composite_score" | "accuracy" | "time_seconds" | "total_turns" | "total_tokens" | "total_cost";
type SortDirection = "asc" | "desc";

export default function LeaderboardPage() {
  const router = useRouter();
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [selectedChallengeId, setSelectedChallengeId] = useState("");
  const [entries, setEntries] = useState<ApiLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");

  // Fetch challenges on mount
  useEffect(() => {
    getChallenges().then(data => {
      setChallenges(data);
      if (data.length > 0) {
        setSelectedChallengeId(data[0].id);
      }
    }).catch(err => console.error("Failed to load challenges", err));
  }, []);

  // Fetch leaderboard when challenge changes
  useEffect(() => {
    if (!selectedChallengeId) return;
    
    setLoading(true);
    setEntries([]);
    
    getLeaderboard({ challenge_id: selectedChallengeId })
      .then((data) => {
        setEntries(Array.isArray(data) ? data : []);
      })
      .catch(err => {
        console.error("Failed to load leaderboard", err);
        setEntries([]);
      })
      .finally(() => setLoading(false));
  }, [selectedChallengeId]);

  const METRIC_SORT_DIRECTIONS: Record<string, SortDirection> = {
    rank: "asc", 
    composite_score: "desc",
    accuracy: "desc",
    time_seconds: "asc",
    total_turns: "asc",
    total_tokens: "asc",
    total_cost: "asc",
  };

  // Client-side sorting of fetched results
  const sortedEntries = useMemo(() => {
    return [...entries].sort((a, b) => {
      // Handle missing keys safely
      const valA = (a as any)[sortKey] ?? 0;
      const valB = (b as any)[sortKey] ?? 0;
      
      const direction = METRIC_SORT_DIRECTIONS[sortKey] || "desc";
      
      if (valA < valB) return direction === "asc" ? -1 : 1;
      if (valA > valB) return direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [entries, sortKey]);

  const handleSort = (key: string) => {
      // Cast to SortKey if valid
      setSortKey(key as SortKey);
  };

  const getSortIcon = (key: SortKey) => {
    if (sortKey !== key) return <ArrowUpDown className="h-3 w-3 opacity-30" />;
    
    // Always show the fixed direction arrow for the active metric
    const direction = METRIC_SORT_DIRECTIONS[key];
    return direction === "asc" ? (
      <ArrowUp className="h-3 w-3 text-foreground" />
    ) : (
      <ArrowDown className="h-3 w-3 text-foreground" />
    );
  };

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      {/* Header */}
      <header className="flex items-center gap-4 border-b border-border px-8 py-4">
        <button
          onClick={() => router.push("/")}
          className="text-muted hover:text-foreground transition-colors p-2 rounded-full hover:bg-muted/10 cursor-pointer"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-2">
          <Trophy className="h-6 w-6 text-accent" />
          <h1 className="text-xl font-bold tracking-tight">Leaderboard</h1>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto p-8">
        <div className="mx-auto max-w-5xl">
          {/* Controls */}
          <div className="mb-8 flex items-center justify-between">
            <div className="flex flex-col gap-2">
              <label htmlFor="challenge-select" className="text-sm font-medium text-muted">
                Select Challenge
              </label>
              <select
                id="challenge-select"
                value={selectedChallengeId}
                onChange={(e) => setSelectedChallengeId(e.target.value)}
                className="h-10 w-[300px] rounded-lg border border-border bg-card px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              >
                {challenges.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="rounded-xl border border-border bg-card overflow-auto shadow-sm max-h-[600px]">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="sticky top-0 z-10">
                <tr className="border-b border-border bg-card">
                  <th className="px-6 py-4 font-medium text-muted w-16">#</th>
                  <th className="px-6 py-4 font-medium text-muted w-1/4">Name</th>
                  
                  {/* Sortable Headers */}
                  {[
                    { key: "composite_score", label: "Score", icon: Zap },
                    { key: "accuracy", label: "Accuracy", icon: Activity },
                    { key: "time_seconds", label: "Time", icon: Clock },
                    { key: "total_turns", label: "Turns", icon: RefreshCw },
                    { key: "total_tokens", label: "Tokens", icon: Coins },
                    { key: "total_cost", label: "Cost", icon: DollarSign },
                  ].map(({ key, label, icon: Icon }) => (
                    <th
                      key={key}
                      className="px-6 py-4 font-medium text-muted cursor-pointer hover:bg-muted/10 transition-colors select-none"
                      onClick={() => handleSort(key as SortKey)}
                    >
                      <div className="flex items-center gap-2">
                        <Icon className="h-3.5 w-3.5" />
                        <span>{label}</span>
                        {getSortIcon(key as SortKey)}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-muted">
                      Loading…
                    </td>
                  </tr>
                ) : sortedEntries.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-muted">
                      No entries yet. Be the first to submit a score!
                    </td>
                  </tr>
                ) : (
                  sortedEntries.map((entry, index) => (
                    <tr
                      key={entry.id || index}
                      className="border-b border-border last:border-0 hover:bg-muted/5 transition-colors"
                    >
                      <td className="px-6 py-4 text-muted font-mono">{index + 1}</td>
                      <td className="px-6 py-4 font-medium">{entry.username}</td>
                      
                      {/* Metrics */}
                      <td className="px-6 py-4 font-mono font-bold text-accent">
                        {entry.composite_score}
                      </td>
                      <td className="px-6 py-4 font-mono">
                        <div className="flex items-center gap-2">
                          <div
                            className={`h-1.5 w-1.5 rounded-full ${
                              (entry.accuracy || 0) >= 0.8
                                ? "bg-green-500"
                                : (entry.accuracy || 0) >= 0.5
                                ? "bg-yellow-500"
                                : "bg-red-500"
                            }`}
                          />
                          {Math.round((entry.accuracy || 0) * 100)}%
                        </div>
                      </td>
                      <td className="px-6 py-4 font-mono text-muted">
                        {formatTime(entry.time_seconds || 0)}
                      </td>
                      <td className="px-6 py-4 font-mono text-muted">
                        {entry.total_turns}
                      </td>
                      <td className="px-6 py-4 font-mono text-muted">
                        {(entry.total_tokens || 0).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 font-mono text-muted">
                        ${(entry.total_cost || 0).toFixed(4)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
