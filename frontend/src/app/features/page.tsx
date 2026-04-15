import Link from "next/link";
import { LandingNav } from "@/components/LandingNav";

const features = [
  {
    icon: "🧠",
    title: "AI 驱动的自然语言查询",
    desc: "用中文直接提问——「信达生物有哪些 PD-1 资产？」「近两年 GLP-1 领域有哪些交易？」系统实时查询数据库并给出结构化答案，无需学习任何查询语法。",
  },
  {
    icon: "📊",
    title: "全景数据库",
    desc: "覆盖 1000+ 家生物医药公司、5000+ 条管线资产、44000+ 条临床试验、13000+ 笔授权交易，以及 123 家跨国药企的 BD 战略画像。数据持续更新。",
  },
  {
    icon: "⚡",
    title: "催化剂日历",
    desc: "按时间轴展示未来 12 个月内的 PDUFA 截止日期、Phase 3 数据读出、NMPA 审评品种等关键事件，帮助 BD 团队提前布局。",
  },
  {
    icon: "📝",
    title: "一键生成 BD 报告",
    desc: "支持七类结构化报告：疾病竞争格局、靶点雷达、MNC 买方画像、商业化评估、IP 景观、文献综述、临床指南简报。Word 格式直接交付。",
  },
  {
    icon: "🎯",
    title: "买方匹配引擎",
    desc: "输入资产名称，系统自动从 123 家 MNC 的战略 DNA、历史交易偏好、管线缺口中匹配最可能的买方，输出带评分的排名列表。",
  },
  {
    icon: "🔔",
    title: "关注与追踪",
    desc: "将目标公司、资产、疾病领域、靶点加入关注列表，在主页集中查看动态更新，不错过任何关键变化。",
  },
  {
    icon: "🔍",
    title: "全文搜索",
    desc: "跨公司、资产、临床试验、交易四张主表的全文检索，支持中英文、模糊匹配、拼音首字母，秒级响应。",
  },
  {
    icon: "🔐",
    title: "企业级权限管理",
    desc: "邀请制注册，团队账户隔离，所有数据传输 TLS 加密，报告支持一键生成专属分享链接，权限精确到单份文件。",
  },
];

export default function FeaturesPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 720, margin: "0 auto" }}>
        <div style={{ display: "inline-block", fontSize: 12, fontWeight: 700, color: "#2563EB", background: "#EEF2FF", padding: "4px 14px", borderRadius: 20, marginBottom: 20, letterSpacing: "0.05em" }}>功能特性</div>
        <h1 style={{ fontSize: 40, fontWeight: 800, color: "#0F172A", lineHeight: 1.2, margin: "0 0 16px" }}>
          为 BD 团队打造的<br />每一项能力
        </h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          从情报获取到报告交付，BD Go 覆盖生物医药商务拓展的完整工作流。
        </p>
      </div>

      {/* Feature grid */}
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 32px 80px", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 24 }}>
        {features.map((f) => (
          <div key={f.title} style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "28px 28px 24px", boxShadow: "0 2px 12px rgba(30,58,138,0.05)" }}>
            <div style={{ fontSize: 32, marginBottom: 16 }}>{f.icon}</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#0F172A", marginBottom: 10 }}>{f.title}</div>
            <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7 }}>{f.desc}</div>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div style={{ background: "#1E3A8A", textAlign: "center", padding: "56px 32px" }}>
        <h2 style={{ fontSize: 28, fontWeight: 800, color: "#fff", margin: "0 0 12px" }}>准备好开始了吗？</h2>
        <p style={{ fontSize: 15, color: "#93C5FD", margin: "0 0 28px" }}>申请内测资格，免费体验所有功能。</p>
        <Link href="/login" style={{ fontSize: 15, fontWeight: 700, color: "#1E3A8A", background: "#fff", padding: "14px 36px", borderRadius: 12, textDecoration: "none" }}>申请试用 →</Link>
      </div>
    </div>
  );
}
