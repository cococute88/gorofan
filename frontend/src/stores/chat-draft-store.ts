// Draft message + streaming buffer state (design 5.4).
import { create } from "zustand";

interface ChatDraftState {
  drafts: Record<string, string>;
  streaming: Record<string, boolean>;
  setDraft: (chatId: string, value: string) => void;
  clearDraft: (chatId: string) => void;
  setStreaming: (chatId: string, on: boolean) => void;
}

export const useChatDraftStore = create<ChatDraftState>((set) => ({
  drafts: {},
  streaming: {},
  setDraft: (chatId, value) => set((s) => ({ drafts: { ...s.drafts, [chatId]: value } })),
  clearDraft: (chatId) =>
    set((s) => {
      const next = { ...s.drafts };
      delete next[chatId];
      return { drafts: next };
    }),
  setStreaming: (chatId, on) => set((s) => ({ streaming: { ...s.streaming, [chatId]: on } })),
}));
