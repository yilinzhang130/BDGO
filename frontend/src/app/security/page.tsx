import { LandingNav } from "@/components/LandingNav";

const measures = [
  {
    icon: "🔒",
    title: "传输加密",
    desc: "API 请求、文件上传与流式响应全程经 HTTPS/TLS 加密传输，防止中间人窃听。",
  },
  {
    icon: "🔑",
    title: "认证与会话",
    desc: "基于 JWT 的短时效会话认证，会话凭证不持久化在浏览器 Cookie 中；敏感接口要求二次校验。",
  },
  {
    icon: "👥",
    title: "多租户隔离",
    desc: "不同账户与机构之间的数据在应用与查询层严格隔离，用户仅可访问自己有权限的资源。",
  },
  {
    icon: "🛡️",
    title: "最小权限",
    desc: "生产环境访问遵循最小权限原则，涉及生产数据的运维操作需双人授权并留存审计日志。",
  },
  {
    icon: "📋",
    title: "日志与审计",
    desc: "关键操作（登录、权限变更、数据导出等）保留审计日志，用于故障排查与合规追溯。",
  },
  {
    icon: "🚫",
    title: "不训练外部模型",
    desc: "您的查询内容、上传文件与生成报告不会被用于训练任何外部 AI 模型。",
  },
  {
    icon: "🇨🇳",
    title: "境内存储",
    desc: "数据存放于中国境内云服务器，依托基础云服务商提供的物理与网络安全能力。",
  },
  {
    icon: "🧪",
    title: "依赖与漏洞管理",
    desc: "对开源依赖与容器镜像进行常规漏洞扫描，发现高危问题及时修补。",
  },
  {
    icon: "🚦",
    title: "限速与反滥用",
    desc: "对登录、API 调用与 AI 调度实施速率控制与异常访问识别，防止暴力破解与资源滥用。",
  },
];

export default function SecurityPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "72px 32px 44px", maxWidth: 680, margin: "0 auto" }}>
        <div style={{ display: "inline-block", fontSize: 12, fontWeight: 700, color: "#2563EB", background: "#EEF2FF", padding: "4px 14px", borderRadius: 20, marginBottom: 20, letterSpacing: "0.05em" }}>
          安全与合规
        </div>
        <h1 style={{ fontSize: 38, fontWeight: 800, color: "#0F172A", lineHeight: 1.2, margin: "0 0 16px" }}>
          审慎、透明地对待您的数据
        </h1>
        <p style={{ fontSize: 16, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          BD Go 目前处于早期运营阶段。以下是我们实际已采取的安全措施，以及未来将持续完善的方向。我们不以营销名义夸大安全能力。
        </p>
      </div>

      {/* Measures grid */}
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 32px 48px", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 20 }}>
        {measures.map((m) => (
          <div key={m.title} style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "24px", boxShadow: "0 2px 12px rgba(30,58,138,0.04)" }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>{m.icon}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#0F172A", marginBottom: 8 }}>{m.title}</div>
            <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.6 }}>{m.desc}</div>
          </div>
        ))}
      </div>

      <InfoCard title="我们遵循的法规原则">
        <p style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7, margin: "0 0 18px" }}>
          我们的产品设计与数据处理流程以下列法律法规为基本准则进行构建：
        </p>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "#374151", lineHeight: 1.9 }}>
          <li>《中华人民共和国网络安全法》</li>
          <li>《中华人民共和国数据安全法》</li>
          <li>《中华人民共和国个人信息保护法》</li>
          <li>《生成式人工智能服务管理暂行办法》</li>
        </ul>
        <p style={{ fontSize: 12, color: "#94A3B8", lineHeight: 1.7, margin: "18px 0 0" }}>
          遵循上述法律并不等同于已完成第三方认证。BD Go 尚未完成等级保护备案、ISO 27001 或 SOC 2 等外部认证，我们将随业务规模扩大及客户需要推进相关评估，并在取得后于本页面更新。
        </p>
      </InfoCard>

      <InfoCard title="安全事件响应">
        <p style={{ fontSize: 13, color: "#374151", lineHeight: 1.8, margin: 0 }}>
          若发生可能影响您数据的安全事件，我们将依法在合理时间内通知受影响的用户，说明事件性质、可能影响、已采取及建议采取的应对措施，并根据事件严重程度向主管部门报告。我们持续完善事件检测、响应与复盘流程。
        </p>
      </InfoCard>

      <InfoCard title="漏洞披露与联系" bottomPad={80}>
        <p style={{ fontSize: 13, color: "#374151", lineHeight: 1.8, margin: "0 0 14px" }}>
          如您在使用过程中发现潜在安全漏洞或数据异常，欢迎通过 <a href="mailto:security@bdgo.ai" style={{ color: "#2563EB", textDecoration: "none" }}>security@bdgo.ai</a> 与我们联系。我们承诺：
        </p>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "#374151", lineHeight: 1.9 }}>
          <li>在合理期限内确认收到您的报告；</li>
          <li>对善意的安全研究，不追究研究者的法律责任；</li>
          <li>与您协调披露时间，避免在修复前造成扩大影响；</li>
          <li>如有必要，向受影响的用户与主管部门进行同步。</li>
        </ul>
        <p style={{ fontSize: 12, color: "#94A3B8", lineHeight: 1.7, margin: "16px 0 0" }}>
          请在报告中避免涉及真实用户数据，避免使用可能造成服务中断或数据破坏的手段。
        </p>
      </InfoCard>
    </div>
  );
}

function InfoCard({ title, children, bottomPad = 24 }: { title: string; children: React.ReactNode; bottomPad?: number }) {
  return (
    <div style={{ maxWidth: 820, margin: "0 auto", padding: `0 32px ${bottomPad}px` }}>
      <div style={{ background: "#fff", borderRadius: 20, border: "1px solid #E8EFFE", padding: "32px 36px" }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#0F172A", margin: "0 0 10px" }}>{title}</h2>
        {children}
      </div>
    </div>
  );
}
