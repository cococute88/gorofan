"use client";

import { KeyRound, Plus } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, Card, FormField, Input } from "@/components/ui/primitives";
import { ErrorState, ListSkeleton } from "@/components/ui/states";
import {
  useCreateCredential,
  useCreateModelConfig,
  useCredentials,
  useModelConfigs,
  useProviders,
} from "@/hooks/use-ai-config";
import { useUIStore } from "@/stores/ui-store";

export default function SettingsPage() {
  const models = useModelConfigs();
  const creds = useCredentials();
  const providers = useProviders();
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader title="설정" />

      <section>
        <h2 className="mb-3 text-lg font-semibold">화면</h2>
        <Card>
          <FormField label="테마">
            <div className="flex gap-2">
              {(["light", "dark", "system"] as const).map((t) => (
                <Button
                  key={t}
                  variant={theme === t ? "primary" : "outline"}
                  size="sm"
                  onClick={() => setTheme(t)}
                >
                  {t === "light" ? "라이트" : t === "dark" ? "다크" : "시스템"}
                </Button>
              ))}
            </div>
          </FormField>
        </Card>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">모델 설정</h2>
        {models.isPending ? (
          <ListSkeleton count={2} />
        ) : models.isError ? (
          <ErrorState message="모델 설정을 불러오지 못했어요." onRetry={() => models.refetch()} />
        ) : (
          <div className="space-y-3">
            {(models.data ?? []).map((m) => (
              <Card key={m.id} className="flex items-center justify-between">
                <div>
                  <p className="font-medium">
                    {m.model_name} {m.is_default ? <Badge className="ml-1">기본</Badge> : null}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {m.provider} · ctx {m.context_window} · max {m.max_tokens}
                  </p>
                </div>
              </Card>
            ))}
            <ModelConfigForm providers={providers.data ?? []} />
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">API 키</h2>
        <p className="mb-2 text-xs text-muted-foreground">
          키는 백엔드에서 암호화 저장되며 화면에는 마스킹되어 표시됩니다.
        </p>
        {creds.isPending ? (
          <ListSkeleton count={1} />
        ) : (
          <div className="space-y-3">
            {(creds.data ?? []).map((c) => (
              <Card key={c.id} className="flex items-center gap-3">
                <KeyRound className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="font-medium">{c.label || c.provider}</p>
                  <p className="font-mono text-xs text-muted-foreground">{c.masked_key}</p>
                </div>
              </Card>
            ))}
            <CredentialForm providers={providers.data ?? []} />
          </div>
        )}
      </section>
    </div>
  );
}

function ModelConfigForm({ providers }: { providers: { provider: string; models: string[] }[] }) {
  const create = useCreateModelConfig();
  const [provider, setProvider] = useState(providers[0]?.provider ?? "openai");
  const [modelName, setModelName] = useState("");
  const [contextWindow, setContextWindow] = useState(128000);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4" /> 모델 추가
      </Button>
    );
  }

  return (
    <Card>
      <FormField label="공급자">
        <select
          className="h-10 w-full rounded-md border bg-background px-3 text-sm"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {(providers.length ? providers.map((p) => p.provider) : ["openai", "anthropic", "gemini", "ollama"]).map(
            (p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ),
          )}
        </select>
      </FormField>
      <FormField label="모델명">
        <Input value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="gpt-4o" />
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="컨텍스트 윈도우">
          <Input
            type="number"
            value={contextWindow}
            onChange={(e) => setContextWindow(Number(e.target.value))}
          />
        </FormField>
        <FormField label="최대 출력 토큰">
          <Input type="number" value={maxTokens} onChange={(e) => setMaxTokens(Number(e.target.value))} />
        </FormField>
      </div>
      <div className="flex gap-2">
        <Button
          loading={create.isPending}
          disabled={!modelName.trim()}
          onClick={async () => {
            await create.mutateAsync({
              provider,
              model_name: modelName.trim(),
              context_window: contextWindow,
              max_tokens: maxTokens,
            });
            setOpen(false);
            setModelName("");
          }}
        >
          저장
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          취소
        </Button>
      </div>
    </Card>
  );
}

function CredentialForm({ providers }: { providers: { provider: string; models: string[] }[] }) {
  const create = useCreateCredential();
  const [provider, setProvider] = useState(providers[0]?.provider ?? "openai");
  const [apiKey, setApiKey] = useState("");
  const [label, setLabel] = useState("");
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4" /> API 키 추가
      </Button>
    );
  }

  return (
    <Card>
      <FormField label="공급자">
        <select
          className="h-10 w-full rounded-md border bg-background px-3 text-sm"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {(providers.length ? providers.map((p) => p.provider) : ["openai", "anthropic", "gemini", "openrouter"]).map(
            (p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ),
          )}
        </select>
      </FormField>
      <FormField label="API 키">
        <Input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="sk-..."
        />
      </FormField>
      <FormField label="라벨 (선택)">
        <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="개인 키" />
      </FormField>
      <div className="flex gap-2">
        <Button
          loading={create.isPending}
          disabled={!apiKey.trim()}
          onClick={async () => {
            await create.mutateAsync({ provider, api_key: apiKey.trim(), label: label.trim() || undefined });
            setOpen(false);
            setApiKey("");
            setLabel("");
          }}
        >
          저장
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          취소
        </Button>
      </div>
    </Card>
  );
}
