"use client";

import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";

// ---------------------------------------------------------------------------
// Feature cards data
// ---------------------------------------------------------------------------

const FEATURES = [
  {
    icon: "🧬",
    title: "Pipeline Intelligence",
    desc: "Track 22,000+ biotech assets across all therapeutic areas with real-time clinical trial data and competitive landscape analysis.",
  },
  {
    icon: "📊",
    title: "Deal Flow Analytics",
    desc: "Analyze licensing, M&A, and collaboration deals with structured data on deal terms, valuations, and strategic rationale.",
  },
  {
    icon: "🗓",
    title: "Catalyst Calendar",
    desc: "Never miss a critical data readout, regulatory decision, or clinical milestone. Track overdue and upcoming catalysts at a glance.",
  },
  {
    icon: "💬",
    title: "AI-Powered Chat",
    desc: "Ask questions in natural language. BD Go understands your CRM data and delivers insights with sources and context.",
  },
  {
    icon: "🏥",
    title: "Clinical Trial Deep Dive",
    desc: "Access 44,000+ clinical records with endpoint results, safety data, trial design, and head-to-head comparisons.",
  },
  {
    icon: "📄",
    title: "Automated Reports",
    desc: "Generate company analyses, buyer profiles, asset evaluations, and rNPV models — formatted and ready to share.",
  },
];

const STATS = [
  { value: "22K+", label: "Pipeline Assets" },
  { value: "44K+", label: "Clinical Records" },
  { value: "7K+", label: "BD Deals" },
  { value: "4K+", label: "Companies" },
];

