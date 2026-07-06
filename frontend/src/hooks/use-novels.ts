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

export function useUpdateChapter(workId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: {
      id: string;
      title?: string;
      content_text?: string;
      content_doc?: unknown;
      version: number;
    }) => api.updateChapter(b.id, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chapters", workId] }),
  });
}

export function useDeleteChapter(workId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (chapterId: string) => api.deleteChapter(chapterId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chapters", workId] }),
  });
}

export function useDeleteWork() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteWork(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["works"] }),
  });
}

export function useWorkCharacters(workId: string) {
  return useQuery({
    queryKey: ["work-characters", workId],
    queryFn: () => api.listWorkCharacters(workId),
    enabled: !!workId,
  });
}

export function useLinkCharacter(workId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { character_id: string; role_in_work?: string }) =>
      api.linkWorkCharacter(workId, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-characters", workId] }),
  });
}

export function useUnlinkCharacter(workId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (characterId: string) => api.unlinkWorkCharacter(workId, characterId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-characters", workId] }),
  });
}
