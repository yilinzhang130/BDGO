"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  getToken,
  getUser,
  setAuth,
  clearAuth,
  type AuthUser,
} from "@/lib/auth";

// ═══════════════════════════════════════════
// Context type
// ═══════════════════════════════════════════

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

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

const PUBLIC_PATHS = ["/login"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
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
    const isPublic = PUBLIC_PATHS.some(
      (p) => pathname === p || pathname.startsWith(p + "/"),
    );
    if (!user && !isPublic) {
      router.replace("/login");
    }
    if (user && pathname === "/login") {
      router.replace("/chat");
    }
  }, [user, loading, pathname, router]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Login failed: ${res.status}`);
    }
    const data = await res.json();
    setAuth(data.token, data.user);
    setUser(data.user);
    setToken(data.token);
    router.replace("/chat");
  }, [router]);

  const register = useCallback(
    async (email: string, password: string, name: string) => {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Registration failed: ${res.status}`);
      }
      const data = await res.json();
      setAuth(data.token, data.user);
      setUser(data.user);
      setToken(data.token);
      router.replace("/chat");
    },
    [router],
  );

  const loginWithGoogle = useCallback(
    async (idToken: string) => {
      const res = await fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: idToken }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Google login failed: ${res.status}`);
      }
      const data = await res.json();
      setAuth(data.token, data.user);
      setUser(data.user);
      setToken(data.token);
      router.replace("/chat");
    },
    [router],
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

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    setToken(null);
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{ user, token, loading, login, register, loginWithGoogle, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}
