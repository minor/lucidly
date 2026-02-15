"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { Trophy, ArrowRight, Code, Layout, Bug, Database, FileText } from "lucide-react";

const CATEGORIES = [
  { label: "Function", icon: Code, count: 3 },
  { label: "UI", icon: Layout, count: 3 },
  { label: "Debug", icon: Bug, count: 2 },
  { label: "Data", icon: Database, count: 1 },
  { label: "Product", icon: FileText, count: 1 },
];

export default function Home() {
  const router = useRouter();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 relative">
      {/* Header */}
      <header className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <Image
            src="/logo.svg"
            alt="No Shot"
            width={28}
            height={28}
            className="h-7 w-7"
          />
          <span className="font-serif text-lg font-semibold tracking-tight">
            No Shot
          </span>
        </div>
        <button
          onClick={() => router.push("/leaderboard")}
          className="flex items-center gap-2 text-sm font-medium text-muted hover:text-foreground transition-colors cursor-pointer"
        >
          <Trophy className="h-4 w-4" />
          Leaderboard
        </button>
      </header>

      {/* Hero — centered, understated */}
      <div className="mb-10 text-center fade-in-up">
        <h1 className="font-serif text-4xl font-normal leading-tight tracking-tight sm:text-5xl">
          Master the art of{" "}
          <span className="highlight-underline font-italic">prompting</span>
        </h1>
        <p className="mt-4 text-base text-muted max-w-md mx-auto leading-relaxed">
          Like Leetcode, but for the age of AI.
          <br />
          Solve challenges, get scored, improve your skills.
        </p>
      </div>

      {/* Start button */}
      <div className="mb-14 fade-in-up" style={{ animationDelay: "0.1s" }}>
        <button
          onClick={() => router.push("/play")}
          className="inline-flex items-center gap-2 rounded-lg bg-foreground px-6 py-3 text-sm font-medium text-background hover:opacity-90 transition-opacity cursor-pointer"
        >
          Start practicing
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      {/* Category pills — what you can practice */}
      <div
        className="flex flex-wrap items-center justify-center gap-2 mb-16 fade-in-up"
        style={{ animationDelay: "0.2s" }}
      >
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          return (
            <button
              key={cat.label}
              onClick={() => router.push("/play")}
              className="card-hover inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5 text-sm text-muted hover:text-foreground hover:border-accent/30 transition-colors cursor-pointer"
            >
              <Icon className="h-3.5 w-3.5" />
              <span className="font-medium">{cat.label}</span>
              <span className="text-xs text-muted/60 font-mono">{cat.count}</span>
            </button>
          );
        })}
      </div>

      {/* Quick stats */}
      <div
        className="flex items-center gap-8 text-sm text-muted fade-in-up"
        style={{ animationDelay: "0.3s" }}
      >
        <div className="text-center">
          <p className="text-2xl font-bold font-mono text-foreground">10</p>
          <p className="text-xs uppercase tracking-wider">Challenges</p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="text-center">
          <p className="text-2xl font-bold font-mono text-foreground">1000</p>
          <p className="text-xs uppercase tracking-wider">Max ELO</p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="text-center">
          <p className="text-2xl font-bold font-mono text-foreground">Free</p>
          <p className="text-xs uppercase tracking-wider">To play</p>
        </div>
      </div>
    </div>
  );
}
