import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

const openings = [
  {
    title: "生物医药数据分析师",
    type: "全职",
    location: "上海 / 远程",
    desc: "负责 BD Go 数据库的数据治理、标准化与质量控制，深度参与管线资产、临床试验、授权交易数据的结构化建设。",
    reqs: ["生命科学相关专业本科及以上", "有生物医药数据处理经验优先", "熟悉 Python 或 SQL", "英文读写流利"],
  },
  {
    title: "全栈工程师（Next.js + FastAPI）",
    type: "全职",
    location: "上海 / 远程",
    desc: "参与 BD Go 前端与后端核心功能开发，包括 AI 查询接口、报告生成引擎、权限系统等。",
    reqs: ["3 年以上全栈开发经验", "熟悉 React / Next.js / TypeScript", "熟悉 Python / FastAPI", "有 LLM 应用开发经验优先"],
  },
  {
    title: "BD 行业产品经理",
    type: "全职",
    location: "上海",
    desc: "深入理解生物医药 BD 工作流，将用户需求转化为产品功能，与工程和数据团队紧密协作。",
    reqs: ["有生物医药 BD 或投资行业背景", "2 年以上产品经理经验", "英文工作能力", "有 SaaS 产品经验优先"],
  },
];

export default function CareersPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 640, margin: "0 auto" }}>
        <div style={{ display: "inline-block", fontSize: 12, fontWeight: 700, color: "#2563EB", background: "#EEF2FF", padding: "4px 14px", borderRadius: 20, marginBottom: 20, letterSpacing: "0.05em" }}>招贤纳士</div>
        <h1 style={{ fontSize: 40, fontWeight: 800, color: "#0F172A", lineHeight: 1.2, margin: "0 0 16px" }}>和我们一起重新定义<br />生物医药情报</h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          我们是一支小而精的团队，正在寻找对生物医药充满热情、希望用技术改变行业的伙伴。
        </p>
      </div>

      {/* Openings */}
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 32px 80px", display: "flex", flexDirection: "column", gap: 20 }}>
        {openings.map((job) => (
          <div key={job.title} style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "28px", boxShadow: "0 2px 12px rgba(30,58,138,0.05)" }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div>
                <h3 style={{ fontSize: 17, fontWeight: 700, color: "#0F172A", margin: "0 0 6px" }}>{job.title}</h3>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: "#2563EB", background: "#EEF2FF", padding: "2px 10px", borderRadius: 12 }}>{job.type}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: "#475569", background: "#F1F5F9", padding: "2px 10px", borderRadius: 12 }}>{job.location}</span>
                </div>
              </div>
              <Link href="/contact" style={{ fontSize: 13, fontWeight: 600, color: "#fff", background: "#1E3A8A", padding: "9px 18px", borderRadius: 8, textDecoration: "none", flexShrink: 0 }}>申请职位</Link>
            </div>
            <p style={{ fontSize: 13, color: "#475569", lineHeight: 1.7, margin: "0 0 16px" }}>{job.desc}</p>
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
              {job.reqs.map((r) => (
                <li key={r} style={{ fontSize: 13, color: "#64748B", display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ color: "#2563EB", flexShrink: 0 }}>·</span>{r}
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div style={{ background: "#F8FAFF", border: "1px dashed #CBD5E1", borderRadius: 16, padding: "28px", textAlign: "center" }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#0F172A", marginBottom: 8 }}>没有看到合适的职位？</div>
          <p style={{ fontSize: 13, color: "#64748B", margin: "0 0 16px" }}>我们欢迎主动投递。告诉我们你擅长什么，以及你想为 BD Go 带来什么。</p>
          <Link href="/contact" style={{ fontSize: 13, fontWeight: 600, color: "#2563EB", textDecoration: "none" }}>发送简历 →</Link>
        </div>
      </div>
    </div>
  );
}
