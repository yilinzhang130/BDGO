import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

const measures = [
  {
    icon: "🔒",
    title: "传输加密",
    desc: "所有数据传输通过 TLS 1.3 加密，包括 API 请求、报告下载和实时流式响应。",
  },
  {
    icon: "🗄️",
    title: "存储加密",
    desc: "数据库静态数据采用 AES-256 加密存储，报告文件存储于加密卷，容器重启不丢失。",
  },
  {
    icon: "🔑",
    title: "JWT 认证",
    desc: "基于 JWT 的无状态认证，Token 有效期短，刷新机制完善，不使用 Cookie 存储凭证。",
  },
  {
    icon: "👥",
    title: "权限隔离",
    desc: "每个团队账户数据严格隔离，用户只能访问自己组织内的资源和报告。",
  },
  {
    icon: "🛡️",
    title: "最小权限",
    desc: "内部系统访问遵循最小权限原则，生产数据库访问需双重审批。",
  },
  {
    icon: "📋",
    title: "安全审计",
    desc: "定期进行依赖扫描、渗透测试和代码安全审查，关键操作留有审计日志。",
  },
  {
    icon: "🚫",
    title: "数据不训练模型",
    desc: "您的查询内容、报告和业务数据不会被用于训练任何外部 AI 模型。",
  },
  {
    icon: "🇨🇳",
    title: "数据本地化",
    desc: "所有数据存储于中国境内服务器，符合《数据安全法》和《个人信息保护法》要求。",
  },
];

export default function SecurityPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 640, margin: "0 auto" }}>
        <div style={{ display: "inline-block", fontSize: 12, fontWeight: 700, color: "#2563EB", background: "#EEF2FF", padding: "4px 14px", borderRadius: 20, marginBottom: 20, letterSpacing: "0.05em" }}>安全合规</div>
        <h1 style={{ fontSize: 40, fontWeight: 800, color: "#0F172A", lineHeight: 1.2, margin: "0 0 16px" }}>企业级安全<br />从架构层面内建</h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          BD Go 的安全措施不是事后补丁，而是产品设计的核心部分。
        </p>
      </div>

      {/* Measures grid */}
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 32px 64px", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 20 }}>
        {measures.map((m) => (
          <div key={m.title} style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "24px", boxShadow: "0 2px 12px rgba(30,58,138,0.04)" }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>{m.icon}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#0F172A", marginBottom: 8 }}>{m.title}</div>
            <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.6 }}>{m.desc}</div>
          </div>
        ))}
      </div>

      {/* Compliance */}
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 32px 80px" }}>
        <div style={{ background: "#fff", borderRadius: 20, border: "1px solid #E8EFFE", padding: "36px" }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#0F172A", marginBottom: 20 }}>合规框架</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {[
              { law: "数据安全法（2021）", status: "✓ 符合" },
              { law: "个人信息保护法（2021）", status: "✓ 符合" },
              { law: "网络安全法", status: "✓ 符合" },
              { law: "等级保护 2.0（二级）", status: "评估中" },
            ].map((c) => (
              <div key={c.law} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "#F8FAFF", borderRadius: 10, border: "1px solid #E8EFFE" }}>
                <span style={{ fontSize: 13, color: "#374151" }}>{c.law}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: c.status.startsWith("✓") ? "#16A34A" : "#D97706" }}>{c.status}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ textAlign: "center", marginTop: 40 }}>
          <p style={{ fontSize: 14, color: "#64748B", marginBottom: 16 }}>发现安全漏洞？我们有负责任披露计划。</p>
          <a href="mailto:security@bdgo.ai" style={{ fontSize: 14, fontWeight: 600, color: "#2563EB", textDecoration: "none" }}>security@bdgo.ai →</a>
        </div>
      </div>
    </div>
  );
}
