"use client";

import { Zap, Clock, Coins, RefreshCw, DollarSign } from "lucide-react";

interface ScoreBarProps {
  accuracy?: number;
  turns: number;
  tokens: number;
  elapsedSec: number;
  cost?: number;
  compositeScore?: number;
}

export function ScoreBar({
  accuracy,
  turns,
  tokens,
  elapsedSec,
  cost,
  compositeScore,
}: ScoreBarProps) {
  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const formatCost = (c: number) => {
    if (c === 0) return "$0.00";
    return `$${c.toFixed(4)}`;
  };

  return (
    <div className="flex items-center gap-6 rounded-xl border border-border bg-card px-5 py-3">
      {/* Composite score */}
      {compositeScore !== undefined && (
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-accent" />
          <div>
            <p className="text-lg font-bold font-mono text-foreground">
              {compositeScore}
            </p>
            <p className="text-[10px] text-muted uppercase tracking-wider">
              Score
            </p>
          </div>
        </div>
      )}

      {/* Accuracy */}
      {accuracy !== undefined && (
        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${
              accuracy >= 0.8
                ? "bg-success"
                : accuracy >= 0.5
                  ? "bg-accent"
                  : "bg-error"
            }`}
          />
          <div>
            <p className="text-sm font-semibold font-mono">
              {Math.round(accuracy * 100)}%
            </p>
            <p className="text-[10px] text-muted uppercase tracking-wider">
              Accuracy
            </p>
          </div>
        </div>
      )}

      {/* Time */}
      <div className="flex items-center gap-2">
        <Clock className="h-3.5 w-3.5 text-muted" />
        <div>
          <p className="text-sm font-semibold font-mono">
            {formatTime(elapsedSec)}
          </p>
          <p className="text-[10px] text-muted uppercase tracking-wider">
            Time
          </p>
        </div>
      </div>

      {/* Turns */}
      <div className="flex items-center gap-2">
        <RefreshCw className="h-3.5 w-3.5 text-muted" />
        <div>
          <p className="text-sm font-semibold font-mono">{turns}</p>
          <p className="text-[10px] text-muted uppercase tracking-wider">
            Turns
          </p>
        </div>
      </div>

      {/* Tokens Output */}
      <div className="flex items-center gap-2">
        <Coins className="h-3.5 w-3.5 text-muted" />
        <div>
          <p className="text-sm font-semibold font-mono">
            {tokens.toLocaleString()}
          </p>
          <p className="text-[10px] text-muted uppercase tracking-wider">
            Tokens Output
          </p>
        </div>
      </div>

      {/* Inference Cost */}
      {cost !== undefined && (
        <div className="flex items-center gap-2">
          <DollarSign className="h-3.5 w-3.5 text-muted" />
          <div>
            <p className="text-sm font-semibold font-mono">
              {formatCost(cost)}
            </p>
            <p className="text-[10px] text-muted uppercase tracking-wider">
              Cost
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
