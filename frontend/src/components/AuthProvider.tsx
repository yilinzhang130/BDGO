"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getToken, getUser, setAuth, clearAuth, type AuthUser } from "@/lib/auth";
import { useLocale } from "@/lib/locale";

// ═══════════════════════════════════════════
// Context type
// ═══════════════════════════════════════════

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, inviteCode: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  updateUser: (u: AuthUser) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ═══════════════════════════════════════════
// Error message translator
// ═══════════════════════════════════════════
// Turn raw HTTP status + backend detail into user-facing Chinese messages.
// Never show "Login failed: 502" — those are noise to end users.

type TFn = (key: string) => string;

function friendlyAuthError(
  action: "login" | "register" | "google",
  status: number,
  t: TFn,
  detail?: string,
): string {
  // Backend-provided detail wins if it looks like a real message (not a raw number)
  if (detail && detail.length > 4 && !/^\d+$/.test(detail)) return detail;

  if (status === 401) {
    return action === "login" ? t("auth.error.wrongPassword") : t("auth.error.authFailed");
  }
  if (status === 403) return detail || t("auth.error.noPermission");
  if (status === 404) {
    return action === "login" ? t("auth.error.emailNotFound") : t("auth.error.apiNotFound");
  }
  if (status === 409) return t("auth.error.emailExists");
  if (status === 400) return detail || t("auth.error.badRequest");
  if (status === 422) return detail || t("auth.error.incomplete");
  if (status === 429) return t("auth.error.tooManyRequests");
  if (status >= 500 && status < 600) return t("auth.error.serverError");
  if (status === 0) {
    // Network-level failure (caller sets status=0 on fetch throw)
    return t("auth.error.networkError");
  }
  return detail || t("auth.error.fallback");
}

async function parseErrorDetail(res: Response): Promise<string | undefined> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  } catch {}
  return undefined;
}

// ═══════════════════════════════════════════
// Hook
// ═══════════════════════════════════════════

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

// ═══════════════════════════════════════════
// Provider
// ═══════════════════════════════════════════

const PUBLIC_PATHS = [
  "/login",
  "/",
  "/apply",
  "/changelog",
  "/share",
  "/privacy",
  "/terms",
  "/security",
  "/blog",
  "/docs",
  "/about",
  "/features",
  "/pricing",
  "/use-cases",
  "/api-docs",
  "/contact",
];

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useLocale();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Validate token on mount
  useEffect(() => {
    const stored = getToken();
    if (!stored) {
      setLoading(false);
      return;
    }

    fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${stored}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("invalid");
        return res.json();
      })
      .then((u: AuthUser) => {
        setUser(u);
        setToken(stored);
        setAuth(stored, u); // refresh cached user info
      })
      .catch(() => {
        clearAuth();
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // Route protection: redirect unauthenticated users to /login
  useEffect(() => {
    if (loading) return;
    const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
    if (!user && !isPublic) {
      router.replace("/login");
    }
    if (user && pathname === "/login") {
      router.replace("/chat");
    }
  }, [user, loading, pathname, router]);

  const login = useCallback(
    async (email: string, password: string) => {
      let res: Response;
      try {
        res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
      } catch {
        throw new Error(friendlyAuthError("login", 0, t));
      }
      if (!res.ok) {
        const detail = await parseErrorDetail(res);
        throw new Error(friendlyAuthError("login", res.status, t, detail));
      }
      const data = await res.json();
      setAuth(data.token, data.user);
      setUser(data.user);
      setToken(data.token);
      router.replace("/chat");
    },
    [router, t],
  );

  const register = useCallback(
    async (email: string, password: string, name: string, inviteCode: string) => {
      let res: Response;
      try {
        res = await fetch("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, name, invite_code: inviteCode }),
        });
      } catch {
        throw new Error(friendlyAuthError("register", 0, t));
      }
      if (!res.ok) {
        const detail = await parseErrorDetail(res);
        throw new Error(friendlyAuthError("register", res.status, t, detail));
      }
      const data = await res.json();
      setAuth(data.token, data.user);
      setUser(data.user);
      setToken(data.token);
      router.replace("/chat");
    },
    [router, t],
  );

  const loginWithGoogle = useCallback(
    async (idToken: string) => {
      let res: Response;
      try {
        res = await fetch("/api/auth/google", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: idToken }),
        });
      } catch {
        throw new Error(friendlyAuthError("google", 0, t));
      }
      if (!res.ok) {
        const detail = await parseErrorDetail(res);
        throw new Error(friendlyAuthError("google", res.status, t, detail));
      }
      const data = await res.json();
      setAuth(data.token, data.user);
      setUser(data.user);
      setToken(data.token);
      router.replace("/chat");
    },
    [router, t],
  );

  const refreshUser = useCallback(async () => {
    const stored = getToken();
    if (!stored) return;
    const res = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${stored}` },
    });
    if (!res.ok) return;
    const u: AuthUser = await res.json();
    setUser(u);
    setAuth(stored, u);
  }, []);

  const updateUser = useCallback((u: AuthUser) => {
    const stored = getToken();
    setUser(u);
    if (stored) setAuth(stored, u);
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    setToken(null);
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        loginWithGoogle,
        logout,
        refreshUser,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
