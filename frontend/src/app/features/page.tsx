import Link from "next/link";
import { LandingNav } from "@/components/LandingNav";

const features = [
  {
    icon: "🧠",
    title: "自然语言对话",
    desc: "用中文直接提问——「信达生物有哪些 PD-1 资产？」「近两年 GLP-1 领域有哪些交易？」复杂任务先出计划再跑、简单问题直接答，跨多轮对话保持上下文。",
  },
  {
    icon: "📊",
    title: "结构化情报库",
    desc: "覆盖中国 + 全球生物医药公司、管线资产、临床试验、授权交易、跨国药企买方画像。结构化、可筛选、带引用，不是网页抓取的拼凑。",
  },
  {
    icon: "⚡",
    title: "催化剂日历",
    desc: "未来 12 个月内的 PDUFA、Phase 3 数据读出、NMPA 审评、监管里程碑——按紧迫度自动着色，BD 提前布局的入口。",
  },
  {
    icon: "📝",
    title: "30 个 BD 报告生成器",
    desc: "覆盖分析（疾病 / 靶点 / IP / 商业化 / 买方画像）、BD 闭环（synthesize / outreach / 会前 brief）、合同草稿（TS / MTA / License / 共开发 / SPA）、尽调（DD checklist / FAQ / 数据室）。Word / Excel / Markdown 直接导出。",
  },
  {
    icon: "🎯",
    title: "买方匹配",
    desc: "输入资产，系统从跨国药企的战略画像、历史交易偏好、管线缺口里匹配最可能的买方，输出带评分的排名清单——和 outreach 工作流串通。",
  },
  {
    icon: "🔔",
    title: "关注列表 + 通知",
    desc: "公司、资产、靶点、疾病、孵化器加入关注，动态推送到通知中心。关注列表支持团队共享，同邮箱域同事自动加入。",
  },
  {
    icon: "🔍",
    title: "跨库搜索",
    desc: "公司、资产、临床、交易、专利同一个搜索入口，中英文混合、模糊匹配，结果直接结构化展示。",
  },
  {
    icon: "🔐",
    title: "企业级数据边界",
    desc: "邀请制、团队账户隔离、TLS 传输、报告分享链接细到单文件。对话、上传文件、业务数据不会用于训练任何外部模型，也不会出售或用于广告。",
  },
];

