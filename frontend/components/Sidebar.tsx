"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Zap,
  PlusCircle,
  Trophy,
  Bot,
  ChevronDown,
} from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";

const NAV_ITEMS = [
  { href: "/play", label: "New Challenge", icon: PlusCircle },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
];

const MIN_WIDTH = 64; // 16 * 4 = 64px (w-16)
const MAX_WIDTH = 400;
const DEFAULT_WIDTH = 240; // 60 * 4 = 240px (w-60)
const COLLAPSED_WIDTH = 64;

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

export function Sidebar() {
  const pathname = usePathname();
  const {
    isLoading: authLoading,
    isAuthenticated,
    user,
    loginWithRedirect,
    logout,
  } = useAuth0();
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
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
          <Zap className="h-5 w-5 text-accent shrink-0" />
          {!collapsed && (
            <span className="font-serif text-lg font-semibold tracking-tight whitespace-nowrap overflow-hidden">
              Lucidly
            </span>
          )}
        </Link>
        <button
          onClick={toggleCollapse}
          className="ml-auto text-muted hover:text-foreground transition-colors shrink-0 cursor-pointer"
          aria-label="Toggle sidebar"
        >
          <ChevronDown
            className={`h-4 w-4 transition-transform ${
              collapsed ? "-rotate-90" : ""
            }`}
          />
        </button>
      </div>

      {/* Mode selector */}
      {!collapsed && (
        <div className="px-4 py-3 border-b border-border shrink-0">
          <button className="flex items-center gap-1.5 text-sm font-medium text-muted hover:text-foreground transition-colors w-full min-w-0 cursor-pointer">
            <Zap className="h-3.5 w-3.5 shrink-0" />
            <span className="whitespace-nowrap overflow-hidden min-w-0 flex-1">Arena Mode</span>
            <ChevronDown className="h-3 w-3 shrink-0" />
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-1 min-w-0 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);
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

      {/* Auth */}
      {!collapsed && (
        <div className="border-t border-border px-4 py-3 shrink-0 space-y-2">
          {authLoading ? (
            <div className="text-xs text-muted">Loading...</div>
          ) : isAuthenticated && user ? (
            <div className="min-w-0">
              <p className="text-xs text-muted truncate" title={user.email ?? undefined}>
                {user.email}
              </p>
              <button
                type="button"
                onClick={() => logout({ logoutParams: { returnTo: appUrl } })}
                className="text-xs text-muted hover:text-foreground transition-colors cursor-pointer"
              >
                Logout
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: "signup" } })}
                className="text-xs text-muted hover:text-foreground transition-colors cursor-pointer"
              >
                Signup
              </button>
              <button
                type="button"
                onClick={() => loginWithRedirect()}
                className="text-xs text-muted hover:text-foreground transition-colors cursor-pointer"
              >
                Login
              </button>
            </div>
          )}
          <div className="flex items-center gap-3 text-xs text-muted min-w-0 pt-2 border-t border-border">
            <Link href="#" className="hover:text-foreground transition-colors whitespace-nowrap overflow-hidden">
              Terms
            </Link>
            <Link href="#" className="hover:text-foreground transition-colors whitespace-nowrap overflow-hidden">
              Privacy
            </Link>
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
