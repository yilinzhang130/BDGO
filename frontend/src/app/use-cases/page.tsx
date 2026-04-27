import Link from "next/link";
import { LandingNav } from "@/components/LandingNav";

type Section = {
  id: string;
  eyebrow: string;
  title: string;
  body: string[];
  flow: string[];
};

const roles: Section[] = [
  {
    id: "role-bd",
    eyebrow: "角色 · BD 团队",
    title: "把判断之前的信息整理工作交出去",
    body: [
      "BD 这个工种最值钱的是判断力，最稀缺的是判断之前不被信息淹没的精力。竞品在研、最近交易、买方动作、临床读出——这些信息散落在十几个数据源里，过去需要 senior 一个人扛。",
      "BD Go 的工作台想替你省掉的就是后者。一个对话框接通了 BD 工作里高频会用到的公开数据源，复杂任务先出计划再跑、简单问题直接答。情报、画像、报告生成留在同一个上下文里，跨多轮对话不掉线。",
    ],
    flow: ["拉竞品 / 交易 / 会议情报", "为目标买方画 BD 战略图", "出竞品对标和 outreach 草稿"],
  },
  {
    id: "role-ic",
    eyebrow: "角色 · 立项委员会",
    title: "让每一份立项材料都有可追溯的论据",
    body: [
      "立项决策最难的不是判断本身，是判断背后的论据能不能交代清楚——为什么这条线、为什么现在、为什么是我们。投决会上一句「差异化窗口」如果没有切片支撑，分量就是直觉。",
      "DEF 把疾病、终点、技术前沿三轴叠在一起，给你看现有管线挤在哪里、空在哪里。AIDD 把候选靶点跑成一份带分数的立项包，每一步的中间产物都摊开。两件工具串起来，立项材料从「叙事」变成「叙事 + 证据」。",
    ],
    flow: ["DEF 切片找差异化窗口", "AIDD 流水线跑成药性 + IP", "导出投决材料 + 风险列表"],
  },
  {
    id: "role-ai4s",
    eyebrow: "角色 · AI4S 研究员",
    title: "把跑通的流水线公开给行业",
    body: [
      "AI4S 这个领域过去几年最不缺的是漂亮的 demo，最缺的是别人能在自己机器上重新跑出同一个数的东西。一条流水线如果只在一个团队的环境里跑得通，就还停留在 demo 阶段。",
      "AIDD 把每一步写成独立脚本、每一步落产物文件、每一步的方法学和阈值写进文档。需要 GPU 的步骤上云端，没有 GPU 的环境用本地的轻量替代——产出会标注是哪条路径出来的，不假装一样。AI4S 实验室是 BD Go 的研究端开放平台，欢迎你的团队把跑通的工作流提交进来。",
    ],
    flow: ["靶点 / 适应症双向反查", "Portfolio 对比与差异化分析", "提交可复现的 notebook"],
  },
  {
    id: "role-ir",
    eyebrow: "角色 · IR / 战略",
    title: "全球管线和交易动向的同一张视图",
    body: [
      "战略和 IR 看的不是单个交易，而是模式：某家 MNC 这一季在补哪条线、某个治疗领域里最近半年的交易溢价怎么走、某条管线和我们手上资产的潜在替代关系。这些判断需要的是横向、纵向都能拉的视图。",
      "BD Go 把全球管线、交易、读出、监管节点放在同一个查询入口。你可以问「过去 18 个月双抗交易的预付款分布」或「某 MNC 肿瘤管线在哪些靶点上有缺口」——结构化结果直接回写到关注列表，下次有动态自动推送。",
    ],
    flow: ["全球管线追踪 + 关注列表", "买方策略横纵对比", "季度 / 周报自动汇总"],
  },
];

const scenarios: Section[] = [
  {
    id: "scene-aacr",
    eyebrow: "场景 · AACR / ASCO 跟会",
    title: "几千份 abstract 里，谁在做什么",
    body: [
      "学术会议是 BD 一年里信息密度最高的几天。AACR / ASCO 几千份 abstract、poster、late-breaking——靠人扫一遍既慢又会漏。重要的不是看完所有，是先看完和你正在跟的靶点 / 适应症 / 中国公司相关的部分。",
      "BD Go 把会议日程接成实时摘要：按公司、靶点、适应症、阶段过滤；中国公司单独聚合一栏；BD 热度高的标记出来。会期开始前就能拉好你的「必看」清单，会期中跟着更新走。",
    ],
    flow: ["按你的关注列表自动过滤", "中国公司聚合 + BD 热度标注", "导出会前 brief 和会后跟进"],
  },
  {
    id: "scene-jpm",
    eyebrow: "场景 · JPM 周尽调",
    title: "一周里把所有要见的公司过一遍",
    body: [
      "JPM 那一周时间是稀缺资源——每天十几场会、每场会前要把对方的管线、最近交易、上一季业绩看一遍。准备工作如果用传统方式做，一个人一晚上只能过两三家。",
      "BD Go 把这件事压缩成批量任务：把要见的公司清单丢进去，工作台并行拉每家的管线、SEC 申报、最近半年的交易和合作动向，出一张「会前一页纸」。会议中拿到新信息，回到工作台直接更新；会后的 follow-up 草稿也在同一个会话里生成。",
    ],
    flow: ["批量公司画像 + 会前一页纸", "现场更新 + 下一场快速切换", "会后 follow-up 草稿一键生成"],
  },
  {
    id: "scene-target",
    eyebrow: "场景 · 靶点立项",
    title: "DEF + AIDD 把立项做成流水线",
    body: [
      "传统的靶点立项是这样：BD 拿回来一个候选靶点，先开会讨论要不要做；定下来要做之后，生信、AI 制药、化学、专利各自启动一段工作；几周之后再开会拼成立项材料。整个过程最大的浪费在等和拼。",
      "BD Go 把这条路径串成一条流水线：DEF 先在三轴上切片找差异化窗口，AIDD 把候选靶点跑成抗体或小分子立项包，最后落到一份带分数的报告。每一步的中间产物都可追溯，立项委员会上能直接看到论据。",
    ],
    flow: ["DEF 三轴切片找窗口", "AIDD 流水线出立项包", "立项材料 + 风险列表导出"],
  },
  {
    id: "scene-comp",
    eyebrow: "场景 · 竞品对标",
    title: "把「我们 vs 竞品」做成一张可更新的雷达",
    body: [
      "竞品对标这件事的难点不在于一次做完，而在于持续更新。今天做完一份「我们 vs 五家竞品」的对标，下个月某家发了 Phase 2 数据、某家拿了授权、某家专利到期了——整张表又要重新拉一遍。",
      "BD Go 把对标做成一张可订阅的雷达：把竞品列入关注列表，管线、IP、交易、临床读出有任何变化都会推送过来；自动生成的对标表在每次有新动态时增量更新，不用每次重做。",
    ],
    flow: ["管线 / IP / 交易雷达订阅", "差异化机会画像（vs. 竞品）", "增量更新对标表"],
  },
];

