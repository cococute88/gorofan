"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { removeReviewQueueEntry } from "@/components/review/review-utils";
import * as api from "@/lib/api/endpoints";
import type {
  EntryReviewEdit,
  EntryReviewEntry,
  EntryReviewSupersedeResponse,
} from "@/types";

export const entryReviewQueueKey = ["entry-review"] as const;

function useReviewQueueInvalidation() {
  const queryClient = useQueryClient();

  return {
    remove(entryId: string) {
      queryClient.setQueryData<EntryReviewEntry[]>(entryReviewQueueKey, (entries) =>
        entries ? removeReviewQueueEntry(entries, entryId) : undefined,
      );
      queryClient.removeQueries({ queryKey: ["entry-review", entryId] });
    },
    refresh() {
      void queryClient.invalidateQueries({ queryKey: entryReviewQueueKey });
    },
  };
}

export function useEntryReviewQueue() {
  return useQuery({
    queryKey: entryReviewQueueKey,
    queryFn: api.listReviewEntries,
  });
}

export function useEntryReviewEntry(entryId: string) {
  return useQuery({
    queryKey: ["entry-review", entryId],
    queryFn: () => api.getReviewEntry(entryId),
    enabled: Boolean(entryId),
  });
}

export function useAcceptReviewEntry() {
  const queue = useReviewQueueInvalidation();
  return useMutation({
    mutationFn: api.acceptReviewEntry,
    onSuccess: (entry) => queue.remove(entry.id),
    onSettled: queue.refresh,
  });
}

export function useRejectReviewEntry() {
  const queue = useReviewQueueInvalidation();
  return useMutation({
    mutationFn: api.rejectReviewEntry,
    onSuccess: (entry) => queue.remove(entry.id),
    onSettled: queue.refresh,
  });
}

export function useEditThenAcceptReviewEntry() {
  const queue = useReviewQueueInvalidation();
  return useMutation({
    mutationFn: async ({ entryId, edit }: { entryId: string; edit: EntryReviewEdit }) => {
      await api.editReviewEntry(entryId, edit);
      return api.acceptReviewEntry(entryId);
    },
    onSuccess: (entry) => queue.remove(entry.id),
    // The edit can succeed before an accept lifecycle conflict. Refetching on
    // either outcome keeps the rendered proposal equal to the server's state.
    onSettled: queue.refresh,
  });
}

export function useSupersedeReviewEntry() {
  const queue = useReviewQueueInvalidation();
  return useMutation({
    mutationFn: ({ entryId, currentEntryId }: { entryId: string; currentEntryId: string }) =>
      api.supersedeReviewEntry(entryId, currentEntryId),
    onSuccess: (result: EntryReviewSupersedeResponse) => queue.remove(result.new_entry.id),
    onSettled: queue.refresh,
  });
}
