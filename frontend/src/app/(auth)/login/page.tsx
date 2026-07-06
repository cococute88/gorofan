"use client";

import { Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/primitives";
import { API_BASE } from "@/lib/api/client";
import { googleLoginUrl } from "@/lib/api/endpoints";

const ERROR_MESSAGES: Record<string, string> = {
  no_token: "로그인이 완료되지 않았어요. 다시 시도해 주세요.",
  auth_disabled: "이 서버는 로컬 모드로 실행 중이에요. 로그인 없이 계속할 수 있어요.",
  UNAUTHENTICATED: "인증에 실패했어요. 다시 시도해 주세요.",
};

function LoginCard() {
  const router = useRouter();
  const params = useSearchParams();
  const errorCode = params.get("error");
  const errorMessage = errorCode
    ? ERROR_MESSAGES[errorCode] ?? "로그인 중 문제가 발생했어요. 다시 시도해 주세요."
    : null;

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
          <Sparkles className="h-7 w-7 text-primary" />
        </div>
        <h1 className="text-xl font-bold">AI Creative Workspace</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          나만의 AI 캐릭터 채팅과 소설 창작 워크스페이스
        </p>

        {errorMessage ? (
          <p
            role="alert"
            className="mt-4 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            {errorMessage}
          </p>
        ) : null}

        <div className="mt-6 space-y-3">
          <Button
            className="w-full"
            onClick={() => {
              window.location.href = `${API_BASE}${googleLoginUrl("/")}`;
            }}
          >
            Google로 계속하기
          </Button>
          <Button variant="outline" className="w-full" onClick={() => router.push("/")}>
            로컬 모드로 계속
          </Button>
        </div>

        <p className="mt-4 text-xs text-muted-foreground">
          로컬 모드에서는 로그인 없이 이 기기에서만 데이터를 사용합니다.
        </p>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginCard />
    </Suspense>
  );
}
