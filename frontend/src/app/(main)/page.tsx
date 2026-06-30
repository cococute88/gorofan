"use client";

import { BookOpen, Globe, MessageCircle, Plus, User } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/primitives";
import { ListSkeleton } from "@/components/ui/states";
import { useChats } from "@/hooks/use-chats";
import { useWorks } from "@/hooks/use-novels";

const QUICK_ACTIONS = [
  { href: "/characters/new", label: "캐릭터", icon: User },
  { href: "/worlds/new", label: "세계관", icon: Globe },
  { href: "/novels/new", label: "소설", icon: BookOpen },
];

export default function HomePage() {
  const works = useWorks();
  const chats = useChats();

  return (
    <div className="space-y-8">
      <PageHeader title="홈" />
      <p className="text-muted-foreground">안녕하세요 👋 오늘은 무엇을 만들까요?</p>

      <div className="grid grid-cols-3 gap-3">
        {QUICK_ACTIONS.map((a) => (
          <Link key={a.href} href={a.href}>
            <Card className="flex flex-col items-center gap-2 py-6 text-center transition hover:border-primary">
              <a.icon className="h-6 w-6 text-primary" />
              <span className="text-sm font-medium">
                <Plus className="mr-1 inline h-3 w-3" />
                {a.label}
              </span>
            </Card>
          </Link>
        ))}
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-semibold">최근 채팅</h2>
          <Link href="/chats" className="text-sm text-primary">
            전체보기 →
          </Link>
        </div>
        {chats.isPending ? (
          <ListSkeleton count={3} />
        ) : chats.data && chats.data.items.length > 0 ? (
          <div className="flex gap-3 overflow-x-auto pb-2">
            {chats.data.items.map((c) => (
              <Link key={c.id} href={`/chats/${c.id}`}>
                <Card className="w-40 shrink-0">
                  <p className="truncate font-medium">{c.title}</p>
                  <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                    <MessageCircle className="h-3 w-3" /> 대화
                  </p>
                </Card>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">아직 채팅이 없어요.</p>
        )}
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-semibold">이어서 쓰기</h2>
          <Link href="/novels" className="text-sm text-primary">
            전체보기 →
          </Link>
        </div>
        {works.isPending ? (
          <ListSkeleton count={2} />
        ) : works.data && works.data.items.length > 0 ? (
          <div className="space-y-3">
            {works.data.items.map((w) => (
              <Link key={w.id} href={`/novels/${w.id}`}>
                <Card className="transition hover:border-primary">
                  <p className="font-medium">📖 {w.title}</p>
                  <p className="mt-1 truncate text-sm text-muted-foreground">{w.synopsis || w.genre}</p>
                </Card>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">첫 작품을 시작해 볼까요?</p>
        )}
      </section>
    </div>
  );
}
