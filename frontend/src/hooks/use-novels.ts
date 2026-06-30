"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/endpoints";
import type { Work } from "@/types";

export function useWorks() {
  return useQuery({ queryKey: ["works"], queryFn: api.listWorks });
}

export function useWork(id: string) {
  return useQuery({ queryKey: ["work", id], queryFn: () => api.getWork(id), enabled: !!id });
}

export function useCreateWork() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: Partial<Work>) => api.createWork(b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["works"] }),
  });
}

export function useChapters(workId: string) {
  return useQuery({
    queryKey: ["chapters", workId],
    queryFn: () => api.listChapters(workId),
    enabled: !!workId,
  });
}

export function useCreateChapter(workId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { title?: string; content_text?: string }) => api.createChapter(workId, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chapters", workId] }),
  });
}
