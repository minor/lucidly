"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { usePathname } from "next/navigation";
import { LogIn, LogOut, UserPlus } from "lucide-react";
import { useUsername } from "@/hooks/useUsername";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

/**
 * Floating auth buttons pinned to the top-right of the page.
 * Hidden on the home page.
 */
export function TopAuthBar() {
  const { isLoading, isAuthenticated, user, loginWithRedirect, logout } = useAuth0();
  const { username } = useUsername(user);
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  // Don't show on the home page
  if (pathname === "/") return null;
  if (isLoading) return null;

  return (
    <div className="fixed top-4 right-5 z-50 flex flex-col items-end gap-0" ref={menuRef}>
      {isAuthenticated ? (
        <>
          {menuOpen && (
            <button
              type="button"
              onClick={() => {
                logout({ logoutParams: { returnTo: appUrl } });
                setMenuOpen(false);
              }}
              className="flex items-center gap-1.5 rounded-lg border border-border bg-card shadow-lg px-3 py-2 text-xs font-medium text-muted hover:text-foreground hover:border-foreground/20 transition-colors cursor-pointer mb-1.5"
            >
              <LogOut className="h-3.5 w-3.5" />
              Log out
            </button>
          )}
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            className="flex items-center gap-2 rounded-xl bg-background px-3 py-2 text-xs font-medium text-foreground border border-border shadow-sm hover:border-foreground/20 transition-colors cursor-pointer"
          >
            <span className="rounded-full h-5 w-5 flex items-center justify-center bg-accent/20 text-accent text-[10px] font-semibold">
              {(username || user?.nickname || user?.name || "U").charAt(0).toUpperCase()}
            </span>
            <span className="max-w-[120px] truncate">
              {username || user?.nickname || user?.name || "User"}
            </span>
          </button>
        </>
      ) : (
        <div className="flex items-center gap-2">
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
      )}
    </div>
  );
}
