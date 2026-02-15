"use client";

import { useState, useMemo } from "react";
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

// Mock Challenge Data (Should eventually come from API)
const CHALLENGES = [
  { id: "cpp-lockfree-stack", title: "Debug: Lock-Free Stack Race Conditions" },
  { id: "build-landing-page", title: "Build this UI: Landing Page" },
  { id: "fizzbuzz", title: "FizzBuzz" },
  { id: "two-sum", title: "Two Sum" },
  { id: "cpp-sum", title: "Sum of Two Integers (C++)" },
];

interface LeaderboardEntry {
  id: string;
  rank: number;
  name: string;
  challengeId: string;
  score: number;
  accuracy: number;
  timeSec: number;
  turns: number;
  tokens: number;
  cost: number;
  date: string;
}

// Dummy Data Generator
const generateDummyData = (challengeId: string): LeaderboardEntry[] => {
  const count = 10;
  return Array.from({ length: count }).map((_, i) => ({
    id: `entry-${i}`,
    rank: i + 1,
    name: "test", // User requested "test" for now
    challengeId,
    score: Math.floor(Math.random() * 50) + 50, // 50-100
    accuracy: Math.random() * 0.5 + 0.5, // 50-100%
    timeSec: Math.floor(Math.random() * 300) + 30, // 30s - 5m
    turns: Math.floor(Math.random() * 10) + 1,
    tokens: Math.floor(Math.random() * 5000) + 500,
    cost: Math.random() * 0.1,
    date: new Date().toISOString(),
  }));
};

type SortKey = keyof Omit<LeaderboardEntry, "id" | "challengeId" | "date" | "name">;
type SortDirection = "asc" | "desc";

export default function LeaderboardPage() {
  const router = useRouter();
  const [selectedChallengeId, setSelectedChallengeId] = useState(CHALLENGES[0].id);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  // Sort direction is now derived from the key, no state needed

  // In a real app, we'd fetch data here based on selectedChallengeId
  // For now, we generate stable dummy data based on the ID (re-generated on change simplifies this demo)
  const entries = useMemo(() => generateDummyData(selectedChallengeId), [selectedChallengeId]);

  // Fixed sort directions for each metric
  const METRIC_SORT_DIRECTIONS: Record<SortKey, SortDirection> = {
    rank: "asc",
    score: "desc",
    accuracy: "desc",
    timeSec: "asc",
    turns: "asc",
    tokens: "asc",
    cost: "asc",
  };

  const sortedEntries = useMemo(() => {
    return [...entries].sort((a, b) => {
      const aValue = a[sortKey];
      const bValue = b[sortKey];

      // Use the fixed direction for the current sort key
      const direction = METRIC_SORT_DIRECTIONS[sortKey];

      if (aValue < bValue) return direction === "asc" ? -1 : 1;
      if (aValue > bValue) return direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [entries, sortKey]);

  const handleSort = (key: SortKey) => {
    setSortKey(key);
    // Direction is implicitly handled by the updated sortedEntries logic
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
          className="text-muted hover:text-foreground transition-colors p-2 rounded-full hover:bg-muted/10"
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
                {CHALLENGES.map((c) => (
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
                <tr className="border-b border-border bg-muted/90 backdrop-blur-sm">
                  <th className="px-6 py-4 font-medium text-muted w-16">#</th>
                  <th className="px-6 py-4 font-medium text-muted w-1/4">Name</th>
                  
                  {/* Sortable Headers */}
                  {[
                    { key: "score", label: "Score", icon: Zap },
                    { key: "accuracy", label: "Accuracy", icon: Activity },
                    { key: "timeSec", label: "Time", icon: Clock },
                    { key: "turns", label: "Turns", icon: RefreshCw },
                    { key: "tokens", label: "Tokens", icon: Coins },
                    { key: "cost", label: "Cost", icon: DollarSign },
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
                {sortedEntries.map((entry, index) => (
                  <tr
                    key={entry.id}
                    className="border-b border-border last:border-0 hover:bg-muted/5 transition-colors"
                  >
                    <td className="px-6 py-4 text-muted font-mono">{index + 1}</td>
                    <td className="px-6 py-4 font-medium">{entry.name}</td>
                    
                    {/* Metrics */}
                    <td className="px-6 py-4 font-mono font-bold text-accent">
                      {entry.score}
                    </td>
                    <td className="px-6 py-4 font-mono">
                      <div className="flex items-center gap-2">
                        <div
                          className={`h-1.5 w-1.5 rounded-full ${
                            entry.accuracy >= 0.8
                              ? "bg-green-500"
                              : entry.accuracy >= 0.5
                              ? "bg-yellow-500"
                              : "bg-red-500"
                          }`}
                        />
                        {Math.round(entry.accuracy * 100)}%
                      </div>
                    </td>
                    <td className="px-6 py-4 font-mono text-muted">
                      {formatTime(entry.timeSec)}
                    </td>
                    <td className="px-6 py-4 font-mono text-muted">
                      {entry.turns}
                    </td>
                    <td className="px-6 py-4 font-mono text-muted">
                      {entry.tokens.toLocaleString()}
                    </td>
                    <td className="px-6 py-4 font-mono text-muted">
                      ${entry.cost.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
