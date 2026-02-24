"use client";

import { useAuth0 } from "@auth0/auth0-react";
import { useUsername } from "@/hooks/useUsername";
import { UsernameModal } from "@/components/UsernameModal";
import { setAuthToken } from "@/lib/api";

/**
 * Global overlay that prompts authenticated users to pick a username
 * if they haven't already. Renders nothing otherwise.
 */
export function UsernameGate() {
  const { user, isAuthenticated, getAccessTokenSilently } = useAuth0();
  const { needsUsername, setUsername } = useUsername(user);

  if (!isAuthenticated || !needsUsername) return null;

  const handleConfirm = async (name: string) => {
    const token = await getAccessTokenSilently();
    setAuthToken(token);
    await setUsername(name);
  };

  return (
    <UsernameModal
      defaultValue={user?.nickname || user?.name?.split("@")[0] || ""}
      onConfirm={handleConfirm}
    />
  );
}
