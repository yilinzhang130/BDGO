"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";

// ---------------------------------------------------------------------------
// Design tokens — light + dark
// ---------------------------------------------------------------------------

type Theme = "light" | "dark";

type Tokens = {
  bg: string;
  bgAlt: string;
  bgCard: string;
  fg: string;
  fg2: string;
  fg3: string;
  border: string;
  borderStrong: string;
  brand: string;
  brandSoft: string;
  accent1: string;
  accent2: string;
  accent3: string;
  rule: string;
  codebg: string;
};

const LIGHT: Tokens = {
  bg: "#F5F4EE",
  bgAlt: "#EBE9DF",
  bgCard: "#FFFDF7",
  fg: "#1A1814",
  fg2: "#52504A",
  fg3: "#8A877E",
  border: "#DCD8CB",
  borderStrong: "#BFB9A6",
  brand: "#1E3A8A",
  brandSoft: "rgba(30,58,138,.08)",
  accent1: "#0891B2",
  accent2: "#7C3AED",
  accent3: "#059669",
  rule: "rgba(26,24,20,.08)",
  codebg: "#0F172A",
};

const DARK: Tokens = {
  bg: "#0A0E1A",
  bgAlt: "#0F1525",
  bgCard: "#141B30",
  fg: "#F1F5FB",
  fg2: "#A8B2C8",
  fg3: "#6B7488",
  border: "#1E2538",
  borderStrong: "#2A3450",
  brand: "#3B82F6",
  brandSoft: "rgba(59,130,246,.18)",
  accent1: "#22D3EE",
  accent2: "#A78BFA",
  accent3: "#34D399",
  rule: "rgba(255,255,255,.06)",
  codebg: "#0B1020",
};

const fontSans =
  '"Space Grotesk", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", -apple-system, sans-serif';
