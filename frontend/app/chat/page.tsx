"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Sparkles } from "lucide-react";
import { PromptInput } from "@/components/PromptInput";
import { streamChat, type ChatMessage } from "@/lib/api";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  
  // Chat window resize state
  const [chatWidth, setChatWidth] = useState(50); // Percentage of screen width
  const [isResizing, setIsResizing] = useState(false);
  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load chat width from localStorage on mount
  useEffect(() => {
    const savedWidth = localStorage.getItem("chat-width");
    if (savedWidth) {
      const parsedWidth = parseFloat(savedWidth);
      if (parsedWidth >= 33.33 && parsedWidth <= 100) {
        setChatWidth(parsedWidth);
      }
    }
  }, []);

  // Save chat width to localStorage when it changes
  useEffect(() => {
    if (chatWidth >= 33.33 && chatWidth <= 100) {
      localStorage.setItem("chat-width", chatWidth.toString());
    }
  }, [chatWidth]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    startXRef.current = e.clientX;
    startWidthRef.current = chatWidth;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [chatWidth]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing || !containerRef.current) return;
    
    const containerWidth = containerRef.current.offsetWidth;
    const diff = e.clientX - startXRef.current;
    const diffPercent = (diff / containerWidth) * 100;
    // When dragging right (positive diff), chat window gets smaller (decrease width)
    // When dragging left (negative diff), chat window gets larger (increase width)
    const newWidth = Math.max(33.33, Math.min(100, startWidthRef.current - diffPercent));
    setChatWidth(newWidth);
  }, [isResizing]);

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, []);

  useEffect(() => {
    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      return () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };
    }
  }, [isResizing, handleMouseMove, handleMouseUp]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  const handleSubmit = async (prompt: string) => {
    if (!prompt.trim() || isStreaming) return;

    // Add user message
    const userMessage: ChatMessage = { role: "user", content: prompt };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsStreaming(true);
    setCurrentStreamingMessage("");

    // Stream response
    await streamChat(
      updatedMessages,
      undefined, // Use default model
      (chunk) => {
        setCurrentStreamingMessage((prev) => prev + chunk);
      },
      (fullResponse) => {
        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: fullResponse,
        };
        setMessages([...updatedMessages, assistantMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
      },
      (error) => {
        console.error("Chat error:", error);
        const errorMessage: ChatMessage = {
          role: "assistant",
          content: `Error: ${error}`,
        };
        setMessages([...updatedMessages, errorMessage]);
        setCurrentStreamingMessage("");
        setIsStreaming(false);
      }
    );
  };

  return (
    <div ref={containerRef} className="flex h-full relative">
      {/* Left Side - Blank */}
      <div 
        className="border-r border-border"
        style={{ width: `${100 - chatWidth}%` }}
      ></div>

      {/* Resize handle */}
      <div
        onMouseDown={handleMouseDown}
        className="absolute top-0 bottom-0 cursor-col-resize"
        style={{ 
          left: `calc(${100 - chatWidth}% - 20px)`,
          zIndex: 1000,
          width: '40px',
          pointerEvents: 'auto',
          userSelect: 'none',
          backgroundColor: '#ff0000',
          border: '2px solid #ff0000'
        }}
        aria-label="Resize chat window"
        title="Drag to resize"
      />

      {/* Right Side - Chat Interface (Cursor-style) */}
      <div 
        className={`flex flex-col h-full bg-background ${
          !isResizing ? "transition-all duration-200" : ""
        }`}
        style={{ width: `${chatWidth}%` }}
      >
        {/* Minimal Header */}
        <div className="border-b border-border px-6 py-3 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-muted" />
          <h2 className="text-sm font-medium text-foreground">Chat</h2>
        </div>

        {/* Messages Container - Cursor style */}
        <div
          ref={chatContainerRef}
          className="flex-1 overflow-y-auto"
        >
          <div className="max-w-3xl mx-auto px-6 py-8">
            {messages.length === 0 && !isStreaming && (
              <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
                <div className="text-center max-w-md">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent/10 mb-4">
                    <Sparkles className="h-6 w-6 text-accent" />
                  </div>
                  <h3 className="text-lg font-medium text-foreground mb-2">
                    Start a conversation
                  </h3>
                  <p className="text-sm text-muted">
                    Ask anything and get help from Claude Code
                  </p>
                </div>
              </div>
            )}

            {/* Messages */}
            <div className="space-y-8">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex gap-4 group ${
                    message.role === "user" ? "flex-row-reverse" : ""
                  }`}
                >
                  {/* Message Content */}
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

              {/* Streaming Message */}
              {isStreaming && (
                <div className="flex gap-4 group">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm leading-relaxed text-foreground">
                      <div className="whitespace-pre-wrap break-words">
                        {currentStreamingMessage}
                        <span className="inline-block w-0.5 h-4 bg-foreground ml-1 align-middle animate-pulse" />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area - Cursor style (more integrated) */}
        <div className="border-t border-border bg-background">
          <div className="max-w-3xl mx-auto px-6 py-4">
            <PromptInput
              onSubmit={handleSubmit}
              loading={isStreaming}
              placeholder="Ask anything..."
              disabled={isStreaming}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