export default function FeaturesPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
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
          功能特性
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
          为 BD 团队打造的
          <br />
          每一项能力
        </h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          从情报获取到报告交付，BD Go 覆盖生物医药商务拓展的完整工作流。
        </p>
      </div>

      {/* DEF section */}
      <ProductSection
        id="def"
        eyebrow="DEF · 痛点引擎"
        accent="#7C3AED"
        title="把杂音结构化成立项假设"
        body={[
          "BD 工作台拉回来的情报越来越多——交易、管线、读出、专利、会议——多到判断本身被信息淹没。DEF 站在这个位置：把疾病、临床终点、技术前沿三件事叠在同一个切面上，找出还没被现有管线占住的窗口。",
          "DEF 不做搜索，不做总结，只做切片。它不告诉你某条线打几分，它告诉你在这个位置上还有没有人在做。要不要做、值不值得做最后还是人决定，但人有了切片，决策就不再是直觉对直觉。",
          "DEF 现在的工作是把各家自己最近一年判断过的项目反过来校准三轴口径——这一步不能跳，否则评分只是另一种自欺。",
        ]}
        bullets={[
          ["Disease 维度", "未满足需求的痛感，看的不只是疾病规模，是现有标准治疗的天花板"],
          ["Endpoint 维度", "终点是否被监管和市场认可、是否能直接对应到资产估值的抓手"],
          ["Frontier 维度", "技术路径已经有人探到边、还没人做完——窗口的位置"],
        ]}
        ctaLabel="阅读 DEF 设计原理 →"
        ctaHref="/blog"
      />

      {/* AIDD section */}
      <ProductSection
        id="aidd"
        eyebrow="AIDD · AI Drug Discovery"
        accent="#059669"
        title="把立项做成一条可复现的流水线"
        body={[
          "当一个候选靶点被 BD 推到立项桌上，下一步 48 小时通常是这样：生信工程师拉结构、AI 制药团队跑设计、化学跑 ADMET、专利团队查 IP，最后产品经理把所有产物拼成 PPT。每一段都得等上家、每一段都得现搭环境、每一段的产出都不一定能复现。",
          "AIDD 把这条路径写成一条流水线。抗体走一条、小分子走另一条，但骨架一样：从公开数据库抓输入，跑结构 / 设计 / 筛选 / ADMET / IP，最后落成一份带分数的立项包。每一步都有产物文件，每一步都能单独复现。",
          "AIDD 不替你做判断，它替你把判断之前要做的所有重复工作跑完。每一步的中间产物都摊开、方法学和阈值都写在文档里——可以质疑、可以替换。AI4S 这个领域过去几年最不缺的是漂亮的 demo，最缺的是别人能在自己机器上重新跑出同一个数的东西。",
        ]}
        bullets={[
          ["抗体路径", "从抗原信息到结构、可开发性、IP、突变效应、综合评分"],
          ["小分子路径", "从靶点画像到活性数据、设计与对接、ADMET、QSAR、IP、最终报告"],
          ["云端 + 本地", "需要 GPU 的步骤上云端，没有 GPU 的环境本地跑得动轻量替代"],
        ]}
        ctaLabel="阅读 AIDD 流水线白皮书 →"
        ctaHref="/blog"
      />

      {/* Feature grid */}
      <div
        style={{
          maxWidth: 1100,
          margin: "40px auto 0",
          padding: "0 32px 12px",
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 700, color: "#64748B", letterSpacing: ".1em" }}>
          BD GO · 工作台能力
        </div>
        <h2
          id="bdgo"
          style={{
            fontSize: 24,
            fontWeight: 800,
            color: "#0F172A",
            margin: "8px 0 0",
            scrollMarginTop: 80,
          }}
        >
          一个对话框，一整条 BD 工作流
        </h2>
      </div>
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding: "20px 32px 80px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: 24,
        }}
      >
        {features.map((f) => (
          <div
            key={f.title}
            style={{
              background: "#fff",
              borderRadius: 16,
              border: "1px solid #E8EFFE",
              padding: "28px 28px 24px",
              boxShadow: "0 2px 12px rgba(30,58,138,0.05)",
            }}
          >
            <div style={{ fontSize: 32, marginBottom: 16 }}>{f.icon}</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#0F172A", marginBottom: 10 }}>
              {f.title}
            </div>
            <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7 }}>{f.desc}</div>
          </div>
        ))}
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

function ProductSection({
  id,
  eyebrow,
  accent,
  title,
  body,
  bullets,
  ctaLabel,
  ctaHref,
}: {
  id: string;
  eyebrow: string;
  accent: string;
  title: string;
  body: string[];
  bullets: [string, string][];
  ctaLabel: string;
  ctaHref: string;
}) {
  return (
    <section
      id={id}
      style={{
        maxWidth: 1100,
        margin: "0 auto",
        padding: "16px 32px 56px",
        scrollMarginTop: 80,
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 20,
          border: "1px solid #E8EFFE",
          padding: "40px 44px",
          boxShadow: "0 4px 20px rgba(30,58,138,0.06)",
          display: "grid",
          gridTemplateColumns: "1.1fr 1fr",
          gap: 48,
          alignItems: "start",
        }}
      >
        <div>
          <div
            style={{
              display: "inline-block",
              fontSize: 11,
              fontWeight: 700,
              color: accent,
              background: `${accent}15`,
              padding: "4px 12px",
              borderRadius: 999,
              letterSpacing: ".08em",
              textTransform: "uppercase",
              marginBottom: 16,
              fontFamily: "ui-monospace, monospace",
            }}
          >
            {eyebrow}
          </div>
          <h2
            style={{
              fontSize: 30,
              fontWeight: 800,
              color: "#0F172A",
              lineHeight: 1.2,
              margin: "0 0 20px",
            }}
          >
            {title}
          </h2>
          {body.map((p, i) => (
            <p
              key={i}
              style={{ fontSize: 14.5, color: "#475569", lineHeight: 1.75, margin: "0 0 14px" }}
            >
              {p}
            </p>
          ))}
          <Link
            href={ctaHref}
            style={{
              display: "inline-block",
              marginTop: 12,
              fontSize: 13.5,
              fontWeight: 600,
              color: accent,
              textDecoration: "none",
            }}
          >
            {ctaLabel}
          </Link>
        </div>
        <div>
          {bullets.map(([title, desc]) => (
            <div
              key={title}
              style={{
                padding: "16px 0",
                borderTop: "1px solid #E8EFFE",
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: accent, marginBottom: 6 }}>
                {title}
              </div>
              <div style={{ fontSize: 13, color: "#475569", lineHeight: 1.7 }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