const fontMono = '"JetBrains Mono", ui-monospace, Menlo, monospace';
const fontSerif = '"PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", sans-serif';

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const { user, loading } = useAuth();
  const ctaHref = user ? "/chat" : "/login";

  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const saved = (typeof window !== "undefined" &&
      localStorage.getItem("bdgo-theme")) as Theme | null;
    if (saved === "light" || saved === "dark") {
      setTheme(saved);
    } else if (
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ) {
      setTheme("dark");
    }
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("bdgo-theme", theme);
  }, [theme]);

  const T = theme === "dark" ? DARK : LIGHT;
  const dark = theme === "dark";

  return (
    <div
      style={{
        background: T.bg,
        color: T.fg,
        fontFamily: fontSans,
        minHeight: "100vh",
        transition: "background 0.18s, color 0.18s",
      }}
    >
      <style>{`
        @keyframes bdgo-pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.3); opacity: .6; }
        }
        @media (prefers-reduced-motion: reduce) {
          .bdgo-pulse { animation: none !important; }
        }
        html { scroll-behavior: smooth; }
      `}</style>

      <Nav T={T} ctaHref={ctaHref} authReady={!loading} authed={!!user} theme={theme} onThemeChange={setTheme} />

      <Hero T={T} dark={dark} ctaHref={ctaHref} />

      <Story T={T} />

      <AIDDHighlight T={T} dark={dark} />

      <DEFSection T={T} dark={dark} />

      <Products T={T} ctaHref={ctaHref} />

      <AI4SLab T={T} dark={dark} />

      <FooterCTA T={T} dark={dark} ctaHref={ctaHref} />

      <FooterMeta T={T} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Brand mark (inline SVG, theme-aware)
// ---------------------------------------------------------------------------

function BDGoLogo({ size = 24, T }: { size?: number; T: Tokens }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none" style={{ flexShrink: 0 }}>
      <rect width="36" height="36" rx="9" fill={T.brand} />
      <circle cx="11" cy="18" r="3.5" fill="#fff" />
      <line
        x1="15"
        y1="18"
        x2="22.5"
        y2="18"
        stroke="#fff"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path d="M22 13 L29 18 L22 23 Z" fill="#fff" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Nav with mega-menu dropdowns
// ---------------------------------------------------------------------------

type MegaKind = "products" | "solutions" | "pricing" | "resources" | null;

function Nav({
  T,
  ctaHref,
  authReady,
  authed,
  theme,
  onThemeChange,
}: {
  T: Tokens;
  ctaHref: string;
  authReady: boolean;
  authed: boolean;
  theme: Theme;
  onThemeChange: (t: Theme) => void;
}) {
  const [open, setOpen] = useState<MegaKind>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onEnter = (k: MegaKind) => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpen(k);
  };
  const onLeave = () => {
    closeTimer.current = setTimeout(() => setOpen(null), 140);
  };

  const link: React.CSSProperties = {
    color: T.fg2,
    textDecoration: "none",
    fontWeight: 500,
    fontSize: 13.5,
    padding: "8px 4px",
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    cursor: "pointer",
    fontFamily: fontSans,
  };

  const caret = (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ opacity: 0.55 }}>
      <path
        d="M2 4l3 3 3-3"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: `${T.bg}E6`,
        backdropFilter: "blur(16px)",
        borderBottom: `1px solid ${T.rule}`,
        padding: "14px 48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 36 }}>
        <Link
          href="/"
          style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none" }}
        >
          <BDGoLogo size={24} T={T} />
          <span
            style={{
              fontFamily: fontSans,
              fontWeight: 600,
              fontSize: 15,
              letterSpacing: ".08em",
              color: T.fg,
              textTransform: "uppercase",
              lineHeight: 1,
            }}
          >
            BD&nbsp;GO
          </span>
          <span
            style={{
              fontSize: 9.5,
              color: T.fg3,
              padding: "2px 6px",
              border: `1px solid ${T.border}`,
              borderRadius: 3,
              fontFamily: fontMono,
              letterSpacing: ".05em",
              marginLeft: 2,
            }}
          >
            v0.9
          </span>
        </Link>

        <nav style={{ display: "flex", gap: 24, alignItems: "center" }}>
          <div
            onMouseEnter={() => onEnter("products")}
            onMouseLeave={onLeave}
            style={{ position: "relative" }}
          >
            <span style={link}>产品 {caret}</span>
            {open === "products" && <Mega T={T} kind="products" />}
          </div>
          <div
            onMouseEnter={() => onEnter("solutions")}
            onMouseLeave={onLeave}
            style={{ position: "relative" }}
          >
            <span style={link}>方案 {caret}</span>
            {open === "solutions" && <Mega T={T} kind="solutions" />}
          </div>
          <div
            onMouseEnter={() => onEnter("pricing")}
            onMouseLeave={onLeave}
            style={{ position: "relative" }}
          >
            <span style={link}>定价 {caret}</span>
            {open === "pricing" && <Mega T={T} kind="pricing" />}
          </div>
          <div
            onMouseEnter={() => onEnter("resources")}
            onMouseLeave={onLeave}
            style={{ position: "relative" }}
          >
            <span style={link}>资源 {caret}</span>
            {open === "resources" && <Mega T={T} kind="resources" />}
          </div>
          <Link href="#ai4s" style={link}>
            AI4S 实验室
          </Link>
          <Link href="/docs" style={link}>
            文档
          </Link>
        </nav>
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
        <a
          href="#ai4s"
          style={{
            ...link,
            padding: "6px 10px",
            borderRadius: 6,
            background: T.brandSoft,
            color: T.brand,
            fontWeight: 600,
            fontSize: 12,
            fontFamily: fontMono,
            letterSpacing: ".02em",
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: T.accent3,
              boxShadow: `0 0 0 3px ${T.accent3}33`,
              display: "inline-block",
            }}
          />
          v0.9.2 · NEW
        </a>
        <Link href="/blog" style={{ ...link, fontSize: 13 }}>
          博客
        </Link>
        {authReady &&
          (authed ? (
            <Link
              href="/chat"
              style={{
                padding: "9px 18px",
                borderRadius: 8,
                background: T.fg,
                color: T.bg,
                fontSize: 13,
                fontWeight: 600,
                textDecoration: "none",
                fontFamily: fontSans,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              进入工作台 <span style={{ fontSize: 14 }}>→</span>
            </Link>
          ) : (
            <>
              <Link href="/login" style={{ ...link, fontSize: 13 }}>
                登录
              </Link>
              <Link
                href={ctaHref}
                style={{
                  padding: "9px 18px",
                  borderRadius: 8,
                  background: T.fg,
                  color: T.bg,
                  fontSize: 13,
                  fontWeight: 600,
                  textDecoration: "none",
                  fontFamily: fontSans,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                免费试用 <span style={{ fontSize: 14 }}>→</span>
              </Link>
            </>
          ))}
      </div>
    </header>
  );
}

function Mega({ T, kind }: { T: Tokens; kind: Exclude<MegaKind, null> }) {
  const wrap: React.CSSProperties = {
    position: "absolute",
    top: "calc(100% + 12px)",
    left: -20,
    background: T.bgCard,
    border: `1px solid ${T.border}`,
    borderRadius: 14,
    padding: 24,
    boxShadow: `0 24px 60px rgba(0,0,0,.12)`,
    minWidth: 560,
    zIndex: 60,
  };
  const eyebrow: React.CSSProperties = {
    fontFamily: fontMono,
    fontSize: 10,
    color: T.fg3,
    letterSpacing: ".12em",
    marginBottom: 14,
    fontWeight: 700,
    textTransform: "uppercase",
  };

  if (kind === "products") {
    const items: { tag: string; color: string; title: string; desc: string; href: string }[] = [
      {
        tag: "BD GO",
        color: T.brand,
        title: "对话式 BD 工作台",
        desc: "自然语言抓情报、做尽调、写竞品分析。",
        href: "/chat",
      },
      {
        tag: "DEF",
        color: T.accent2,
        title: "痛点 · 立项引擎",
        desc: "疾病 × 终点 × 前沿三维交叉，找未满足窗口。",
        href: "/features",
      },
      {
        tag: "AIDD",
        color: T.accent3,
        title: "AI Drug Discovery",
        desc: "结构 + ADMET + IP 一条流水线跑完。",
        href: "/features",
      },
    ];
    return (
      <div style={wrap}>
        <div style={eyebrow}>三条产品线</div>
        <div style={{ display: "grid", gap: 4 }}>
          {items.map((it) => (
            <Link
              key={it.tag}
              href={it.href}
              style={{
                display: "grid",
                gridTemplateColumns: "60px 1fr auto",
                gap: 14,
                alignItems: "center",
                padding: 10,
                borderRadius: 8,
                textDecoration: "none",
                transition: "background .12s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = T.bgAlt)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: ".08em",
                  color: it.color,
                  padding: "4px 8px",
                  background: `${it.color}1A`,
                  borderRadius: 4,
                  textAlign: "center",
                }}
              >
                {it.tag}
              </span>
              <div>
                <div style={{ fontFamily: fontSerif, fontSize: 18, color: T.fg, lineHeight: 1.2 }}>
                  {it.title}
                </div>
                <div style={{ fontSize: 12, color: T.fg2, marginTop: 2 }}>{it.desc}</div>
              </div>
              <span style={{ color: T.fg3, fontSize: 14 }}>→</span>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  if (kind === "solutions") {
    const roles: [string, string][] = [
      ["BD 团队", "竞品 / 交易 / 会议情报"],
      ["立项委员会", "未满足需求 + 立项打分"],
      ["AI4S 研究员", "靶点反查 + Portfolio"],
      ["IR / 战略", "全球管线追踪"],
    ];
    const scenes: [string, string][] = [
      ["AACR / ASCO 跟会", "实时摘要 + 中国公司聚合"],
      ["JPM 周尽调", "13F + 交易 + 管线"],
      ["靶点立项", "DEF + AIDD 串联"],
      ["竞品对标", "管线 / IP / 交易雷达"],
    ];
    const renderCol = (label: string, items: [string, string][]) => (
      <div>
        <div style={eyebrow}>{label}</div>
        {items.map(([t, d]) => (
          <Link
            key={t}
            href="/use-cases"
            style={{
              display: "block",
              padding: "8px 10px",
              borderRadius: 6,
              textDecoration: "none",
              margin: "0 -10px",
            }}
          >
            <div style={{ fontFamily: fontSerif, fontSize: 17, color: T.fg, lineHeight: 1.2 }}>
              {t}
            </div>
            <div style={{ fontSize: 11.5, color: T.fg2, marginTop: 1 }}>{d}</div>
          </Link>
        ))}
      </div>
    );
    return (
      <div style={wrap}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {renderCol("按角色", roles)}
          {renderCol("按场景", scenes)}
        </div>
      </div>
    );
  }

  if (kind === "pricing") {
    const tiers: [string, string, string, string][] = [
      ["Starter", "免费", "5 个 Agent · 月 50 次查询", T.fg3],
      ["Team", "¥ 4,800 / 席 / 月", "全部 Agent · 立项报告 · DEF 接入", T.brand],
      ["Enterprise", "面议", "AIDD 流水线 · 私有部署 · SSO", T.accent2],
    ];
    return (
      <div style={{ ...wrap, minWidth: 480 }}>
        <div style={eyebrow}>三档定价</div>
        {tiers.map(([n, p, d, c]) => (
          <Link
            key={n}
            href="/pricing"
            style={{
              display: "grid",
              gridTemplateColumns: "110px 1fr auto",
              gap: 16,
              alignItems: "center",
              padding: "12px 10px",
              borderRadius: 8,
              textDecoration: "none",
              borderTop: `1px dashed ${T.border}`,
            }}
          >
            <div style={{ fontFamily: fontSerif, fontSize: 18, color: T.fg }}>{n}</div>
            <div>
              <div style={{ fontFamily: fontMono, fontSize: 12.5, color: c, fontWeight: 700 }}>
                {p}
              </div>
              <div style={{ fontSize: 11.5, color: T.fg2, marginTop: 2 }}>{d}</div>
            </div>
            <span style={{ color: T.fg3, fontSize: 14 }}>→</span>
          </Link>
        ))}
        <Link
          href="/pricing"
          style={{
            display: "block",
            marginTop: 14,
            padding: "10px 12px",
            borderRadius: 6,
            background: T.fg,
            color: T.bg,
            textAlign: "center",
            fontSize: 12,
            fontWeight: 600,
            textDecoration: "none",
            fontFamily: fontSans,
          }}
        >
          查看完整定价 →
        </Link>
      </div>
    );
  }

  // resources
  const releases: [string, string, string | null][] = [
    ["v0.9.2", "AIDD 流水线 GA · 2026.04.26", "NEW"],
    ["v0.9.1", "DEF 痛点引擎公测", null],
    ["v0.9.0", "BD GO 多 Agent 协作", null],
    ["所有版本", "Release Notes →", null],
  ];
  const blog: [string, string][] = [
    ["从 BD 到立项的 4 小时", "工程实践"],
    ["DEF 是什么 · 设计原理", "产品思考"],
    ["AIDD 流水线技术白皮书", "技术博客"],
    ["API 文档", "Developer"],
  ];
  return (
    <div style={wrap}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <div>
          <div style={eyebrow}>更新</div>
          {releases.map(([v, d, badge]) => (
            <Link
              key={v}
              href="/blog"
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 10,
                padding: "7px 10px",
                borderRadius: 6,
                textDecoration: "none",
                margin: "0 -10px",
              }}
            >
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 11,
                  color: T.brand,
                  fontWeight: 700,
                  minWidth: 48,
                }}
              >
                {v}
              </span>
              <span style={{ fontSize: 13, color: T.fg2, flex: 1 }}>{d}</span>
              {badge && (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: ".08em",
                    padding: "2px 6px",
                    borderRadius: 3,
                    background: `${T.accent3}1A`,
                    color: T.accent3,
                  }}
                >
                  {badge}
                </span>
              )}
            </Link>
          ))}
        </div>
        <div>
          <div style={eyebrow}>博客 · 文档</div>
          {blog.map(([t, d]) => (
            <Link
              key={t}
              href="/blog"
              style={{
                display: "block",
                padding: "7px 10px",
                borderRadius: 6,
                textDecoration: "none",
                margin: "0 -10px",
              }}
            >
              <div style={{ fontSize: 13.5, color: T.fg, lineHeight: 1.3, fontWeight: 500 }}>
                {t}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: T.fg3,
                  marginTop: 1,
                  fontFamily: fontMono,
                  letterSpacing: ".04em",
                }}
              >
                {d}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

function Hero({ T, dark, ctaHref }: { T: Tokens; dark: boolean; ctaHref: string }) {
  return (
    <section
      style={{
        padding: "44px 64px 56px",
        borderBottom: `1px solid ${T.rule}`,
        position: "relative",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.05fr 1fr",
          gap: 56,
          alignItems: "start",
          maxWidth: 1820,
          margin: "0 auto",
        }}
      >
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "5px 14px 5px 8px",
              borderRadius: 999,
              color: T.fg2,
              border: `1px solid ${T.border}`,
              fontSize: 11,
              fontWeight: 500,
              letterSpacing: ".06em",
              fontFamily: fontMono,
              textTransform: "uppercase",
              marginBottom: 28,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: 999,
                background: T.accent3,
                boxShadow: `0 0 0 3px ${T.accent3}33`,
              }}
            />
            BD GO · DEF · AIDD&nbsp;<span style={{ color: T.fg3 }}>v0.9 内测</span>
          </div>

          <h1
            style={{
              fontFamily: fontSans,
              fontWeight: 700,
              margin: 0,
              color: T.fg,
              letterSpacing: "-0.02em",
            }}
          >
            <span
              style={{
                display: "block",
                fontSize: 32,
                lineHeight: 1.15,
                color: T.fg2,
                fontWeight: 500,
              }}
            >
              一句话，问出
            </span>
            <span
              style={{
                display: "block",
                fontSize: 88,
                lineHeight: 1,
                letterSpacing: "-0.03em",
                marginTop: 4,
                fontWeight: 800,
                fontSynthesis: "none",
                background: dark
                  ? `linear-gradient(180deg, ${T.fg} 0%, ${T.accent1} 100%)`
                  : `linear-gradient(180deg, ${T.brand} 0%, ${T.accent1} 100%)`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              立项决策
            </span>
            <span
              style={{
                display: "block",
                fontSize: 20,
                lineHeight: 1.3,
                marginTop: 12,
                color: T.fg3,
                fontWeight: 400,
              }}
            >
              —— 一份完整的立项报告。
            </span>
          </h1>

          <p
            style={{
              fontFamily: fontSans,
              fontSize: 15,
              lineHeight: 1.65,
              color: T.fg2,
              maxWidth: 560,
              marginTop: 24,
              marginBottom: 0,
              fontWeight: 400,
            }}
          >
            对话驱动的 BD 与 AI4S 协作平台。BD GO 抓情报，DEF 拆痛点，AIDD
            把分子、靶点、临床数据自动跑成一份立项报告。业内首个把 BD、生信、AI
            制药串起来的中文工作流。
          </p>

          <div style={{ display: "flex", gap: 12, marginTop: 24, alignItems: "center" }}>
            <Link
              href={ctaHref}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "15px 26px",
                borderRadius: 8,
                background: T.fg,
                color: T.bg,
                fontFamily: fontSans,
                fontSize: 14,
                fontWeight: 500,
                letterSpacing: ".01em",
                textDecoration: "none",
              }}
            >
              进入 BD GO 工作台
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M5 12h14M13 5l7 7-7 7" />
              </svg>
            </Link>
            <Link
              href="#story"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "15px 22px",
                borderRadius: 8,
                color: T.fg,
                fontFamily: fontSans,
                fontSize: 14,
                fontWeight: 500,
                letterSpacing: ".01em",
                textDecoration: "none",
                border: `1px solid ${T.borderStrong}`,
              }}
            >
              看 90 秒工作流
            </Link>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              marginTop: 72,
              borderTop: `1px solid ${T.border}`,
              paddingTop: 24,
            }}
          >
            {(
              [
                ["13", "家中国药企", "AACR 2026 已抓"],
                ["7", "类 Agent", "并行协作"],
                ["120s", "立项评分", "P50 时延"],
                ["3", "条产品线", "BD · DEF · AIDD"],
              ] as [string, string, string][]
            ).map(([n, l, s], i) => (
              <div
                key={i}
                style={{
                  paddingLeft: i === 0 ? 0 : 20,
                  borderLeft: i === 0 ? "none" : `1px solid ${T.border}`,
                }}
              >
                <div
                  style={{
                    fontFamily: fontSerif,
                    fontStyle: "italic",
                    fontSize: 52,
                    fontWeight: 400,
                    color: T.fg,
                    lineHeight: 1,
                    letterSpacing: "-0.03em",
                  }}
                >
                  {n}
                </div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10.5,
                    color: T.fg2,
                    marginTop: 12,
                    fontWeight: 500,
                    letterSpacing: ".06em",
                    textTransform: "uppercase",
                  }}
                >
                  {l}
                </div>
                <div style={{ fontSize: 11.5, color: T.fg3, marginTop: 4, fontFamily: fontSans }}>
                  {s}
                </div>
              </div>
            ))}
          </div>
        </div>

        <AgentTrace T={T} dark={dark} />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Agent trace (live terminal mock)
