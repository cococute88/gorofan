"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Sparkles, Square } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { TipTapEditor, type TipTapHandle } from "@/components/novel/tiptap-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/primitives";
import { Spinner } from "@/components/ui/states";
import { useChapters, useUpdateChapter } from "@/hooks/use-novels";
import * as api from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";

type SaveState = "idle" | "saving" | "saved" | "conflict" | "error";

export default function ChapterEditorPage() {
  const params = useParams<{ id: string; chapterId: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const workId = params.id;
  const chapterId = params.chapterId;

  const chapters = useChapters(workId);
  const update = useUpdateChapter(workId);
  const chapter = chapters.data?.find((c) => c.id === chapterId);

  const editorRef = useRef<TipTapHandle>(null);
  const initializedRef = useRef(false);
  const versionRef = useRef(0);
  const textRef = useRef("");
  const jsonRef = useRef<unknown>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [remountKey, setRemountKey] = useState(0);
  const [initialText, setInitialText] = useState("");
  const [title, setTitle] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [streaming, setStreaming] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [targetWords, setTargetWords] = useState(600);
  const [genError, setGenError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);

  // Initialise local state once when the chapter first loads.
  useEffect(() => {
    if (chapter && !initializedRef.current) {
      initializedRef.current = true;
      versionRef.current = chapter.version;
      textRef.current = chapter.content_text;
      setInitialText(chapter.content_text);
      setTitle(chapter.title);
      setRemountKey((k) => k + 1);
    }
  }, [chapter]);

  const doSave = useCallback(async () => {
    if (streaming) return;
    setSaveState("saving");
    try {
      const saved = await update.mutateAsync({
        id: chapterId,
        title,
        content_text: textRef.current,
        content_doc: jsonRef.current ?? undefined,
        version: versionRef.current,
      });
      versionRef.current = saved.version;
      setSaveState("saved");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setSaveState("conflict");
      } else {
        setSaveState("error");
      }
    }
  }, [chapterId, title, streaming, update]);

  function scheduleSave() {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaveState("idle");
    saveTimer.current = setTimeout(() => void doSave(), 1200);
  }

  async function reloadFromServer() {
    const fresh = await qc.fetchQuery({
      queryKey: ["chapters", workId],
      queryFn: () => api.listChapters(workId),
    });
    const c = fresh.find((x) => x.id === chapterId);
    if (c) {
      versionRef.current = c.version;
      textRef.current = c.content_text;
      setInitialText(c.content_text);
      setRemountKey((k) => k + 1);
    }
  }

  async function startContinue() {
    setGenError(null);
    setStreaming(true);
    stoppedRef.current = false;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    editorRef.current?.focusEnd();
    editorRef.current?.appendText("\n\n");
    await api.streamContinueChapter(
      chapterId,
      { instruction, target_words: targetWords },
      {
        onToken: (delta) => editorRef.current?.appendText(delta),
        onError: (e) => {
          if (!stoppedRef.current && e.code !== "SSE_DISCONNECTED") {
            setGenError(e.message || "생성 중 오류가 발생했어요.");
          }
        },
      },
      { signal: ctrl.signal },
    );
    setStreaming(false);
    abortRef.current = null;
    // Server persisted the appended content (design 11.6); reload authoritative version.
    await reloadFromServer();
  }

  function stopContinue() {
    stoppedRef.current = true;
    abortRef.current?.abort();
  }

  if (chapters.isPending || !chapter) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col">
      <div className="mb-2 flex items-center justify-between gap-2">
        <button
          onClick={() => router.push(`/novels/${workId}`)}
          className="flex shrink-0 items-center gap-1 text-sm text-muted-foreground"
        >
          <ChevronLeft className="h-4 w-4" /> 작품
        </button>
        <span className="text-xs text-muted-foreground">{saveLabel(saveState)}</span>
      </div>

      <Input
        value={title}
        onChange={(e) => {
          setTitle(e.target.value);
          scheduleSave();
        }}
        placeholder="챕터 제목"
        className="mb-3 h-11 border-none px-0 text-xl font-bold focus-visible:ring-0"
      />

      {saveState === "conflict" ? (
        <div className="mb-2 flex items-center justify-between rounded-md border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
          <span>다른 곳에서 먼저 저장되어 충돌했어요.</span>
          <Button size="sm" variant="outline" onClick={reloadFromServer}>
            최신 내용 불러오기
          </Button>
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto rounded-[var(--radius)] border bg-card p-4">
        <TipTapEditor
          key={remountKey}
          ref={editorRef}
          initialText={initialText}
          editable={!streaming}
          onChange={(text, json) => {
            textRef.current = text;
            jsonRef.current = json;
            if (!streaming) scheduleSave();
          }}
        />
      </div>

      {genError ? (
        <p className="mt-2 text-center text-sm text-destructive" role="alert">
          {genError}
        </p>
      ) : null}

      <div className="mt-3 flex flex-col gap-2 border-t pt-3 sm:flex-row sm:items-center">
        <Input
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="이어쓰기 지시 (선택): 예) 긴장감을 높여줘"
          className="flex-1"
          disabled={streaming}
        />
        <div className="flex items-center gap-2">
          <Input
            type="number"
            value={targetWords}
            onChange={(e) => setTargetWords(Number(e.target.value))}
            className="w-24"
            disabled={streaming}
            aria-label="목표 분량(단어)"
          />
          {streaming ? (
            <Button variant="destructive" onClick={stopContinue}>
              <Square className="h-4 w-4" /> 중단
            </Button>
          ) : (
            <Button onClick={startContinue}>
              <Sparkles className="h-4 w-4" /> AI 이어쓰기
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function saveLabel(s: SaveState): string {
  switch (s) {
    case "saving":
      return "저장 중…";
    case "saved":
      return "저장됨";
    case "conflict":
      return "충돌 발생";
    case "error":
      return "저장 실패";
    default:
      return "";
  }
}
