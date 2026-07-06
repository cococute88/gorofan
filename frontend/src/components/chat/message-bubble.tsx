"use client";

import { cn } from "@/lib/utils";

export function MessageBubble({
  role,
  content,
  status,
  streaming,
}: {
  role: "user" | "assistant" | "system";
  content: string;
  status?: string;
  streaming?: boolean;
}) {
  const isUser = role === "user";
  if (role === "system") return null;
  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm sm:max-w-[75%]",
          isUser
            ? "rounded-br-sm bg-primary text-primary-foreground"
            : "rounded-bl-sm bg-accent text-foreground",
        )}
      >
        {content}
        {streaming ? (
          <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-current align-middle motion-reduce:animate-none" />
        ) : null}
        {status === "partial" ? (
          <span className="mt-1 block text-xs italic opacity-70">· 중단됨 (부분 저장)</span>
        ) : null}
      </div>
    </div>
  );
}
