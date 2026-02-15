"use client";

import { Auth0Provider as Auth0ProviderSDK } from "@auth0/auth0-react";
import { type ReactNode } from "react";

const domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN;
const clientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID;
const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

if (!domain || !clientId) {
  throw new Error(
    "Missing Auth0 env: set NEXT_PUBLIC_AUTH0_DOMAIN and NEXT_PUBLIC_AUTH0_CLIENT_ID"
  );
}

export function Auth0Provider({ children }: { children: ReactNode }) {
  return (
    <Auth0ProviderSDK
      domain={domain!}
      clientId={clientId!}
      authorizationParams={{
        redirect_uri: appUrl,
      }}
    >
      {children}
    </Auth0ProviderSDK>
  );
}
