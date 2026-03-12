"use client";

import { useState, useEffect, useCallback } from "react";
import { getIntegrationStatus } from "@/lib/api";
import type { IntegrationStatus } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useIntegrationStatus() {
  const [status, setStatus] = useState<IntegrationStatus>({ linear: false, github: false });
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const s = await getIntegrationStatus();
      setStatus(s);
    } catch {
      // unauthenticated or error — keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const connectProvider = useCallback(
    (provider: "linear" | "github"): Promise<void> => {
      return new Promise((resolve, reject) => {
        const url = `${API_BASE}/api/integrations/${provider}/connect`;
        const popup = window.open(url, `connect_${provider}`, "width=600,height=700");

        const handler = (event: MessageEvent) => {
          if (event.data?.type === "oauth_success" && event.data?.provider === provider) {
            window.removeEventListener("message", handler);
            refresh().then(resolve);
          } else if (event.data?.type === "oauth_error" && event.data?.provider === provider) {
            window.removeEventListener("message", handler);
            reject(new Error(event.data.error || "OAuth failed"));
          }
        };
        window.addEventListener("message", handler);

        // Fallback: if popup closes without postMessage
        const interval = setInterval(() => {
          if (popup?.closed) {
            clearInterval(interval);
            window.removeEventListener("message", handler);
            refresh().then(resolve).catch(reject);
          }
        }, 500);
      });
    },
    [refresh]
  );

  return { status, loading, refresh, connectProvider };
}
