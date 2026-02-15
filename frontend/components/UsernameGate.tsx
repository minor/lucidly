"use client";

import { useAuth0 } from "@auth0/auth0-react";
import { useUsername } from "@/hooks/useUsername";
import { UsernameModal } from "@/components/UsernameModal";

/**
 * Global overlay that prompts authenticated users to pick a username
 * if they haven't already. Renders nothing otherwise.
 */
export function UsernameGate() {
  const { user, isAuthenticated } = useAuth0();
  const { needsUsername, setUsername } = useUsername(user);

  if (!isAuthenticated || !needsUsername) return null;

  return (
    <UsernameModal
      defaultValue={user?.nickname || user?.name?.split("@")[0] || ""}
      onConfirm={setUsername}
    />
  );
}
