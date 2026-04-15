import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

const posts = [
  {
    date: "2026-04-10",
    tag: "行业洞察",
    title: "2026 Q1 中国 Biotech 授权交易复盘：GLP-1 退潮，ADC 依然强劲",
    desc: "我们梳理了 Q1 发生的 38 笔授权交易，分析买卖双方的战略逻辑与定价趋势，看看哪些靶点最受跨国药企青睐。",
    readTime: "8 分钟",
  },
  {
    date: "2026-03-28",
    tag: "产品更新",
    title: "BD Go v2.3 上线：买方匹配引擎全面升级",
    desc: "新版匹配引擎引入了 MNC 管线缺口分析模块，准确率提升 40%。同时支持批量资产匹配与 Excel 导出。",
    readTime: "4 分钟",
  },
  {
    date: "2026-03-15",
    tag: "方法论",
    title: "如何在 30 分钟内完成一份 License-in 竞争格局报告",
    desc: "分步拆解 BD Go 的工作流：从输入适应症关键词，到生成带竞品对比表的完整 Word 报告，全程示范。",
    readTime: "6 分钟",
  },
  {
    date: "2026-02-20",
    tag: "行业洞察",
    title: "NMPA 2025 年审评数据解读：哪些靶点批准速度最快？",
    desc: "基于 BD Go 数据库的 NMPA 审评记录分析，找出审评周期最短的适应症领域与关键影响因素。",
    readTime: "10 分钟",
  },
  {
    date: "2026-02-05",
    tag: "产品更新",
    title: "催化剂日历新增 NMPA 品种追踪，覆盖 200+ 在审产品",
    desc: "除了 FDA PDUFA 日期，BD Go 现在同步追踪 NMPA 在审品种的审评进度，支持按适应症和公司过滤。",
    readTime: "3 分钟",
  },
  {
    date: "2026-01-18",
    tag: "方法论",
    title: "MNC 买方画像怎么读？6 个维度判断合作意向",
    desc: "解读 BD Go 买方画像报告中的战略 DNA、历史交易偏好、管线缺口三个核心模块，教你识别真正的潜在买家。",
    readTime: "7 分钟",
  },
];

const tagColor: Record<string, { bg: string; color: string }> = {
  "行业洞察": { bg: "#EEF2FF", color: "#4338CA" },
  "产品更新": { bg: "#F0FDF4", color: "#16A34A" },
  "方法论": { bg: "#FFF7ED", color: "#C2410C" },
};

export default function BlogPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 640, margin: "0 auto" }}>
        <div style={{ display: "inline-block", fontSize: 12, fontWeight: 700, color: "#2563EB", background: "#EEF2FF", padding: "4px 14px", borderRadius: 20, marginBottom: 20, letterSpacing: "0.05em" }}>博客</div>
        <h1 style={{ fontSize: 40, fontWeight: 800, color: "#0F172A", lineHeight: 1.2, margin: "0 0 16px" }}>行业洞察与产品动态</h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          来自 BD Go 团队的生物医药 BD 方法论、数据分析与平台更新。
        </p>
      </div>

      {/* Posts */}
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 32px 80px", display: "flex", flexDirection: "column", gap: 20 }}>
        {posts.map((p) => {
          const tc = tagColor[p.tag] || { bg: "#F1F5F9", color: "#475569" };
          return (
            <div key={p.title} style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "28px", boxShadow: "0 2px 12px rgba(30,58,138,0.04)", cursor: "pointer" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: tc.color, background: tc.bg, padding: "2px 10px", borderRadius: 12 }}>{p.tag}</span>
                <span style={{ fontSize: 12, color: "#94A3B8" }}>{p.date}</span>
                <span style={{ fontSize: 12, color: "#94A3B8" }}>· {p.readTime}阅读</span>
              </div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: "#0F172A", margin: "0 0 10px", lineHeight: 1.4 }}>{p.title}</h3>
              <p style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7, margin: 0 }}>{p.desc}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
