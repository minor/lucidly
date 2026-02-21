"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Trophy,
  Zap,
  Clock,
  RefreshCw,
  Coins,
  DollarSign,
  Activity,
  ChevronLeft,
  ChevronRight,
  User,
  Hash,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";

import { getChallenges, getLeaderboard, getOverallLeaderboard } from "@/lib/api";
import { useUsername } from "@/hooks/useUsername";
import type {
  Challenge,
  LeaderboardEntry,
  OverallLeaderboardEntry,
  LeaderboardUserEntry,
} from "@/lib/types";

type SortKey =
  | "composite_score"
  | "accuracy"
  | "time_seconds"
  | "total_turns"
  | "total_tokens"
  | "total_cost";

const SORT_DIRECTION: Record<SortKey, "asc" | "desc"> = {
  composite_score: "desc",
  accuracy: "desc",
  time_seconds: "asc",
  total_turns: "asc",
  total_tokens: "asc",
  total_cost: "asc",
};

const PAGE_SIZE = 10;
const MAX_ENTRIES = 100;
const MAX_PAGES = MAX_ENTRIES / PAGE_SIZE;

export default function LeaderboardPage() {
  const { user } = useAuth0();
  const { username } = useUsername(user);

  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [selectedView, setSelectedView] = useState<string>("overall");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");

  const [overallEntries, setOverallEntries] = useState<OverallLeaderboardEntry[]>([]);
  const [questionEntries, setQuestionEntries] = useState<LeaderboardEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [userEntry, setUserEntry] = useState<LeaderboardUserEntry | null>(null);

  const isOverall = selectedView === "overall";

  useEffect(() => {
    getChallenges()
      .then((data) => setChallenges(data))
      .catch((err) => console.error("Failed to load challenges", err));
  }, []);

  const fetchData = useCallback(
    async (view: string, pageNum: number, sort: SortKey) => {
      setLoading(true);
      const offset = pageNum * PAGE_SIZE;

      try {
        if (view === "overall") {
          const res = await getOverallLeaderboard({
            limit: PAGE_SIZE,
            offset,
            username: username ?? undefined,
          });
          setOverallEntries(res.entries);
          setQuestionEntries([]);
          setTotalCount(res.total_count);
          setUserEntry(res.user_entry ?? null);
        } else {
          const res = await getLeaderboard({
            challenge_id: view,
            limit: PAGE_SIZE,
            offset,
            username: username ?? undefined,
            sort_by: sort,
          });
          setQuestionEntries(res.entries);
          setOverallEntries([]);
          setTotalCount(res.total_count);
          setUserEntry(res.user_entry ?? null);
        }
      } catch (err) {
        console.error("Failed to load leaderboard", err);
        setOverallEntries([]);
        setQuestionEntries([]);
        setTotalCount(0);
        setUserEntry(null);
      } finally {
        setLoading(false);
      }
    },
    [username],
  );

  useEffect(() => {
    fetchData(selectedView, page, sortKey);
  }, [selectedView, page, sortKey, fetchData]);

  const handleViewChange = (view: string) => {
    setSelectedView(view);
    setSortKey("composite_score");
    setPage(0);
  };

  const handleSort = (key: SortKey) => {
    setSortKey(key);
    setPage(0);
  };

  const getSortIcon = (key: SortKey) => {
    if (sortKey !== key)
      return <ArrowUpDown className="h-3 w-3 opacity-30" />;
    return SORT_DIRECTION[key] === "asc" ? (
      <ArrowUp className="h-3 w-3 text-foreground" />
    ) : (
      <ArrowDown className="h-3 w-3 text-foreground" />
    );
  };

  const totalPages = Math.min(Math.ceil(totalCount / PAGE_SIZE), MAX_PAGES);

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const isCurrentUser = (entryUsername: string) =>
    username != null && entryUsername === username;

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      {/* Header */}
      <header className="flex items-center justify-center px-4 sm:px-8 py-4 sm:py-5">
        <div className="flex items-center gap-2">
          <Trophy className="h-6 w-6 text-accent" />
          <h1 className="text-xl font-bold tracking-tight">Leaderboard</h1>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto p-4 sm:p-8">
        <div className="mx-auto max-w-5xl">
          {/* View Selector */}
          <div className="mb-6 sm:mb-8">
            <div className="flex flex-col gap-2">
              <label
                htmlFor="view-select"
                className="text-sm font-medium text-muted"
              >
                View
              </label>
              <select
                id="view-select"
                value={selectedView}
                onChange={(e) => handleViewChange(e.target.value)}
                className="h-10 w-full sm:w-[300px] rounded-lg border border-border bg-card px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="overall">Overall</option>
                {challenges.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Your Ranking Bar */}
          {username && userEntry && (
            <div className="mb-4 flex items-center gap-4 rounded-lg border border-accent/30 bg-accent/5 px-4 py-3 text-sm">
              <User className="h-4 w-4 text-accent shrink-0" />
              <span className="font-medium">Your Rank</span>
              <span className="font-mono font-bold text-accent">
                #{userEntry.rank}
              </span>
              <span className="text-muted">|</span>
              <span className="text-muted">Score</span>
              <span className="font-mono font-bold text-accent">
                {isOverall
                  ? userEntry.total_score ?? 0
                  : userEntry.composite_score ?? 0}
              </span>
              {isOverall && userEntry.challenges_completed != null && (
                <>
                  <span className="text-muted">|</span>
                  <span className="text-muted">Challenges</span>
                  <span className="font-mono font-semibold">
                    {userEntry.challenges_completed}
                  </span>
                </>
              )}
            </div>
          )}

          {/* Table */}
          <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead>
                <tr className="border-b border-border bg-card">
                  <th className="px-3 sm:px-6 py-3 sm:py-4 font-medium text-muted w-10 sm:w-16">
                    <div className="flex items-center gap-1.5">
                      <Hash className="h-3.5 w-3.5" />
                    </div>
                  </th>
                  <th className="px-3 sm:px-6 py-3 sm:py-4 font-medium text-muted">
                    Name
                  </th>
                  {isOverall ? (
                    <>
                      <th className="px-3 sm:px-6 py-3 sm:py-4 font-medium text-muted">
                        <div className="flex items-center gap-2">
                          <Zap className="h-3.5 w-3.5" />
                          <span>Total Score</span>
                        </div>
                      </th>
                      <th className="px-3 sm:px-6 py-3 sm:py-4 font-medium text-muted">
                        <div className="flex items-center gap-2">
                          <Activity className="h-3.5 w-3.5" />
                          <span>Challenges</span>
                        </div>
                      </th>
                    </>
                  ) : (
                    <>
                      {([
                        { key: "composite_score" as SortKey, label: "Score", icon: Zap },
                        { key: "accuracy" as SortKey, label: "Accuracy", icon: Activity },
                        { key: "time_seconds" as SortKey, label: "Time", icon: Clock },
                        { key: "total_turns" as SortKey, label: "Turns", icon: RefreshCw },
                        { key: "total_tokens" as SortKey, label: "Tokens", icon: Coins },
                        { key: "total_cost" as SortKey, label: "Cost", icon: DollarSign },
                      ] as const).map(({ key, label, icon: Icon }) => (
                        <th
                          key={key}
                          className="px-3 sm:px-6 py-3 sm:py-4 font-medium text-muted cursor-pointer hover:bg-muted/10 transition-colors select-none"
                          onClick={() => handleSort(key)}
                        >
                          <div className="flex items-center gap-2">
                            <Icon className="h-3.5 w-3.5" />
                            <span>{label}</span>
                            {getSortIcon(key)}
                          </div>
                        </th>
                      ))}
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td
                      colSpan={isOverall ? 4 : 8}
                      className="px-6 py-12 text-center text-muted"
                    >
                      Loading&hellip;
                    </td>
                  </tr>
                ) : isOverall && overallEntries.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-12 text-center text-muted">
                      No entries yet. Be the first to submit a score!
                    </td>
                  </tr>
                ) : !isOverall && questionEntries.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-muted">
                      No entries yet. Be the first to submit a score!
                    </td>
                  </tr>
                ) : isOverall ? (
                  overallEntries.map((entry) => {
                    const highlighted = isCurrentUser(entry.username);
                    return (
                      <tr
                        key={entry.username}
                        className={`border-b border-border last:border-0 transition-colors ${
                          highlighted
                            ? "bg-[#fff7ed]"
                            : "hover:bg-muted/5"
                        }`}
                      >
                        <td className="px-3 sm:px-6 py-3 sm:py-4 text-muted font-mono">
                          {entry.rank}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-medium">
                          {entry.username}
                          {highlighted && (
                            <span className="ml-2 text-xs text-accent font-normal">
                              (you)
                            </span>
                          )}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-mono font-bold text-accent">
                          {entry.total_score}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-mono text-muted">
                          {entry.challenges_completed}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  questionEntries.map((entry) => {
                    const highlighted = isCurrentUser(entry.username);
                    return (
                      <tr
                        key={entry.id || entry.username}
                        className={`border-b border-border last:border-0 transition-colors ${
                          highlighted
                            ? "bg-[#fff7ed]"
                            : "hover:bg-muted/5"
                        }`}
                      >
                        <td className="px-3 sm:px-6 py-3 sm:py-4 text-muted font-mono">
                          {entry.rank}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-medium">
                          {entry.username}
                          {highlighted && (
                            <span className="ml-2 text-xs text-accent font-normal">
                              (you)
                            </span>
                          )}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-mono font-bold text-accent">
                          {entry.composite_score}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-mono">
                          <div className="flex items-center gap-2">
                            <div
                              className={`h-1.5 w-1.5 rounded-full ${
                                (entry.accuracy || 0) >= 0.8
                                  ? "bg-green-500"
                                  : (entry.accuracy || 0) >= 0.5
                                    ? "bg-orange-500"
                                    : "bg-red-500"
                              }`}
                            />
                            {Math.round((entry.accuracy || 0) * 100)}%
                          </div>
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-mono text-muted">
                          {formatTime(entry.time_seconds || 0)}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-mono text-muted">
                          {entry.total_turns}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-mono text-muted">
                          {(entry.total_tokens || 0).toLocaleString()}
                        </td>
                        <td className="px-3 sm:px-6 py-3 sm:py-4 font-mono text-muted">
                          ${(entry.total_cost || 0).toFixed(4)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-sm disabled:opacity-30 hover:bg-muted/10 transition-colors cursor-pointer disabled:cursor-default"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              {Array.from({ length: totalPages }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setPage(i)}
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border text-sm font-medium transition-colors cursor-pointer ${
                    i === page
                      ? "border-accent bg-accent text-white"
                      : "border-border bg-card hover:bg-muted/10"
                  }`}
                >
                  {i + 1}
                </button>
              ))}

              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-sm disabled:opacity-30 hover:bg-muted/10 transition-colors cursor-pointer disabled:cursor-default"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
