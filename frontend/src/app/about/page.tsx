import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

const values = [
  { icon: "🎯", title: "专注垂直", desc: "我们只做生物医药 BD 情报，不做通用工具。深度胜于广度。" },
  { icon: "🔬", title: "数据优先", desc: "所有洞察来自结构化数据库，而非网页抓取。准确、可溯源。" },
  { icon: "⚡", title: "效率驱动", desc: "每个功能都以「节省 BD 团队时间」为唯一衡量标准。" },
  { icon: "🔐", title: "安全可信", desc: "企业级权限隔离，TLS 加密，数据不用于训练任何模型。" },
];

export default function AboutPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div
        style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 680, margin: "0 auto" }}
      >
        <div
          style={{
            display: "inline-block",
            fontSize: 12,
            fontWeight: 700,
            color: "#2563EB",
            background: "#EEF2FF",
            padding: "4px 14px",
            borderRadius: 20,
            marginBottom: 20,
            letterSpacing: "0.05em",
          }}
        >
          关于我们
        </div>
        <h1
          style={{
            fontSize: 40,
            fontWeight: 800,
            color: "#0F172A",
            lineHeight: 1.2,
            margin: "0 0 16px",
          }}
        >
          我们为什么
          <br />
          构建 BD Go
        </h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          生物医药 BD 团队每天在信息海洋里打捞决策依据。我们认为这件事应该更快、更准、更系统。
        </p>
      </div>

      {/* Story */}
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "0 32px 64px" }}>
        <div
          style={{
            background: "#fff",
            borderRadius: 20,
            border: "1px solid #E8EFFE",
            padding: "40px",
            boxShadow: "0 2px 12px rgba(30,58,138,0.05)",
          }}
        >
          <h2 style={{ fontSize: 22, fontWeight: 700, color: "#0F172A", marginBottom: 16 }}>
            故事起点
          </h2>
          <p style={{ fontSize: 15, color: "#475569", lineHeight: 1.8, margin: "0 0 16px" }}>
            BD Go
            的创始人在生物医药投资和商务拓展领域深耕多年。他们发现，无论是规模最大的跨国药企还是初创
            Biotech，BD 团队面对的信息碎片化问题几乎相同：数据分散在
            PubMed、ClinicalTrials、公司公告、交易数据库里，整合一份竞争格局报告动辄数天。
          </p>
          <p style={{ fontSize: 15, color: "#475569", lineHeight: 1.8, margin: "0 0 16px" }}>
            2024 年，我们开始构建一个专为中国 BD
            团队设计的情报平台——覆盖国内外管线资产、临床试验、交易记录，并以 AI
            自然语言接口打通所有数据。今天，BD Go 服务于多家头部 Biotech 和 CRO 的 BD 团队。
          </p>
          <p style={{ fontSize: 15, color: "#475569", lineHeight: 1.8, margin: 0 }}>
            我们相信，最好的 BD 决策来自最快的情报获取。BD Go 的使命是让每一位 BD
            从业者都拥有顶尖分析师的信息密度。
          </p>
        </div>
      </div>

      {/* Values */}
      <div
        style={{
          maxWidth: 1000,
          margin: "0 auto",
          padding: "0 32px 80px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 20,
        }}
      >
        {values.map((v) => (
          <div
            key={v.title}
            style={{
              background: "#fff",
              borderRadius: 16,
              border: "1px solid #E8EFFE",
              padding: "24px",
            }}
          >
            <div style={{ fontSize: 28, marginBottom: 12 }}>{v.icon}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#0F172A", marginBottom: 8 }}>
              {v.title}
            </div>
            <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.6 }}>{v.desc}</div>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div style={{ background: "#1E3A8A", textAlign: "center", padding: "56px 32px" }}>
        <h2 style={{ fontSize: 28, fontWeight: 800, color: "#fff", margin: "0 0 12px" }}>
          加入我们的旅程
        </h2>
        <p style={{ fontSize: 15, color: "#93C5FD", margin: "0 0 28px" }}>
          我们正在招募对生物医药充满热情的伙伴。
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <Link
            href="/careers"
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: "#1E3A8A",
              background: "#fff",
              padding: "14px 36px",
              borderRadius: 12,
              textDecoration: "none",
            }}
          >
            查看职位
          </Link>
          <Link
            href="/contact"
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.4)",
              padding: "14px 36px",
              borderRadius: 12,
              textDecoration: "none",
            }}
          >
            联系我们
          </Link>
        </div>
      </div>
    </div>
  );
}
