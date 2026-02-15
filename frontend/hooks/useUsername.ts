"use client";

import { useState, useEffect, useCallback } from "react";
import type { User } from "@auth0/auth0-react";
import { getUsername as fetchUsername, setUsername as saveUsername } from "@/lib/api";

/**
 * Fetches and stores a user-chosen display name in Supabase,
 * keyed by the Auth0 user id (`user.sub`).
 *
 * Returns:
 *  - username: the stored display name, or null if not yet chosen
 *  - setUsername: persist a new display name (async, may throw on duplicates)
 *  - needsUsername: true when the user is logged in but hasn't picked a name yet
 *  - loading: true while fetching the initial username from the server
 */
export function useUsername(user: User | undefined) {
  const [username, setUsernameState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const auth0Id = user?.sub ?? null;

  // Load from Supabase on mount / user change
  useEffect(() => {
    if (!auth0Id) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchUsername(auth0Id)
      .then((name) => {
        if (!cancelled) setUsernameState(name);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth0Id]);

  const setUsername = useCallback(
    async (name: string) => {
      if (!auth0Id) throw new Error("Not logged in");
      const saved = await saveUsername(auth0Id, name);
      setUsernameState(saved);
    },
    [auth0Id]
  );

  return {
    username,
    setUsername,
    needsUsername: !loading && !!user && !username,
    loading,
  };
}
