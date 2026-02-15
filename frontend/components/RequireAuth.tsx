"use client";

import { useAuth0 } from "@auth0/auth0-react";
import { useEffect, type ReactNode } from "react";
import { Loader2 } from "lucide-react";

/**
 * Wrapper that redirects unauthenticated users to Auth0 login.
 * After login, the user is returned to the page they were trying to access.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      loginWithRedirect({
        appState: { returnTo: window.location.pathname },
      });
    }
  }, [isLoading, isAuthenticated, loginWithRedirect]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  return <>{children}</>;
}
