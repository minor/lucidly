"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { Trophy } from "lucide-react";
import { PromptInput } from "@/components/PromptInput";

export default function Home() {
  const router = useRouter();

  const handlePrompt = () => {
    // Navigate to challenge selector when user tries to prompt from landing
    router.push("/play");
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 relative">
      {/* Header */}
      <header className="absolute top-0 right-0 p-6">
        <button
          onClick={() => router.push("/leaderboard")}
          className="flex items-center gap-2 text-sm font-medium text-muted hover:text-foreground transition-colors cursor-pointer"
        >
          <Trophy className="h-4 w-4" />
          Leaderboard
        </button>
      </header>

      {/* Hero */}
      <div className="mb-12 text-center">
        {/* Brand icon */}
        <div className="mb-6 flex items-center justify-center gap-2">
          <Image
            src="/logo.svg"
            alt="No Shot"
            width={40}
            height={40}
            className="h-10 w-10"
          />
          <span className="font-serif text-xl font-semibold tracking-tight">
            No Shot
          </span>
        </div>

        {/* Tagline */}
        <h1 className="font-serif text-4xl font-normal leading-tight tracking-tight sm:text-5xl">
          Master the art of{" "}
          <span className="highlight font-italic">prompting</span>
        </h1>
        <p className="mt-4 text-base text-muted max-w-md mx-auto leading-relaxed">
          Like Leetcode, but for the age of AI.
        </p>
      </div>

      {/* Prompt input */}
      <PromptInput
        onSubmit={handlePrompt}
        placeholder="Select a challenge to begin..."
      />

      {/* Quick stats or CTA */}
      <div className="mt-16 flex items-center gap-8 text-sm text-muted">
        <div className="text-center">
          <p className="text-2xl font-bold font-mono text-foreground">10</p>
          <p className="text-xs uppercase tracking-wider">Challenges</p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="text-center">
          <p className="text-2xl font-bold font-mono text-foreground">5</p>
          <p className="text-xs uppercase tracking-wider">Categories</p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="text-center">
          <p className="text-2xl font-bold font-mono text-foreground">3</p>
          <p className="text-xs uppercase tracking-wider">Difficulties</p>
        </div>
      </div>
    </div>
  );
}
