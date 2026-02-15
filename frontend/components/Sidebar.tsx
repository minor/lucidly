"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Zap,
  PlusCircle,
  Trophy,
  Bot,
  ChevronDown,
  ClipboardList,
} from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useUsername } from "@/hooks/useUsername";

const MODES = [
  { id: "arena", label: "Arena Mode", icon: Zap, href: "/play" },
  { id: "interview", label: "Interview Mode", icon: ClipboardList, href: "/interview/create" },
] as const;

const ARENA_NAV = [
  { href: "/play", label: "New Challenge", icon: PlusCircle },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
];

const INTERVIEW_NAV = [
  { href: "/interview/create", label: "Create Interview", icon: PlusCircle },
];

const MIN_WIDTH = 64; // 16 * 4 = 64px (w-16)
const MAX_WIDTH = 400;
const DEFAULT_WIDTH = 240; // 60 * 4 = 240px (w-60)
const COLLAPSED_WIDTH = 64;


export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, user } = useAuth0();
  const { username } = useUsername(user);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [modeOpen, setModeOpen] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(0);

  // Load width from localStorage on mount
  useEffect(() => {
    const savedWidth = localStorage.getItem("sidebar-width");
    if (savedWidth) {
      const parsedWidth = parseInt(savedWidth, 10);
      if (parsedWidth >= MIN_WIDTH && parsedWidth <= MAX_WIDTH) {
        setWidth(parsedWidth);
        setIsCollapsed(parsedWidth <= COLLAPSED_WIDTH);
      }
    }
  }, []);

  // Save width to localStorage when it changes
  useEffect(() => {
    if (width >= MIN_WIDTH && width <= MAX_WIDTH) {
      localStorage.setItem("sidebar-width", width.toString());
    }
  }, [width]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    startXRef.current = e.clientX;
    startWidthRef.current = width;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [width]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing) return;
    
    const diff = e.clientX - startXRef.current;
    const newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidthRef.current + diff));
    setWidth(newWidth);
    setIsCollapsed(newWidth <= COLLAPSED_WIDTH);
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

  const toggleCollapse = () => {
    if (isCollapsed) {
      // Expand to default width or last saved width
      setWidth(width === COLLAPSED_WIDTH ? DEFAULT_WIDTH : Math.max(DEFAULT_WIDTH, width));
      setIsCollapsed(false);
    } else {
      // Collapse to minimum width
      setWidth(COLLAPSED_WIDTH);
      setIsCollapsed(true);
    }
  };

  const collapsed = isCollapsed || width <= COLLAPSED_WIDTH;

  return (
    <div className="relative h-screen" style={{ width: `${width}px` }}>
      <aside
        ref={sidebarRef}
        className={`flex flex-col h-full border-r border-border bg-sidebar ${
          !isResizing ? "transition-all duration-200" : ""
        }`}
        style={{ width: `${width}px` }}
      >
      {/* Brand */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-4 shrink-0">
        <Link href="/" className="flex items-center gap-2 min-w-0">
          <Image
            src="/logo.svg"
            alt="No Shot"
            width={28}
            height={28}
            className="h-7 w-7 shrink-0"
          />
          {!collapsed && (
            <span className="font-serif text-lg font-semibold tracking-tight whitespace-nowrap overflow-hidden">
              No Shot
            </span>
          )}
        </Link>
        <button
          onClick={toggleCollapse}
          className="ml-auto text-muted hover:text-foreground transition-colors shrink-0 cursor-pointer"
          aria-label="Toggle sidebar"
        >
          <ChevronDown
            className={`h-4 w-4 transition-transform ${collapsed ? "-rotate-90" : ""}`}
          />
        </button>
      </div>

      {/* Mode selector */}
      {!collapsed && (() => {
        const isInterviewMode = pathname.startsWith("/interview");
        const currentMode = isInterviewMode ? MODES[1] : MODES[0];
        const CurrentIcon = currentMode.icon;
        return (
          <div className="px-4 py-3 border-b border-border shrink-0 relative">
            <button
              onClick={() => setModeOpen(!modeOpen)}
              className="flex items-center gap-1.5 text-sm font-medium text-muted hover:text-foreground transition-colors w-full min-w-0 cursor-pointer"
            >
              <CurrentIcon className="h-3.5 w-3.5 shrink-0" />
              <span className="whitespace-nowrap overflow-hidden min-w-0 flex-1 text-left">{currentMode.label}</span>
              <ChevronDown className={`h-3 w-3 shrink-0 transition-transform ${modeOpen ? "rotate-180" : ""}`} />
            </button>
            {modeOpen && (
              <div className="absolute left-3 right-3 top-full mt-1 rounded-lg border border-border bg-card shadow-lg z-20 overflow-hidden">
                {MODES.map((mode) => {
                  const Icon = mode.icon;
                  const isActive = mode.id === currentMode.id;
                  return (
                    <button
                      key={mode.id}
                      onClick={() => {
                        setModeOpen(false);
                        if (!isActive) router.push(mode.href);
                      }}
                      className={`flex items-center gap-2 w-full px-3 py-2.5 text-sm transition-colors cursor-pointer ${
                        isActive
                          ? "bg-accent/10 text-foreground font-medium"
                          : "text-muted hover:text-foreground hover:bg-muted/10"
                      }`}
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" />
                      {mode.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })()}

      {/* Navigation */}
      {(() => {
        const isInterviewMode = pathname.startsWith("/interview");
        const navItems = isInterviewMode ? INTERVIEW_NAV : ARENA_NAV;
        return (
          <nav className="flex-1 px-2 py-3 space-y-1 min-w-0 overflow-y-auto">
            {navItems.map((item) => {
              const isActive = pathname === item.href || (item.href !== "/play" && pathname.startsWith(item.href));
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors min-w-0 ${
                    isActive
                      ? "bg-accent-bg text-foreground font-medium"
                      : "text-muted hover:text-foreground hover:bg-accent-bg/50"
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {!collapsed && (
                    <span className="whitespace-nowrap overflow-hidden">
                      {item.label}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        );
      })()}

      {/* User info — bottom-left */}
      {!collapsed && isAuthenticated && user && (
        <div className="px-3 py-3 shrink-0 min-w-0">
          <div className="flex items-center gap-2.5 rounded-xl bg-background px-3 py-2.5 min-w-0">
            {/* Avatar circle */}
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/20 text-sm font-semibold text-accent">
              {(username || user.nickname || user.name || "U").charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground truncate leading-tight" title={username || user.nickname || user.name || undefined}>
                {username || user.nickname || user.name || "User"}
              </p>
              <p className="text-[11px] text-muted truncate leading-tight mt-0.5" title={user.email ?? undefined}>
                {user.email}
              </p>
            </div>
          </div>
        </div>
      )}
      </aside>
      {/* Resize handle */}
      <div
        onMouseDown={handleMouseDown}
        className={`absolute right-0 top-0 bottom-0 w-1 cursor-col-resize transition-all ${
          isResizing ? "bg-accent w-1" : "bg-transparent hover:bg-accent/40"
        }`}
        style={{ zIndex: 10 }}
        aria-label="Resize sidebar"
        title="Drag to resize"
      />
    </div>
  );
}
