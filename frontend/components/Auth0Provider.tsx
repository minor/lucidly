"use client";

import {
  Auth0Provider as Auth0ProviderSDK,
  type AppState,
} from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { type ReactNode, useCallback } from "react";

const domain = process.env.AUTH0_ISSUER_BASE_URL;
const clientId = process.env.AUTH0_CLIENT_ID;
const appUrl = process.env.AUTH0_BASE_URL || "http://localhost:3000";

if (!domain || !clientId) {
  throw new Error(
    "Missing Auth0 env: set NEXT_PUBLIC_AUTH0_DOMAIN and NEXT_PUBLIC_AUTH0_CLIENT_ID",
  );
}

export function Auth0Provider({ children }: { children: ReactNode }) {
  const router = useRouter();

  const onRedirectCallback = useCallback(
    (appState?: AppState) => {
      // After login, navigate to the page the user was trying to reach
      router.replace(appState?.returnTo || "/");
    },
    [router],
  );

  return (
    <Auth0ProviderSDK
      domain={domain!}
      clientId={clientId!}
      authorizationParams={{
        redirect_uri: appUrl,
      }}
      onRedirectCallback={onRedirectCallback}
    >
      {children}
    </Auth0ProviderSDK>
  );
}
