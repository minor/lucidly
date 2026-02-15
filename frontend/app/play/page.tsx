"use client";

import { useEffect, useState } from "react";
import { getChallenges } from "@/lib/api";
import { ChallengeCard } from "@/components/ChallengeCard";
import type { Challenge } from "@/lib/types";
import { Loader2, Filter } from "lucide-react";

const CATEGORIES = ["all", "ui", "function", "debug", "data", "system"];
const DIFFICULTIES = ["all", "easy", "medium", "hard"];

export default function PlayPage() {
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState("all");
  const [difficulty, setDifficulty] = useState("all");

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    getChallenges({
      category: category === "all" ? undefined : category,
      difficulty: difficulty === "all" ? undefined : difficulty,
    })
      .then((data) => {
        if (!ignore) setChallenges(data);
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
  }, [category, difficulty]);

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">
          Challenges
        </h1>
        <p className="mt-2 text-sm text-muted">
          Select a challenge to begin your prompting session.
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Filter className="h-4 w-4 text-muted" />
        <div className="flex gap-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${
                category === cat
                  ? "bg-foreground text-background"
                  : "bg-card border border-border text-muted hover:text-foreground"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
        <div className="h-4 w-px bg-border" />
        <div className="flex gap-1">
          {DIFFICULTIES.map((diff) => (
            <button
              key={diff}
              onClick={() => setDifficulty(diff)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${
                difficulty === diff
                  ? "bg-foreground text-background"
                  : "bg-card border border-border text-muted hover:text-foreground"
              }`}
            >
              {diff}
            </button>
          ))}
        </div>
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
      ) : challenges.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <p className="text-sm text-muted">
            No challenges found with the current filters.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {challenges.map((challenge) => (
            <ChallengeCard key={challenge.id} challenge={challenge} />
          ))}
        </div>
      )}
    </div>
  );
}
