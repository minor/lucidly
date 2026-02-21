"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Code,
  Layout,
  Bug,
  FileText,
  ClipboardList,
} from "lucide-react";

const CATEGORIES = [
  { label: "Function", icon: Code, count: 1 },
  { label: "UI", icon: Layout, count: 2 },
  { label: "Debug", icon: Bug, count: 1 },
  { label: "Product", icon: FileText, count: 1 },
];

export default function Home() {
  const router = useRouter();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 sm:px-6 pt-16 pb-8">
      {/* Logo + title */}
      <div className="flex items-center gap-1.5 mb-4 sm:mb-6 fade-in-up">
        <Image
          src="/logo.svg"
          alt="No Shot"
          width={80}
          height={80}
          className="h-8 w-8 sm:h-12 sm:w-12"
        />
        <span className="font-heading text-2xl font-semibold tracking-tight sm:text-4xl">
          No Shot
        </span>
      </div>

      {/* Hero — centered, understated */}
      <div className="mb-8 sm:mb-10 text-center fade-in-up px-2" style={{ animationDelay: "0.05s" }}>
        <h1 className="font-heading text-3xl font-semibold leading-tight tracking-tight sm:text-5xl md:text-6xl">
          Master the art of{" "}
          <span className="highlight-underline italic">prompting</span>
        </h1>
        <p className="mt-3 sm:mt-4 text-sm sm:text-base text-muted max-w-md mx-auto leading-relaxed">
          Like LeetCode, but for the age of AI.
          <br />
          Solve challenges, get scored, improve your skills!
        </p>
      </div>

      {/* Start button + Interview mode link */}
      <div
        className="mb-10 sm:mb-14 flex flex-col items-center gap-3 fade-in-up"
        style={{ animationDelay: "0.1s" }}
      >
        <button
          onClick={() => router.push("/play")}
          className="inline-flex items-center gap-2 rounded-lg bg-foreground px-5 py-2.5 sm:px-6 sm:py-3 text-sm font-medium text-background hover:opacity-90 transition-opacity cursor-pointer"
        >
          Start practicing
          <ArrowRight className="h-4 w-4" />
        </button>
        <button
          onClick={() => router.push("/interview/create")}
          className="inline-flex items-center gap-2 text-sm text-muted hover:text-accent transition-colors cursor-pointer"
        >
          <ClipboardList className="h-3.5 w-3.5" />
          Hiring? Try Interview Mode
          <ArrowRight className="h-3 w-3" />
        </button>
      </div>

      {/* Category pills — what you can practice */}
      <div
        className="flex flex-wrap items-center justify-center gap-2 mb-10 sm:mb-16 fade-in-up"
        style={{ animationDelay: "0.2s" }}
      >
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          return (
            <button
              key={cat.label}
              onClick={() => router.push("/play")}
              className="card-hover inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 sm:px-4 sm:py-2.5 text-sm text-muted hover:text-foreground hover:border-accent/30 transition-colors cursor-pointer"
            >
              <Icon className="h-3.5 w-3.5" />
              <span className="font-medium">{cat.label}</span>
              <span className="text-xs text-muted/60 font-mono">
                {cat.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Quick stats */}
      <div
        className="flex items-center gap-5 sm:gap-8 text-sm text-muted fade-in-up"
        style={{ animationDelay: "0.3s" }}
      >
        <div className="text-center">
          <p className="text-xl sm:text-2xl font-bold font-mono text-foreground">
            5
          </p>
          <p className="text-[10px] sm:text-xs uppercase tracking-wider">
            Challenges
          </p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="text-center">
          <p className="text-xl sm:text-2xl font-bold font-mono text-foreground">
            1000
          </p>
          <p className="text-[10px] sm:text-xs uppercase tracking-wider">
            Max ELO
          </p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="text-center">
          <p className="text-xl sm:text-2xl font-bold font-mono text-foreground">
            Free
          </p>
          <p className="text-[10px] sm:text-xs uppercase tracking-wider">
            To play
          </p>
        </div>
      </div>
    </div>
  );
}
