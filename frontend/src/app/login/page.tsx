"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useAuth } from "@/components/AuthProvider";

type Tab = "login" | "register";

function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export default function LoginPage() {
  const { login, register, loginWithGoogle, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<Tab>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (!validateEmail(email)) {
      setError("Please enter a valid email address");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }
    if (tab === "register" && !name.trim()) {
      setError("Please enter your name");
      return;
    }

    setSubmitting(true);
    try {
      if (tab === "login") {
        await login(email, password);
      } else {
        await register(email, password, name.trim());
      }
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setSubmitting(false);
    }
  };

  // Load Google Identity Services via useEffect (must be before any conditional returns)
  const googleInitRef = useRef(false);
  useEffect(() => {
    if (googleInitRef.current) return;
    googleInitRef.current = true;
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => {
      const google = (window as any).google;
      if (!google?.accounts?.id) return;
      google.accounts.id.initialize({
        client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
        callback: async (response: any) => {
          if (response.credential) {
            setSubmitting(true);
            setError("");
            try {
              await loginWithGoogle(response.credential);
            } catch (err: any) {
              setError(err.message || "Google login failed");
            } finally {
              setSubmitting(false);
            }
          }
        },
      });
    };
    document.head.appendChild(script);
  }, [loginWithGoogle]);

  const handleGoogleLogin = () => {
    if (typeof window === "undefined") return;
    const google = (window as any).google;
    if (!google?.accounts?.id) {
      setError("Google Sign-In is not available");
      return;
    }
    google.accounts.id.prompt((notification: any) => {
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        setError("Google Sign-In popup was blocked or unavailable");
      }
    });
  };

  // Show nothing while AuthProvider checks initial token
  if (authLoading) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.card}>
          <div style={styles.loadingDot} />
        </div>
      </div>
    );
  }

  return (
    <>
      <div style={styles.wrapper}>
        <div style={styles.card}>
          {/* Logo */}
          <div style={styles.logoSection}>
            <img
              src="/logo.png"
              alt="BD Go"
              style={styles.logo}
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
            <h1 style={styles.title}>BD Go</h1>
            <p style={styles.subtitle}>Biotech BD Intelligence Platform</p>
          </div>

          {/* Tab switcher */}
          <div style={styles.tabs}>
            <button
              style={{
                ...styles.tab,
                ...(tab === "login" ? styles.tabActive : {}),
              }}
              onClick={() => { setTab("login"); setError(""); }}
            >
              登录
            </button>
            <button
              style={{
                ...styles.tab,
                ...(tab === "register" ? styles.tabActive : {}),
              }}
              onClick={() => { setTab("register"); setError(""); }}
            >
              注册
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} style={styles.form}>
            {tab === "register" && (
              <input
                type="text"
                placeholder="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={styles.input}
                autoComplete="name"
              />
            )}
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={styles.input}
              autoComplete="email"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              autoComplete={tab === "login" ? "current-password" : "new-password"}
            />

            {error && <div style={styles.error}>{error}</div>}

            <button
              type="submit"
              disabled={submitting}
              style={{
                ...styles.submitBtn,
                ...(submitting ? styles.submitBtnDisabled : {}),
              }}
            >
              {submitting ? "..." : tab === "login" ? "登录" : "注册"}
            </button>
          </form>

          {/* Divider */}
          <div style={styles.divider}>
            <span style={styles.dividerLine} />
            <span style={styles.dividerText}>or</span>
            <span style={styles.dividerLine} />
          </div>

          {/* Google sign-in */}
          <button
            onClick={handleGoogleLogin}
            disabled={submitting}
            style={styles.googleBtn}
          >
            <svg width="18" height="18" viewBox="0 0 48 48" style={{ flexShrink: 0 }}>
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            <span>Sign in with Google</span>
          </button>
        </div>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════
// Inline styles using CSS variable values
// ═══════════════════════════════════════════

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "100vh",
    background: "var(--bg)",
    padding: "20px",
  },
  card: {
    width: "100%",
    maxWidth: 400,
    background: "var(--bg-card)",
    borderRadius: "var(--radius-lg)",
    border: "1px solid var(--border)",
    boxShadow: "var(--shadow-lg)",
    padding: "40px 36px",
  },
  logoSection: {
    textAlign: "center" as const,
    marginBottom: 28,
  },
  logo: {
    width: 56,
    height: 56,
    marginBottom: 12,
    borderRadius: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: "var(--text)",
    margin: "0 0 4px",
  },
  subtitle: {
    fontSize: 13,
    color: "var(--text-muted)",
    margin: 0,
  },
  tabs: {
    display: "flex",
    gap: 0,
    marginBottom: 24,
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--border)",
    overflow: "hidden",
  },
  tab: {
    flex: 1,
    padding: "10px 0",
    fontSize: 14,
    fontWeight: 500,
    border: "none",
    cursor: "pointer",
    background: "var(--bg)",
    color: "var(--text-secondary)",
    transition: "all 0.15s",
  },
  tabActive: {
    background: "var(--accent)",
    color: "var(--text-inverse)",
  },
  form: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 12,
  },
  input: {
    padding: "10px 14px",
    fontSize: 14,
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    background: "var(--bg-input)",
    color: "var(--text)",
    outline: "none",
    transition: "border-color 0.15s",
  },
  error: {
    fontSize: 13,
    color: "var(--red)",
    padding: "8px 12px",
    background: "rgba(220, 38, 38, 0.06)",
    borderRadius: "var(--radius-sm)",
  },
  submitBtn: {
    padding: "11px 0",
    fontSize: 15,
    fontWeight: 600,
    border: "none",
    borderRadius: "var(--radius-sm)",
    background: "var(--accent)",
    color: "var(--text-inverse)",
    cursor: "pointer",
    transition: "background 0.15s",
    marginTop: 4,
  },
  submitBtnDisabled: {
    opacity: 0.6,
    cursor: "not-allowed",
  },
  divider: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    margin: "20px 0",
  },
  dividerLine: {
    flex: 1,
    height: 1,
    background: "var(--border)",
  },
  dividerText: {
    fontSize: 12,
    color: "var(--text-muted)",
  },
  googleBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    width: "100%",
    padding: "10px 0",
    fontSize: 14,
    fontWeight: 500,
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    background: "var(--bg-card)",
    color: "var(--text)",
    cursor: "pointer",
    transition: "background 0.15s",
  },
  loadingDot: {
    width: 24,
    height: 24,
    margin: "40px auto",
    borderRadius: "50%",
    border: "3px solid var(--border)",
    borderTopColor: "var(--accent)",
    animation: "spin 0.8s linear infinite",
  },
};
