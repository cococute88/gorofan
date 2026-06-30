"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/endpoints";
import type { World } from "@/types";

export function useWorlds() {
  return useQuery({ queryKey: ["worlds"], queryFn: api.listWorlds });
}

export function useWorld(id: string) {
  return useQuery({ queryKey: ["world", id], queryFn: () => api.getWorld(id), enabled: !!id });
}

export function useCreateWorld() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: Partial<World>) => api.createWorld(b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["worlds"] }),
  });
}

export function useUpdateWorld(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: Partial<World>) => api.updateWorld(id, b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["worlds"] });
      qc.invalidateQueries({ queryKey: ["world", id] });
    },
  });
}

export function useLorebooks(worldId: string) {
  return useQuery({
    queryKey: ["lorebooks", worldId],
    queryFn: () => api.listLorebooks(worldId),
    enabled: !!worldId,
  });
}

export function useLoreEntries(lorebookId: string | undefined) {
  return useQuery({
    queryKey: ["lore-entries", lorebookId],
    queryFn: () => api.listLoreEntries(lorebookId as string),
    enabled: !!lorebookId,
  });
}

export function useGlossary(worldId: string) {
  return useQuery({
    queryKey: ["glossary", worldId],
    queryFn: () => api.listGlossary(worldId),
    enabled: !!worldId,
  });
}
