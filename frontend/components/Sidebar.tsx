"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Zap,
  PlusCircle,
  Trophy,
  Search,
  ChevronDown,
} from "lucide-react";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/play", label: "New Challenge", icon: PlusCircle },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`flex flex-col border-r border-border bg-sidebar transition-all duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Brand */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <Link href="/" className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-accent" />
          {!collapsed && (
            <span className="font-serif text-lg font-semibold tracking-tight">
              Lucidly
            </span>
          )}
        </Link>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="ml-auto text-muted hover:text-foreground transition-colors"
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
        <div className="px-4 py-3 border-b border-border">
          <button className="flex items-center gap-1.5 text-sm font-medium text-muted hover:text-foreground transition-colors">
            <Zap className="h-3.5 w-3.5" />
            Arena Mode
            <ChevronDown className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                isActive
                  ? "bg-accent-bg text-foreground font-medium"
                  : "text-muted hover:text-foreground hover:bg-accent-bg/50"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="border-t border-border px-4 py-3">
          <div className="flex items-center gap-3 text-xs text-muted">
            <Link href="#" className="hover:text-foreground transition-colors">
              Terms
            </Link>
            <Link href="#" className="hover:text-foreground transition-colors">
              Privacy
            </Link>
          </div>
        </div>
      )}
    </aside>
  );
}
