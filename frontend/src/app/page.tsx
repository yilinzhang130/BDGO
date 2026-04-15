"use client";

import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const STATS = [
  { value: "10K+",  label: "生物医药企业" },
  { value: "50K+",  label: "管线资产" },
  { value: "100K+", label: "临床试验" },
  { value: "5K+",   label: "BD交易" },
];

const USE_CASES = [
  {
    color: "#2563EB",
    bg: "#DBEAFE",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
      </svg>
    ),
    title: "资产发现",
    desc: "精准定位符合治疗领域策略的潜在并购和许可标的",
  },
  {
    color: "#059669",
    bg: "#D1FAE5",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
    title: "竞争情报",
    desc: "实时追踪竞争对手管线进展与临床数据读出",
  },
  {
    color: "#7C3AED",
    bg: "#EDE9FE",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 9h18M9 21V9" />
      </svg>
    ),
    title: "尽职调查",
    desc: "一键生成包含临床、IP与交易数据的综合分析报告",
  },
];

const FEATURES = [
  { icon: "🤖", title: "AI对话引擎",     desc: "用中英文自然语言提问，即获得带引用来源的深度洞察" },
  { icon: "📊", title: "管线情报",       desc: "覆盖所有治疗领域的22,000+生物资产实时跟踪与竞争格局分析" },
  { icon: "📅", title: "催化剂日历",     desc: "随时掌握临床数据读出、监管决策与里程碑节点" },
  { icon: "🤝", title: "交易流分析",     desc: "结构化许可、M&A与合作交易数据，含条款、估值与战略逻辑" },
  { icon: "🏥", title: "临床深度拆解",   desc: "44,000+临床记录，涵盖终点、安全性、试验设计与头对头比较" },
  { icon: "📄", title: "自动化报告",     desc: "生成公司分析、买方画像、资产评估与rNPV模型，格式专业可直接分享" },
];

// ---------------------------------------------------------------------------
// Logo mark (inline SVG — no image dependency)
// ---------------------------------------------------------------------------

function NavLogo() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
      <svg width="32" height="32" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0 }}>
        <rect width="36" height="36" rx="9" fill="#1E3A8A" />
        <circle cx="11" cy="18" r="3.5" fill="white" />
        <line x1="15" y1="18" x2="22.5" y2="18" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M22 13 L29 18 L22 23 Z" fill="white" />
      </svg>
      <span style={{ fontSize: 16, fontWeight: 800, color: "#1E3A8A", letterSpacing: "-0.01em" }}>
        BD<span style={{ fontWeight: 500 }}> Go</span>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mock dashboard card (hero right side)
// ---------------------------------------------------------------------------