export default function UseCasesPage() {
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
          按你的角色和场景看 BD Go
        </h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          BD 团队、立项委员会、AI4S 研究员、IR /
          战略——四种角色都在用，都从同一个工作台里取自己要的那一段。
        </p>
      </div>

      {/* Anchor nav */}
      <SectionNav
        groups={[
          [
            "按角色",
            roles.map((r) => [r.id, r.eyebrow.replace(/^角色 · /, "")] as [string, string]),
          ],
          [
            "按场景",
            scenarios.map((s) => [s.id, s.eyebrow.replace(/^场景 · /, "")] as [string, string]),
          ],
        ]}
      />

      <SectionGroup label="按角色" sections={roles} />
      <SectionGroup label="按场景" sections={scenarios} />

      {/* CTA */}
      <div style={{ background: "#1E3A8A", textAlign: "center", padding: "56px 32px" }}>
        <h2 style={{ fontSize: 28, fontWeight: 800, color: "#fff", margin: "0 0 12px" }}>
          找到你的工作流了吗？
        </h2>
        <p style={{ fontSize: 15, color: "#93C5FD", margin: "0 0 28px" }}>
          申请内测，把这条路径在自己的项目上跑一遍。
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

function SectionNav({ groups }: { groups: [string, [string, string][]][] }) {
  return (
    <div
      style={{
        maxWidth: 1100,
        margin: "0 auto 12px",
        padding: "0 32px",
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 32,
      }}
    >
      {groups.map(([label, items]) => (
        <div key={label}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "#64748B",
              letterSpacing: ".12em",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            {label}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {items.map(([id, label]) => (
              <Link
                key={id}
                href={`#${id}`}
                style={{
                  fontSize: 13,
                  color: "#1E3A8A",
                  background: "#fff",
                  border: "1px solid #E8EFFE",
                  borderRadius: 999,
                  padding: "6px 14px",
                  textDecoration: "none",
                  fontWeight: 500,
                }}
              >
                {label}
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function SectionGroup({ label, sections }: { label: string; sections: Section[] }) {
  return (
    <div style={{ maxWidth: 1100, margin: "32px auto 0", padding: "0 32px" }}>
      <div
        style={{
          fontSize: 12,
          fontWeight: 700,
          color: "#64748B",
          letterSpacing: ".12em",
          textTransform: "uppercase",
          margin: "16px 0 20px",
        }}
      >
        {label}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {sections.map((s) => (
          <SectionCard key={s.id} section={s} />
        ))}
      </div>
    </div>
  );
}

function SectionCard({ section }: { section: Section }) {
  return (
    <section
      id={section.id}
      style={{
        background: "#fff",
        borderRadius: 16,
        border: "1px solid #E8EFFE",
        padding: "32px 36px",
        boxShadow: "0 2px 12px rgba(30,58,138,0.05)",
        scrollMarginTop: 80,
        display: "grid",
        gridTemplateColumns: "1.4fr 1fr",
        gap: 36,
      }}
    >
      <div>
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "#2563EB",
            letterSpacing: ".08em",
            textTransform: "uppercase",
            marginBottom: 12,
            fontFamily: "ui-monospace, monospace",
          }}
        >
          {section.eyebrow}
        </div>
        <h3
          style={{
            fontSize: 22,
            fontWeight: 800,
            color: "#0F172A",
            lineHeight: 1.3,
            margin: "0 0 16px",
          }}
        >
          {section.title}
        </h3>
        {section.body.map((p, i) => (
          <p
            key={i}
            style={{ fontSize: 14, color: "#475569", lineHeight: 1.75, margin: "0 0 12px" }}
          >
            {p}
          </p>
        ))}
      </div>
      <div
        style={{
          background: "#F8FAFF",
          borderRadius: 12,
          padding: "20px 22px",
          alignSelf: "start",
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "#64748B",
            letterSpacing: ".1em",
            textTransform: "uppercase",
            marginBottom: 12,
          }}
        >
          典型路径
        </div>
        {section.flow.map((step, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              gap: 10,
              padding: "8px 0",
              borderTop: i === 0 ? "none" : "1px solid #E8EFFE",
            }}
          >
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#2563EB",
                fontFamily: "ui-monospace, monospace",
                minWidth: 18,
              }}
            >
              0{i + 1}
            </span>
            <span style={{ fontSize: 13, color: "#0F172A", lineHeight: 1.5 }}>{step}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
