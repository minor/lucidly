"use client";

import { useAuth0 } from "@auth0/auth0-react";
import { useEffect } from "react";
import { setAuthToken } from "@/lib/api";

/**
 * Keeps the API client's auth token in sync with the Auth0 session.
 * Render once near the app root (e.g. in LayoutShell).
 */
export function AuthTokenSync() {
  const { isAuthenticated, getAccessTokenSilently, loginWithRedirect } = useAuth0();

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
      .catch((err) => {
        console.error("[AuthTokenSync] Failed to get access token:", err);
        if (!cancelled) {
          setAuthToken(null);
          // Session expired or refresh token invalidated — redirect to login
          if (err?.error === "login_required" || err?.error === "missing_refresh_token") {
            loginWithRedirect({ appState: { returnTo: window.location.pathname } });
          }
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, getAccessTokenSilently, loginWithRedirect]);

  return null;
}
