import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

const principles = [
  {
    title: "三条产品线一根主线",
    desc: "BD GO 拉情报、DEF 切立项窗口、AIDD 跑可成药性流水线——三件事是一条工作流的三段，不是三个孤立产品。",
  },
  {
    title: "切片器不是评分器",
    desc: "我们不替你做判断。把决策需要的论据摆开、把切片做清楚，要不要做最后还是人决定。",
  },
  {
    title: "可复现优先于好看",
    desc: "AI4S 这个领域过去几年最不缺的是漂亮的 demo，最缺的是别人能在自己机器上重新跑出同一个数的东西。",
  },
  {
    title: "不卖你的数据",
    desc: "对话、上传文件、业务数据都不会用于训练任何外部模型，也不会出售或用于广告定向。",
  },
];

export default function AboutPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F5F4EE", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div
        style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 720, margin: "0 auto" }}
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
          关于 BD Go
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
          把 BD、立项、AI 制药
          <br />
          串成一条工作流
        </h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          BD Go 是我们对一个老问题的新尝试：让 BD 团队判断之前不被信息淹没。
        </p>
      </div>

      {/* Maker badge */}
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "0 32px 24px", textAlign: "center" }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            fontSize: 13,
            color: "#64748B",
          }}
        >
          BD Go 由
          <a
            href="https://yafocapital.com"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "#1E3A8A",
              fontWeight: 700,
              textDecoration: "none",
              borderBottom: "1px solid #93C5FD",
            }}
          >
            雅法资本 · YAFO Capital ↗
          </a>
          团队构建
        </div>
      </div>

      {/* Story */}
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "0 32px 64px" }}>
        <div
          style={{
            background: "#fff",
            borderRadius: 20,
            border: "1px solid #E8EFFE",
            padding: "44px 48px",
            boxShadow: "0 2px 12px rgba(30,58,138,0.05)",
          }}
        >
          <h2 style={{ fontSize: 22, fontWeight: 700, color: "#0F172A", margin: "0 0 18px" }}>
            起点
          </h2>
          <p style={{ fontSize: 15, color: "#475569", lineHeight: 1.85, margin: "0 0 14px" }}>
            BD Go 来自雅法资本（YAFO
            Capital）。雅法是一家专注生物医药的投资机构，我们在做投资和投后管理的过程中，对 BD
            与立项这件事有相对完整的一手观察——从一个 license 的问询到 term
            sheet、从一个候选靶点到立项包，整条路径上每一处卡点都见过。
          </p>
          <p style={{ fontSize: 15, color: "#475569", lineHeight: 1.85, margin: "0 0 14px" }}>
            最重的卡点不是判断本身，是判断之前要做的信息整理工作。BD
            那边，竞品在研、最近交易、买方动作、临床读出散落在十几个数据源里；立项那边，疾病、终点、技术前沿三轴的判断完全靠
            senior 的直觉；AI
            制药那边，每一次跑流水线都要重搭环境，跑出来的数也不一定能在别人机器上复现。三条线孤立运转，浪费就出在每一段都要等上家、每一段都要拼回来。
          </p>
          <p style={{ fontSize: 15, color: "#475569", lineHeight: 1.85, margin: "0 0 14px" }}>
            BD Go 想做的事是把这三段串成一条流水线：BD GO 工作台拉情报、DEF
            把杂音结构化成立项窗口、AIDD
            把候选靶点跑成一份可复现的立项包。每一段是独立工具，串起来是一条从问题到报告的路径。
          </p>
          <p style={{ fontSize: 15, color: "#475569", lineHeight: 1.85, margin: 0 }}>
            我们不打算覆盖所有人。BD Go 是给已经在做药、做 BD、做立项的人用的——它不是为"看看 AI
            能干嘛"的好奇心准备的，它是为这件事下周二的投决会准备的。
          </p>
        </div>
      </div>

      {/* Principles */}
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "0 32px 80px" }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: "#64748B",
            letterSpacing: ".12em",
            textTransform: "uppercase",
            marginBottom: 16,
            textAlign: "center",
          }}
        >
          我们怎么做产品
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
            gap: 20,
          }}
        >
          {principles.map((p) => (
            <div
              key={p.title}
              style={{
                background: "#fff",
                borderRadius: 14,
                border: "1px solid #E8EFFE",
                padding: "24px 26px",
              }}
            >
              <div style={{ fontSize: 14.5, fontWeight: 700, color: "#0F172A", marginBottom: 10 }}>
                {p.title}
              </div>
              <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7 }}>{p.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div style={{ background: "#1E3A8A", textAlign: "center", padding: "56px 32px" }}>
        <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", margin: "0 0 12px" }}>
          想聊聊？
        </h2>
        <p style={{ fontSize: 15, color: "#93C5FD", margin: "0 0 28px" }}>
          BD 工作流里的卡点、对产品的反馈、合作意向——任何一种都欢迎。
        </p>
        <Link
          href="/contact"
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
          联系我们 →
        </Link>
      </div>
    </div>
  );
}
