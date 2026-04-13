// ═══════════════════════════════════════════
// BD Go — Auth token & user storage (localStorage)
// ═══════════════════════════════════════════

import { isBrowser } from "./utils";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  provider: string;
  created_at?: string;
  last_login?: string;
  company?: string;
  title?: string;
  phone?: string;
  bio?: string;
  preferences_json?: string;
}

const TOKEN_KEY = "bdgo.auth.token";
const USER_KEY = "bdgo.auth.user";

export function getToken(): string | null {
  if (!isBrowser()) return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  if (!isBrowser()) return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: AuthUser): void {
  if (!isBrowser()) return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

// ═══════════════════════════════════════════
// Structured preferences (stored as JSON in preferences_json)
// ═══════════════════════════════════════════

export interface UserPreferences {
  show_database_nav?: boolean;
}

export function parsePreferences(user: AuthUser | null): UserPreferences {
  if (!user?.preferences_json) return {};
  try {
    return JSON.parse(user.preferences_json) as UserPreferences;
  } catch {
    return {};
  }
}