// ---------------------------------------------------------------------------
// Landing Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const { user, loading } = useAuth();

  const ctaHref = user ? "/chat" : "/login";
  const ctaLabel = user ? "Enter Dashboard" : "Get Started";

  return (
    <div style={s.page}>
      {/* ─── Nav ─── */}
      <nav style={s.nav}>
        <div style={s.navInner}>
          <div style={s.navBrand}>
            <img
              src="/logo.png"
              alt="BD Go"
              style={s.navLogo}
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
            <span style={s.navTitle}>BD Go</span>
          </div>
          <div style={s.navActions}>
            {!loading && (
              user ? (
                <Link href="/chat" style={s.navCta}>Enter Dashboard →</Link>
              ) : (
                <>
                  <Link href="/login" style={s.navLogin}>Log In</Link>
                  <Link href="/login" style={s.navCta}>Get Started</Link>
                </>
              )
            )}
          </div>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <section style={s.hero}>
        <div style={s.heroInner}>
          <div style={s.badge}>Biotech BD Intelligence Platform</div>
          <h1 style={s.heroTitle}>
            The operating system for
            <br />
            <span style={s.heroGradient}>Biotech Business Development</span>
          </h1>
          <p style={s.heroDesc}>
            BD Go aggregates pipeline data, clinical trials, deal intelligence, and
            AI-powered analytics into one platform — so your BD team can find,
            evaluate, and act on opportunities faster.
          </p>
          <div style={s.heroCtas}>
            <Link href={ctaHref} style={s.ctaPrimary}>{ctaLabel}</Link>
            <a href="#features" style={s.ctaSecondary}>See Features ↓</a>
          </div>
        </div>
      </section>

      {/* ─── Stats ─── */}
      <section style={s.statsSection}>
        <div style={s.statsGrid}>
          {STATS.map((st) => (
            <div key={st.label} style={s.statCard}>
              <div style={s.statValue}>{st.value}</div>
              <div style={s.statLabel}>{st.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Features ─── */}
      <section id="features" style={s.featuresSection}>
        <h2 style={s.sectionTitle}>Everything your BD team needs</h2>
        <p style={s.sectionDesc}>
          From pipeline scouting to deal execution — one integrated platform.
        </p>
        <div style={s.featuresGrid}>
          {FEATURES.map((f) => (
            <div key={f.title} style={s.featureCard}>
              <div style={s.featureIcon}>{f.icon}</div>
              <h3 style={s.featureTitle}>{f.title}</h3>
              <p style={s.featureDesc}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── CTA banner ─── */}
      <section style={s.ctaBanner}>
        <h2 style={s.ctaBannerTitle}>Ready to accelerate your BD workflow?</h2>
        <p style={s.ctaBannerDesc}>
          Join BD professionals who use BD Go to find and evaluate biotech
          opportunities 10× faster.
        </p>
        <Link href={ctaHref} style={s.ctaPrimaryLg}>{ctaLabel}</Link>
      </section>

      {/* ─── Footer ─── */}
      <footer style={s.footer}>
        <div style={s.footerInner}>
          <span style={s.footerBrand}>BD Go</span>
          <span style={s.footerCopy}>© {new Date().getFullYear()} BD Go. Built for biotech BD teams.</span>
        </div>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const s: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#fafbfc",
    color: "#111827",
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },

  // Nav
  nav: {
    position: "sticky",
    top: 0,
    zIndex: 100,
    background: "rgba(255,255,255,0.85)",
    backdropFilter: "blur(12px)",
    borderBottom: "1px solid #e5e7eb",
  },
  navInner: {
    maxWidth: 1100,
    margin: "0 auto",
    padding: "0 24px",
    height: 64,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  navBrand: { display: "flex", alignItems: "center", gap: 10 },
  navLogo: { width: 32, height: 32, borderRadius: 8 },
  navTitle: { fontSize: 18, fontWeight: 700, color: "#1E3A8A" },
  navActions: { display: "flex", alignItems: "center", gap: 12 },
  navLogin: {
    fontSize: 14,
    fontWeight: 500,
    color: "#374151",
    textDecoration: "none",
    padding: "8px 16px",
  },
  navCta: {
    fontSize: 14,
    fontWeight: 600,
    color: "#fff",
    background: "#1E3A8A",
    padding: "8px 20px",
    borderRadius: 8,
    textDecoration: "none",
  },

  // Hero
  hero: {
    padding: "100px 24px 60px",
    textAlign: "center" as const,
  },
  heroInner: { maxWidth: 760, margin: "0 auto" },
  badge: {
    display: "inline-block",
    fontSize: 12,
    fontWeight: 600,
    color: "#1E3A8A",
    background: "#EFF6FF",
    border: "1px solid #BFDBFE",
    borderRadius: 20,
    padding: "6px 16px",
    marginBottom: 24,
    letterSpacing: "0.02em",
    textTransform: "uppercase" as const,
  },
  heroTitle: {
    fontSize: 48,
    fontWeight: 800,
    lineHeight: 1.15,
    color: "#111827",
    margin: "0 0 20px",
    letterSpacing: "-0.02em",
  },
  heroGradient: {
    background: "linear-gradient(135deg, #1E3A8A 0%, #3B82F6 50%, #0EA5E9 100%)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  },
  heroDesc: {
    fontSize: 18,
    lineHeight: 1.7,
    color: "#6b7280",
    maxWidth: 600,
    margin: "0 auto 36px",
  },
  heroCtas: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    flexWrap: "wrap" as const,
  },
  ctaPrimary: {
    fontSize: 16,
    fontWeight: 600,
    color: "#fff",
    background: "#1E3A8A",
    padding: "14px 32px",
    borderRadius: 10,
    textDecoration: "none",
    transition: "background 0.2s",
  },
  ctaSecondary: {
    fontSize: 16,
    fontWeight: 500,
    color: "#374151",
    padding: "14px 24px",
    textDecoration: "none",
  },

  // Stats
  statsSection: {
    padding: "0 24px 80px",
  },
  statsGrid: {
    maxWidth: 900,
    margin: "0 auto",
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 24,
  },
  statCard: {
    textAlign: "center" as const,
    padding: "28px 16px",
    background: "#fff",
    borderRadius: 12,
    border: "1px solid #e5e7eb",
  },
  statValue: {
    fontSize: 32,
    fontWeight: 800,
    color: "#1E3A8A",
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 13,
    color: "#6b7280",
    fontWeight: 500,
  },

  // Features
  featuresSection: {
    padding: "80px 24px",
    background: "#fff",
    borderTop: "1px solid #e5e7eb",
    borderBottom: "1px solid #e5e7eb",
  },
  sectionTitle: {
    fontSize: 32,
    fontWeight: 700,
    textAlign: "center" as const,
    margin: "0 0 12px",
    color: "#111827",
  },
  sectionDesc: {
    fontSize: 16,
    color: "#6b7280",
    textAlign: "center" as const,
    margin: "0 auto 48px",
    maxWidth: 500,
  },
  featuresGrid: {
    maxWidth: 1000,
    margin: "0 auto",
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 24,
  },
  featureCard: {
    padding: "28px 24px",
    borderRadius: 12,
    border: "1px solid #e5e7eb",
    background: "#fafbfc",
    transition: "box-shadow 0.2s",
  },
  featureIcon: {
    fontSize: 28,
    marginBottom: 14,
  },
  featureTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: "#111827",
    margin: "0 0 8px",
  },
  featureDesc: {
    fontSize: 14,
    lineHeight: 1.6,
    color: "#6b7280",
    margin: 0,
  },

  // CTA banner
  ctaBanner: {
    textAlign: "center" as const,
    padding: "80px 24px",
    background: "linear-gradient(135deg, #1E3A8A 0%, #2563eb 100%)",
    color: "#fff",
  },
  ctaBannerTitle: {
    fontSize: 28,
    fontWeight: 700,
    margin: "0 0 12px",
  },
  ctaBannerDesc: {
    fontSize: 16,
    opacity: 0.85,
    maxWidth: 500,
    margin: "0 auto 32px",
    lineHeight: 1.6,
  },
  ctaPrimaryLg: {
    display: "inline-block",
    fontSize: 16,
    fontWeight: 600,
    color: "#1E3A8A",
    background: "#fff",
    padding: "14px 36px",
    borderRadius: 10,
    textDecoration: "none",
  },

  // Footer
  footer: {
    padding: "24px",
    borderTop: "1px solid #e5e7eb",
    background: "#fff",
  },
  footerInner: {
    maxWidth: 1100,
    margin: "0 auto",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  footerBrand: {
    fontSize: 15,
    fontWeight: 700,
    color: "#1E3A8A",
  },
  footerCopy: {
    fontSize: 13,
    color: "#9ca3af",
  },
};
