"use client";

import { ChevronLeft, Plus } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, Card, FormField, Input, Textarea } from "@/components/ui/primitives";
import { Spinner } from "@/components/ui/states";
import * as api from "@/lib/api/endpoints";
import { useGlossary, useLoreEntries, useLorebooks, useUpdateWorld, useWorld } from "@/hooks/use-worlds";
import { useQueryClient } from "@tanstack/react-query";

type Tab = "info" | "lore" | "glossary";

export default function WorldEditorPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const world = useWorld(params.id);
  const update = useUpdateWorld(params.id);
  const lorebooks = useLorebooks(params.id);
  const firstLb = lorebooks.data?.[0];
  const entries = useLoreEntries(firstLb?.id);
  const glossary = useGlossary(params.id);
  const [tab, setTab] = useState<Tab>("info");

  if (world.isPending || !world.data) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  async function ensureLorebookThenAddEntry(keywords: string, content: string) {
    let lb = firstLb;
    if (!lb) {
      lb = await api.createLorebook(params.id, { name: "기본 로어북" });
      await qc.invalidateQueries({ queryKey: ["lorebooks", params.id] });
    }
    await api.createLoreEntry(lb.id, {
      keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
      content,
    });
    await qc.invalidateQueries({ queryKey: ["lore-entries", lb.id] });
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm">
          <ChevronLeft className="h-4 w-4" /> {world.data.name}
        </button>
      </div>

      <div className="mb-4 flex gap-2 border-b">
        {(["info", "lore", "glossary"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm ${tab === t ? "border-b-2 border-primary font-medium" : "text-muted-foreground"}`}
          >
            {t === "info" ? "기본정보" : t === "lore" ? "로어북" : "용어집"}
          </button>
        ))}
      </div>

      {tab === "info" ? (
        <WorldInfoForm world={world.data} onSave={(b) => update.mutateAsync(b)} saving={update.isPending} />
      ) : tab === "lore" ? (
        <LoreTab entries={entries.data ?? []} onAdd={ensureLorebookThenAddEntry} />
      ) : (
        <GlossaryTab
          worldId={params.id}
          terms={glossary.data ?? []}
          onAdded={() => qc.invalidateQueries({ queryKey: ["glossary", params.id] })}
        />
      )}
    </div>
  );
}

function WorldInfoForm({
  world,
  onSave,
  saving,
}: {
  world: { name: string; description: string; era: string };
  onSave: (b: { name: string; description: string; era: string }) => Promise<unknown>;
  saving: boolean;
}) {
  const [name, setName] = useState(world.name);
  const [description, setDescription] = useState(world.description);
  const [era, setEra] = useState(world.era);
  return (
    <div>
      <FormField label="이름">
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </FormField>
      <FormField label="설명">
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
      </FormField>
      <FormField label="시대">
        <Input value={era} onChange={(e) => setEra(e.target.value)} />
      </FormField>
      <Button onClick={() => onSave({ name, description, era })} loading={saving}>
        저장
      </Button>
    </div>
  );
}

function LoreTab({
  entries,
  onAdd,
}: {
  entries: { id: string; keywords: string[]; content: string }[];
  onAdd: (keywords: string, content: string) => Promise<void>;
}) {
  const [keywords, setKeywords] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="space-y-4">
      {entries.map((e) => (
        <Card key={e.id}>
          <div className="mb-1 flex flex-wrap gap-1">
            {e.keywords.map((k) => (
              <Badge key={k}>🔑 {k}</Badge>
            ))}
          </div>
          <p className="text-sm text-muted-foreground">{e.content}</p>
        </Card>
      ))}
      <Card>
        <FormField label="키워드 (쉼표로 구분)">
          <Input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="왕국, 아르카디아" />
        </FormField>
        <FormField label="로어 내용">
          <Textarea value={content} onChange={(e) => setContent(e.target.value)} />
        </FormField>
        <Button
          loading={busy}
          onClick={async () => {
            setBusy(true);
            await onAdd(keywords, content);
            setKeywords("");
            setContent("");
            setBusy(false);
          }}
        >
          <Plus className="h-4 w-4" /> 로어 추가
        </Button>
      </Card>
    </div>
  );
}

function GlossaryTab({
  worldId,
  terms,
  onAdded,
}: {
  worldId: string;
  terms: { id: string; term: string; definition: string }[];
  onAdded: () => void;
}) {
  const [term, setTerm] = useState("");
  const [definition, setDefinition] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="space-y-4">
      {terms.map((t) => (
        <Card key={t.id}>
          <p className="font-medium">{t.term}</p>
          <p className="text-sm text-muted-foreground">{t.definition}</p>
        </Card>
      ))}
      <Card>
        <FormField label="용어">
          <Input value={term} onChange={(e) => setTerm(e.target.value)} />
        </FormField>
        <FormField label="정의">
          <Textarea value={definition} onChange={(e) => setDefinition(e.target.value)} />
        </FormField>
        <Button
          loading={busy}
          onClick={async () => {
            setBusy(true);
            await api.createGlossary(worldId, { term, definition });
            setTerm("");
            setDefinition("");
            onAdded();
            setBusy(false);
          }}
        >
          <Plus className="h-4 w-4" /> 용어 추가
        </Button>
      </Card>
    </div>
  );
}