function HeroDashboardCard() {
  return (
    <div style={{
      background: "#fff", borderRadius: 16, border: "1px solid #E2E8F0",
      boxShadow: "0 20px 60px rgba(30,58,138,0.12)", padding: "20px 22px",
      width: 320, flexShrink: 0,
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#0F172A", marginBottom: 4 }}>管线情报</div>
      <div style={{ fontSize: 11, color: "#94A3B8", marginBottom: 16 }}>实时BD机会总览</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 18 }}>
        {[["活跃交易","156"],["公司","2.8K"],["资产","12K"]].map(([l, v]) => (
          <div key={l}>
            <div style={{ fontSize: 10, color: "#94A3B8", marginBottom: 2 }}>{l}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#1E3A8A" }}>{v}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 4, alignItems: "flex-end", marginBottom: 14 }}>
        {[40,60,45,75,55,80,65,90,70,85].map((h, i) => (
          <div key={i} style={{
            flex: 1, height: h * 0.7, borderRadius: 3,
            background: i >= 8 ? "#1E3A8A" : "#DBEAFE",
          }} />
        ))}
      </div>
      <div style={{ background: "#F0FDF4", border: "1px solid #BBF7D0", borderRadius: 10, padding: "10px 12px", display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 15 }}>✓</span>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#065F46" }}>AI分析完成</div>
          <div style={{ fontSize: 10, color: "#047857" }}>匹配度评分 87%</div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Landing Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const { user, loading } = useAuth();
  const ctaHref = user ? "/chat" : "/login";

  return (
    <div style={{ minHeight: "100vh", background: "#fff", color: "#0F172A", fontFamily: '"Inter", -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif' }}>

      {/* ─── Navbar ─── */}
      <nav style={{ position: "sticky", top: 0, zIndex: 100, background: "rgba(255,255,255,0.92)", backdropFilter: "blur(12px)", borderBottom: "1px solid #F1F5F9" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto", padding: "0 32px", height: 60, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <NavLogo />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {!loading && (user ? (
              <Link href="/chat" style={btn.primary}>进入平台 →</Link>
            ) : (
              <>
                <Link href="/login" style={btn.ghost}>登录</Link>
                <Link href="/login" style={btn.primary}>免费试用 →</Link>
              </>
            ))}
          </div>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <section style={{ background: "#fff", padding: "80px 32px 96px", borderBottom: "1px solid #F1F5F9" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto", display: "flex", alignItems: "center", gap: 64, flexWrap: "wrap" }}>
          {/* Left */}
          <div style={{ flex: "1 1 420px", minWidth: 300 }}>
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 7,
              background: "#EEF2FF", border: "1px solid #C7D2FE",
              borderRadius: 999, padding: "6px 14px", marginBottom: 28,
            }}>
              <span style={{ fontSize: 13 }}>✨</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#3730A3", letterSpacing: "0.02em" }}>AI驱动的BD情报平台</span>
            </div>
            <h1 style={{ fontSize: 52, fontWeight: 800, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 10px", color: "#0F172A" }}>
              加速您的
            </h1>
            <h1 style={{ fontSize: 52, fontWeight: 800, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 24px", color: "#1E3A8A" }}>
              Biotech 交易
            </h1>
            <p style={{ fontSize: 17, lineHeight: 1.7, color: "#475569", margin: "0 0 36px", maxWidth: 460 }}>
              BD Go 是专为生物医药BD总监打造的AI情报平台——发现资产、分析合作机会、加速决策，覆盖中国及全球市场。
            </p>
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 36 }}>
              <Link href={ctaHref} style={btn.primaryLg}>免费开始使用 →</Link>
              <button style={btn.demoLg}>
                <span style={{ width: 30, height: 30, background: "#1E3A8A", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <svg width="10" height="12" viewBox="0 0 10 12" fill="white"><path d="M0 0l10 6-10 6z"/></svg>
                </span>
                观看演示
              </button>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ display: "flex" }}>
                {["#2563EB","#059669","#D97706","#7C3AED"].map((c,i) => (
                  <div key={i} style={{ width: 28, height: 28, borderRadius: "50%", background: c, border: "2px solid #fff", marginLeft: i ? -8 : 0, zIndex: 4-i, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#fff", fontWeight: 700 }}>
                    {["B","C","D","E"][i]}
                  </div>
                ))}
              </div>
              <span style={{ fontSize: 13, color: "#64748B", fontWeight: 500 }}>200+ BD团队正在使用</span>
            </div>
          </div>
          {/* Right */}
          <div style={{ flex: "1 1 320px", display: "flex", justifyContent: "center" }}>
            <div style={{ position: "relative" }}>
              <HeroDashboardCard />
              {/* Floating alert */}
              <div style={{
                position: "absolute", top: -18, right: -18,
                background: "#fff", border: "1px solid #E2E8F0",
                borderRadius: 12, padding: "10px 14px",
                boxShadow: "0 8px 24px rgba(0,0,0,0.1)",
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#22C55E", display: "inline-block" }} />
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#0F172A" }}>交易预警</div>
                  <div style={{ fontSize: 10, color: "#64748B" }}>发现新许可机会</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Stats ─── */}
      <section style={{ background: "#fff", borderTop: "1px solid #F1F5F9", borderBottom: "1px solid #F1F5F9" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto", padding: "40px 32px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0 }}>
          {STATS.map((s, i) => (
            <div key={s.label} style={{ textAlign: "center", padding: "8px 0", borderRight: i < 3 ? "1px solid #F1F5F9" : "none" }}>
              <div style={{ fontSize: 36, fontWeight: 800, color: "#1E3A8A", letterSpacing: "-0.02em", lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: 13, color: "#64748B", marginTop: 6, fontWeight: 500 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Use Cases ─── */}
      <section style={{ padding: "96px 32px" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 60 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#F59E0B", textTransform: "uppercase", marginBottom: 14 }}>使用场景</div>
            <h2 style={{ fontSize: 38, fontWeight: 800, letterSpacing: "-0.02em", margin: "0 0 14px", color: "#0F172A" }}>专为BD总监与交易撮合者打造</h2>
            <p style={{ fontSize: 16, color: "#64748B", maxWidth: 520, margin: "0 auto" }}>从资产筛查到合作评估，全面优化您的工作流程</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24 }}>
            {USE_CASES.map((uc) => (
              <div key={uc.title} style={{ background: "#fff", border: "1px solid #EEF2F7", borderRadius: 16, padding: "28px 28px 32px", boxShadow: "0 2px 12px rgba(15,23,42,0.04)", transition: "box-shadow 0.2s" }}>
                <div style={{ width: 52, height: 52, borderRadius: 14, background: uc.bg, display: "flex", alignItems: "center", justifyContent: "center", color: uc.color, marginBottom: 20 }}>
                  {uc.icon}
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 10px", color: "#0F172A" }}>{uc.title}</h3>
                <p style={{ fontSize: 14, lineHeight: 1.65, color: "#64748B", margin: 0 }}>{uc.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── AI Chat Section ─── */}
      <section style={{ background: "linear-gradient(135deg, #1E3A8A 0%, #2563EB 60%, #3B82F6 100%)", padding: "80px 32px" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto", display: "flex", gap: 64, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 380px", color: "#fff" }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#93C5FD", textTransform: "uppercase", marginBottom: 16 }}>AI驱动</div>
            <h2 style={{ fontSize: 34, fontWeight: 800, letterSpacing: "-0.02em", margin: "0 0 16px", lineHeight: 1.2 }}>
              复杂问题<br />即时解答
            </h2>
            <p style={{ fontSize: 15, lineHeight: 1.7, color: "#BFDBFE", margin: "0 0 28px", maxWidth: 400 }}>
              BD Go AI 跨越50,000+资产、临床试验、专利与交易数据进行分析，提供精准洞察与引用来源。
            </p>
            {["支持中英文自然语言提问","实时覆盖10,000+生物医药企业","自动报告附引用来源","基于历史记录的智能推荐"].map((t) => (
              <div key={t} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <div style={{ width: 18, height: 18, borderRadius: "50%", background: "rgba(255,255,255,0.2)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <svg width="10" height="8" viewBox="0 0 10 8" fill="none"><path d="M1 4l2.5 2.5L9 1" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </div>
                <span style={{ fontSize: 14, color: "#E0EFFE" }}>{t}</span>
              </div>
            ))}
          </div>
          <div style={{ flex: "1 1 340px" }}>
            <div style={{ background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 16, padding: "20px 22px", backdropFilter: "blur(8px)" }}>
              <div style={{ fontSize: 11, color: "#93C5FD", marginBottom: 14, fontWeight: 500 }}>示例查询：</div>
              <div style={{ fontSize: 14, color: "#BFDBFE", lineHeight: 1.65, marginBottom: 18, fontStyle: "italic" }}>
                "哪些中国肿瘤公司有处于Phase II的ADC资产，近期与MNC有合作，且在美国有布局？"
              </div>
              <div style={{ background: "rgba(255,255,255,0.12)", borderRadius: 10, padding: "12px 14px", display: "flex", alignItems: "center", gap: 8 }}>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="white"><path d="M8 1l1.76 3.57 3.94.57-2.85 2.78.67 3.9L8 10.36 4.48 12.32l.67-3.9L2.3 5.64l3.94-.57L8 1z"/></svg>
                <span style={{ fontSize: 12, color: "#E0EFFE", fontWeight: 500 }}>已找到 12 家匹配企业，正在生成分析报告…</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Platform Features ─── */}
      <section style={{ padding: "96px 32px", background: "#FAFBFF" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 60 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#2563EB", textTransform: "uppercase", marginBottom: 14 }}>平台功能</div>
            <h2 style={{ fontSize: 38, fontWeight: 800, letterSpacing: "-0.02em", margin: "0 0 14px" }}>BD情报，一站解决</h2>
            <p style={{ fontSize: 16, color: "#64748B", maxWidth: 480, margin: "0 auto" }}>
              从机会发现到交易落地，BD Go 提供全链路工具帮助团队更快行动
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {FEATURES.map((f) => (
              <div key={f.title} style={{ background: "#fff", border: "1px solid #EEF2F7", borderRadius: 14, padding: "24px 22px", boxShadow: "0 1px 4px rgba(15,23,42,0.04)" }}>
                <div style={{ fontSize: 26, marginBottom: 12 }}>{f.icon}</div>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 8px", color: "#0F172A" }}>{f.title}</h3>
                <p style={{ fontSize: 13, lineHeight: 1.65, color: "#64748B", margin: 0 }}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Product Ecosystem ─── */}
      <section style={{ padding: "96px 32px", background: "#fff", borderTop: "1px solid #F1F5F9" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#059669", textTransform: "uppercase", marginBottom: 14 }}>产品生态</div>
            <h2 style={{ fontSize: 38, fontWeight: 800, letterSpacing: "-0.02em", margin: "0 0 14px", color: "#0F172A" }}>覆盖医药研发全链路</h2>
            <p style={{ fontSize: 16, color: "#64748B", maxWidth: 480, margin: "0 auto" }}>从早期药物发现到商务拓展，两大平台无缝协作</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28 }}>
            {/* BD Go card */}
            <div style={{ background: "#EEF2FF", border: "1px solid #C7D2FE", borderRadius: 20, padding: "36px 36px 32px", position: "relative", overflow: "hidden" }}>
              <div style={{ position: "absolute", top: -40, right: -40, width: 200, height: 200, borderRadius: "50%", background: "rgba(37,99,235,0.06)" }} />
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
                <svg width="40" height="40" viewBox="0 0 36 36" fill="none">
                  <rect width="36" height="36" rx="9" fill="#1E3A8A" />
                  <circle cx="11" cy="18" r="3.5" fill="white" />
                  <line x1="15" y1="18" x2="22.5" y2="18" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
                  <path d="M22 13 L29 18 L22 23 Z" fill="white" />
                </svg>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: "#1E3A8A" }}>BD <span style={{ fontWeight: 500 }}>Go</span></div>
                  <div style={{ fontSize: 12, color: "#6366F1", fontWeight: 500 }}>商务拓展情报平台</div>
                </div>
              </div>
              <p style={{ fontSize: 14, lineHeight: 1.7, color: "#3730A3", margin: "0 0 28px" }}>
                AI驱动的生物医药BD情报平台。发现资产、分析合作机会、生成DD报告，覆盖中国及全球市场。
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 28 }}>
                {["管线情报", "交易数据库", "AI对话分析", "自动化报告"].map(t => (
                  <span key={t} style={{ fontSize: 12, fontWeight: 500, color: "#3730A3", background: "rgba(99,102,241,0.12)", padding: "4px 10px", borderRadius: 99 }}>{t}</span>
                ))}
              </div>
              <Link href="/login" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 700, color: "#fff", background: "#1E3A8A", padding: "10px 22px", borderRadius: 9, textDecoration: "none" }}>
                进入平台 →
              </Link>
            </div>

            {/* AIDD card */}
            <div style={{ background: "#F0FDF4", border: "1px solid #A7F3D0", borderRadius: 20, padding: "36px 36px 32px", position: "relative", overflow: "hidden" }}>
              <div style={{ position: "absolute", top: -40, right: -40, width: 200, height: 200, borderRadius: "50%", background: "rgba(5,150,105,0.06)" }} />
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
                <div style={{ width: 40, height: 40, borderRadius: 9, background: "#059669", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <svg width="22" height="22" viewBox="0 0 28 28" fill="none">
                    <circle cx="14" cy="14" r="3.5" fill="white" />
                    <circle cx="6" cy="8" r="2.5" fill="white" opacity="0.85" />
                    <circle cx="22" cy="8" r="2.5" fill="white" opacity="0.85" />
                    <circle cx="6" cy="20" r="2.5" fill="white" opacity="0.85" />
                    <circle cx="22" cy="20" r="2.5" fill="white" opacity="0.85" />
                    <line x1="10.5" y1="11.5" x2="8" y2="9.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
                    <line x1="17.5" y1="11.5" x2="20" y2="9.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
                    <line x1="10.5" y1="16.5" x2="8" y2="18.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
                    <line x1="17.5" y1="16.5" x2="20" y2="18.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </div>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: "#064E3B" }}>AIDD <span style={{ fontWeight: 500 }}>Platform</span></div>
                  <div style={{ fontSize: 12, color: "#059669", fontWeight: 500 }}>AI药物发现平台</div>
                </div>
              </div>
              <p style={{ fontSize: 14, lineHeight: 1.7, color: "#065F46", margin: "0 0 28px" }}>
                端到端AI小分子设计平台。从靶点结构到候选化合物，集成ADMET预测、IP分析与生物信号通路解析。
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 28 }}>
                {["小分子设计", "ADMET预测", "靶点分析", "专利FTO"].map(t => (
                  <span key={t} style={{ fontSize: 12, fontWeight: 500, color: "#065F46", background: "rgba(5,150,105,0.12)", padding: "4px 10px", borderRadius: 99 }}>{t}</span>
                ))}
              </div>
              <a href="http://106.54.202.181:3001" target="_blank" rel="noopener noreferrer"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 700, color: "#fff", background: "#059669", padding: "10px 22px", borderRadius: 9, textDecoration: "none" }}>
                进入平台 →
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ─── CTA Section ─── */}
      <section style={{ background: "#0F172A", padding: "100px 32px", position: "relative", overflow: "hidden" }}>
        {/* Dot grid overlay */}
        <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.06) 1px, transparent 1px)", backgroundSize: "28px 28px" }} />
        <div style={{ position: "relative", maxWidth: 680, margin: "0 auto", textAlign: "center" }}>
          <Link href={ctaHref} style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)",
            borderRadius: 999, padding: "8px 18px", marginBottom: 32,
            fontSize: 13, fontWeight: 600, color: "#93C5FD", textDecoration: "none",
          }}>
            ⚡ 立即开始免费试用
          </Link>
          <h2 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.02em", color: "#fff", margin: "0 0 20px", lineHeight: 1.15 }}>
            准备好达成<br />更好的交易了吗？
          </h2>
          <p style={{ fontSize: 16, color: "#94A3B8", margin: "0 auto 44px", maxWidth: 460, lineHeight: 1.7 }}>
            加入 200+ 个使用 BD Go 的BD团队，在中国及全球范围内更快发现机会、加速合作。
          </p>
          <div style={{ display: "flex", gap: 16, justifyContent: "center", marginBottom: 28, flexWrap: "wrap" }}>
            <Link href={ctaHref} style={{ ...btn.primaryLg, background: "#fff", color: "#1E3A8A" }}>免费试用 →</Link>
            <Link href="/login" style={{ ...btn.demoLg, color: "#CBD5E1", borderColor: "rgba(255,255,255,0.2)", background: "rgba(255,255,255,0.06)" }}>联系销售</Link>
          </div>
          <div style={{ display: "flex", gap: 28, justifyContent: "center", color: "#64748B", fontSize: 13 }}>
            {["14天免费试用","无需信用卡","随时取消"].map((t) => (
              <div key={t} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#475569" strokeWidth="1.5"/><path d="M5 8l2 2 4-4" stroke="#475569" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                {t}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer style={{ background: "#fff", borderTop: "1px solid #F1F5F9", padding: "56px 32px 32px" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto" }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 48, marginBottom: 48 }}>
            {/* Brand col */}
            <div>
              <div style={{ marginBottom: 14 }}>
                <NavLogo />
              </div>
              <p style={{ fontSize: 13, lineHeight: 1.7, color: "#64748B", maxWidth: 260, margin: "0 0 16px" }}>
                AI驱动的生物医药商务拓展情报平台，服务全球交易撮合者。
              </p>
              <div style={{ fontSize: 12, color: "#94A3B8" }}>© 2026 BD Go. 保留所有权利</div>
            </div>
            {/* Link cols */}
            {[
              { title: "产品", links: [{ label: "功能特性", href: "/features" }, { label: "定价", href: "/pricing" }, { label: "使用案例", href: "/use-cases" }, { label: "API接入", href: "/api-docs" }] },
              { title: "公司", links: [{ label: "关于我们", href: "/about" }, { label: "博客", href: "/blog" }, { label: "招贤纳士", href: "/careers" }, { label: "联系我们", href: "/contact" }] },
              { title: "法律", links: [{ label: "隐私政策", href: "/privacy" }, { label: "服务条款", href: "/terms" }, { label: "安全合规", href: "/security" }] },
            ].map((col) => (
              <div key={col.title}>
                <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "#94A3B8", marginBottom: 16 }}>{col.title}</div>
                {col.links.map((l) => (
                  <div key={l.label} style={{ marginBottom: 10 }}>
                    <a href={l.href} style={{ fontSize: 13, color: "#475569", textDecoration: "none", transition: "color 0.15s" }}
                      onMouseEnter={e => (e.target as HTMLElement).style.color = "#1E3A8A"}
                      onMouseLeave={e => (e.target as HTMLElement).style.color = "#475569"}
                    >{l.label}</a>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared button styles
// ---------------------------------------------------------------------------

const btn: Record<string, React.CSSProperties> = {
  primary: {
    fontSize: 13, fontWeight: 600, color: "#fff",
    background: "#1E3A8A", padding: "9px 20px",
    borderRadius: 9, textDecoration: "none",
    transition: "background 0.15s",
  },
  ghost: {
    fontSize: 13, fontWeight: 500, color: "#374151",
    padding: "9px 16px", textDecoration: "none",
  },
  primaryLg: {
    display: "inline-block",
    fontSize: 15, fontWeight: 700, color: "#fff",
    background: "#1E3A8A", padding: "14px 32px",
    borderRadius: 12, textDecoration: "none",
    boxShadow: "0 4px 14px rgba(30,58,138,0.3)",
  },
  demoLg: {
    display: "inline-flex", alignItems: "center", gap: 10,
    fontSize: 15, fontWeight: 600, color: "#374151",
    background: "#fff", padding: "13px 26px",
    borderRadius: 12, border: "1px solid #E2E8F0",
    cursor: "pointer",
  },
};
