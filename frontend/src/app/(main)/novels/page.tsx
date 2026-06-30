"use client";

import { BookOpen, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { useWorks } from "@/hooks/use-novels";

export default function NovelsPage() {
  const router = useRouter();
  const { data, isPending, isError, refetch } = useWorks();

  return (
    <div>
      <PageHeader
        title="소설"
        action={
          <Link href="/novels/new">
            <Button>
              <Plus className="h-4 w-4" /> 만들기
            </Button>
          </Link>
        }
      />
      {isPending ? (
        <ListSkeleton count={3} />
      ) : isError ? (
        <ErrorState message="목록을 불러오지 못했어요." onRetry={() => refetch()} />
      ) : data && data.items.length > 0 ? (
        <div className="space-y-3">
          {data.items.map((w) => (
            <Link key={w.id} href={`/novels/${w.id}`}>
              <Card className="transition hover:border-primary">
                <p className="font-semibold">📖 {w.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {[w.genre, ...(w.tags ?? [])].filter(Boolean).join(" · ")}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={BookOpen}
          title="작품이 없어요"
          description="첫 작품을 시작해 볼까요? AI가 집필을 도와드려요."
          ctaLabel="+ 작품 만들기"
          onCta={() => router.push("/novels/new")}
        />
      )}
    </div>
  );
}
