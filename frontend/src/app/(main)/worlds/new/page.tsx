"use client";

import { ChevronLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { FormField, Input, Textarea } from "@/components/ui/primitives";
import { useCreateWorld } from "@/hooks/use-worlds";

export default function NewWorldPage() {
  const router = useRouter();
  const create = useCreateWorld();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [era, setEra] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!name.trim()) {
      setError("이름을 입력해 주세요.");
      return;
    }
    const w = await create.mutateAsync({ name, description, era });
    router.push(`/worlds/${w.id}`);
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm">
          <ChevronLeft className="h-4 w-4" /> 새 세계관
        </button>
        <Button onClick={submit} loading={create.isPending}>
          저장
        </Button>
      </div>
      {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}
      <FormField label="이름" required>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="아르카디아" />
      </FormField>
      <FormField label="설명">
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
      </FormField>
      <FormField label="시대">
        <Input value={era} onChange={(e) => setEra(e.target.value)} placeholder="중세 판타지" />
      </FormField>
    </div>
  );
}
