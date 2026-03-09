"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Zap,
  PlusCircle,
  Trophy,
  // DISABLED: Bot icon unused while Agents tab is hidden
  // Bot,
  ChevronDown,
  ClipboardList,
  LogOut,
  LibraryBig,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useUsernameContext } from "@/hooks/UsernameContext";
import { useTheme, type ThemeMode } from "@/hooks/ThemeContext";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

// DISABLED: Set to true to re-enable Interview Mode in sidebar UI.
const INTERVIEW_MODE_ENABLED = false;

const MODES = [
  { id: "arena", label: "Arena Mode", icon: Zap, href: "/play" },
  { id: "interview", label: "Interview Mode", icon: ClipboardList, href: "/interview/create" },
] as const;

const ARENA_NAV = [
  { href: "/play", label: "New Challenge", icon: PlusCircle },
  // DISABLED: Agents tab hidden until re-enabled
  // { href: "/agents", label: "Agents", icon: Bot },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
  { href: "/resources", label: "Resources", icon: LibraryBig },
];
const INTERVIEW_NAV = [
  { href: "/interview/create", label: "Create Interview", icon: PlusCircle },
];

const MIN_WIDTH = 64; // 16 * 4 = 64px (w-16)
const MAX_WIDTH = 400;
const DEFAULT_WIDTH = 240; // 60 * 4 = 240px (w-60)
const COLLAPSED_WIDTH = 64;

interface SidebarProps {
  onNavigate?: () => void;
  isMobile?: boolean;
}

