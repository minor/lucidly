"use client";

import { useState } from "react";
import { ExternalLink, CheckCircle, Loader2 } from "lucide-react";

interface Props {
  provider: "linear" | "github";
  connected: boolean;
  onConnect: () => Promise<void>;
  label: string;
}

export function OAuthConnectButton({ provider, connected, onConnect, label }: Props) {
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setConnecting(true);
    setError(null);
    try {
      await onConnect();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setConnecting(false);
    }
  };

  if (connected) {
    return (
      <div className="flex items-center gap-2 text-sm text-green-500">
        <CheckCircle className="h-4 w-4" />
        {label} connected
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        onClick={handleClick}
        disabled={connecting}
        className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm hover:border-accent hover:text-foreground text-muted transition-colors disabled:opacity-50 cursor-pointer"
      >
        {connecting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <ExternalLink className="h-4 w-4" />
        )}
        Connect {label}
      </button>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
