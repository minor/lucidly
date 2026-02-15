"use client";

import Link from "next/link";
import { Code, Layout, Bug, Database, Server, FileText } from "lucide-react";
import type { Challenge } from "@/lib/types";

const CATEGORY_ICONS: Record<string, typeof Code> = {
  function: Code,
  ui: Layout,
  debug: Bug,
  data: Database,
  system: Server,
  product: FileText,
};

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "bg-success/10 text-success",
  medium: "bg-accent/20 text-accent",
  hard: "bg-error/10 text-error",
};

interface ChallengeCardProps {
  challenge: Challenge;
}

export function ChallengeCard({ challenge }: ChallengeCardProps) {
  const Icon = CATEGORY_ICONS[challenge.category] || Code;
  const difficultyClass =
    DIFFICULTY_COLORS[challenge.difficulty] || "bg-muted/10 text-muted";

  return (
    <Link
      href={`/play/${challenge.id}`}
      className="card-hover group block rounded-2xl border border-border bg-card p-5 transition-all hover:border-accent/40"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent">
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${difficultyClass}`}
          >
            {challenge.difficulty}
          </span>
          <span className="rounded-full bg-background px-2.5 py-0.5 text-xs font-medium text-muted border border-border">
            {challenge.category}
          </span>
        </div>
      </div>
      <h3 className="text-base font-semibold text-foreground group-hover:text-accent transition-colors">
        {challenge.title}
      </h3>
      <p className="mt-1.5 text-sm text-muted leading-relaxed line-clamp-2">
        {challenge.description}
      </p>
    </Link>
  );
}
