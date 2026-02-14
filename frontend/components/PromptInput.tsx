"use client";

import { useState, useRef } from "react";
import { ArrowRight, Loader2 } from "lucide-react";

interface PromptInputProps {
  onSubmit: (prompt: string) => void;
  loading?: boolean;
  placeholder?: string;
  disabled?: boolean;
}

export function PromptInput({
  onSubmit,
  loading = false,
  placeholder = "Ask anything...",
  disabled = false,
}: PromptInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || loading || disabled) return;
    onSubmit(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }
  };

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      <div className="flex items-end gap-2 rounded-2xl border border-input-border bg-input px-4 py-3 shadow-sm transition-shadow focus-within:shadow-md focus-within:border-accent/40">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={placeholder}
          disabled={disabled || loading}
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm leading-relaxed text-foreground placeholder:text-muted/60 focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={handleSubmit}
          disabled={!value.trim() || loading || disabled}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-foreground text-background transition-opacity hover:opacity-80 disabled:opacity-30"
          aria-label="Submit prompt"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowRight className="h-4 w-4" />
          )}
        </button>
      </div>
      <p className="mt-2 text-center text-xs text-muted/60">
        Press{" "}
        <kbd className="rounded border border-border bg-background px-1 py-0.5 text-[10px] font-mono">
          Cmd+Enter
        </kbd>{" "}
        to submit
      </p>
    </div>
  );
}
