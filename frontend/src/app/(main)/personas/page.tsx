"use client";

import { Pencil, Plus, Trash2, UserCircle2, X } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, FormField, Input, Textarea } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import {
  useCreatePersona,
  useDeletePersona,
  usePersonas,
  useUpdatePersona,
} from "@/hooks/use-personas";
import type { Persona } from "@/types";

export default function PersonasPage() {
  const { data, isPending, isError, refetch } = usePersonas();
  const [creating, setCreating] = useState(false);

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="페르소나"
        action={
          !creating ? (
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> 만들기
            </Button>
          ) : undefined
        }
      />
      <p className="mb-4 text-sm text-muted-foreground">
        페르소나는 채팅에서 &lsquo;나&rsquo;의 역할입니다. 대화를 시작할 때 선택할 수 있어요.
      </p>

      {creating ? (
        <div className="mb-4">
          <PersonaEditor onClose={() => setCreating(false)} />
        </div>
      ) : null}

      {isPending ? (
        <ListSkeleton count={3} />
      ) : isError ? (
        <ErrorState message="페르소나를 불러오지 못했어요." onRetry={() => refetch()} />
      ) : data && data.items.length > 0 ? (
        <div className="space-y-3">
          {data.items.map((p) => (
            <PersonaRow key={p.id} persona={p} />
          ))}
        </div>
      ) : !creating ? (
        <EmptyState
          icon={UserCircle2}
          title="아직 페르소나가 없어요"
          description="채팅 속 나를 표현할 첫 페르소나를 만들어 보세요."
          ctaLabel="+ 페르소나 만들기"
          onCta={() => setCreating(true)}
        />
      ) : null}
    </div>
  );
}

function PersonaRow({ persona }: { persona: Persona }) {
  const [editing, setEditing] = useState(false);
  const del = useDeletePersona();

  if (editing) {
    return <PersonaEditor persona={persona} onClose={() => setEditing(false)} />;
  }

  return (
    <Card className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <UserCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-primary" />
        <div className="min-w-0">
          <p className="font-semibold">{persona.name}</p>
          {persona.description ? (
            <p className="mt-0.5 whitespace-pre-wrap text-sm text-muted-foreground">
              {persona.description}
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 gap-1">
        <button
          aria-label="페르소나 편집"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent"
          onClick={() => setEditing(true)}
        >
          <Pencil className="h-4 w-4" />
        </button>
        <button
          aria-label="페르소나 삭제"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
          disabled={del.isPending}
          onClick={() => {
            if (confirm(`'${persona.name}' 페르소나를 삭제할까요?`)) del.mutate(persona.id);
          }}
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </Card>
  );
}

function PersonaEditor({ persona, onClose }: { persona?: Persona; onClose: () => void }) {
  const create = useCreatePersona();
  const update = useUpdatePersona();
  const [name, setName] = useState(persona?.name ?? "");
  const [description, setDescription] = useState(persona?.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const saving = create.isPending || update.isPending;

  async function save() {
    if (!name.trim()) {
      setError("이름을 입력하세요.");
      return;
    }
    setError(null);
    try {
      if (persona) {
        await update.mutateAsync({ id: persona.id, name: name.trim(), description });
      } else {
        await create.mutateAsync({ name: name.trim(), description });
      }
      onClose();
    } catch {
      setError("저장에 실패했어요. 다시 시도해 주세요.");
    }
  }

  return (
    <Card>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-semibold">{persona ? "페르소나 편집" : "새 페르소나"}</h3>
        <button aria-label="닫기" className="text-muted-foreground" onClick={onClose}>
          <X className="h-4 w-4" />
        </button>
      </div>
      <FormField label="이름" required error={error ?? undefined}>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="예) 견습 마법사" />
      </FormField>
      <FormField label="설명">
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="말투, 성격, 배경 등 '나'의 설정"
        />
      </FormField>
      <div className="flex gap-2">
        <Button loading={saving} onClick={save}>
          저장
        </Button>
        <Button variant="ghost" onClick={onClose}>
          취소
        </Button>
      </div>
    </Card>
  );
}
