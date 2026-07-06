"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { PWALifecycle } from "@/components/pwa";
import { setAccessToken } from "@/lib/api/client";
import { getToken } from "@/lib/auth";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );

  // Hydrate the in-memory access token from localStorage on first mount.
  // In local mode (AUTH_ENABLED=false) this is simply null and the backend
  // injects the default user.
  useEffect(() => {
    setAccessToken(getToken());
  }, []);

  return (
    <QueryClientProvider client={client}>
      {children}
      <PWALifecycle />
    </QueryClientProvider>
  );
}
