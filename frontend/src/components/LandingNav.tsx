import Link from "next/link";

// ─── BD Go SVG Mark ───────────────────────────────────────────────────────
// A deep-blue rounded square with a bold node→arrow inside.
// Works equally well on white, light-grey, or any light background.
// Use <BDGoMark size={N} /> anywhere you need just the icon.

export function BDGoMark({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0 }}>
      <rect width="36" height="36" rx="9" fill="#1E3A8A" />
      {/* Source node */}
      <circle cx="11" cy="18" r="3.5" fill="white" />
      {/* Arrow shaft */}
      <line x1="15" y1="18" x2="22.5" y2="18" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
      {/* Arrow head (filled triangle) */}
      <path d="M22 13 L29 18 L22 23 Z" fill="white" />
    </svg>
  );
}

// ─── Landing Nav ──────────────────────────────────────────────────────────
// Shared top-bar for all public landing pages.

export function LandingNav() {
  return (
    <nav style={{
      background: "#fff",
      borderBottom: "1px solid #E8EFFE",
      padding: "0 32px",
      height: 60,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
    }}>
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
        <BDGoMark size={32} />
        <span style={{ fontSize: 16, fontWeight: 800, color: "#1E3A8A", letterSpacing: "-0.01em" }}>
          BD<span style={{ fontWeight: 500 }}> Go</span>
        </span>
      </Link>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <Link href="/login" style={{ fontSize: 13, color: "#475569", textDecoration: "none", padding: "8px 16px" }}>登录</Link>
        <Link href="/login" style={{
          fontSize: 13, fontWeight: 600, color: "#fff",
          background: "#1E3A8A", padding: "8px 18px",
          borderRadius: 8, textDecoration: "none",
        }}>申请试用</Link>
      </div>
    </nav>
  );
}
