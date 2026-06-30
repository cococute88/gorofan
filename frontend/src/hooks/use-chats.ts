"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/endpoints";

export function useChats() {
  return useQuery({ queryKey: ["chats"], queryFn: api.listChats });
}

export function useMessages(chatId: string) {
  return useQuery({
    queryKey: ["messages", chatId],
    queryFn: () => api.listMessages(chatId),
    enabled: !!chatId,
  });
}

export function useCreateChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { character_id: string; title?: string }) => api.createChat(b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chats"] }),
  });
}
