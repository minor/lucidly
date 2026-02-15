"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { Loader2, Check, X } from "lucide-react";
import { checkUsernameAvailable } from "@/lib/api";

interface UsernameModalProps {
  /** Default suggestion (e.g. Auth0 nickname / email prefix) */
  defaultValue?: string;
  /** Called when the user confirms their chosen name. May throw on duplicates. */
  onConfirm: (name: string) => Promise<void>;
}

export function UsernameModal({
  defaultValue = "",
  onConfirm,
}: UsernameModalProps) {
  const [value, setValue] = useState(defaultValue);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Real-time availability check (debounced)
  const [checking, setChecking] = useState(false);
  const [available, setAvailable] = useState<boolean | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const trimmed = value.trim();
    if (trimmed.length < 2) {
      setAvailable(null);
      setChecking(false);
      return;
    }

    setChecking(true);
    setAvailable(null);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const ok = await checkUsernameAvailable(trimmed);
        setAvailable(ok);
      } catch {
        setAvailable(null);
      } finally {
        setChecking(false);
      }
    }, 400);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [value]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || trimmed.length < 2) return;

    setSubmitting(true);
    setError(null);
    try {
      await onConfirm(trimmed);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to set username.");
    } finally {
      setSubmitting(false);
    }
  };

  const trimmed = value.trim();
  const tooShort = trimmed.length > 0 && trimmed.length < 2;
  const tooLong = trimmed.length > 30;
  const hasError =
    tooShort ||
    tooLong ||
    (!checking && available === false && trimmed.length >= 2) ||
    !!error;

  return (
    <div className="fixed inset-0 z-[60] flex flex-col items-center justify-center bg-background/95 backdrop-blur-sm animate-in fade-in duration-200">
      {/* Logo + brand */}
      <div className="flex items-center gap-1.5 mb-4">
        <Image
          src="/logo.svg"
          alt="NoShot"
          width={64}
          height={64}
          className="h-16 w-16"
        />
        <span className="font-serif text-5xl font-semibold tracking-tight">
          NoShot
        </span>
      </div>

      {/* Content */}
      <div className="flex flex-col items-center">
        <h2 className="text-3xl font-semibold tracking-tight mb-2 whitespace-nowrap">
          Choose a username
        </h2>
        <p className="text-base text-muted font-serif italic mb-6 whitespace-nowrap">
          This will appear on the leaderboard
        </p>

        <form onSubmit={handleSubmit} className="w-[320px] space-y-3">
          <div className="relative">
            <input
              type="text"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setError(null);
              }}
              placeholder="username"
              autoFocus
              maxLength={30}
              className={`w-full rounded-md border bg-card px-3.5 py-2.5 text-sm font-mono placeholder:text-muted/50 focus:outline-none transition-colors ${
                hasError
                  ? "border-red-400 focus:border-red-400"
                  : available === true
                    ? "border-green-400 focus:border-green-400"
                    : "border-border focus:border-accent"
              }`}
            />
            {/* Availability indicator */}
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
              {checking && (
                <Loader2 className="h-4 w-4 animate-spin text-muted" />
              )}
              {!checking && available === true && trimmed.length >= 2 && (
                <Check className="h-4 w-4 text-green-500" />
              )}
              {!checking && available === false && trimmed.length >= 2 && (
                <X className="h-4 w-4 text-red-500" />
              )}
            </div>
          </div>

          {/* Validation — compact single line */}
          {hasError && (
            <p className="text-xs text-red-500 leading-tight">
              {tooShort
                ? "Must be at least 2 characters."
                : tooLong
                  ? "Must be 30 characters or fewer."
                  : !checking && available === false && trimmed.length >= 2
                    ? "This username is already taken."
                    : error || ""}
            </p>
          )}

          <button
            type="submit"
            disabled={
              submitting ||
              !trimmed ||
              tooShort ||
              tooLong ||
              available === false ||
              checking
            }
            className="w-full rounded-md bg-foreground px-4 py-2.5 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin mx-auto" />
            ) : (
              "Continue"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
