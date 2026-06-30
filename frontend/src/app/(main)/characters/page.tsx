"use client";

import { MessageCircle, Plus, User } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { useCharacters } from "@/hooks/use-characters";
import { useCreateChat } from "@/hooks/use-chats";

export default function CharactersPage() {
  const router = useRouter();
  const { data, isPending, isError, refetch } = useCharacters();
  const createChat = useCreateChat();

  async function startChat(characterId: string) {
    const chat = await createChat.mutateAsync({ character_id: characterId });
    router.push(`/chats/${chat.id}`);
  }

  return (
    <div>
      <PageHeader
        title="캐릭터"
        action={
          <Link href="/characters/new">
            <Button>
              <Plus className="h-4 w-4" /> 만들기
            </Button>
          </Link>
        }
      />

      {isPending ? (
        <ListSkeleton count={6} />
      ) : isError ? (
        <ErrorState message="목록을 불러오지 못했어요." onRetry={() => refetch()} />
      ) : data && data.items.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((c) => (
            <Card key={c.id} className="flex flex-col gap-2">
              <Link href={`/characters/${c.id}`} className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent">
                  <User className="h-6 w-6" />
                </div>
                <div className="min-w-0">
                  <p className="truncate font-semibold">{c.name}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.tags.slice(0, 3).map((t) => (
                      <Badge key={t}>#{t}</Badge>
                    ))}
                  </div>
                </div>
              </Link>
              <Button variant="outline" size="sm" onClick={() => startChat(c.id)} loading={createChat.isPending}>
                <MessageCircle className="h-4 w-4" /> 채팅
              </Button>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={User}
          title="아직 캐릭터가 없어요"
          description="첫 캐릭터를 만들어 대화를 시작해 보세요."
          ctaLabel="+ 캐릭터 만들기"
          onCta={() => router.push("/characters/new")}
        />
      )}
    </div>
  );
}