// ---------------------------------------------------------------------------

function AgentTrace({ T, dark }: { T: Tokens; dark: boolean }) {
  const steps = [
    {
      t: "00:01",
      agent: "bdgo.search",
      color: T.brand,
      msg: "AACR 2026 中国公司 CT 摘要",
      meta: "13 公司 · 24 摘要 · 来源已锁定",
      done: true,
    },
    {
      t: "00:14",
      agent: "def.extract_pains",
      color: "#A78BFA",
      msg: "从摘要中拆解未满足需求",
      meta: "提取出 8 个候选靶点 · 3 个差异化窗口",
      done: true,
    },
    {
      t: "00:38",
      agent: "aidd.score_targets",
      color: "#34D399",
      msg: "对候选靶点跑结构 + ADMET + IP",
      meta: "ROR1 评分 8.4 · CD79B 评分 6.2 · GPRC5D 7.9",
      done: true,
    },
    {
      t: "01:47",
      agent: "report.compose",
      color: "#F59E0B",
      msg: "生成立项 Portfolio v1",
      meta: "11 个文件 · 完整可追溯 · 已发送至飞书",
      done: false,
    },
  ];

  return (
    <div
      style={{
        background: dark ? T.codebg : "#0F172A",
        borderRadius: 16,
        padding: "24px 28px 28px",
        color: "#E2E8F0",
        fontFamily: fontMono,
        fontSize: 13,
        lineHeight: 1.5,
        boxShadow: dark ? "none" : "0 24px 60px rgba(15,23,42,.18)",
        border: `1px solid ${dark ? T.border : "rgba(255,255,255,.06)"}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 20,
          paddingBottom: 16,
          borderBottom: "1px solid rgba(255,255,255,.08)",
        }}
      >
        <span style={{ width: 11, height: 11, borderRadius: 999, background: "#FF5F57" }} />
        <span style={{ width: 11, height: 11, borderRadius: 999, background: "#FEBC2E" }} />
        <span style={{ width: 11, height: 11, borderRadius: 999, background: "#28C840" }} />
        <div
          style={{
            flex: 1,
            textAlign: "center",
            color: "#94A3B8",
            fontSize: 11,
            letterSpacing: ".05em",
          }}
        >
          BD GO &nbsp;·&nbsp; session_2026_04_26
        </div>
        <div
          style={{
            padding: "2px 8px",
            borderRadius: 4,
            background: "rgba(52,211,153,.16)",
            color: "#34D399",
            fontSize: 10,
            fontWeight: 700,
          }}
        >
          LIVE
        </div>
      </div>

      <div
        style={{
          background: "rgba(59,130,246,.1)",
          border: "1px solid rgba(59,130,246,.25)",
          borderRadius: 10,
          padding: "12px 14px",
          marginBottom: 22,
          fontSize: 13,
          lineHeight: 1.55,
          color: "#DBEAFE",
        }}
      >
        <div
          style={{
            fontSize: 10,
            color: "#93C5FD",
            marginBottom: 6,
            letterSpacing: ".08em",
            fontWeight: 700,
          }}
        >
          USER · 14:23
        </div>
        AACR 2026 上中国公司有什么值得关注的 CT 摘要？帮我评估一下 ROR1 的立项机会。
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {steps.map((s, i) => (
          <div key={i} style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
            <div
              style={{
                fontSize: 10,
                color: "#64748B",
                letterSpacing: ".04em",
                minWidth: 38,
                paddingTop: 4,
              }}
            >
              {s.t}
            </div>
            <div
              className={s.done ? "" : "bdgo-pulse"}
              style={{
                width: 8,
                height: 8,
                borderRadius: 999,
                marginTop: 7,
                background: s.done ? s.color : "transparent",
                border: `2px solid ${s.color}`,
                boxShadow: s.done ? "none" : `0 0 0 4px ${s.color}22`,
                animation: s.done ? "none" : "bdgo-pulse 1.4s ease-in-out infinite",
              }}
            />
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                <span style={{ color: s.color, fontWeight: 600, fontSize: 12 }}>{s.agent}</span>
                {s.done ? (
                  <span
                    style={{
                      fontSize: 9,
                      color: "#64748B",
                      padding: "1px 6px",
                      border: "1px solid #2A3450",
                      borderRadius: 3,
                    }}
                  >
                    DONE
                  </span>
                ) : (
                  <span
                    style={{
                      fontSize: 9,
                      color: "#FBBF24",
                      padding: "1px 6px",
                      background: "rgba(251,191,36,.12)",
                      border: "1px solid rgba(251,191,36,.3)",
                      borderRadius: 3,
                    }}
                  >
                    RUNNING…
                  </span>
                )}
              </div>
              <div style={{ color: "#CBD5E1", fontSize: 12.5 }}>{s.msg}</div>
              <div style={{ color: "#64748B", fontSize: 11, marginTop: 3 }}>{s.meta}</div>
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 22,
          padding: "12px 14px",
          background: "rgba(255,255,255,.03)",
          border: "1px solid rgba(255,255,255,.06)",
          borderRadius: 10,
        }}
      >
        <div
          style={{
            fontSize: 10,
            color: "#64748B",
            marginBottom: 8,
            letterSpacing: ".08em",
            fontWeight: 700,
          }}
        >
          PORTFOLIO PREVIEW
        </div>
        <div style={{ display: "flex", gap: 16, fontSize: 12 }}>
          {(
            [
              ["ROR1", "84", "#34D399"],
              ["CD79B", "62", "#FBBF24"],
              ["GPRC5D", "79", "#34D399"],
            ] as [string, string, string][]
          ).map(([k, v, c]) => (
            <div key={k} style={{ flex: 1 }}>
              <div style={{ color: "#94A3B8", fontSize: 10, marginBottom: 3 }}>{k}</div>
              <div style={{ color: c, fontWeight: 700, fontSize: 22, fontFamily: fontSerif }}>
                {v}
                <span style={{ color: "#475569", fontSize: 13, fontWeight: 400 }}>/100</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Story · Three acts
// ---------------------------------------------------------------------------

function Story({ T }: { T: Tokens }) {
  return (
    <section
      id="story"
      style={{
        padding: "120px 64px",
        background: T.bgAlt,
        borderBottom: `1px solid ${T.rule}`,
      }}
    >
      <div style={{ maxWidth: 1820, margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: 80,
            gap: 64,
          }}
        >
          <h2
            style={{
              fontFamily: fontSerif,
              fontWeight: 400,
              margin: 0,
              color: T.fg,
              maxWidth: 880,
            }}
          >
            <span
              style={{
                display: "block",
                fontSize: 28,
                lineHeight: 1.2,
                color: T.fg3,
                fontStyle: "italic",
                marginBottom: 8,
              }}
            >
              三条产品线，
            </span>
            <span
              style={{
                display: "block",
                fontSize: 112,
                lineHeight: 0.95,
                letterSpacing: "-0.035em",
              }}
            >
              串成一条
            </span>
            <span
              style={{
                display: "block",
                fontSize: 112,
                lineHeight: 0.95,
                letterSpacing: "-0.035em",
                fontStyle: "italic",
                color: T.brand,
              }}
            >
              立项流水线。
            </span>
          </h2>
          <div
            style={{ fontSize: 14, color: T.fg2, lineHeight: 1.7, maxWidth: 420, paddingTop: 12 }}
          >
            传统 BD 团队在 PPT、Excel、PubMed、CT.gov、PDB 之间手动来回；
            我们让三个产品互相喂数据，让你只看结论。
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 0,
            alignItems: "stretch",
            background: T.bgCard,
            borderRadius: 20,
            border: `1px solid ${T.border}`,
            overflow: "hidden",
          }}
        >
          <Act
            T={T}
            act="第一幕"
            tag="BD GO"
            tagColor={T.brand}
            title="对话驱动 · 拉数据"
            body="自然语言问出竞品/会议/交易/专利/管线情报。AACR、ASCO、JPM、SEC、专利局、CT.gov 全部接通。"
            bullets={[
              "「AACR 2026 中国公司 CT 摘要」",
              "「ROR1 全球管线 + 最新交易」",
              "「Hengrui Q3 BD 动向」",
            ]}
            output="结构化情报卡 + 可追溯引文"
          />
          <Act
            T={T}
            act="第二幕"
            tag="DEF"
            tagColor={T.accent2}
            title="痛点拆解 · 定方向"
            body="把 BD 拉来的情报喂给 DEF 痛点引擎，自动拆解未满足临床需求、治疗窗口、机制空白、可成药性。"
            bullets={[
              "未满足需求矩阵（适应症 × 机制）",
              "可成药靶点优先级排序",
              "差异化机会画像（vs. 竞品）",
            ]}
            output="痛点报告 + 候选靶点 ×N"
            divider
          />
          <Act
            T={T}
            act="第三幕"
            tag="AIDD"
            tagColor={T.accent3}
            title="AI 立项 · 出报告"
            body="把候选靶点丢进 AI Drug Discovery 流水线，自动跑结构、ADMET、可成药性、IP 可绕开性，输出立项打分。"
            bullets={["ESMFold 3D 结构预测", "ADMET / 可成药性评估", "竞争格局 + IP 自由度"]}
            output="立项 Portfolio + 综合评分"
            divider
          />
        </div>

        <div
          style={{
            marginTop: 32,
            padding: "20px 28px",
            background: T.bgCard,
            borderRadius: 14,
            border: `1px solid ${T.border}`,
            fontFamily: fontMono,
            fontSize: 12,
            color: T.fg2,
            display: "flex",
            alignItems: "center",
            gap: 14,
            flexWrap: "wrap",
          }}
        >
          <span style={{ color: T.fg3 }}>flow</span>
          <span style={{ color: T.brand, fontWeight: 600 }}>
            bdgo.search(&quot;AACR 2026&quot;)
          </span>
          <Arrow T={T} />
          <span style={{ color: T.accent2, fontWeight: 600 }}>def.extract_pains(report)</span>
          <Arrow T={T} />
          <span style={{ color: T.accent3, fontWeight: 600 }}>aidd.run_pipeline(targets[])</span>
          <Arrow T={T} />
          <span style={{ color: T.fg, fontWeight: 600 }}>portfolio.score()</span>
          <span
            style={{
              marginLeft: "auto",
              padding: "4px 10px",
              borderRadius: 6,
              background: T.brandSoft,
              color: T.brand,
              fontWeight: 600,
            }}
          >
            ~120s e2e
          </span>
        </div>
      </div>
    </section>
  );
}

function Act({
  T,
  act,
  tag,
  tagColor,
  title,
  body,
  bullets,
  output,
  divider,
}: {
  T: Tokens;
  act: string;
  tag: string;
  tagColor: string;
  title: string;
  body: string;
  bullets: string[];
  output: string;
  divider?: boolean;
}) {
  return (
    <div
      style={{
        padding: 48,
        borderLeft: divider ? `1px solid ${T.border}` : "none",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontFamily: fontMono,
          fontSize: 11,
          color: T.fg3,
          letterSpacing: ".12em",
          textTransform: "uppercase",
          fontWeight: 700,
          marginBottom: 24,
        }}
      >
        {act}
      </div>
      <div
        style={{
          display: "inline-flex",
          alignSelf: "flex-start",
          padding: "5px 11px",
          borderRadius: 6,
          background: `${tagColor}1A`,
          color: tagColor,
          fontFamily: fontMono,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: ".08em",
          marginBottom: 28,
        }}
      >
        {tag}
      </div>
      <h3
        style={{
          fontFamily: fontSerif,
          fontSize: 36,
          fontWeight: 400,
          lineHeight: 1.15,
          letterSpacing: "-0.02em",
          color: T.fg,
          margin: 0,
        }}
      >
        {title}
      </h3>
      <p style={{ fontSize: 14.5, color: T.fg2, lineHeight: 1.65, margin: "18px 0 0" }}>{body}</p>

      <div style={{ marginTop: 28, display: "flex", flexDirection: "column", gap: 8 }}>
        {bullets.map((b, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 12px",
              background: T.bgAlt,
              borderRadius: 6,
              fontFamily: fontMono,
              fontSize: 12,
              color: T.fg,
            }}
          >
            <span style={{ color: tagColor, fontWeight: 700 }}>›</span>
            {b}
          </div>
        ))}
      </div>

      <div style={{ marginTop: "auto", paddingTop: 32 }}>
        <div
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: T.fg3,
            letterSpacing: ".12em",
            textTransform: "uppercase",
            fontWeight: 700,
            marginBottom: 8,
          }}
        >
          输出
        </div>
        <div style={{ fontSize: 14, color: T.fg, fontWeight: 600 }}>{output}</div>
      </div>
    </div>
  );
}

function Arrow({ T }: { T: Tokens }) {
  return (
    <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
      <path
        d="M1 5h12M9 1l4 4-4 4"
        stroke={T.fg3}
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// AIDD highlight (dark slab in light theme)
// ---------------------------------------------------------------------------

function AIDDHighlight({ T, dark }: { T: Tokens; dark: boolean }) {
  return (
    <section
      style={{
        padding: "120px 64px",
        background: dark ? T.bgCard : "#0A0F1F",
        color: dark ? T.fg : "#F8FAFC",
      }}
    >
      <div style={{ maxWidth: 1820, margin: "0 auto" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1.2fr",
            gap: 96,
            alignItems: "start",
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "5px 11px",
                borderRadius: 999,
                background: "rgba(52,211,153,.16)",
                color: "#34D399",
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: ".08em",
                textTransform: "uppercase",
                marginBottom: 32,
                fontFamily: fontMono,
              }}
            >
              <span style={{ width: 5, height: 5, borderRadius: 999, background: "#34D399" }} />
              AIDD · AI4S 引擎
            </div>
            <h2
              style={{
                fontFamily: fontSerif,
                fontWeight: 400,
                margin: 0,
                color: dark ? T.fg : "#F8FAFC",
              }}
            >
              <span
                style={{
                  display: "block",
                  fontSize: 26,
                  lineHeight: 1.2,
                  color: dark ? T.fg3 : "#64748B",
                  fontStyle: "italic",
                  marginBottom: 8,
                }}
              >
                立项决策，不只是
              </span>
              <span
                style={{
                  display: "block",
                  fontSize: 144,
                  lineHeight: 0.92,
                  letterSpacing: "-0.04em",
                  fontStyle: "italic",
                  background: "linear-gradient(180deg, #34D399 0%, #22D3EE 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                看 PPT。
              </span>
            </h2>
            <p
              style={{
                fontSize: 17,
                lineHeight: 1.65,
                color: dark ? T.fg2 : "#94A3B8",
                marginTop: 32,
                maxWidth: 480,
              }}
            >
              AIDD 把每个候选靶点当成一条 AI4S 流水线跑： 抓 UniProt / PDB / CT.gov / Patent， 跑
              ESMFold、ESM2、可开发性、ADMET， 最后吐出一份 11 个文件的完整立项包。
            </p>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 32 }}>
              {[
                "ESMFold",
                "ESM2",
                "PDB",
                "UniProt",
                "CT.gov",
                "ADMET",
                "可开发性",
                "IP 自由度",
                "靶点反查",
                "适应症反查",
              ].map((t) => (
                <span
                  key={t}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 6,
                    background: "rgba(255,255,255,.06)",
                    border: "1px solid rgba(255,255,255,.1)",
                    color: dark ? T.fg2 : "#CBD5E1",
                    fontFamily: fontMono,
                    fontSize: 12,
                  }}
                >
                  {t}
                </span>
              ))}
            </div>
          </div>

          <AIDDPipeline />
        </div>
      </div>
    </section>
  );
}

function AIDDPipeline() {
  const rows: [string, string, string, string, string][] = [
    ["00", "antigen_uniprot", "UniProt 抗原信息", "P52803", "12kb"],
    ["01", "antigen_sequence", "FASTA 序列", "ROR1_HUMAN", "1.2kb"],
    ["02", "pdb_complexes", "PDB 抗体复合物", "6BA5, 6BAJ", "2 hits"],
    ["03", "therapeutic_abs", "已知治疗性抗体", "Cirmtuzumab + 4", "5 rows"],
    ["04", "antibody_trials", "临床试验", "NCT04686305 + 11", "12 trials"],
    ["05", "developability", "可开发性评估", "Score 0.84 · GREEN", "18kb"],
    ["06", "esmfold_structure", "ESMFold 3D 结构", "pLDDT 81.4", "PDB"],
    ["07", "esmfold_report", "结构预测报告", "高置信度区域 78%", "MD"],
    ["08", "antibody_ip", "IP & 竞争情报", "可绕开 · 7 项核心专利", "MD"],
    ["09", "esm2_mutations", "突变效应预测", "Hot-spot ×6", "CSV"],
    ["10", "final_report", "综合评估报告", "立项打分 84/100", "MD"],
  ];
  return (
    <div
      style={{
        background: "#0F1525",
        border: "1px solid rgba(255,255,255,.08)",
        borderRadius: 16,
        padding: 32,
        color: "#E2E8F0",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
          paddingBottom: 20,
          borderBottom: "1px solid rgba(255,255,255,.08)",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: "#64748B",
              letterSpacing: ".12em",
              textTransform: "uppercase",
              fontWeight: 700,
            }}
          >
            RUN PIPELINE
          </div>
          <div
            style={{
              fontFamily: fontSerif,
              fontSize: 28,
              fontWeight: 400,
              color: "#F8FAFC",
              marginTop: 6,
              letterSpacing: "-0.02em",
            }}
          >
            ROR1 · 抗体立项
          </div>
        </div>
        <div
          style={{
            padding: "6px 12px",
            borderRadius: 999,
            background: "rgba(52,211,153,.16)",
            color: "#34D399",
            fontFamily: fontMono,
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          ● COMPLETE · 142s
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {rows.map(([n, name, desc, val], i) => (
          <div
            key={i}
            style={{
              display: "grid",
              gridTemplateColumns: "32px 1fr 1.2fr auto",
              gap: 14,
              alignItems: "center",
              padding: "11px 0",
              borderBottom: i < rows.length - 1 ? "1px solid rgba(255,255,255,.04)" : "none",
              fontSize: 12.5,
              fontFamily: fontMono,
            }}
          >
            <div style={{ color: "#475569", fontSize: 11, fontWeight: 700 }}>{n}</div>
            <div style={{ color: "#60A5FA" }}>{name}</div>
            <div style={{ color: "#CBD5E1" }}>{desc}</div>
            <div
              style={{
                color: "#34D399",
                fontWeight: 600,
                padding: "2px 8px",
                background: "rgba(52,211,153,.08)",
                borderRadius: 4,
                fontSize: 11,
              }}
            >
              {val}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 24,
          padding: "16px 18px",
          background: "linear-gradient(135deg, rgba(52,211,153,.12) 0%, rgba(34,211,238,.08) 100%)",
          border: "1px solid rgba(52,211,153,.2)",
          borderRadius: 10,
          display: "flex",
          alignItems: "center",
          gap: 14,
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: "rgba(52,211,153,.2)",
            color: "#34D399",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: fontSerif,
            fontSize: 22,
            fontWeight: 700,
          }}
        >
          ★
        </div>
        <div style={{ flex: 1 }}>
          <div
            style={{
              color: "#34D399",
              fontSize: 12,
              fontWeight: 700,
              fontFamily: fontMono,
              letterSpacing: ".08em",
            }}
          >
            FINAL SCORE
          </div>
          <div style={{ color: "#F8FAFC", fontSize: 14, marginTop: 2 }}>
            建议立项 · 差异化窗口明确 · IP 自由度高
          </div>
        </div>
        <div style={{ fontFamily: fontSerif, fontSize: 36, fontWeight: 700, color: "#34D399" }}>
          84<span style={{ color: "#475569", fontSize: 18, fontWeight: 400 }}>/100</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DEF Pain Points
// ---------------------------------------------------------------------------

function DEFSection({ T, dark }: { T: Tokens; dark: boolean }) {
  return (
    <section style={{ padding: "120px 64px", background: T.bg }}>
      <div style={{ maxWidth: 1820, margin: "0 auto" }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "5px 11px",
            borderRadius: 999,
            background: dark ? "rgba(167,139,250,.16)" : "rgba(124,58,237,.1)",
            color: T.accent2,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: ".08em",
            textTransform: "uppercase",
            marginBottom: 28,
            fontFamily: fontMono,
          }}
        >
          DEF · 痛点引擎
        </div>
        <h2
          style={{ fontFamily: fontSerif, fontWeight: 400, margin: 0, color: T.fg, maxWidth: 1200 }}
        >
          <span
            style={{
              display: "block",
              fontSize: 26,
              lineHeight: 1.2,
              color: T.fg3,
              fontStyle: "italic",
              marginBottom: 12,
            }}
          >
            DEF 把 BD 拉到的&ldquo;杂音&rdquo;
          </span>
          <span
            style={{ display: "block", fontSize: 96, lineHeight: 0.95, letterSpacing: "-0.035em" }}
          >
            自动结构化成
          </span>
          <span
            style={{
              display: "block",
              fontSize: 96,
              lineHeight: 0.95,
              letterSpacing: "-0.035em",
              fontStyle: "italic",
              color: T.accent2,
            }}
          >
            立项假设。
          </span>
        </h2>
        <p style={{ fontSize: 16, color: T.fg2, lineHeight: 1.6, marginTop: 24, maxWidth: 720 }}>
          Disease · Endpoint · Frontier ——
          把疾病、终点、技术前沿三者交叉切片，找出还没被对手占住的窗口。
        </p>

        <div
          style={{ marginTop: 64, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}
        >
          <PainCard
            T={T}
            tag="DISEASE"
            tagColor={T.brand}
            title="r/r DLBCL"
            meta="3L+ · 弥漫大 B 细胞淋巴瘤"
            rows={[
              ["未满足需求", "ORR < 40%", "严重"],
              ["在研管线", "12 条", "拥挤"],
              ["最新交易", "$280M", "Roche/Adagene"],
              ["DEF 评分", "6.4 / 10", "中等机会"],
            ]}
          />
          <PainCard
            T={T}
            tag="ENDPOINT"
            tagColor={T.accent1}
            title="HR+/HER2-low mBC"
            meta="二线 · TROP2 / HER2 low"
            rows={[
              ["未满足需求", "PFS 6.5m", "可改善"],
              ["在研管线", "5 条 ADC", "适中"],
              ["最新交易", "$650M", "Daiichi/AZ"],
              ["DEF 评分", "8.2 / 10", "高机会"],
            ]}
            highlight
          />
          <PainCard
            T={T}
            tag="FRONTIER"
            tagColor={T.accent3}
            title="GPCR × ADC"
            meta="新机制 · 跨膜小分子靶向"
            rows={[
              ["未满足需求", "—", "概念前沿"],
              ["在研管线", "2 条", "稀缺"],
              ["最新交易", "Pre-clinical", "无可比"],
              ["DEF 评分", "7.5 / 10", "差异化"],
            ]}
          />
        </div>
      </div>
    </section>
  );
}

function PainCard({
  T,
  tag,
  tagColor,
  title,
  meta,
  rows,
  highlight,
}: {
  T: Tokens;
  tag: string;
  tagColor: string;
  title: string;
  meta: string;
  rows: [string, string, string][];
  highlight?: boolean;
}) {
  return (
    <div
      style={{
        background: T.bgCard,
        border: `1px solid ${highlight ? tagColor : T.border}`,
        borderRadius: 14,
        padding: 28,
        boxShadow: highlight ? `0 0 0 1px ${tagColor}30, 0 12px 32px ${tagColor}1A` : "none",
        position: "relative",
      }}
    >
      {highlight && (
        <div
          style={{
            position: "absolute",
            top: -12,
            right: 20,
            padding: "4px 10px",
            borderRadius: 999,
            background: tagColor,
            color: "#fff",
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: ".08em",
          }}
        >
          RECOMMENDED
        </div>
      )}
      <div
        style={{
          display: "inline-flex",
          padding: "4px 9px",
          borderRadius: 4,
          background: `${tagColor}1A`,
          color: tagColor,
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: ".1em",
          marginBottom: 16,
          fontFamily: fontMono,
        }}
      >
        {tag}
      </div>
      <h4
        style={{
          fontFamily: fontSerif,
          fontSize: 28,
          fontWeight: 400,
          lineHeight: 1.15,
          letterSpacing: "-0.02em",
          color: T.fg,
          margin: 0,
        }}
      >
        {title}
      </h4>
      <div style={{ fontSize: 12.5, color: T.fg3, marginTop: 6, marginBottom: 24 }}>{meta}</div>
      <div style={{ borderTop: `1px solid ${T.border}` }}>
        {rows.map(([k, v, badge], i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "13px 0",
              borderBottom: i < rows.length - 1 ? `1px solid ${T.border}` : "none",
              fontSize: 13,
            }}
          >
            <span style={{ color: T.fg3 }}>{k}</span>
            <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <span style={{ color: T.fg, fontWeight: 600 }}>{v}</span>
              <span
                style={{
                  fontSize: 11,
                  color: T.fg2,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: T.bgAlt,
                  border: `1px solid ${T.border}`,
                }}
              >
                {badge}
              </span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Products
// ---------------------------------------------------------------------------

function Products({ T, ctaHref }: { T: Tokens; ctaHref: string }) {
  return (
    <section
      style={{
        padding: "120px 64px",
        background: T.bgAlt,
        borderTop: `1px solid ${T.rule}`,
        borderBottom: `1px solid ${T.rule}`,
      }}
    >
      <div style={{ maxWidth: 1820, margin: "0 auto" }}>
        <h2
          style={{
            fontFamily: fontSerif,
            fontSize: 76,
            fontWeight: 400,
            lineHeight: 1.05,
            letterSpacing: "-0.02em",
            margin: "0 0 72px",
            color: T.fg,
          }}
        >
          三条产品线，<span style={{ color: T.fg3 }}>同一个工作台</span>。
        </h2>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24 }}>
          <ProductCard
            T={T}
            tag="BD GO"
            color={T.brand}
            title="对话式 BD 工作台"
            desc="自然语言抓情报、做尽调、写竞品分析、一键出 BD 报告。"
            features={["多 Agent 协作", "AACR/ASCO/JPM 全接", "立项一键导出"]}
            cta="进入 BD GO →"
            href={ctaHref}
          />
          <ProductCard
            T={T}
            tag="DEF"
            color={T.accent2}
            title="痛点 · 立项引擎"
            desc="疾病 × 终点 × 前沿三维交叉，自动找出未满足的立项窗口。"
            features={["未满足需求矩阵", "靶点优先级", "差异化机会画像"]}
            cta="进入 DEF →"
            href="/features"
          />
          <ProductCard
            T={T}
            tag="AIDD"
            color={T.accent3}
            title="AI Drug Discovery"
            desc="结构、ADMET、可成药性、IP 一条流水线跑完，输出立项打分。"
            features={["ESMFold/ESM2", "靶点 ↔ 适应症反查", "Portfolio 对比"]}
            cta="进入 AIDD →"
            href="/features"
          />
        </div>
      </div>
    </section>
  );
}

function ProductCard({
  T,
  tag,
  color,
  title,
  desc,
  features,
  cta,
  href,
}: {
  T: Tokens;
  tag: string;
  color: string;
  title: string;
  desc: string;
  features: string[];
  cta: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      style={{
        display: "block",
        textDecoration: "none",
        background: T.bgCard,
        borderRadius: 18,
        padding: 36,
        border: `1px solid ${T.border}`,
        position: "relative",
        overflow: "hidden",
        transition: "transform .2s, box-shadow .2s",
      }}
    >
      <div
        style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: color }}
      />
      <div
        style={{
          display: "inline-flex",
          padding: "5px 10px",
          borderRadius: 5,
          background: `${color}1A`,
          color: color,
          fontFamily: fontMono,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: ".08em",
          marginBottom: 20,
          marginTop: 8,
        }}
      >
        {tag}
      </div>
      <h3
        style={{
          fontFamily: fontSerif,
          fontSize: 28,
          fontWeight: 400,
          lineHeight: 1.2,
          letterSpacing: "-0.02em",
          color: T.fg,
          margin: 0,
        }}
      >
        {title}
      </h3>
      <p style={{ fontSize: 14, color: T.fg2, lineHeight: 1.6, margin: "12px 0 0" }}>{desc}</p>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
          marginTop: 24,
          paddingTop: 24,
          borderTop: `1px solid ${T.border}`,
        }}
      >
        {features.map((f) => (
          <div
            key={f}
            style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: T.fg2 }}
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke={color}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M5 12l5 5 9-11" />
            </svg>
            {f}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 28, fontSize: 13.5, fontWeight: 600, color: color }}>{cta}</div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// AI4S Lab template
// ---------------------------------------------------------------------------

function AI4SLab({ T, dark }: { T: Tokens; dark: boolean }) {
  const projects = [
    {
      kind: "PIPELINE",
      kindColor: T.brand,
      title: "TCR-T 适应症反查",
      sub: "从 HLA-peptide 库反查适应症机会",
      tags: ["NetMHCpan", "TCGA"],
      status: "Beta",
    },
    {
      kind: "BENCHMARK",
      kindColor: T.accent2,
      title: "ADC payload 可成药性榜",
      sub: "23 个 payload 在 6 个维度的 head-to-head",
      tags: ["RDKit", "ADMET"],
      status: "Live",
    },
    {
      kind: "DATASET",
      kindColor: T.accent1,
      title: "中国 IND 全量数据集",
      sub: "2018-2026 · 8,400 条 · 周更",
      tags: ["NMPA", "CDE"],
      status: "Live",
    },
    {
      kind: "MODEL",
      kindColor: T.accent3,
      title: "BD-LM · BD 领域语言模型",
      sub: "在交易 / 管线 / 财报上 finetune",
      tags: ["7B", "Qwen2"],
      status: "Preprint",
    },
    {
      kind: "PIPELINE",
      kindColor: T.brand,
      title: "GPCR × ADC 前沿扫描",
      sub: "把 GPCR 全家与 ADC payload 配对评估",
      tags: ["AlphaFold", "RDKit"],
      status: "WIP",
    },
    {
      kind: "TEMPLATE",
      kindColor: "#D97706",
      title: "[ 你的项目 ]",
      sub: "[ 一句话描述这个 pipeline 在做什么 ]",
      tags: ["[tag]", "[tag]"],
      status: "WIP",
      placeholder: true,
    },
  ];

  return (
    <section
      id="ai4s"
      style={{ padding: "120px 64px", background: T.bg, borderTop: `1px solid ${T.rule}` }}
    >
      <div style={{ maxWidth: 1820, margin: "0 auto" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.1fr 1fr",
            gap: 96,
            alignItems: "end",
            marginBottom: 80,
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "5px 11px",
                borderRadius: 999,
                background: dark ? "rgba(34,211,238,.12)" : "rgba(8,145,178,.1)",
                color: T.accent1,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: ".12em",
                textTransform: "uppercase",
                marginBottom: 28,
                fontFamily: fontMono,
              }}
            >
              <span style={{ width: 5, height: 5, borderRadius: 999, background: T.accent1 }} />
              AI4S 实验室
            </div>
            <h2
              style={{
                fontFamily: fontSerif,
                fontSize: 80,
                fontWeight: 400,
                lineHeight: 1.0,
                letterSpacing: "-0.02em",
                margin: 0,
                color: T.fg,
              }}
            >
              把生信、AI 制药与药物经济学
              <br />
              <span style={{ fontStyle: "italic", color: T.accent1 }}>做成可复用的研究流水线</span>
              。
            </h2>
          </div>
          <div>
            <p style={{ fontSize: 16, lineHeight: 1.7, color: T.fg2, margin: 0, maxWidth: 520 }}>
              AI4S 实验室是 BD Go 的研究端开放平台。我们把内部跑通的 AI4S 工作流、benchmark 和
              reproducible notebook 公开出来，给生信工程师、临床研究员、AI 制药团队当起点。
            </p>
            <div style={{ marginTop: 28, display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Link
                href="/blog"
                style={{
                  padding: "12px 22px",
                  borderRadius: 8,
                  background: T.fg,
                  color: T.bg,
                  textDecoration: "none",
                  fontSize: 13,
                  fontWeight: 600,
                  fontFamily: fontSans,
                }}
              >
                浏览全部 Notebook →
              </Link>
              <Link
                href="/contact"
                style={{
                  padding: "12px 22px",
                  borderRadius: 8,
                  color: T.fg,
                  textDecoration: "none",
                  fontSize: 13,
                  fontWeight: 500,
                  border: `1px solid ${T.borderStrong}`,
                  fontFamily: fontSans,
                }}
              >
                提交你的 pipeline
              </Link>
            </div>
          </div>
        </div>

        {/* Hero project card */}
        <div
          style={{
            background: T.bgCard,
            border: `1px solid ${T.border}`,
            borderRadius: 18,
            padding: 40,
            marginBottom: 32,
            display: "grid",
            gridTemplateColumns: "1.4fr 1fr",
            gap: 56,
            alignItems: "stretch",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: 3,
              background: `linear-gradient(90deg, ${T.brand} 0%, ${T.accent1} 50%, ${T.accent3} 100%)`,
            }}
          />
          <div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 20 }}>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: ".1em",
                  padding: "4px 9px",
                  borderRadius: 4,
                  background: T.accent3,
                  color: "#fff",
                }}
              >
                ● LIVE
              </span>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: ".1em",
                  padding: "4px 9px",
                  borderRadius: 4,
                  background: T.bgAlt,
                  color: T.fg2,
                  border: `1px solid ${T.border}`,
                }}
              >
                FLAGSHIP
              </span>
            </div>
            <h3
              style={{
                fontFamily: fontSerif,
                fontSize: 44,
                fontWeight: 400,
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                margin: 0,
                color: T.fg,
              }}
            >
              ROR1 抗体立项 · 全流程 reproducible
            </h3>
            <div
              style={{
                fontSize: 16,
                color: T.fg2,
                marginTop: 12,
                fontStyle: "italic",
                fontFamily: fontSerif,
              }}
            >
              ESMFold + ESM2 + 可开发性 + IP 一键跑完
            </div>
            <p
              style={{
                fontSize: 14.5,
                lineHeight: 1.65,
                color: T.fg2,
                marginTop: 24,
                maxWidth: 520,
              }}
            >
              把一个候选抗原从 UniProt 拉到立项打分的完整 pipeline。11
              个产物文件，全部可追溯。Notebook 打开即跑。
            </p>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 24 }}>
              {["ESMFold", "ESM2", "PDB", "UniProt", "可开发性", "ADMET"].map((c) => (
                <span
                  key={c}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 4,
                    background: T.bgAlt,
                    color: T.fg2,
                    fontFamily: fontMono,
                    fontSize: 11,
                    border: `1px solid ${T.border}`,
                  }}
                >
                  {c}
                </span>
              ))}
            </div>
            <Link
              href="/blog"
              style={{
                display: "inline-flex",
                marginTop: 28,
                gap: 8,
                alignItems: "center",
                color: T.fg,
                fontWeight: 600,
                fontSize: 14,
                textDecoration: "none",
                paddingBottom: 4,
                borderBottom: `1.5px solid ${T.fg}`,
              }}
            >
              查看 Notebook →
            </Link>
          </div>

          <div
            style={{
              background: T.bgAlt,
              borderRadius: 12,
              padding: 28,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: T.fg3,
                letterSpacing: ".12em",
                fontWeight: 700,
                marginBottom: 18,
                textTransform: "uppercase",
              }}
            >
              Pipeline 指标
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              {(
                [
                  ["运行时长", "142s"],
                  ["产物文件", "11"],
                  ["立项分", "84/100"],
                  ["复现性", "100%"],
                ] as [string, string][]
              ).map(([k, v]) => (
                <div key={k}>
                  <div style={{ fontSize: 12, color: T.fg3, marginBottom: 4 }}>{k}</div>
                  <div
                    style={{
                      fontFamily: fontSerif,
                      fontSize: 36,
                      color: T.fg,
                      letterSpacing: "-0.02em",
                      lineHeight: 1,
                    }}
                  >
                    {v}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Project library */}
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginTop: 80,
            marginBottom: 24,
            gap: 24,
          }}
        >
          <h3
            style={{
              fontFamily: fontSerif,
              fontSize: 36,
              fontWeight: 400,
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
              margin: 0,
              color: T.fg,
            }}
          >
            项目库 <span style={{ color: T.fg3, fontStyle: "italic" }}>· 全部公开</span>
          </h3>
          <Link
            href="/blog"
            style={{
              fontSize: 13,
              color: T.fg2,
              textDecoration: "none",
              fontFamily: fontSans,
              display: "inline-flex",
              gap: 4,
              alignItems: "center",
            }}
          >
            查看全部 ({projects.length}+) →
          </Link>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {projects.map((p, i) => (
            <Link
              key={i}
              href="/blog"
              style={{
                display: "block",
                textDecoration: "none",
                background: p.placeholder ? "transparent" : T.bgCard,
                border: p.placeholder ? `1.5px dashed ${T.borderStrong}` : `1px solid ${T.border}`,
                borderRadius: 12,
                padding: 24,
                transition: "transform .15s, box-shadow .15s",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 16,
                }}
              >
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: ".1em",
                    padding: "3px 8px",
                    borderRadius: 3,
                    background: `${p.kindColor}1A`,
                    color: p.kindColor,
                  }}
                >
                  {p.kind}
                </span>
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: T.fg3,
                    letterSpacing: ".06em",
                  }}
                >
                  ● {p.status}
                </span>
              </div>
              <div
                style={{
                  fontFamily: fontSerif,
                  fontSize: 22,
                  fontWeight: 400,
                  lineHeight: 1.2,
                  letterSpacing: "-0.01em",
                  color: p.placeholder ? T.fg3 : T.fg,
                  fontStyle: p.placeholder ? "italic" : "normal",
                }}
              >
                {p.title}
              </div>
              <div
                style={{
                  fontSize: 13,
                  color: T.fg2,
                  marginTop: 6,
                  lineHeight: 1.5,
                  fontStyle: p.placeholder ? "italic" : "normal",
                }}
              >
                {p.sub}
              </div>
              <div style={{ display: "flex", gap: 6, marginTop: 16, flexWrap: "wrap" }}>
                {p.tags.map((t) => (
                  <span
                    key={t}
                    style={{
                      fontFamily: fontMono,
                      fontSize: 10.5,
                      color: T.fg3,
                      padding: "2px 7px",
                      borderRadius: 3,
                      border: `1px solid ${T.border}`,
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Footer CTA + meta
// ---------------------------------------------------------------------------

function FooterCTA({ T, dark, ctaHref }: { T: Tokens; dark: boolean; ctaHref: string }) {
  return (
    <section style={{ padding: "120px 64px", background: T.bg, textAlign: "center" }}>
      <div
        style={{
          fontFamily: fontMono,
          fontSize: 11,
          color: T.fg3,
          letterSpacing: ".18em",
          textTransform: "uppercase",
          fontWeight: 500,
          marginBottom: 32,
        }}
      >
        · Get started ·
      </div>
      <h2
        style={{
          fontFamily: fontSerif,
          fontWeight: 400,
          margin: 0,
          color: T.fg,
          maxWidth: 1400,
          marginInline: "auto",
        }}
      >
        <span
          style={{
            display: "block",
            fontSize: 56,
            lineHeight: 1.05,
            letterSpacing: "-0.02em",
            color: T.fg2,
          }}
        >
          下一份立项报告，
        </span>
        <span
          style={{
            display: "block",
            fontSize: 168,
            lineHeight: 0.95,
            letterSpacing: "-0.04em",
            fontStyle: "italic",
            marginTop: 4,
            background: dark
              ? `linear-gradient(180deg, ${T.fg} 0%, ${T.accent1} 100%)`
              : `linear-gradient(180deg, ${T.brand} 0%, ${T.accent1} 100%)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          从一句话开始。
        </span>
      </h2>
      <div
        style={{
          display: "flex",
          gap: 14,
          justifyContent: "center",
          marginTop: 56,
          flexWrap: "wrap",
        }}
      >
        <Link
          href={ctaHref}
          style={{
            padding: "18px 36px",
            borderRadius: 10,
            background: T.brand,
            color: "#fff",
            fontSize: 16,
            fontWeight: 600,
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          进入 BD GO
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M5 12h14M13 5l7 7-7 7" />
          </svg>
        </Link>
        <Link
          href="/contact"
          style={{
            padding: "18px 36px",
            borderRadius: 10,
            color: T.fg,
            border: `1px solid ${T.borderStrong}`,
            fontSize: 16,
            fontWeight: 500,
            textDecoration: "none",
          }}
        >
          预约演示
        </Link>
      </div>
    </section>
  );
}

function FooterMeta({ T }: { T: Tokens }) {
  return (
    <footer
      style={{
        padding: "32px 64px",
        background: T.bg,
        borderTop: `1px solid ${T.border}`,
      }}
    >
      <div
        style={{
          maxWidth: 1820,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr 1fr",
          gap: 48,
          paddingBottom: 32,
          borderBottom: `1px solid ${T.rule}`,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <BDGoLogo size={24} T={T} />
            <span
              style={{
                fontFamily: fontSans,
                fontWeight: 600,
                fontSize: 14,
                letterSpacing: ".08em",
                color: T.fg,
                textTransform: "uppercase",
              }}
            >
              BD GO
            </span>
          </div>
          <p style={{ fontSize: 13, lineHeight: 1.7, color: T.fg2, maxWidth: 320, margin: 0 }}>
            对话驱动的 BD 与 AI4S 协作平台 — BD GO 抓情报，DEF 拆痛点，AIDD 出立项。
          </p>
        </div>
        {[
          {
            title: "产品",
            links: [
              { label: "功能特性", href: "/features" },
              { label: "定价", href: "/pricing" },
              { label: "使用案例", href: "/use-cases" },
              { label: "使用文档", href: "/docs" },
            ],
          },
          {
            title: "公司",
            links: [
              { label: "关于我们", href: "/about" },
              { label: "博客", href: "/blog" },
              { label: "联系我们", href: "/contact" },
            ],
          },
          {
            title: "法律",
            links: [
              { label: "隐私政策", href: "/privacy" },
              { label: "服务条款", href: "/terms" },
              { label: "安全合规", href: "/security" },
            ],
          },
        ].map((col) => (
          <div key={col.title}>
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: ".12em",
                color: T.fg3,
                marginBottom: 16,
              }}
            >
              {col.title}
            </div>
            {col.links.map((l) => (
              <div key={l.label} style={{ marginBottom: 10 }}>
                <Link href={l.href} style={{ fontSize: 13, color: T.fg2, textDecoration: "none" }}>
                  {l.label}
                </Link>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div
        style={{
          maxWidth: 1820,
          margin: "0 auto",
          paddingTop: 24,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 12,
          color: T.fg3,
          fontFamily: fontMono,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>© 2026 BD Go · Made for biopharma BD teams</div>
        <div>v0.9.2 · build 2026.04.26</div>
      </div>
    </footer>
  );
}
