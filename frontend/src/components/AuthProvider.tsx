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

function friendlyAuthError(
  action: "login" | "register" | "google",
  status: number,
  detail?: string,
): string {
  // Backend-provided detail wins if it's already human-readable Chinese
  if (detail && /[\u4e00-\u9fa5]/.test(detail)) return detail;

  if (status === 401) {
    return action === "login" ? "邮箱或密码错误，请重试" : "身份验证失败";
  }
  if (status === 403) return detail || "没有访问权限";
  if (status === 404) {
    return action === "login" ? "该邮箱未注册，请先注册账户" : "接口不存在";
  }
  if (status === 409) return "该邮箱已被注册";
  if (status === 400) return detail || "请求格式有误";
  if (status === 422) return detail || "填写的信息不完整";
  if (status === 429) return "请求过于频繁，请稍后再试";
  if (status >= 500 && status < 600) {
    return "服务暂时不可用，请稍后再试（后端异常）";
  }
  if (status === 0) {
    // Network-level failure (caller sets status=0 on fetch throw)
    return "无法连接服务器，请检查网络或稍后再试";
  }
  return detail || "操作失败，请稍后重试";
}

async function parseErrorDetail(res: Response): Promise<string | undefined> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail[0]?.msg)
      return body.detail[0].msg;
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

const PUBLIC_PATHS = ["/login", "/", "/share"];

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
    let res: Response;
    try {
      res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
    } catch {
      throw new Error(friendlyAuthError("login", 0));
    }
    if (!res.ok) {
      const detail = await parseErrorDetail(res);
      throw new Error(friendlyAuthError("login", res.status, detail));
    }
    const data = await res.json();
    setAuth(data.token, data.user);
    setUser(data.user);
    setToken(data.token);
    router.replace("/chat");
  }, [router]);

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
        throw new Error(friendlyAuthError("register", 0));
      }
      if (!res.ok) {
        const detail = await parseErrorDetail(res);
        throw new Error(friendlyAuthError("register", res.status, detail));
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
      let res: Response;
      try {
        res = await fetch("/api/auth/google", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: idToken }),
        });
      } catch {
        throw new Error(friendlyAuthError("google", 0));
      }
      if (!res.ok) {
        const detail = await parseErrorDetail(res);
        throw new Error(friendlyAuthError("google", res.status, detail));
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
      value={{ user, token, loading, login, register, loginWithGoogle, logout, refreshUser, updateUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}
