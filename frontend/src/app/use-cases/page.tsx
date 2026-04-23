import Link from "next/link";
import { LandingNav } from "@/components/LandingNav";

const cases = [
  {
    role: "BD 总监",
    company: "国内头部 Biotech",
    quote: "以前整理一份竞争格局报告要两天，现在 20 分钟生成初稿，我的团队把时间全放在谈判上了。",
    tag: "报告效率 ↑ 90%",
  },
  {
    role: "战略分析师",
    company: "大型 CRO",
    quote: "催化剂日历帮我们提前三个月锁定了五个潜在合作靶点，其中两个已经推进到 NDA 阶段。",
    tag: "先手布局",
  },
  {
    role: "授权引进负责人",
    company: "跨国药企亚太区",
    quote: "买方匹配引擎给出的排名和我们内部评审结果高度吻合，节省了大量尽调前期的摸索成本。",
    tag: "匹配准确率高",
  },
];

const scenarios = [
  {
    icon: "🔎",
    title: "竞争格局分析",
    desc: "输入疾病领域或靶点，30 秒生成覆盖全球管线的竞争格局报告，包含临床进展、公司背景、交易历史。",
  },
  {
    icon: "🤝",
    title: "License-out 买家筛选",
    desc: "上传资产信息，系统自动从 123 家 MNC 的战略画像和历史交易中匹配最佳潜在买家，附评分排名。",
  },
  {
    icon: "📅",
    title: "提前布局催化剂",
    desc: "追踪未来 12 个月内的 PDUFA 日期、Phase 3 数据读出，在关键节点前完成接触，把握谈判窗口。",
  },
  {
    icon: "📄",
    title: "快速生成尽调报告",
    desc: "支持 IP 景观、商业化评估、临床指南简报等七类结构化报告，Word 格式直接分享给委托方。",
  },
  {
    icon: "📡",
    title: "实时情报追踪",
    desc: "关注目标公司或资产，首页集中呈现最新动态——融资、临床进展、合作公告，不错过任何时机。",
  },
  {
    icon: "🌐",
    title: "全文跨库检索",
    desc: "一次搜索横跨公司、资产、临床、交易四张主表，中英文混合、模糊匹配，秒级返回结构化结果。",
  },
];

export default function UseCasesPage() {
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
          使用案例
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
          BD 团队如何用
          <br />
          BD Go 赢得先机
        </h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          从情报获取到报告交付，看看同行怎么用 BD Go 缩短交易周期。
        </p>
      </div>

      {/* Scenarios */}
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding: "0 32px 64px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: 24,
        }}
      >
        {scenarios.map((s) => (
          <div
            key={s.title}
            style={{
              background: "#fff",
              borderRadius: 16,
              border: "1px solid #E8EFFE",
              padding: "28px 28px 24px",
              boxShadow: "0 2px 12px rgba(30,58,138,0.05)",
            }}
          >
            <div style={{ fontSize: 32, marginBottom: 16 }}>{s.icon}</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#0F172A", marginBottom: 10 }}>
              {s.title}
            </div>
            <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7 }}>{s.desc}</div>
          </div>
        ))}
      </div>

      {/* Testimonials */}
      <div
        style={{
          background: "#fff",
          borderTop: "1px solid #E8EFFE",
          borderBottom: "1px solid #E8EFFE",
          padding: "64px 32px",
        }}
      >
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <h2
            style={{
              fontSize: 28,
              fontWeight: 800,
              color: "#0F172A",
              textAlign: "center",
              marginBottom: 40,
            }}
          >
            用户怎么说
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
              gap: 24,
            }}
          >
            {cases.map((c) => (
              <div
                key={c.role}
                style={{
                  background: "#F8FAFF",
                  borderRadius: 16,
                  border: "1px solid #E8EFFE",
                  padding: "28px",
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "#2563EB",
                    background: "#EEF2FF",
                    display: "inline-block",
                    padding: "2px 10px",
                    borderRadius: 12,
                    marginBottom: 16,
                  }}
                >
                  {c.tag}
                </div>
                <p
                  style={{
                    fontSize: 14,
                    color: "#374151",
                    lineHeight: 1.7,
                    margin: "0 0 20px",
                    fontStyle: "italic",
                  }}
                >
                  "{c.quote}"
                </p>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#0F172A" }}>{c.role}</div>
                <div style={{ fontSize: 12, color: "#94A3B8" }}>{c.company}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CTA */}
      <div style={{ background: "#1E3A8A", textAlign: "center", padding: "56px 32px" }}>
        <h2 style={{ fontSize: 28, fontWeight: 800, color: "#fff", margin: "0 0 12px" }}>
          准备好开始了吗？
        </h2>
        <p style={{ fontSize: 15, color: "#93C5FD", margin: "0 0 28px" }}>
          申请内测资格，免费体验所有功能。
        </p>
        <Link
          href="/login"
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
          申请试用 →
        </Link>
      </div>
    </div>
  );
}
