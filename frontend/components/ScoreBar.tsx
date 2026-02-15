"use client";

import { Zap, Clock, Coins, RefreshCw, DollarSign } from "lucide-react";

interface ScoreBarProps {
  accuracy?: number;
  turns: number;
  tokens: number;
  elapsedSec: number;
  cost?: number;
  compositeScore?: number;
  score?: number; // Score out of 100, undefined means pending (for accuracy display)
  scoreLoading?: boolean; // Whether score is currently being evaluated
}

export function ScoreBar({
  accuracy,
  turns,
  tokens,
  elapsedSec,
  cost,
  compositeScore,
  score,
  scoreLoading = false,
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

  // Determine circle color based on score (0-100)
  const getScoreColor = (scoreValue: number) => {
    if (scoreValue <= 50) return "bg-red-500"; // Red for 0-50
    if (scoreValue <= 80) return "bg-yellow-500"; // Yellow for 51-80
    return "bg-green-500"; // Green for 81-100
  };

  // Use score if available (for UI challenges), otherwise use accuracy
  // Score takes precedence when both are available
  const hasScore = score !== undefined;
  const hasAccuracy = accuracy !== undefined;
  const showAccuracy = hasScore || hasAccuracy;
  
  // Determine pending/loading state
  const isPending = hasScore 
    ? (score === undefined && !scoreLoading) 
    : (accuracy === undefined);
  const isLoading = scoreLoading;
  
  // Determine display value and color
  const displayValue = hasScore 
    ? (score ?? 0) 
    : (accuracy !== undefined ? accuracy * 100 : 0);
  
  // Determine circle color - use score color logic if score is provided, otherwise use accuracy color logic
  const getCircleColor = () => {
    if (isPending || isLoading) return "bg-muted";
    if (hasScore) {
      return getScoreColor(displayValue);
    }
    // Use accuracy-based colors
    if (accuracy! >= 0.8) return "bg-success";
    if (accuracy! >= 0.5) return "bg-accent";
    return "bg-error";
  };

  return (
    <div className="flex items-center gap-6 rounded-xl border border-border bg-card px-5 py-3">
      {/* Composite score */}
      {compositeScore !== undefined && (
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-accent" />
          <div>
            <p className="text-sm font-semibold font-mono">
              {compositeScore}
            </p>
            <p className="text-[10px] text-muted uppercase tracking-wider">
              Score
            </p>
          </div>
        </div>
      )}

      {/* Accuracy (with score logic when score is provided) */}
      {showAccuracy && (
        <div className="flex items-center gap-2">
          <div className={`h-2 w-2 rounded-full ${getCircleColor()}`} />
          <div>
            <p className="text-sm font-semibold font-mono">
              {isLoading ? (
                <span className="text-muted animate-pulse">...</span>
              ) : (
                `${Math.round(displayValue)}%`
              )}
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
            Tokens
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
