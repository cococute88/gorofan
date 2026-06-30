"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, MessageCircle, Plus, User } from "lucide-react";
import { apiGet } from "@/lib/api/client";

interface Character {
  id: string;
  name: string;
  greeting: string;
}

export default function HomePage() {
  const { data, isPending, error } = useQuery({
    queryKey: ["characters"],
    queryFn: () => apiGet<{ items: Character[] }>("/characters"),
  });

  return (
    <main className="mx-auto max-w-screen-xl px-4 py-8">
      <h1 className="text-2xl font-bold">안녕하세요 👋 오늘은 무엇을 만들까요?</h1>

      <div className="mt-6 grid grid-cols-3 gap-4">
        <QuickAction icon={<User size={20} />} label="캐릭터" />
        <QuickAction icon={<BookOpen size={20} />} label="소설" />
        <QuickAction icon={<MessageCircle size={20} />} label="채팅" />
      </div>

      <section className="mt-10">
        <h2 className="text-xl font-semibold">최근 캐릭터</h2>
        {isPending && <p className="mt-2 text-sm opacity-70">불러오는 중…</p>}
        {error && (
          <p className="mt-2 text-sm text-red-500">연결이 불안정해요. 백엔드가 실행 중인지 확인하세요.</p>
        )}
        {data && data.items.length === 0 && (
          <div className="mt-4 rounded border border-border p-6 text-center">
            <p className="opacity-70">아직 캐릭터가 없어요. 첫 캐릭터를 만들어 대화를 시작해 보세요.</p>
            <button className="mt-3 inline-flex items-center gap-1 rounded-md bg-[hsl(var(--primary))] px-4 py-2 text-white">
              <Plus size={16} /> 캐릭터 만들기
            </button>
          </div>
        )}
        {data && data.items.length > 0 && (
          <ul className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {data.items.map((c) => (
              <li key={c.id} className="rounded border border-border p-4">
                <p className="font-medium">{c.name}</p>
                <p className="mt-1 line-clamp-2 text-sm opacity-70">{c.greeting}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function QuickAction({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <button className="flex flex-col items-center gap-2 rounded-lg border border-border p-4 hover:bg-[hsl(var(--muted))]">
      {icon}
      <span className="text-sm">+ {label}</span>
    </button>
  );
}
