// Lightweight access-token management (design 5.3, 14.4).
// In local mode (AUTH_ENABLED=false) the backend injects default-user, so no token is needed.

const TOKEN_KEY = "acw_access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

/**
 * Extract the access token the OAuth callback delivers in the URL fragment,
 * e.g. `#access_token=ey...`. Returns null when absent/empty. Pure + SSR-safe
 * so it can be unit-tested (login completion flow, design 14.4).
 */
export function parseAccessTokenFromHash(hash: string): string | null {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  const token = new URLSearchParams(raw).get("access_token");
  return token && token.length > 0 ? token : null;
}
