"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/endpoints";
import type { Persona } from "@/types";

export function usePersonas() {
  return useQuery({ queryKey: ["personas"], queryFn: api.listPersonas });
}

export function useCreatePersona() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: Partial<Persona>) => api.createPersona(b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["personas"] }),
  });
}

export function useUpdatePersona() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { id: string } & Partial<Persona>) => api.updatePersona(b.id, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["personas"] }),
  });
}

export function useDeletePersona() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deletePersona(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["personas"] }),
  });
}
