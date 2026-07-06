"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Spinner } from "@/components/ui/states";
import { setAccessToken } from "@/lib/api/client";
import { parseAccessTokenFromHash, setToken } from "@/lib/auth";

/**
 * OAuth login completion (design 14.4). The backend bounces the browser here
 * with the freshly issued access token in the URL fragment (never sent to a
 * server / not logged). We persist it and forward into the app.
 */
export default function AuthCallbackPage() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const token = parseAccessTokenFromHash(window.location.hash);
    if (token) {
      setToken(token);
      setAccessToken(token);
      // Strip the fragment so the token is not left in history, then enter the app.
      window.history.replaceState(null, "", "/auth/callback");
      router.replace("/");
    } else {
      setFailed(true);
      const t = setTimeout(() => router.replace("/login?error=no_token"), 1500);
      return () => clearTimeout(t);
    }
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-4 text-center">
      <Spinner className="h-6 w-6" />
      <p className="text-sm text-muted-foreground">
        {failed ? "로그인 정보를 확인하지 못했어요. 로그인 화면으로 이동합니다…" : "로그인 중…"}
      </p>
    </div>
  );
}
