"use client";

import { UserPlus, Users, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/primitives";
import { Spinner } from "@/components/ui/states";
import { useCharacters } from "@/hooks/use-characters";
import { useLinkCharacter, useUnlinkCharacter, useWorkCharacters } from "@/hooks/use-novels";

const ROLES = ["주연", "조연", "단역"] as const;

export function WorkCharacters({ workId }: { workId: string }) {
  const links = useWorkCharacters(workId);
  const characters = useCharacters();
  const link = useLinkCharacter(workId);
  const unlink = useUnlinkCharacter(workId);
  const [adding, setAdding] = useState(false);

  const nameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of characters.data?.items ?? []) m.set(c.id, c.name);
    return m;
  }, [characters.data]);

  const linkedIds = new Set((links.data ?? []).map((l) => l.character_id));
  const available = (characters.data?.items ?? []).filter((c) => !linkedIds.has(c.id));

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">등장인물</h2>
        {!adding && available.length > 0 ? (
          <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
            <UserPlus className="h-4 w-4" /> 인물 추가
          </Button>
        ) : null}
      </div>

      {adding ? (
        <Card className="mb-3">
          <p className="mb-2 text-sm font-medium">추가할 캐릭터를 선택하세요</p>
          <div className="space-y-2">
            {available.map((c) => (
              <AddRow
                key={c.id}
                name={c.name}
                busy={link.isPending}
                onAdd={async (role) => {
                  await link.mutateAsync({ character_id: c.id, role_in_work: role });
                }}
              />
            ))}
          </div>
          <Button className="mt-3" variant="ghost" size="sm" onClick={() => setAdding(false)}>
            닫기
          </Button>
        </Card>
      ) : null}

      {links.isPending ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : links.data && links.data.length > 0 ? (
        <div className="space-y-2">
          {links.data.map((l) => (
            <Card key={l.id} className="flex items-center justify-between py-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">{nameById.get(l.character_id) ?? "삭제된 캐릭터"}</span>
                <Badge>{l.role_in_work}</Badge>
              </div>
              <button
                aria-label="등장인물 제외"
                className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
                disabled={unlink.isPending}
                onClick={() => unlink.mutate(l.character_id)}
              >
                <X className="h-4 w-4" />
              </button>
            </Card>
          ))}
        </div>
      ) : (
        <p className="flex items-center gap-2 rounded-[var(--radius)] border border-dashed px-4 py-6 text-sm text-muted-foreground">
          <Users className="h-4 w-4" />
          {(characters.data?.items?.length ?? 0) === 0
            ? "먼저 캐릭터를 만들면 작품에 등장인물로 연결할 수 있어요."
            : "아직 연결된 등장인물이 없어요. '인물 추가'로 캐릭터를 연결하세요."}
        </p>
      )}
    </section>
  );
}

function AddRow({
  name,
  busy,
  onAdd,
}: {
  name: string;
  busy: boolean;
  onAdd: (role: string) => Promise<void>;
}) {
  const [role, setRole] = useState<string>("조연");
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
      <span className="min-w-0 truncate text-sm font-medium">{name}</span>
      <div className="flex shrink-0 items-center gap-2">
        <select
          aria-label={`${name} 역할`}
          className="h-8 rounded-md border bg-background px-2 text-sm"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <Button size="sm" loading={busy} onClick={() => onAdd(role)}>
          추가
        </Button>
      </div>
    </div>
  );
}
