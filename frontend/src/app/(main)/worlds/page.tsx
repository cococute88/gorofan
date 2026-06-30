"use client";

import { Globe, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { useWorlds } from "@/hooks/use-worlds";

export default function WorldsPage() {
  const router = useRouter();
  const { data, isPending, isError, refetch } = useWorlds();

  return (
    <div>
      <PageHeader
        title="세계관"
        action={
          <Link href="/worlds/new">
            <Button>
              <Plus className="h-4 w-4" /> 만들기
            </Button>
          </Link>
        }
      />
      {isPending ? (
        <ListSkeleton count={4} />
      ) : isError ? (
        <ErrorState message="목록을 불러오지 못했어요." onRetry={() => refetch()} />
      ) : data && data.items.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {data.items.map((w) => (
            <Link key={w.id} href={`/worlds/${w.id}`}>
              <Card className="transition hover:border-primary">
                <p className="flex items-center gap-2 font-semibold">
                  <Globe className="h-5 w-5 text-primary" /> {w.name}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">{w.era || w.description}</p>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Globe}
          title="세계관이 없어요"
          description="세계관을 만들면 캐릭터와 소설이 같은 무대를 공유해요."
          ctaLabel="+ 세계관 만들기"
          onCta={() => router.push("/worlds/new")}
        />
      )}
    </div>
  );
}
