"use client";

import { Check, ChevronDown, FilePenLine, RefreshCw, X } from "lucide-react";
import { FormEvent, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, Card, Input, Label, Textarea } from "@/components/ui/primitives";
import {
  useAcceptReviewEntry,
  useEditThenAcceptReviewEntry,
  useRejectReviewEntry,
  useSupersedeReviewEntry,
} from "@/hooks/use-entry-review";
import type { EntryReviewEdit, EntryReviewEntry, EntryReviewSupersedeResponse } from "@/types";

import { compactJson, formatReviewError, reviewOutcomeMessage, type ReviewAction } from "./review-utils";

interface ReviewCardProps {
  entry: EntryReviewEntry;
  onResolved: (message: string) => void;
}

function ProvenanceDetails({ entry }: { entry: EntryReviewEntry }) {
  const locator = compactJson(entry.provenance.locator);
  const data = compactJson(entry.data);
  const subjectData = compactJson(entry.subject_data);

  return (
    <div className="space-y-3 border-t pt-4 text-sm">
      <div>
        <p className="font-medium">판단 근거</p>
        <dl className="mt-2 grid gap-x-4 gap-y-1 text-muted-foreground sm:grid-cols-[auto_1fr]">
          {entry.provenance.source_kind ? (
            <>
              <dt>출처 유형</dt>
              <dd className="break-all">{entry.provenance.source_kind}</dd>
            </>
          ) : null}
          {entry.provenance.source_id ? (
            <>
              <dt>출처 ID</dt>
              <dd className="break-all">{entry.provenance.source_id}</dd>
            </>
          ) : null}
          {entry.provenance.capture_method ? (
            <>
              <dt>수집 방식</dt>
              <dd>{entry.provenance.capture_method}</dd>
            </>
          ) : null}
          {entry.provenance.producer ? (
            <>
              <dt>생성 주체</dt>
              <dd className="break-all">{entry.provenance.producer}</dd>
            </>
          ) : null}
          {entry.created_at_chapter_id ? (
            <>
              <dt>생성 챕터</dt>
              <dd className="break-all">{entry.created_at_chapter_id}</dd>
            </>
          ) : null}
        </dl>
      </div>

      {locator ? (
        <details>
          <summary className="cursor-pointer font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            출처 위치
          </summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-xs">{locator}</pre>
        </details>
      ) : null}
      {entry.subject_type || entry.subject_id || subjectData ? (
        <details>
          <summary className="cursor-pointer font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            적용 대상
          </summary>
          <dl className="mt-2 grid gap-x-4 gap-y-1 text-muted-foreground sm:grid-cols-[auto_1fr]">
            {entry.subject_type ? <><dt>유형</dt><dd>{entry.subject_type}</dd></> : null}
            {entry.subject_id ? <><dt>ID</dt><dd className="break-all">{entry.subject_id}</dd></> : null}
          </dl>
          {subjectData ? <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-xs">{subjectData}</pre> : null}
        </details>
      ) : null}
      {data ? (
        <details>
          <summary className="cursor-pointer font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            추가 데이터
          </summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-xs">{data}</pre>
        </details>
      ) : null}
    </div>
  );
}

export function ReviewCard({ entry, onResolved }: ReviewCardProps) {
  const accept = useAcceptReviewEntry();
  const reject = useRejectReviewEntry();
  const editThenAccept = useEditThenAcceptReviewEntry();
  const supersede = useSupersedeReviewEntry();
  const actionInFlight = useRef(false);

  const [activeAction, setActiveAction] = useState<ReviewAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(entry.title ?? "");
  const [editContent, setEditContent] = useState(entry.content);
  const [editValidationError, setEditValidationError] = useState<string | null>(null);
  const [showSupersede, setShowSupersede] = useState(false);
  const [currentEntryId, setCurrentEntryId] = useState("");

  const isBusy = activeAction !== null;
  const scope = [entry.scope_kind, entry.scope_id].filter(Boolean).join(" · ");

  async function runAction<T extends { status?: string } | EntryReviewSupersedeResponse>(
    action: ReviewAction,
    operation: () => Promise<T>,
  ) {
    if (actionInFlight.current) return;

    actionInFlight.current = true;
    setActiveAction(action);
    setActionError(null);
    try {
      const result = await operation();
      onResolved(reviewOutcomeMessage(action, result));
    } catch (error) {
      setActionError(formatReviewError(error));
    } finally {
      actionInFlight.current = false;
      setActiveAction(null);
    }
  }

  function cancelEdit() {
    setEditing(false);
    setEditTitle(entry.title ?? "");
    setEditContent(entry.content);
    setEditValidationError(null);
  }

  function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = editContent.trim();
    if (!content) {
      setEditValidationError("내용을 비워둘 수 없습니다.");
      return;
    }

    const edit: EntryReviewEdit = {};
    const normalizedTitle = editTitle.trim();
    if (normalizedTitle !== (entry.title ?? "")) edit.title = normalizedTitle || null;
    if (content !== entry.content) edit.content = content;

    void runAction("edit-accept", () =>
      Object.keys(edit).length > 0
        ? editThenAccept.mutateAsync({ entryId: entry.id, edit })
        : accept.mutateAsync(entry.id),
    );
  }

  return (
    <Card className="space-y-4 overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{entry.type}</Badge>
            <Badge className="bg-muted text-muted-foreground">{entry.status}</Badge>
          </div>
          {entry.title ? <h3 className="mt-2 break-words text-base font-semibold">{entry.title}</h3> : null}
        </div>
        <dl className="text-right text-xs text-muted-foreground">
          <div><dt className="sr-only">적용 범위</dt><dd className="break-all">{scope}</dd></div>
          <div><dt className="sr-only">신뢰도</dt><dd>신뢰도: {entry.confidence ?? "제공되지 않음"}</dd></div>
        </dl>
      </div>

      {editing ? (
        <form className="space-y-3" onSubmit={submitEdit} aria-label="제안 수정 후 승인">
          <div>
            <Label htmlFor={`review-title-${entry.id}`}>제목</Label>
            <Input
              id={`review-title-${entry.id}`}
              value={editTitle}
              onChange={(event) => setEditTitle(event.target.value)}
              disabled={isBusy}
            />
          </div>
          <div>
            <Label htmlFor={`review-content-${entry.id}`}>내용</Label>
            <Textarea
              id={`review-content-${entry.id}`}
              value={editContent}
              onChange={(event) => {
                setEditContent(event.target.value);
                setEditValidationError(null);
              }}
              disabled={isBusy}
              aria-describedby={editValidationError ? `review-content-error-${entry.id}` : undefined}
              required
            />
            {editValidationError ? <p id={`review-content-error-${entry.id}`} className="mt-1 text-xs text-destructive">{editValidationError}</p> : null}
          </div>
          <div className="grid grid-cols-1 gap-2 sm:flex sm:justify-end">
            <Button type="button" variant="ghost" className="min-h-11" onClick={cancelEdit} disabled={isBusy}>취소</Button>
            <Button type="submit" className="min-h-11" loading={activeAction === "edit-accept"} disabled={isBusy}>
              <Check className="h-4 w-4" /> 수정 후 승인
            </Button>
          </div>
        </form>
      ) : (
        <p className="whitespace-pre-wrap break-words text-sm leading-6">{entry.content}</p>
      )}

      <ProvenanceDetails entry={entry} />

      {actionError ? <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">{actionError}</p> : null}

      {!editing ? (
        <div className="grid grid-cols-1 gap-2 sm:flex sm:flex-wrap sm:justify-end">
          <Button className="min-h-11" onClick={() => void runAction("accept", () => accept.mutateAsync(entry.id))} loading={activeAction === "accept"} disabled={isBusy}>
            <Check className="h-4 w-4" /> 승인
          </Button>
          <Button type="button" variant="outline" className="min-h-11" onClick={() => setEditing(true)} disabled={isBusy} aria-expanded={editing}>
            <FilePenLine className="h-4 w-4" /> 수정 후 승인
          </Button>
          <Button type="button" variant="destructive" className="min-h-11" onClick={() => void runAction("reject", () => reject.mutateAsync(entry.id))} loading={activeAction === "reject"} disabled={isBusy}>
            <X className="h-4 w-4" /> 거절
          </Button>
          <Button type="button" variant="ghost" className="min-h-11" onClick={() => setShowSupersede((open) => !open)} disabled={isBusy} aria-expanded={showSupersede}>
            <RefreshCw className="h-4 w-4" /> 기존 canon 교체 <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      ) : null}

      {showSupersede && !editing ? (
        <div className="space-y-2 rounded-md border border-border bg-muted/40 p-3">
          <Label htmlFor={`supersede-target-${entry.id}`}>교체할 현재 canon Entry ID</Label>
          <p className="text-xs text-muted-foreground">기존 canon을 확인한 뒤 ID를 명시적으로 입력하세요. 서버가 scope·type·subject·anchor 및 lifecycle을 다시 검증합니다.</p>
          <div className="grid grid-cols-1 gap-2 sm:flex">
            <Input
              id={`supersede-target-${entry.id}`}
              value={currentEntryId}
              onChange={(event) => setCurrentEntryId(event.target.value)}
              disabled={isBusy}
              placeholder="현재 canon Entry ID"
            />
            <Button
              type="button"
              className="min-h-11 shrink-0"
              loading={activeAction === "supersede"}
              disabled={isBusy || !currentEntryId.trim()}
              onClick={() => void runAction("supersede", () => supersede.mutateAsync({ entryId: entry.id, currentEntryId: currentEntryId.trim() }))}
            >
              교체 승인
            </Button>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
