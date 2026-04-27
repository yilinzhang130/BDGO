import Link from "next/link";
import { LandingNav } from "@/components/LandingNav";

const BG = "#F5F4EE";
const CARD = "#FFFDF7";
const BORDER = "#DCD8CB";
const TEXT = "#1A1814";
const TEXT2 = "#52504A";
const TEXT3 = "#8A8780";
const BRAND = "#1E3A8A";

const releases = [
  {
    version: "v0.9.2",
    date: "2026-04-26",
    badge: "最新",
    title: "AIDD 流水线 GA",
    summary:
      "把「立项」从一份 PPT 变成一条可复现的流水线。AIDD 抗体与小分子两条路径打通，从靶点到立项包端到端跑通。",
    items: [
      "抗体和小分子两条 AIDD 路径正式 GA",
      "云端 GPU（Modal）调度，无 GPU 环境自动降级到本地 CPU",
      "每一步产物落盘，支持断点续跑与中间结果复用",
      "ROR1 抗体立项作为 flagship 示例开箱即用",
      "立项打分自动回写 BD Go 资产库（Beta）",
    ],
    next: [
      "更多抗原模板（多链、糖基化、复合物）",
      "小分子合成路径预测接入",
      "AIDD 立项分数与 BD Go 资产库深度集成",
    ],
  },
  {
    version: "v0.9.1",
    date: "2026-04-12",
    badge: null,
    title: "DEF 痛点引擎公测",
    summary:
      "BD Go 拉回来的情报越来越多，下一个问题是：哪条值得往前走一步？DEF 把疾病、终点、技术前沿三轴叠起来，找出还没被占住的窗口。",
    items: [
      "DEF（Disease × Endpoint × Frontier）三轴切片引擎公测上线",
      "面向 BD Go 受邀团队开放，支持历史项目喂入校准",
      "切片结果可直接对接资产库",
      "公测期间持续校准三轴口径",
    ],
    next: [
      "催化剂日历接得更深（临床读出 / 监管决策 / 里程碑节点）",
      "会议洞察升级到摘要 + BD 热度",
    ],
  },
  {
    version: "v0.9.0",
    date: "2026-03-20",
    badge: null,
    title: "BD GO 工作台开放",
    summary:
      "BD Go 的对话工作台正式开放给所有受邀团队。一个输入框，连着一整条 BD 工作流。",
    items: [
      "对话工作台向所有受邀团队开放",
      "接通监管申报、临床试验、文献、学术会议等公开数据源",
      "Plan Mode：复杂任务先展示执行步骤，简单问题直接答",
      "报告产出支持 Word / Excel / Markdown，可编辑可分享",
      "Share 链接对外发布，对方无需账号即可查看",
      "团队协作：历史会话、关注列表、团队共享、通知中心就绪",
    ],
    next: [],
  },
];

export default function ChangelogPage() {
  return (
    <div style={{ minHeight: "100vh", background: BG, fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "64px 32px 48px", maxWidth: 640, margin: "0 auto" }}>
        <div
          style={{
            display: "inline-block",
            fontSize: 11,
            fontWeight: 700,
            color: BRAND,
            background: CARD,
            border: `1px solid ${BORDER}`,
            padding: "4px 14px",
            borderRadius: 20,
            marginBottom: 20,
            letterSpacing: "0.06em",
          }}
        >
          CHANGELOG
        </div>
        <h1
          style={{
            fontSize: 40,
            fontWeight: 800,
            color: TEXT,
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
            margin: "0 0 16px",
          }}
        >
          版本更新记录
        </h1>
        <p style={{ fontSize: 16, color: TEXT2, lineHeight: 1.7, margin: 0 }}>
          每一个版本都在让「从问题到报告」的路径更短。
        </p>
      </div>

      {/* Timeline */}
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "0 32px 96px" }}>
        <div style={{ position: "relative" }}>
          {/* Vertical line */}
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 8,
              bottom: 0,
              width: 1,
              background: BORDER,
            }}
          />

          {releases.map((r, i) => (
            <div
              key={r.version}
              style={{
                position: "relative",
                paddingLeft: 32,
                marginBottom: i < releases.length - 1 ? 48 : 0,
              }}
            >
              {/* Dot */}
              <div
                style={{
                  position: "absolute",
                  left: -5,
                  top: 10,
                  width: 11,
                  height: 11,
                  borderRadius: "50%",
                  background: i === 0 ? BRAND : BORDER,
                  border: `2px solid ${BG}`,
                  outline: `1px solid ${i === 0 ? BRAND : BORDER}`,
                }}
              />

              {/* Card */}
              <div
                style={{
                  background: CARD,
                  borderRadius: 16,
                  border: `1px solid ${BORDER}`,
                  padding: "28px 32px",
                  boxShadow: i === 0 ? "0 2px 16px rgba(26,24,20,0.07)" : "none",
                }}
              >
                {/* Version header */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    marginBottom: 12,
                    flexWrap: "wrap",
                  }}
                >
                  <span
                    style={{
                      fontFamily: '"SF Mono", "Fira Code", monospace',
                      fontSize: 13,
                      fontWeight: 700,
                      color: BRAND,
                    }}
                  >
                    {r.version}
                  </span>
                  {r.badge && (
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        letterSpacing: "0.08em",
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: `${BRAND}18`,
                        color: BRAND,
                      }}
                    >
                      {r.badge}
                    </span>
                  )}
                  <span style={{ fontSize: 12, color: TEXT3 }}>{r.date}</span>
                </div>

                <h2
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: TEXT,
                    margin: "0 0 10px",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {r.title}
                </h2>

                <p style={{ fontSize: 14, color: TEXT2, lineHeight: 1.7, margin: "0 0 20px" }}>
                  {r.summary}
                </p>

                {/* What's new */}
                <div style={{ marginBottom: r.next.length ? 20 : 0 }}>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: TEXT3,
                      letterSpacing: "0.08em",
                      marginBottom: 10,
                    }}
                  >
                    本版更新
                  </div>
                  <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                    {r.items.map((item) => (
                      <li
                        key={item}
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 8,
                          fontSize: 13.5,
                          color: TEXT2,
                          lineHeight: 1.6,
                          marginBottom: 6,
                        }}
                      >
                        <span style={{ color: BRAND, marginTop: 1, flexShrink: 0 }}>·</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Next */}
                {r.next.length > 0 && (
                  <div
                    style={{
                      borderTop: `1px solid ${BORDER}`,
                      paddingTop: 16,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: TEXT3,
                        letterSpacing: "0.08em",
                        marginBottom: 10,
                      }}
                    >
                      下一版计划
                    </div>
                    <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                      {r.next.map((item) => (
                        <li
                          key={item}
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 8,
                            fontSize: 13,
                            color: TEXT3,
                            lineHeight: 1.6,
                            marginBottom: 5,
                          }}
                        >
                          <span style={{ marginTop: 1, flexShrink: 0 }}>○</span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Footer CTA */}
        <div
          style={{
            marginTop: 56,
            textAlign: "center",
            padding: "32px",
            background: CARD,
            borderRadius: 16,
            border: `1px solid ${BORDER}`,
          }}
        >
          <p style={{ fontSize: 14, color: TEXT2, margin: "0 0 16px" }}>
            想第一时间收到版本更新通知？
          </p>
          <Link
            href="/apply"
            style={{
              display: "inline-block",
              fontSize: 13,
              fontWeight: 700,
              color: "#fff",
              background: BRAND,
              padding: "10px 24px",
              borderRadius: 8,
              textDecoration: "none",
            }}
          >
            申请早期访问
          </Link>
        </div>
      </div>
    </div>
  );
}
