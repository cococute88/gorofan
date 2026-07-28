"use client";

import { ClipboardCheck } from "lucide-react";
import { useState } from "react";

import { ReviewCard } from "@/components/review/review-card";
import { Card } from "@/components/ui/primitives";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { useEntryReviewQueue } from "@/hooks/use-entry-review";

import { formatReviewError } from "./review-utils";

export function ReviewQueue() {
  const queue = useEntryReviewQueue();
  const [outcome, setOutcome] = useState<string | null>(null);

  return (
    <section className="space-y-4" aria-labelledby="review-queue-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="review-queue-title" className="text-xl font-semibold">검토할 제안</h2>
          <p className="mt-1 text-sm text-muted-foreground">AI 제안은 작성과 채팅을 방해하지 않습니다. 준비되었을 때 검토하세요.</p>
        </div>
        {queue.data ? <span className="rounded-full bg-accent px-3 py-1 text-sm font-medium">{queue.data.length}건</span> : null}
      </div>

      {outcome ? <p className="rounded-md bg-primary/10 p-3 text-sm text-foreground" role="status" aria-live="polite">{outcome}</p> : null}

      {queue.isPending ? (
        <Card className="flex min-h-32 items-center justify-center gap-3 text-sm text-muted-foreground" role="status" aria-live="polite">
          <Spinner /> 제안 목록을 불러오는 중입니다.
        </Card>
      ) : queue.isError ? (
        <ErrorState message={formatReviewError(queue.error)} onRetry={() => void queue.refetch()} />
      ) : queue.data && queue.data.length > 0 ? (
        <div className="space-y-4">
          {queue.data.map((entry) => <ReviewCard key={entry.id} entry={entry} onResolved={setOutcome} />)}
        </div>
      ) : (
        <EmptyState
          icon={ClipboardCheck}
          title="검토할 제안이 없어요"
          description="새 AI 제안이 생기면 여기에서 승인, 수정 후 승인 또는 거절할 수 있어요."
        />
      )}
    </section>
  );
}
