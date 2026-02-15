"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAgents, getChallenges, startAgentRun } from "@/lib/api";
import type { Agent as AgentType, Challenge } from "@/lib/types";
import { Loader2, Play, LogIn, UserPlus } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";

export default function AgentsPage() {
  const router = useRouter();
  const { isAuthenticated, loginWithRedirect } = useAuth0();
  const [agents, setAgents] = useState<AgentType[]>([]);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [selectedChallengeId, setSelectedChallengeId] = useState<string>("");
  const [showAuthOverlay, setShowAuthOverlay] = useState(false);

  useEffect(() => {
    let ignore = false;
    Promise.all([getAgents(), getChallenges()])
      .then(([agentsData, challengesData]) => {
        if (!ignore) {
          setAgents(agentsData);
          setChallenges(challengesData);
          if (agentsData.length && !selectedAgentId)
            setSelectedAgentId(agentsData[0].id);
          if (challengesData.length && !selectedChallengeId)
            setSelectedChallengeId(challengesData[0].id);
        }
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

  const handleRun = async () => {
    if (!selectedAgentId || !selectedChallengeId || running) return;

    // Require login before starting a run
    if (!isAuthenticated) {
      setShowAuthOverlay(true);
      return;
    }

    setRunning(true);
    setError(null);
    try {
      const { session_id } = await startAgentRun(selectedAgentId, selectedChallengeId);
      router.push(`/agents/run/${session_id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  return (
    <div className="relative min-h-full">
      {showAuthOverlay && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md animate-in fade-in duration-200">
          <h2 className="text-xl font-semibold tracking-tight mb-2">Sign in to run an agent</h2>
          <p className="text-sm text-muted mb-6">Create an account to start agent runs</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => loginWithRedirect({ appState: { returnTo: "/agents" } })}
              className="flex items-center gap-1.5 rounded-lg border border-border bg-card/80 backdrop-blur-sm px-3 py-2 text-xs font-medium text-muted hover:text-foreground hover:border-foreground/20 shadow-sm transition-colors cursor-pointer"
            >
              <LogIn className="h-3.5 w-3.5" />
              Log in
            </button>
            <button
              type="button"
              onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: "signup" }, appState: { returnTo: "/agents" } })}
              className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-medium text-accent-foreground hover:bg-accent/90 shadow-sm transition-colors cursor-pointer"
            >
              <UserPlus className="h-3.5 w-3.5" />
              Sign up
            </button>
          </div>
        </div>
      )}

      <div className="mx-auto max-w-2xl px-6 py-10">
        <div className="mb-8">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            Agent Benchmark
          </h1>
          <p className="mt-2 text-sm text-muted">
            Select an agent and a challenge, then run to watch the agent complete the task. Results appear on the leaderboard.
          </p>
        </div>

      {error && (
        <div className="mb-6 rounded-xl border border-error/20 bg-error/5 p-4 text-sm text-error">
          {error}
        </div>
      )}

      <div className="space-y-6 rounded-xl border border-border bg-card p-6">
        <div>
          <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-muted">
            Agent
          </label>
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} — {a.description}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-muted">
            Challenge
          </label>
          <select
            value={selectedChallengeId}
            onChange={(e) => setSelectedChallengeId(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {challenges.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={handleRun}
          disabled={running || !selectedAgentId || !selectedChallengeId}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-3 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {running ? "Starting…" : "Run"}
        </button>
      </div>
      </div>
    </div>
  );
}
