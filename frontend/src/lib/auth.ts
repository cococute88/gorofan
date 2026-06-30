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
