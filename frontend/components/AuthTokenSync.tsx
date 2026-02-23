"use client";

import { useAuth0 } from "@auth0/auth0-react";
import { useEffect } from "react";
import { setAuthToken } from "@/lib/api";

/**
 * Keeps the API client's auth token in sync with the Auth0 session.
 * Render once near the app root (e.g. in LayoutShell).
 */
export function AuthTokenSync() {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();

  useEffect(() => {
    if (!isAuthenticated) {
      setAuthToken(null);
      return;
    }

    let cancelled = false;
    getAccessTokenSilently()
      .then((token) => {
        if (!cancelled) setAuthToken(token);
      })
      .catch(() => {
        if (!cancelled) setAuthToken(null);
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, getAccessTokenSilently]);

  return null;
}
