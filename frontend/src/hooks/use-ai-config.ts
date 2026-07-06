"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/endpoints";
import type { ModelConfig } from "@/types";

export function useModelConfigs() {
  return useQuery({ queryKey: ["model-configs"], queryFn: api.listModelConfigs });
}

export function useCredentials() {
  return useQuery({ queryKey: ["credentials"], queryFn: api.listCredentials });
}

export function useProviders() {
  return useQuery({ queryKey: ["providers"], queryFn: api.listProviders, staleTime: 5 * 60_000 });
}

export function useCreateModelConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: Partial<ModelConfig>) => api.createModelConfig(b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["model-configs"] }),
  });
}

export function useCreateCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { provider: string; api_key: string; label?: string }) =>
      api.createCredential(b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["credentials"] }),
  });
}
