"use client";

import { useEffect, useRef } from "react";
import { Sparkles } from "lucide-react";
import { PromptInput } from "@/components/PromptInput";
import type { ChatMessage } from "@/lib/api";

const REASONING_MODELS = new Set([
  "gpt-5.2-reasoning",
  "grok-4-1-fast-reasoning",
]);

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
  currentStreamingMessage: string;
  isWaitingForFirstToken: boolean;
  selectedModel: string;
  onModelChange: (model: string) => void;
  onSubmit: (prompt: string, model: string) => void;
  onStop: () => void;
  disabled?: boolean;
  submitDisabled?: boolean;
  fixedModel?: string;
  extraButton?: React.ReactNode;
  footerPrefix?: React.ReactNode;
  placeholder?: string;
  emptyTitle?: string;
  emptyDescription?: string;
}

export function ChatPanel({
  messages,
  isStreaming,
  currentStreamingMessage,
  isWaitingForFirstToken,
  selectedModel,
  onModelChange,
  onSubmit,
  onStop,
  disabled,
  submitDisabled,
  fixedModel,
  extraButton,
  footerPrefix,
  placeholder = "Ask anything…",
  emptyTitle = "Start a conversation",
  emptyDescription = "Describe what you want to build.",
}: Props) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isThinking = isWaitingForFirstToken && REASONING_MODELS.has(selectedModel);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  return (
    <>
      <div className="flex-1 overflow-y-auto">
        <div className="px-6 py-8">
          {messages.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
              <div className="text-center max-w-md">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent/10 mb-4">
                  <Sparkles className="h-6 w-6 text-accent" />
                </div>
                <h3 className="text-lg font-medium text-foreground mb-2">
                  {emptyTitle}
                </h3>
                <p className="text-sm text-muted">{emptyDescription}</p>
              </div>
            </div>
          )}

          <div className="space-y-8">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex gap-4 group ${
                  message.role === "user" ? "flex-row-reverse" : ""
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm leading-relaxed">
                    {message.role === "user" ? (
                      <div className="bg-foreground/5 border border-border rounded-lg px-4 py-3 text-foreground">
                        <div className="whitespace-pre-wrap break-words">
                          {message.content}
                        </div>
                      </div>
                    ) : (
                      <div className="text-foreground">
                        <div className="whitespace-pre-wrap break-words">
                          {message.content}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {isStreaming && (
              <div className="flex gap-4 group">
                <div className="flex-1 min-w-0">
                  <div className="text-sm leading-relaxed text-foreground">
                    {isThinking ? (
                      <div className="flex items-center gap-2 text-muted-foreground py-1 animate-pulse">
                        <Sparkles className="h-4 w-4 text-accent" />
                        <span className="font-medium">Thinking...</span>
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap break-words">
                        {currentStreamingMessage}
                        <span className="inline-block w-0.5 h-4 bg-foreground ml-1 align-middle animate-pulse" />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t border-border bg-background">
        {footerPrefix}
        <div className="px-6 py-4">
          <PromptInput
            onSubmit={onSubmit}
            onStop={onStop}
            isStreaming={isStreaming}
            selectedModel={selectedModel}
            onModelChange={onModelChange}
            placeholder={placeholder}
            disabled={disabled}
            submitDisabled={submitDisabled}
            fixedModel={fixedModel}
            extraButton={extraButton}
          />
        </div>
      </div>
    </>
  );
}
