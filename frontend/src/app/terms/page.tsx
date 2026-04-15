import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

const sections = [
  {
    title: "1. 接受条款",
    content: `访问或使用 BD Go 平台即表示您同意受本服务条款约束。如果您不同意这些条款，请勿使用本平台。

BD Go 保留随时修改这些条款的权利。继续使用平台即视为接受修改后的条款。`,
  },
  {
    title: "2. 账户与访问",
    content: `BD Go 采用邀请制注册。您有责任维护账户凭证的安全，并对账户下发生的所有活动负责。

一个账户不得由多人共享使用。如发现账户被未授权使用，请立即联系我们。`,
  },
  {
    title: "3. 许可与使用限制",
    content: `BD Go 授予您有限的、不可转让的非独占许可，用于个人或企业内部商业目的访问和使用本平台。

您不得：
• 对平台内容进行抓取、爬取或批量下载
• 将平台数据用于构建竞争性产品或服务
• 将账户访问权转让或出售给第三方
• 对平台进行反向工程或尝试获取源代码`,
  },
  {
    title: "4. 内容所有权",
    content: `BD Go 数据库、AI 模型、软件代码及报告模板的知识产权归 BD Go 所有。

您在平台上生成的报告归您所有，但 BD Go 保留将匿名化数据用于产品改进的权利。`,
  },
  {
    title: "5. 数据准确性",
    content: `BD Go 的数据来源于公开信息和经授权的数据库，我们尽力确保数据的准确性。但 BD Go 不对数据的完整性、实时性或适用于特定商业决策承担保证责任。

平台内容仅供参考，不构成投资建议或法律意见。`,
  },
  {
    title: "6. 服务可用性",
    content: `我们努力保持平台 99% 以上的可用率，但不对因技术故障、维护或不可抗力导致的服务中断承担责任。

计划内维护将提前通知。`,
  },
  {
    title: "7. 终止",
    content: `您可以随时注销账户。BD Go 保留在违反本条款时暂停或终止账户的权利。

账户终止后，您在平台上生成的报告文件将在 30 天内删除。`,
  },
  {
    title: "8. 争议解决",
    content: `本条款受中华人民共和国法律管辖。任何争议应首先通过友好协商解决；协商不成的，提交上海仲裁委员会仲裁。`,
  },
];

export default function TermsPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      <div style={{ maxWidth: 720, margin: "0 auto", padding: "56px 32px 80px" }}>
        <div style={{ marginBottom: 40 }}>
          <h1 style={{ fontSize: 36, fontWeight: 800, color: "#0F172A", margin: "0 0 12px" }}>服务条款</h1>
          <p style={{ fontSize: 14, color: "#94A3B8", margin: 0 }}>最后更新：2026 年 4 月 1 日</p>
        </div>

        <div style={{ fontSize: 14, color: "#475569", lineHeight: 1.8, marginBottom: 32, padding: "16px 20px", background: "#EEF2FF", borderRadius: 10, borderLeft: "3px solid #2563EB" }}>
          请在使用 BD Go 前仔细阅读本服务条款。使用本平台即表示您接受以下条款和条件。
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
            如有任何关于服务条款的疑问，请联系 <a href="mailto:legal@bdgo.ai" style={{ color: "#2563EB", textDecoration: "none" }}>legal@bdgo.ai</a>
          </p>
        </div>
      </div>
    </div>
  );
}
