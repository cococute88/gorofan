"use client";

import { MessageCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { useChats } from "@/hooks/use-chats";

export default function ChatsPage() {
  const router = useRouter();
  const { data, isPending, isError, refetch } = useChats();

  return (
    <div>
      <PageHeader title="채팅" />
      {isPending ? (
        <ListSkeleton count={4} />
      ) : isError ? (
        <ErrorState message="대화 목록을 불러오지 못했어요." onRetry={() => refetch()} />
      ) : data && data.items.length > 0 ? (
        <div className="space-y-3">
          {data.items.map((c) => (
            <Link key={c.id} href={`/chats/${c.id}`}>
              <Card className="flex items-center gap-3 transition hover:border-primary">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent">
                  <MessageCircle className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="truncate font-medium">{c.title || "새 대화"}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(c.updated_at).toLocaleString()}
                  </p>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={MessageCircle}
          title="아직 대화가 없어요"
          description="캐릭터 화면에서 '채팅' 버튼을 눌러 대화를 시작해 보세요."
          ctaLabel="캐릭터로 이동"
          onCta={() => router.push("/characters")}
        />
      )}
    </div>
  );
}