export function Sidebar({ onNavigate, isMobile }: SidebarProps = {}) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, user, logout } = useAuth0();
  const { username } = useUsernameContext();
  const { theme, setTheme } = useTheme();
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [modeOpen, setModeOpen] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const userBlockRef = useRef<HTMLDivElement>(null);
  const modeBlockRef = useRef<HTMLDivElement>(null);
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

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsResizing(true);
      startXRef.current = e.clientX;
      startWidthRef.current = width;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [width],
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing) return;

      const diff = e.clientX - startXRef.current;
      const newWidth = Math.max(
        MIN_WIDTH,
        Math.min(MAX_WIDTH, startWidthRef.current + diff),
      );
      setWidth(newWidth);
      setIsCollapsed(newWidth <= COLLAPSED_WIDTH);
    },
    [isResizing],
  );

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

  useEffect(() => {
    if (!logoutOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        userBlockRef.current &&
        !userBlockRef.current.contains(e.target as Node)
      ) {
        setLogoutOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [logoutOpen]);

  useEffect(() => {
    if (!modeOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        modeBlockRef.current &&
        !modeBlockRef.current.contains(e.target as Node)
      ) {
        setModeOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [modeOpen]);

  const toggleCollapse = () => {
    if (isCollapsed) {
      // Expand to default width or last saved width
      setWidth(
        width === COLLAPSED_WIDTH
          ? DEFAULT_WIDTH
          : Math.max(DEFAULT_WIDTH, width),
      );
      setIsCollapsed(false);
    } else {
      // Collapse to minimum width
      setWidth(COLLAPSED_WIDTH);
      setIsCollapsed(true);
    }
  };

  const collapsed = isCollapsed || width <= COLLAPSED_WIDTH;

  return (
    <div
      className={isMobile ? "w-full h-full" : "relative h-screen"}
      style={isMobile ? undefined : { width: `${width}px` }}
    >
      <aside
        ref={sidebarRef}
        className={`flex flex-col h-full border-r border-border bg-sidebar ${
          !isResizing ? "transition-all duration-200" : ""
        }`}
        style={isMobile ? undefined : { width: `${width}px` }}
      >
        {/* Brand — same height expanded/collapsed; logo centered when collapsed */}
        <div
          className={`flex items-center border-b border-border shrink-0 relative min-h-[60px] py-4 ${collapsed ? "justify-center pl-0 pr-2" : "gap-1 pl-4 pr-2"}`}
        >
          <Link
            href="/"
            className={`flex items-center min-w-0 ${collapsed ? "flex-none justify-center" : "gap-1.5"}`}
          >
            <Image
              src="/logo.svg"
              alt="No Shot"
              width={28}
              height={28}
              className="h-7 w-7 shrink-0"
            />
            {!collapsed && (
              <span className="font-heading text-lg font-semibold tracking-tight whitespace-nowrap overflow-hidden">
                No Shot
              </span>
            )}
          </Link>
          {!isMobile && (
            <button
              onClick={toggleCollapse}
              className={`text-muted hover:text-foreground transition-colors shrink-0 cursor-pointer ${collapsed ? "absolute right-2 top-1/2 -translate-y-1/2" : "ml-auto mr-0"}`}
              aria-label={collapsed ? "Expand sidebar" : "Toggle sidebar"}
            >
              <ChevronDown
                className={`h-4 w-4 ${collapsed ? "-rotate-90" : ""}`}
              />
            </button>
          )}
        </div>

        {/* Mode selector — same row styling as nav, visible when collapsed (icon only) */}
        {(() => {
          const availableModes = INTERVIEW_MODE_ENABLED ? MODES : [MODES[0]];
          const isInterviewMode = INTERVIEW_MODE_ENABLED && pathname.startsWith("/interview");
          const currentMode = isInterviewMode ? availableModes[1] : availableModes[0];
          const CurrentIcon = currentMode.icon;
          const canSwitchModes = availableModes.length > 1;
          return (
            <div
              ref={modeBlockRef}
              className="pl-2 pr-2 py-3 border-b border-border shrink-0 relative"
            >
              {collapsed ? (
                <button
                  onClick={() => canSwitchModes && setModeOpen(!modeOpen)}
                  className={`flex items-center justify-center rounded-lg py-2 min-h-[40px] w-10 mx-auto text-muted transition-colors ${
                    canSwitchModes ? "hover:text-foreground cursor-pointer" : "cursor-default"
                  }`}
                  title={currentMode.label}
                >
                  <CurrentIcon className="h-4 w-4 shrink-0" />
                </button>
              ) : (
                <>
                  <button
                    onClick={() => canSwitchModes && setModeOpen(!modeOpen)}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2 min-h-[40px] text-sm font-medium text-muted transition-colors w-full min-w-0 ${
                      canSwitchModes ? "hover:text-foreground cursor-pointer" : "cursor-default"
                    }`}
                  >
                    <CurrentIcon className="h-4 w-4 shrink-0" />
                    <span className="whitespace-nowrap overflow-hidden min-w-0 flex-1 text-left">
                      {currentMode.label}
                    </span>
                    {canSwitchModes && (
                      <ChevronDown
                        className={`h-3 w-3 shrink-0 transition-transform ${modeOpen ? "rotate-180" : ""}`}
                      />
                    )}
                  </button>
                  {canSwitchModes && modeOpen && (
                    <div className="absolute left-2 right-2 top-full mt-1 rounded-lg border border-border bg-card shadow-lg z-20 overflow-hidden">
                      {availableModes.map((mode) => {
                        const Icon = mode.icon;
                        const isActive = mode.id === currentMode.id;
                        return (
                          <button
                            key={mode.id}
                            onClick={() => {
                              setModeOpen(false);
                              if (!isActive) {
                                router.push(mode.href);
                                onNavigate?.();
                              }
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
                </>
              )}
              {collapsed && canSwitchModes && modeOpen && (
                <div className="absolute left-full top-0 ml-1 rounded-lg border border-border bg-card shadow-lg z-20 overflow-hidden min-w-[180px]">
                  {availableModes.map((mode) => {
                    const Icon = mode.icon;
                    const isActive = mode.id === currentMode.id;
                    return (
                      <button
                        key={mode.id}
                        onClick={() => {
                          setModeOpen(false);
                          if (!isActive) {
                            router.push(mode.href);
                            onNavigate?.();
                          }
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
          const isInterviewMode =
            INTERVIEW_MODE_ENABLED && pathname.startsWith("/interview");
          const navItems = isInterviewMode ? INTERVIEW_NAV : ARENA_NAV;
          return (
            <nav className="flex-1 px-2 py-3 space-y-1 min-w-0 overflow-y-auto">
              {navItems.map((item) => {
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/play" && pathname.startsWith(item.href));
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    className={`flex items-center rounded-lg py-2 text-sm transition-colors min-w-0 ${
                      collapsed
                        ? "justify-center w-10 mx-auto px-0"
                        : "gap-3 px-3"
                    } ${
                      isActive
                        ? "bg-accent-bg text-foreground font-medium"
                        : "text-muted hover:text-foreground hover:bg-accent-bg/50"
                    }`}
                    title={collapsed ? item.label : undefined}
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

        {/* User info — bottom-left (click to show Log out) */}
        {isAuthenticated && user && (
          <div
            className={`py-3 shrink-0 min-w-0 relative ${collapsed ? "px-0 flex justify-center" : "px-3"}`}
            ref={userBlockRef}
          >
            {logoutOpen && !collapsed && (
              <div className="rounded-lg border border-border bg-card shadow-lg mb-1.5 overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2">
                  {(
                    [
                      { mode: "light" as ThemeMode, icon: Sun, label: "Light" },
                      { mode: "dark" as ThemeMode, icon: Moon, label: "Dark" },
                      { mode: "auto" as ThemeMode, icon: Monitor, label: "Auto" },
                    ] as const
                  ).map(({ mode, icon: Icon, label }) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setTheme(mode)}
                      className={`flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                        theme === mode
                          ? "bg-accent/15 text-accent"
                          : "text-muted hover:text-foreground"
                      }`}
                      title={label}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {label}
                    </button>
                  ))}
                </div>
                <div className="border-t border-border">
                  <button
                    type="button"
                    onClick={() => {
                      logout({ logoutParams: { returnTo: appUrl } });
                      setLogoutOpen(false);
                    }}
                    className="flex items-center gap-1.5 w-full justify-center px-3 py-2 text-xs font-medium text-muted hover:text-foreground transition-colors cursor-pointer"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Log out
                  </button>
                </div>
              </div>
            )}
            {collapsed ? (
              <button
                type="button"
                onClick={() => setLogoutOpen((o) => !o)}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-accent/20 text-sm font-semibold text-accent hover:ring-2 hover:ring-accent/30 transition-all cursor-pointer"
                title={username || user.nickname || user.name || "User"}
              >
                {(username || user.nickname || user.name || "U")
                  .charAt(0)
                  .toUpperCase()}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setLogoutOpen((o) => !o)}
                className="flex items-center gap-2.5 rounded-xl bg-background px-3 py-2.5 min-w-0 w-full text-left hover:bg-muted/30 transition-colors cursor-pointer"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/20 text-sm font-semibold text-accent">
                  {(username || user.nickname || user.name || "U")
                    .charAt(0)
                    .toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <p
                    className="text-sm font-medium text-foreground truncate leading-tight"
                    title={username || user.nickname || user.name || undefined}
                  >
                    {username || user.nickname || user.name || "User"}
                  </p>
                  <p
                    className="text-[11px] text-muted truncate leading-tight mt-0.5"
                    title={user.email ?? undefined}
                  >
                    {user.email}
                  </p>
                </div>
              </button>
            )}
            {logoutOpen && collapsed && (
              <div className="absolute left-full bottom-2 ml-2 rounded-lg border border-border bg-card shadow-lg z-20 overflow-hidden min-w-[140px]">
                <div className="flex items-center justify-center gap-1 px-2 py-2">
                  {(
                    [
                      { mode: "light" as ThemeMode, icon: Sun, label: "Light" },
                      { mode: "dark" as ThemeMode, icon: Moon, label: "Dark" },
                      { mode: "auto" as ThemeMode, icon: Monitor, label: "Auto" },
                    ] as const
                  ).map(({ mode, icon: Icon, label }) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setTheme(mode)}
                      className={`rounded-md p-1.5 transition-colors cursor-pointer ${
                        theme === mode
                          ? "bg-accent/15 text-accent"
                          : "text-muted hover:text-foreground"
                      }`}
                      title={label}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </button>
                  ))}
                </div>
                <div className="border-t border-border">
                  <button
                    type="button"
                    onClick={() => {
                      logout({ logoutParams: { returnTo: appUrl } });
                      setLogoutOpen(false);
                    }}
                    className="flex items-center gap-1.5 w-full px-3 py-2.5 text-sm text-muted hover:text-foreground hover:bg-muted/10 transition-colors cursor-pointer"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Log out
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </aside>
      {/* Resize handle — desktop only */}
      {!isMobile && (
        <div
          onMouseDown={handleMouseDown}
          className={`absolute right-0 top-0 bottom-0 w-1 cursor-col-resize transition-all ${
            isResizing ? "bg-accent w-1" : "bg-transparent hover:bg-accent/40"
          }`}
          style={{ zIndex: 10 }}
          aria-label="Resize sidebar"
          title="Drag to resize"
        />
      )}
    </div>
  );
}
