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

  // Load Google Identity Services and render the official button
  const googleBtnRef = useRef<HTMLDivElement>(null);
  const googleInitRef = useRef(false);
  useEffect(() => {
    if (googleInitRef.current) return;
    googleInitRef.current = true;

    const initGoogle = () => {
      const google = (window as any).google;
      if (!google?.accounts?.id || !googleBtnRef.current) return;
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
      google.accounts.id.renderButton(googleBtnRef.current, {
        theme: "outline",
        size: "large",
        width: googleBtnRef.current.offsetWidth || 328,
        text: "signin_with",
      });
    };

    if ((window as any).google?.accounts?.id) {
      initGoogle();
    } else {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.onload = initGoogle;
      document.head.appendChild(script);
    }
  }, [loginWithGoogle]);

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

          {/* Google sign-in — rendered by Google Identity Services SDK */}
          <div ref={googleBtnRef} style={styles.googleBtnContainer} />
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
  googleBtnContainer: {
    width: "100%",
    display: "flex",
    justifyContent: "center",
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
