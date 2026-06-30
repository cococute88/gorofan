"use client";

import { ChevronDown, ChevronLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, FormField, Input, Textarea } from "@/components/ui/primitives";
import { ApiError } from "@/lib/api/client";
import { useWorlds } from "@/hooks/use-worlds";
import type { Character } from "@/types";

export interface CharacterFormValues {
  name: string;
  greeting: string;
  speech_style: string;
  personality: string;
  tags: string[];
  world_id: string | null;
}

export function CharacterForm({
  initial,
  submitting,
  onSubmit,
}: {
  initial?: Partial<Character>;
  submitting?: boolean;
  onSubmit: (v: CharacterFormValues) => Promise<void>;
}) {
  const router = useRouter();
  const worlds = useWorlds();
  const [advanced, setAdvanced] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tagInput, setTagInput] = useState("");
  const [values, setValues] = useState<CharacterFormValues>({
    name: initial?.name ?? "",
    greeting: initial?.greeting ?? "",
    speech_style: initial?.speech_style ?? "",
    personality: initial?.personality ?? "",
    tags: initial?.tags ?? [],
    world_id: initial?.world_id ?? null,
  });

  function set<K extends keyof CharacterFormValues>(k: K, v: CharacterFormValues[K]) {
    setValues((s) => ({ ...s, [k]: v }));
  }

  async function handleSubmit() {
    setError(null);
    if (!values.name.trim()) {
      setError("이름을 입력해 주세요.");
      return;
    }
    try {
      await onSubmit(values);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "저장에 실패했어요.");
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm">
          <ChevronLeft className="h-4 w-4" /> 캐릭터 만들기
        </button>
        <Button onClick={handleSubmit} loading={submitting}>
          저장
        </Button>
      </div>

      {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}

      <FormField label="이름" required>
        <Input value={values.name} onChange={(e) => set("name", e.target.value)} placeholder="루나" />
      </FormField>
      <FormField label="첫인사">
        <Textarea
          value={values.greeting}
          onChange={(e) => set("greeting", e.target.value)}
          placeholder="안녕, 오늘은 무슨 이야기를 할까?"
        />
      </FormField>
      <FormField label="말투">
        <Input
          value={values.speech_style}
          onChange={(e) => set("speech_style", e.target.value)}
          placeholder="다정하고 장난스러운 반말"
        />
      </FormField>

      <button
        onClick={() => setAdvanced((v) => !v)}
        className="mt-2 flex items-center gap-1 text-sm text-muted-foreground"
      >
        <ChevronDown className={`h-4 w-4 transition ${advanced ? "rotate-180" : ""}`} />
        고급 설정 (성격·태그·세계관 연결)
      </button>

      {advanced ? (
        <div className="mt-3 space-y-4 border-t pt-4">
          <FormField label="성격">
            <Textarea value={values.personality} onChange={(e) => set("personality", e.target.value)} />
          </FormField>
          <FormField label="태그">
            <div className="mb-2 flex flex-wrap gap-1">
              {values.tags.map((t) => (
                <Badge key={t} className="cursor-pointer" onClick={() => set("tags", values.tags.filter((x) => x !== t))}>
                  #{t} ✕
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && tagInput.trim()) {
                    e.preventDefault();
                    set("tags", [...values.tags, tagInput.trim()]);
                    setTagInput("");
                  }
                }}
                placeholder="태그 입력 후 Enter"
              />
            </div>
          </FormField>
          <FormField label="세계관 연결">
            <select
              className="h-10 w-full rounded-md border bg-background px-3 text-sm"
              value={values.world_id ?? ""}
              onChange={(e) => set("world_id", e.target.value || null)}
            >
              <option value="">연결 안 함</option>
              {worlds.data?.items.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </FormField>
        </div>
      ) : null}
    </div>
  );
}
