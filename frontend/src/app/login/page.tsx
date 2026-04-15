"use client";

import { useState, type FormEvent } from "react";
import { useAuth } from "@/components/AuthProvider";

type Tab = "login" | "register";

function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function BDGoLogo() {
  return (
    <img
      src="/logo.png"
      alt="BD Go"
      style={{ width: 56, height: 56, borderRadius: 14, objectFit: "contain", display: "block", margin: "0 auto 16px", boxShadow: "0 4px 16px rgba(30,58,138,0.15)" }}
      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
    />
  );
}

export default function LoginPage() {
  const { login, register, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<Tab>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!validateEmail(email)) { setError("请输入有效的邮箱地址"); return; }
    if (password.length < 6)   { setError("密码至少需要6个字符"); return; }
    if (tab === "register" && !name.trim()) { setError("请输入您的姓名"); return; }
    if (tab === "register" && !inviteCode.trim()) { setError("请输入邀请码"); return; }

    setSubmitting(true);
    try {
      if (tab === "login") {
        await login(email, password);
      } else {
        await register(email, password, name.trim(), inviteCode.trim());
      }
    } catch (err: any) {
      setError(err.message || "操作失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  if (authLoading) {
    return (
      <div style={s.wrapper}>
        <div style={s.card}>
          <div style={s.spinner} />
        </div>
      </div>
    );
  }

  return (
    <div style={s.wrapper}>
      {/* Background decoration */}
      <div style={s.bgDecor} />

      <div style={s.card}>
        {/* Logo + title */}
        <div style={s.header}>
          <BDGoLogo />
          <h1 style={s.title}>BD Go</h1>
          <p style={s.subtitle}>生物医药BD情报平台</p>
        </div>

        {/* Tab switcher */}
        <div style={s.tabs}>
          {(["login", "register"] as Tab[]).map((t) => (
            <button
              key={t}
              style={{ ...s.tab, ...(tab === t ? s.tabActive : {}) }}
              onClick={() => { setTab(t); setError(""); }}
            >
              {t === "login" ? "登录" : "注册"}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={s.form}>
          {tab === "register" && (
            <>
              <div style={s.fieldGroup}>
                <label style={s.label}>姓名</label>
                <input
                  type="text"
                  placeholder="请输入您的姓名"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  style={s.input}
                  autoComplete="name"
                />
              </div>
              <div style={s.fieldGroup}>
                <label style={s.label}>邀请码</label>
                <input
                  type="text"
                  placeholder="BDGO-XXXX-XXXX"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                  style={{ ...s.input, letterSpacing: "0.08em", fontFamily: "monospace" }}
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>
            </>
          )}

          <div style={s.fieldGroup}>
            <label style={s.label}>邮箱地址</label>
            <input
              type="email"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={s.input}
              autoComplete="email"
            />
          </div>

          <div style={s.fieldGroup}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <label style={s.label}>密码</label>
              {tab === "login" && (
                <a href="#" style={{ fontSize: 12, color: "#2563EB", textDecoration: "none", fontWeight: 500 }}>
                  忘记密码？
                </a>
              )}
            </div>
            <input
              type="password"
              placeholder={tab === "login" ? "请输入密码" : "至少6位字符"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={s.input}
              autoComplete={tab === "login" ? "current-password" : "new-password"}
            />
          </div>

          {error && (
            <div style={s.error}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
                <circle cx="8" cy="8" r="7" stroke="#EF4444" strokeWidth="1.5"/>
                <path d="M8 5v4M8 11v.5" stroke="#EF4444" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            style={{ ...s.submitBtn, ...(submitting ? s.submitBtnDisabled : {}) }}
          >
            {submitting ? "处理中…" : tab === "login" ? "登录" : "创建账户"}
          </button>
        </form>

        <p style={s.switchText}>
          {tab === "login" ? "还没有账户？" : "已有账户？"}
          <button
            style={s.switchLink}
            onClick={() => { setTab(tab === "login" ? "register" : "login"); setError(""); }}
          >
            {tab === "login" ? "免费注册" : "立即登录"}
          </button>
        </p>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "100vh",
    background: "linear-gradient(160deg, #EEF2FF 0%, #F0F9FF 60%, #F8FAFF 100%)",
    padding: "24px",
    position: "relative",
    overflow: "hidden",
  },
  bgDecor: {
    position: "absolute",
    top: -120,
    right: -120,
    width: 500,
    height: 500,
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(37,99,235,0.08) 0%, transparent 70%)",
    pointerEvents: "none",
  },
  card: {
    width: "100%",
    maxWidth: 420,
    background: "#fff",
    borderRadius: 20,
    border: "1px solid #E8EFFE",
    boxShadow: "0 20px 60px rgba(30,58,138,0.1)",
    padding: "40px 36px 36px",
    position: "relative",
    zIndex: 1,
  },
  header: {
    textAlign: "center",
    marginBottom: 28,
  },
  title: {
    fontSize: 22,
    fontWeight: 800,
    color: "#0F172A",
    margin: "0 0 4px",
    letterSpacing: "-0.01em",
  },
  subtitle: {
    fontSize: 13,
    color: "#94A3B8",
    margin: 0,
    fontWeight: 500,
  },
  tabs: {
    display: "flex",
    gap: 0,
    marginBottom: 24,
    borderRadius: 10,
    border: "1px solid #E8EFFE",
    overflow: "hidden",
    background: "#F8FAFF",
    padding: 3,
  },
  tab: {
    flex: 1,
    padding: "9px 0",
    fontSize: 13,
    fontWeight: 600,
    border: "none",
    cursor: "pointer",
    background: "transparent",
    color: "#94A3B8",
    borderRadius: 8,
    transition: "all 0.15s",
  },
  tabActive: {
    background: "#fff",
    color: "#1E3A8A",
    boxShadow: "0 1px 4px rgba(30,58,138,0.12)",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 0,
  },
  fieldGroup: {
    marginBottom: 16,
  },
  label: {
    display: "block",
    fontSize: 12,
    fontWeight: 600,
    color: "#374151",
    marginBottom: 6,
    letterSpacing: "0.01em",
  },
  input: {
    width: "100%",
    padding: "11px 14px",
    fontSize: 14,
    border: "1px solid #E2E8F0",
    borderRadius: 10,
    background: "#FAFBFF",
    color: "#0F172A",
    outline: "none",
    transition: "border-color 0.15s, box-shadow 0.15s",
    boxSizing: "border-box",
    fontFamily: "inherit",
  },
  error: {
    fontSize: 13,
    color: "#DC2626",
    padding: "10px 12px",
    background: "#FEF2F2",
    border: "1px solid #FECACA",
    borderRadius: 9,
    marginBottom: 14,
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  submitBtn: {
    width: "100%",
    padding: "13px 0",
    fontSize: 14,
    fontWeight: 700,
    border: "none",
    borderRadius: 11,
    background: "linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%)",
    color: "#fff",
    cursor: "pointer",
    transition: "opacity 0.15s, box-shadow 0.15s",
    boxShadow: "0 4px 14px rgba(30,58,138,0.3)",
    marginTop: 4,
    letterSpacing: "0.01em",
    fontFamily: "inherit",
  },
  submitBtnDisabled: {
    opacity: 0.6,
    cursor: "not-allowed",
    boxShadow: "none",
  },
  switchText: {
    textAlign: "center",
    fontSize: 13,
    color: "#94A3B8",
    marginTop: 20,
    marginBottom: 0,
  },
  switchLink: {
    background: "none",
    border: "none",
    color: "#2563EB",
    fontWeight: 600,
    cursor: "pointer",
    fontSize: 13,
    padding: "0 4px",
    fontFamily: "inherit",
  },
  spinner: {
    width: 28,
    height: 28,
    margin: "40px auto",
    borderRadius: "50%",
    border: "3px solid #EEF2FF",
    borderTopColor: "#2563EB",
    animation: "spin 0.8s linear infinite",
  },
};
