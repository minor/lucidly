"use client";

import { useState, useRef } from "react";
import { ArrowRight, Loader2, Square, Info } from "lucide-react";

import { MODELS, MODEL_PRICING } from "@/lib/api";

interface PromptInputProps {
  onSubmit: (prompt: string, model: string) => void;
  onStop?: () => void;
  loading?: boolean;
  placeholder?: string;
  disabled?: boolean;
  initialModel?: string;
}

export function PromptInput({
  onSubmit,
  onStop,
  loading = false,
  placeholder = "Ask anything...",
  disabled = false,
  initialModel = "gpt-5.2",
}: PromptInputProps) {
  const [value, setValue] = useState("");
  const [model, setModel] = useState(initialModel);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || loading || disabled) return;
    onSubmit(trimmed, model);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };
  
  const handleStop = (e: React.MouseEvent) => {
    e.preventDefault();
    onStop?.();
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
    <div className="relative w-full">
      <div className="flex flex-col gap-2 rounded-lg border border-input-border bg-input px-3 py-2.5 transition-colors focus-within:border-accent/50">
        {/* Model Picker Header */}
        <div className="flex items-center justify-between border-b border-input-border/50 pb-2">
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={loading || disabled}
            className="bg-transparent text-xs font-medium text-muted hover:text-foreground focus:outline-none cursor-pointer"
          >
            {MODELS.map((m) => (
              <option key={m.id} value={m.id} className="bg-popover text-popover-foreground">
                {m.name}
              </option>
            ))}
          </select>

          {/* Pricing Display */}
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground bg-muted/30 px-2 py-1 rounded">
            <Info className="h-3 w-3 opacity-70" />
            <span>
              In: <span className="font-mono text-foreground">${MODEL_PRICING[model]?.input.toFixed(2)}</span> / 
              Out: <span className="font-mono text-foreground">${MODEL_PRICING[model]?.output.toFixed(2)}</span> per 1M
            </span>
          </div>
        </div>

        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={placeholder}
          disabled={disabled || (loading && !onStop)}
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm leading-relaxed text-foreground placeholder:text-muted/60 focus:outline-none disabled:opacity-50"
        />
        {loading && onStop ? (
          <button
            onClick={handleStop}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-destructive text-destructive-foreground transition-opacity hover:opacity-90"
            aria-label="Stop generating"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!value.trim() || loading || disabled}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-foreground text-background transition-opacity hover:opacity-90 disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Submit prompt"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <ArrowRight className="h-3.5 w-3.5" />
            )}
          </button>
        )}
        </div>
      </div>
    </div>
  );
}
