"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useUsername } from "@/hooks/useUsername";

interface UsernameContextValue {
  username: string | null;
  setUsername: (name: string) => Promise<void>;
  needsUsername: boolean;
  loading: boolean;
}

const UsernameContext = createContext<UsernameContextValue | null>(null);

export function UsernameProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth0();
  const value = useUsername(user);
  return (
    <UsernameContext.Provider value={value}>
      {children}
    </UsernameContext.Provider>
  );
}

export function useUsernameContext() {
  const ctx = useContext(UsernameContext);
  if (!ctx) throw new Error("useUsernameContext must be used inside UsernameProvider");
  return ctx;
}
