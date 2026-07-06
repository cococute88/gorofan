"use client";

import { Send, Square } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";

export function ChatComposer({
  onSend,
  onStop,
  streaming,
}: {
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
}) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function submit() {
    const v = text.trim();
    if (!v || streaming) return;
    onSend(v);
    setText("");
    if (ref.current) ref.current.style.height = "auto";
  }

  return (
    <div className="flex items-end gap-2 border-t bg-background p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          e.target.style.height = "auto";
          e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          } else if (e.key === "Escape" && streaming) {
            onStop();
          }
        }}
        rows={1}
        placeholder="메시지를 입력하세요… (Enter 전송, Shift+Enter 줄바꿈)"
        aria-label="메시지 입력"
        className="max-h-40 flex-1 resize-none rounded-2xl border bg-background px-4 py-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      {streaming ? (
        <Button variant="destructive" size="icon" onClick={onStop} aria-label="중단">
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button size="icon" onClick={submit} disabled={!text.trim()} aria-label="전송">
          <Send className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
