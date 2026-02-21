"use client";

import { useState, useCallback, type ReactNode } from "react";
import Image from "next/image";
import { Menu } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { TopAuthBar } from "@/components/TopAuthBar";
import { UsernameGate } from "@/components/UsernameGate";
import { AuthTokenSync } from "@/components/AuthTokenSync";

export function LayoutShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar — hidden on mobile */}
      <div className="hidden sm:block">
        <Sidebar />
      </div>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 sm:hidden">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-[2px] animate-fade-in"
            onClick={closeMobile}
          />
          <div className="relative h-full w-[240px] shadow-xl animate-slide-in-left">
            <Sidebar onNavigate={closeMobile} isMobile />
          </div>
        </div>
      )}

      {/* Mobile top bar — fixed to viewport, only on small screens */}
      <div className="fixed top-0 left-0 right-0 h-14 sm:hidden flex items-center gap-3 border-b border-border bg-background px-4 z-40">
        <button
          onClick={() => setMobileOpen(true)}
          className="text-muted hover:text-foreground transition-colors cursor-pointer p-1 -ml-1"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-1.5">
          <Image
            src="/logo.svg"
            alt="No Shot"
            width={24}
            height={24}
            className="h-8 w-8"
          />
          <span className="font-heading text-base font-semibold tracking-tight">
            No Shot
          </span>
        </div>
      </div>

      {/* Main content — pt-14 on mobile to clear the fixed top bar */}
      <main className="flex-1 overflow-y-auto relative pt-14 sm:pt-0">
        <AuthTokenSync />
        <TopAuthBar />
        <UsernameGate />
        {children}
      </main>
    </div>
  );
}
