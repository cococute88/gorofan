"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/endpoints";
import type { Character } from "@/types";

export function useCharacters(query = "") {
  return useQuery({
    queryKey: ["characters", query],
    queryFn: () => api.listCharacters(query),
  });
}

export function useCharacter(id: string) {
  return useQuery({
    queryKey: ["character", id],
    queryFn: () => api.getCharacter(id),
    enabled: !!id,
  });
}

export function useCreateCharacter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: Partial<Character>) => api.createCharacter(b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["characters"] }),
  });
}

export function useUpdateCharacter(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: Partial<Character>) => api.updateCharacter(id, b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["characters"] });
      qc.invalidateQueries({ queryKey: ["character", id] });
    },
  });
}

export function useDeleteCharacter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteCharacter(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["characters"] }),
  });
}
