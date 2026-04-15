import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

const sections = [
  {
    title: "1. 我们收集哪些信息",
    content: `当您注册 BD Go 时，我们收集您的姓名、邮箱地址和公司信息。在使用平台过程中，我们记录您的查询历史、生成的报告及会话内容，以便提供个性化服务和产品改进。

我们不收集您的支付信息（由第三方支付服务商处理），也不追踪您在 BD Go 以外的网络行为。`,
  },
  {
    title: "2. 我们如何使用这些信息",
    content: `您的数据用于以下目的：
• 提供和改进 BD Go 的核心功能（AI 查询、报告生成、买方匹配）
• 发送与账户相关的通知（如报告完成、系统更新）
• 分析产品使用情况以优化用户体验
• 响应您的支持请求

我们不会将您的数据出售给第三方，也不会用于广告定向。`,
  },
  {
    title: "3. 数据安全",
    content: `所有数据传输通过 TLS 1.3 加密。数据库存储采用 AES-256 加密。我们定期进行安全审计，并对内部访问实施最小权限原则。

您的查询内容和报告数据不会用于训练任何外部 AI 模型。`,
  },
  {
    title: "4. 数据存储与保留",
    content: `您的数据存储在位于中国境内的云服务器上，符合《数据安全法》和《个人信息保护法》的相关要求。

账户注销后，我们将在 30 天内删除您的个人信息和使用记录，法律法规要求保留的信息除外。`,
  },
  {
    title: "5. Cookie 和本地存储",
    content: `BD Go 使用必要的 Cookie 和 localStorage 维持您的登录状态和会话偏好。我们不使用第三方追踪 Cookie。`,
  },
  {
    title: "6. 您的权利",
    content: `您有权访问、更正或删除您的个人信息。如需行使上述权利，请联系 privacy@bdgo.ai。我们将在 15 个工作日内响应。`,
  },
  {
    title: "7. 政策变更",
    content: `我们可能不时更新本隐私政策。重大变更将通过邮件或平台内通知告知您。继续使用 BD Go 即表示您接受更新后的政策。`,
  },
];

export default function PrivacyPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      <div style={{ maxWidth: 720, margin: "0 auto", padding: "56px 32px 80px" }}>
        <div style={{ marginBottom: 40 }}>
          <h1 style={{ fontSize: 36, fontWeight: 800, color: "#0F172A", margin: "0 0 12px" }}>隐私政策</h1>
          <p style={{ fontSize: 14, color: "#94A3B8", margin: 0 }}>最后更新：2026 年 4 月 1 日</p>
        </div>

        <div style={{ fontSize: 14, color: "#475569", lineHeight: 1.8, marginBottom: 32, padding: "16px 20px", background: "#EEF2FF", borderRadius: 10, borderLeft: "3px solid #2563EB" }}>
          BD Go（以下简称「我们」）非常重视您的隐私。本政策说明我们如何收集、使用和保护您在使用 BD Go 平台时产生的信息。
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
          {sections.map((s) => (
            <div key={s.title}>
              <h2 style={{ fontSize: 17, fontWeight: 700, color: "#0F172A", marginBottom: 12 }}>{s.title}</h2>
              <div style={{ fontSize: 14, color: "#475569", lineHeight: 1.8, whiteSpace: "pre-line" }}>{s.content}</div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 48, padding: "20px", background: "#F8FAFF", border: "1px solid #E8EFFE", borderRadius: 12 }}>
          <p style={{ fontSize: 13, color: "#64748B", margin: 0 }}>
            如有任何关于隐私的疑问，请联系 <a href="mailto:privacy@bdgo.ai" style={{ color: "#2563EB", textDecoration: "none" }}>privacy@bdgo.ai</a>
          </p>
        </div>
      </div>
    </div>
  );
}
