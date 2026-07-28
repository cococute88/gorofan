export type ReviewAction = "accept" | "edit-accept" | "reject" | "supersede";

export function removeReviewQueueEntry<T extends { id: string }>(entries: T[], entryId: string): T[] {
  return entries.filter((entry) => entry.id !== entryId);
}

export function formatReviewError(error: unknown): string {
  const message = error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
  const status =
    typeof error === "object" && error !== null && "status" in error && typeof error.status === "number"
      ? error.status
      : undefined;

  if (status === 404) {
    return `다른 요청으로 이미 처리되었거나, 대상 canon 또는 anchor를 찾을 수 없습니다. ${message}`;
  }
  if (status === 400 || status === 409) {
    return `현재 lifecycle 상태에서는 처리할 수 없습니다. ${message}`;
  }
  if (error instanceof TypeError) {
    return "네트워크 연결을 확인한 뒤 다시 시도해 주세요.";
  }
  return message;
}

export function reviewOutcomeMessage(
  action: ReviewAction,
  result: { status?: string; old_entry?: { status: string }; new_entry?: { status: string } },
): string {
  if (action === "supersede") {
    return `교체 완료: 새 Entry는 ${result.new_entry?.status ?? "처리됨"}, 기존 canon은 ${result.old_entry?.status ?? "처리됨"} 상태입니다.`;
  }
  if (action === "reject") {
    return `거절 완료: Entry는 ${result.status ?? "rejected"} 상태입니다.`;
  }
  if (action === "edit-accept") {
    return `수정 후 승인 완료: Entry는 ${result.status ?? "canon"} 상태입니다.`;
  }
  return `승인 완료: Entry는 ${result.status ?? "canon"} 상태입니다.`;
}

export function compactJson(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  if (typeof value === "object" && Object.keys(value).length === 0) return null;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return null;
  }
}
