"use client";

import { ChevronLeft, FileText, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { WorkCharacters } from "@/components/novel/work-characters";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import {
  useChapters,
  useCreateChapter,
  useDeleteChapter,
  useDeleteWork,
  useWork,
} from "@/hooks/use-novels";

export default function WorkDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const workId = params.id;
  const work = useWork(workId);
  const chapters = useChapters(workId);
  const createChapter = useCreateChapter(workId);
  const deleteChapter = useDeleteChapter(workId);
  const deleteWork = useDeleteWork();

  if (work.isPending) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }
  if (work.isError || !work.data) {
    return <ErrorState message="작품을 불러오지 못했어요." onRetry={() => work.refetch()} />;
  }

  async function addChapter() {
    const ch = await createChapter.mutateAsync({ title: "새 챕터" });
    router.push(`/novels/${workId}/chapters/${ch.id}`);
  }

  async function removeWork() {
    if (!confirm("이 작품을 삭제할까요? (보관 처리됩니다)")) return;
    await deleteWork.mutateAsync(workId);
    router.push("/novels");
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={() => router.push("/novels")}
          className="flex items-center gap-1 text-sm text-muted-foreground"
        >
          <ChevronLeft className="h-4 w-4" /> 소설 목록
        </button>
        <Button variant="ghost" size="sm" onClick={removeWork} loading={deleteWork.isPending}>
          <Trash2 className="h-4 w-4" /> 삭제
        </Button>
      </div>

      <h1 className="text-2xl font-bold">📖 {work.data.title}</h1>
      {work.data.synopsis ? (
        <p className="mt-2 text-sm text-muted-foreground">{work.data.synopsis}</p>
      ) : null}
      <div className="mt-1 text-xs text-muted-foreground">
        {[work.data.genre, ...(work.data.tags ?? [])].filter(Boolean).join(" · ")}
      </div>

      <div className="mb-3 mt-8 flex items-center justify-between">
        <h2 className="text-lg font-semibold">챕터</h2>
        <Button size="sm" onClick={addChapter} loading={createChapter.isPending}>
          <Plus className="h-4 w-4" /> 챕터 추가
        </Button>
      </div>

      {chapters.isPending ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : chapters.data && chapters.data.length > 0 ? (
        <div className="space-y-2">
          {chapters.data.map((ch, i) => (
            <Card key={ch.id} className="flex items-center justify-between py-3">
              <Link
                href={`/novels/${workId}/chapters/${ch.id}`}
                className="flex min-w-0 flex-1 items-center gap-3"
              >
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <p className="truncate font-medium">
                    {i + 1}화. {ch.title || "제목 없음"}
                  </p>
                  <p className="text-xs text-muted-foreground">{ch.word_count}자</p>
                </div>
              </Link>
              <button
                aria-label="챕터 삭제"
                className="ml-2 text-muted-foreground hover:text-destructive"
                onClick={async () => {
                  if (confirm("이 챕터를 삭제할까요?")) await deleteChapter.mutateAsync(ch.id);
                }}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FileText}
          title="아직 챕터가 없어요"
          description="첫 챕터를 추가하고 AI 이어쓰기로 집필을 시작하세요."
          ctaLabel="+ 챕터 추가"
          onCta={addChapter}
        />
      )}

      <div className="mt-10">
        <WorkCharacters workId={workId} />
      </div>
    </div>
  );
}
