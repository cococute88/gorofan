"use client";

import { ChevronLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { FormField, Input, Textarea } from "@/components/ui/primitives";
import { useCreateWork } from "@/hooks/use-novels";
import { useWorlds } from "@/hooks/use-worlds";

// 3-step wizard (design 7.3.3).
export default function NewWorkPage() {
  const router = useRouter();
  const create = useCreateWork();
  const worlds = useWorlds();
  const [step, setStep] = useState(1);
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [worldId, setWorldId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function finish() {
    if (!title.trim()) {
      setStep(1);
      setError("제목을 입력해 주세요.");
      return;
    }
    const w = await create.mutateAsync({
      title,
      genre,
      synopsis,
      world_id: worldId || null,
    });
    router.push(`/novels/${w.id}`);
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm">
          <ChevronLeft className="h-4 w-4" /> 작품 만들기
        </button>
        <span className="text-sm text-muted-foreground">Step {step} / 3</span>
      </div>
      {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}

      {step === 1 ? (
        <>
          <FormField label="제목" required>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="별빛 연대기" />
          </FormField>
          <FormField label="장르">
            <Input value={genre} onChange={(e) => setGenre(e.target.value)} placeholder="판타지 · 로맨스" />
          </FormField>
          <Button onClick={() => setStep(2)}>다음</Button>
        </>
      ) : step === 2 ? (
        <>
          <FormField label="줄거리 (선택)">
            <Textarea value={synopsis} onChange={(e) => setSynopsis(e.target.value)} />
          </FormField>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(1)}>
              이전
            </Button>
            <Button onClick={() => setStep(3)}>다음</Button>
          </div>
        </>
      ) : (
        <>
          <FormField label="세계관 연결 (선택)">
            <select
              className="h-10 w-full rounded-md border bg-background px-3 text-sm"
              value={worldId}
              onChange={(e) => setWorldId(e.target.value)}
            >
              <option value="">연결 안 함</option>
              {worlds.data?.items.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </FormField>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(2)}>
              이전
            </Button>
            <Button onClick={finish} loading={create.isPending}>
              작품 생성
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
