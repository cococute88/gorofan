// Typed endpoint wrappers (design 6.2).
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  Chapter,
  Character,
  ChatSession,
  Credential,
  CurrentUser,
  GlossaryTerm,
  Lorebook,
  LoreEntry,
  Message,
  ModelConfig,
  Paged,
  Persona,
  ProviderInfo,
  Work,
  World,
} from "@/types";

// --- auth ---
export const getMe = () => apiGet<CurrentUser>("/auth/me");

// --- characters ---
export const listCharacters = (q = "") => apiGet<Paged<Character>>(`/characters${q}`);
export const getCharacter = (id: string) => apiGet<Character>(`/characters/${id}`);
export const createCharacter = (b: Partial<Character>) => apiPost<Character>("/characters", b);
export const updateCharacter = (id: string, b: Partial<Character>) =>
  apiPatch<Character>(`/characters/${id}`, b);
export const deleteCharacter = (id: string) => apiDelete<void>(`/characters/${id}`);

// --- personas ---
export const listPersonas = () => apiGet<Paged<Persona>>("/personas");
export const createPersona = (b: Partial<Persona>) => apiPost<Persona>("/personas", b);

// --- worlds ---
export const listWorlds = () => apiGet<Paged<World>>("/worlds");
export const getWorld = (id: string) => apiGet<World>(`/worlds/${id}`);
export const createWorld = (b: Partial<World>) => apiPost<World>("/worlds", b);
export const updateWorld = (id: string, b: Partial<World>) => apiPatch<World>(`/worlds/${id}`, b);
export const deleteWorld = (id: string) => apiDelete<void>(`/worlds/${id}`);
export const listLorebooks = (worldId: string) =>
  apiGet<Lorebook[]>(`/worlds/${worldId}/lorebooks`);
export const createLorebook = (worldId: string, b: Partial<Lorebook>) =>
  apiPost<Lorebook>(`/worlds/${worldId}/lorebooks`, b);
export const listLoreEntries = (lorebookId: string) =>
  apiGet<LoreEntry[]>(`/worlds/lorebooks/${lorebookId}/entries`);
export const createLoreEntry = (lorebookId: string, b: Partial<LoreEntry>) =>
  apiPost<LoreEntry>(`/worlds/lorebooks/${lorebookId}/entries`, b);
export const listGlossary = (worldId: string) =>
  apiGet<GlossaryTerm[]>(`/worlds/${worldId}/glossary`);
export const createGlossary = (worldId: string, b: Partial<GlossaryTerm>) =>
  apiPost<GlossaryTerm>(`/worlds/${worldId}/glossary`, b);

// --- chats ---
export const listChats = () => apiGet<Paged<ChatSession>>("/chats");
export const createChat = (b: { character_id: string; title?: string; model_config_id?: string }) =>
  apiPost<ChatSession>("/chats", b);
export const listMessages = (chatId: string, before?: string) =>
  apiGet<Paged<Message>>(`/chats/${chatId}/messages${before ? `?before=${before}` : ""}`);

// --- novels ---
export const listWorks = () => apiGet<Paged<Work>>("/works");
export const getWork = (id: string) => apiGet<Work>(`/works/${id}`);
export const createWork = (b: Partial<Work>) => apiPost<Work>("/works", b);
export const updateWork = (id: string, b: Partial<Work>) => apiPatch<Work>(`/works/${id}`, b);
export const deleteWork = (id: string) => apiDelete<void>(`/works/${id}`);
export const listChapters = (workId: string) => apiGet<Chapter[]>(`/works/${workId}/chapters`);
export const createChapter = (workId: string, b: { title?: string; content_text?: string }) =>
  apiPost<Chapter>(`/works/${workId}/chapters`, b);
export const updateChapter = (
  chapterId: string,
  b: { title?: string; content_text?: string; content_doc?: unknown; version: number },
) => apiPatch<Chapter>(`/works/chapters/${chapterId}`, b);
export const deleteChapter = (chapterId: string) =>
  apiDelete<void>(`/works/chapters/${chapterId}`);
export const reorderChapters = (workId: string, ordered_chapter_ids: string[]) =>
  apiPatch<void>(`/works/${workId}/chapters:reorder`, { ordered_chapter_ids });

// --- ai config ---
export const listModelConfigs = () => apiGet<ModelConfig[]>("/model-configs");
export const createModelConfig = (b: Partial<ModelConfig>) =>
  apiPost<ModelConfig>("/model-configs", b);
export const listCredentials = () => apiGet<Credential[]>("/credentials");
export const createCredential = (b: { provider: string; api_key: string; label?: string }) =>
  apiPost<Credential>("/credentials", b);
export const listProviders = () => apiGet<ProviderInfo[]>("/providers");
