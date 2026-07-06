"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, RefreshCw } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { ChatComposer } from "@/components/chat/chat-composer";
import { MessageBubble } from "@/components/chat/message-bubble";
import { Button } from "@/components/ui/button";
import { ErrorState, Spinner } from "@/components/ui/states";
import { useMessages } from "@/hooks/use-chats";
import * as api from "@/lib/api/endpoints";
import type { Message } from "@/types";

export default function ChatRoomPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const chatId = params.id;
  const { data, isPending, isError, refetch } = useMessages(chatId);

  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [optimisticUser, setOptimisticUser] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const messages = useMemo<Message[]>(() => {
    const items = data?.items ?? [];
    return [...items]
      .filter((m) => m.is_active !== false && m.role !== "system")
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
  }, [data]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamText, optimisticUser]);

  async function finish() {
    setStreaming(false);
    setStreamText("");
    setOptimisticUser(null);
    abortRef.current = null;
    await qc.invalidateQueries({ queryKey: ["messages", chatId] });
    await qc.invalidateQueries({ queryKey: ["chats"] });
  }

  async function runStream(fn: (h: Parameters<typeof api.streamRegenerate>[1], signal: AbortSignal) => Promise<string>) {
    setError(null);
    setStreaming(true);
    setStreamText("");
    stoppedRef.current = false;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    await fn(
      {
        onToken: (delta) => setStreamText((t) => t + delta),
        onDone: () => {},
        onError: (e) => {
          if (!stoppedRef.current && e.code !== "SSE_DISCONNECTED") {
            setError(e.message || "응답 중 오류가 발생했어요.");
          }
        },
      },
      ctrl.signal,
    );
    await finish();
  }

  function send(text: string) {
    setOptimisticUser(text);
    void runStream((h, signal) => api.streamMessage(chatId, text, h, { signal }));
  }

  function regenerate() {
    if (streaming) return;
    void runStream((h, signal) => api.streamRegenerate(chatId, h, { signal }));
  }

  function stop() {
    stoppedRef.current = true;
    abortRef.current?.abort();
  }

  const lastRole = messages[messages.length - 1]?.role;

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col md:h-[calc(100vh-6rem)]">
      <div className="mb-2 flex items-center justify-between">
        <button
          onClick={() => router.push("/chats")}
          className="flex items-center gap-1 text-sm text-muted-foreground"
        >
          <ChevronLeft className="h-4 w-4" /> 대화 목록
        </button>
        {lastRole === "assistant" && !streaming ? (
          <Button variant="ghost" size="sm" onClick={regenerate}>
            <RefreshCw className="h-4 w-4" /> 다시 생성
          </Button>
        ) : null}
      </div>

      <div
        ref={scrollRef}
        role="log"
        aria-live="polite"
        className="flex-1 space-y-3 overflow-y-auto rounded-[var(--radius)] border bg-card/40 p-3"
      >
        {isPending ? (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        ) : isError ? (
          <ErrorState message="메시지를 불러오지 못했어요." onRetry={() => refetch()} />
        ) : (
          <>
            {messages.map((m) => (
              <MessageBubble key={m.id} role={m.role} content={m.content} status={m.status} />
            ))}
            {optimisticUser ? (
              <MessageBubble role="user" content={optimisticUser} />
            ) : null}
            {streaming ? (
              <MessageBubble role="assistant" content={streamText} streaming />
            ) : null}
            {messages.length === 0 && !streaming ? (
              <p className="py-16 text-center text-sm text-muted-foreground">
                첫 메시지를 보내 대화를 시작하세요.
              </p>
            ) : null}
          </>
        )}
      </div>

      {error ? (
        <p className="mt-2 text-center text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <ChatComposer onSend={send} onStop={stop} streaming={streaming} />
    </div>
  );
}
