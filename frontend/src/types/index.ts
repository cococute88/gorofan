// Shared types mirroring backend schemas (design 5.3).

export interface Paged<T> {
  items: T[];
  next_cursor: string | null;
}

export interface World {
  id: string;
  user_id: string;
  name: string;
  description: string;
  era: string;
  races: string[];
  nations: string[];
  taboos: string[];
  created_at: string;
  updated_at: string;
}

export interface Character {
  id: string;
  user_id: string;
  world_id: string | null;
  name: string;
  avatar_url: string | null;
  greeting: string;
  speech_style: string;
  personality: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface Persona {
  id: string;
  user_id: string;
  name: string;
  description: string;
}

export interface Lorebook {
  id: string;
  world_id: string;
  name: string;
  enabled: boolean;
}

export interface LoreEntry {
  id: string;
  lorebook_id: string;
  keywords: string[];
  content: string;
  priority: number;
  enabled: boolean;
  scan_depth: number;
}

export interface GlossaryTerm {
  id: string;
  world_id: string;
  term: string;
  definition: string;
}

export interface ChatSession {
  id: string;
  user_id: string;
  character_id: string;
  persona_id: string | null;
  model_config_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  chat_session_id: string;
  parent_message_id: string | null;
  role: "user" | "assistant" | "system";
  content: string;
  token_count: number;
  status: string;
  is_active: boolean;
  created_at: string;
}

export interface Work {
  id: string;
  user_id: string;
  world_id: string | null;
  title: string;
  synopsis: string;
  genre: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface Chapter {
  id: string;
  work_id: string;
  index: number;
  title: string;
  content_doc: unknown;
  content_text: string;
  summary: string;
  word_count: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WorkCharacter {
  id: string;
  work_id: string;
  character_id: string;
  role_in_work: string;
  created_at: string;
  updated_at: string;
}

export interface ModelConfig {
  id: string;
  provider: string;
  model_name: string;
  base_url: string | null;
  purpose: string;
  temperature: number;
  max_tokens: number;
  context_window: number;
  is_default: boolean;
}

export interface Credential {
  id: string;
  provider: string;
  label: string;
  masked_key: string;
}

export interface ProviderInfo {
  provider: string;
  models: string[];
}

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
}
