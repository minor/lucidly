"use client";

import { useAuth0 } from "@auth0/auth0-react";
import { usePathname } from "next/navigation";
import { LogIn, UserPlus } from "lucide-react";

/**
 * Floating Log in / Sign up buttons pinned to the top-right.
 * Shown only when not authenticated. Hidden on the home page.
 */
export function TopAuthBar() {
  const { isLoading, isAuthenticated, loginWithRedirect } = useAuth0();
  const pathname = usePathname();

  if (pathname === "/") return null;
  if (isLoading) return null;
  if (isAuthenticated) return null;

  return (
    <div className="fixed top-4 right-5 z-50 flex items-center gap-2">
      <button
        type="button"
        onClick={() => loginWithRedirect()}
        className="flex items-center gap-1.5 rounded-lg border border-border bg-card/80 backdrop-blur-sm px-3 py-2 text-xs font-medium text-muted hover:text-foreground hover:border-foreground/20 shadow-sm transition-colors cursor-pointer"
      >
        <LogIn className="h-3.5 w-3.5" />
        Log in
      </button>
      <button
        type="button"
        onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: "signup" } })}
        className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-medium text-accent-foreground hover:bg-accent/90 shadow-sm transition-colors cursor-pointer"
      >
        <UserPlus className="h-3.5 w-3.5" />
        Sign up
      </button>
    </div>
  );
}
