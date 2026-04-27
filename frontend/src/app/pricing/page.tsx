"use client";

import Link from "next/link";
import { useState } from "react";
import { LandingNav } from "@/components/LandingNav";
import { CheckoutButton } from "@/components/CheckoutButton";

type Plan = {
  id: string;
  name: string;
  tagline: string;
  monthly: number | null;
  annual: number | null;
  priceLabel?: string;
  desc: string;
  features: string[];
  cta: string;
  ctaHref?: string;
  planId: "team" | "pro" | null;
  highlight: boolean;
};

const plans: Plan[] = [
  {
    id: "free",
    name: "Free",
    tagline: "先看看产品长什么样",
    monthly: 0,
    annual: 0,
    desc: "无需绑卡，体验 BD Go 的对话工作台和公开数据浏览。",
    features: [
      "每月 30 次 AI 查询",
      "公开公司 / 资产 / 临床 / 交易浏览",
      "1 份示例 BD 报告",
      "社区文档与白皮书访问",
    ],
    cta: "免费开始",
    ctaHref: "/login",
    planId: null,
    highlight: false,
  },
  {
    id: "team",
    name: "Team",
    tagline: "BD 团队日常使用",
    monthly: 9800,
    annual: 8134,
    desc: "适合一支 BD 团队的日常情报查询、尽调与报告生成。",
    features: [
      "5 个席位",
      "全量数据库访问（公司 / 资产 / 临床 / 交易 / 专利）",
      "每月 500 次 AI 查询",
      "每月 50 份 BD 报告",
      "催化剂日历 + 关注列表",
      "买方匹配引擎",
      "邮件支持",
    ],
    cta: "开始订阅",
    planId: "team",
    highlight: false,
  },
  {
    id: "pro",
    name: "Pro",
    tagline: "活跃交易团队 · 几乎天天用",
    monthly: 24800,
    annual: 20584,
    desc: "适合交易频次高的团队，不限查询、优先支持，DEF 立项引擎接入。",
    features: [
      "15 个席位",
      "不限次 AI 查询",
      "不限份 BD 报告",
      "DEF 痛点引擎 · 立项打分接入",
      "催化剂日历 + 自定义提醒",
      "买方匹配引擎 + 导出",
      "报告专属分享链接",
      "优先客服支持",
    ],
    cta: "开始订阅",
    planId: "pro",
    highlight: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    tagline: "全公司部署 · 数据合规要求高",
    monthly: null,
    annual: null,
    priceLabel: "联系销售",
    desc: "面向大型机构，AIDD 流水线接入、私有部署、定制数据集成。",
    features: [
      "席位数量不限",
      "AIDD 流水线接入（抗体 / 小分子）",
      "私有部署可选",
      "SSO / LDAP 对接",
      "定制数据集成与 API",
      "专属客户成功经理",
      "SLA 保障",
      "培训与入职支持",
    ],
    cta: "联系销售",
    ctaHref: "/contact",
    planId: null,
    highlight: false,
  },
];

const formatPrice = (n: number | null) => {
  if (n === null) return "";
  if (n === 0) return "¥0";
  return `¥${n.toLocaleString("en-US")}`;
};

export default function PricingPage() {
  const [annual, setAnnual] = useState(false);

  return (
    <div style={{ minHeight: "100vh", background: "#F5F4EE", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div
        style={{ textAlign: "center", padding: "72px 32px 32px", maxWidth: 720, margin: "0 auto" }}
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
          定价
        </div>
        <h1
          style={{
            fontSize: 40,
            fontWeight: 800,
            color: "#0F172A",
            lineHeight: 1.2,
            margin: "0 0 16px",
            letterSpacing: "-0.02em",
          }}
        >
          按你用 BD Go 的频率付费
        </h1>
        <p style={{ fontSize: 16, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          每个档位都有月付和年付，年付立省一档左右。无隐藏费用，随时可取消。
        </p>
      </div>

      {/* Billing toggle */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          padding: "0 32px 36px",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            background: "#fff",
            borderRadius: 999,
            border: "1px solid #E8EFFE",
            padding: 4,
            boxShadow: "0 2px 8px rgba(30,58,138,0.04)",
          }}
        >
          {[
            ["月付", false],
            ["年付  -17%", true],
          ].map(([label, val]) => {
            const active = annual === val;
            return (
              <button
                key={String(val)}
                onClick={() => setAnnual(val as boolean)}
                style={{
                  border: "none",
                  background: active ? "#1E3A8A" : "transparent",
                  color: active ? "#fff" : "#64748B",
                  padding: "8px 20px",
                  borderRadius: 999,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  transition: "all 0.15s",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Plans */}
      <div
        style={{
          maxWidth: 1280,
          margin: "0 auto",
          padding: "0 32px 64px",
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
          alignItems: "stretch",
        }}
      >
        {plans.map((p) => (
          <PlanCard key={p.id} plan={p} annual={annual} />
        ))}
      </div>

      {/* Annual note */}
      <div style={{ textAlign: "center", padding: "0 32px 24px" }}>
        <p style={{ fontSize: 12, color: "#94A3B8", margin: 0 }}>
          年付价格按月折算显示。所有付费档位 7 天无理由退订。
        </p>
      </div>

      {/* Why these tiers */}
      <div
        style={{
          background: "#fff",
          borderTop: "1px solid #E8EFFE",
          padding: "64px 32px",
        }}
      >
        <div style={{ maxWidth: 880, margin: "0 auto" }}>
          <h2
            style={{
              fontSize: 22,
              fontWeight: 800,
              color: "#0F172A",
              textAlign: "center",
              margin: "0 0 36px",
              letterSpacing: "-0.01em",
            }}
          >
            选哪一档？
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {[
              [
                "如果你只是想看看 BD Go 长什么样",
                "Free 够了。每月 30 次查询足够走完一个真实尽调流程，不绑卡。",
              ],
              [
                "如果你的 BD 团队 5 人左右、每周出几份报告",
                "Team。500 次查询和 50 份报告对一支稳定运转的 BD 小队来说是宽松的。",
              ],
              [
                "如果你的团队几乎天天泡在工作台里、做立项也用 DEF",
                "Pro。不限次查询，加上 DEF 立项打分的接入——这是大多数活跃交易团队选的档位。",
              ],
              [
                "如果你需要 AIDD 流水线、私有部署或 SSO",
                "Enterprise。这一档不公开报价是因为每家集成都不一样，我们直接对接。",
              ],
            ].map(([q, a]) => (
              <div
                key={q}
                style={{
                  background: "#F5F4EE",
                  border: "1px solid #E8EFFE",
                  borderRadius: 12,
                  padding: "20px 24px",
                }}
              >
                <div style={{ fontSize: 14, fontWeight: 700, color: "#0F172A", marginBottom: 6 }}>
                  {q}
                </div>
                <div style={{ fontSize: 13.5, color: "#475569", lineHeight: 1.7 }}>{a}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* FAQ note */}
      <div style={{ textAlign: "center", padding: "48px 32px 80px" }}>
        <p style={{ fontSize: 14, color: "#94A3B8" }}>
          还有疑问？
          <Link
            href="/contact"
            style={{ color: "#2563EB", textDecoration: "none", fontWeight: 600 }}
          >
            联系我们
          </Link>
          ，我们在 24 小时内回复。
        </p>
      </div>
    </div>
  );
}

function PlanCard({ plan, annual }: { plan: Plan; annual: boolean }) {
  const price = annual ? plan.annual : plan.monthly;
  const showPeriod = price !== null && price > 0;
  return (
    <div
      id={plan.id}
      style={{
        background: plan.highlight ? "#1E3A8A" : "#fff",
        borderRadius: 18,
        border: plan.highlight ? "none" : "1px solid #E8EFFE",
        padding: "28px 24px",
        boxShadow: plan.highlight
          ? "0 16px 48px rgba(30,58,138,0.20)"
          : "0 2px 12px rgba(30,58,138,0.05)",
        position: "relative",
        scrollMarginTop: 80,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {plan.highlight && (
        <div
          style={{
            position: "absolute",
            top: -10,
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: 10,
            fontWeight: 700,
            color: "#1E3A8A",
            background: "#BFDBFE",
            padding: "3px 12px",
            borderRadius: 999,
            whiteSpace: "nowrap",
            letterSpacing: ".05em",
          }}
        >
          推荐
        </div>
      )}
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: plan.highlight ? "#93C5FD" : "#0F172A",
          marginBottom: 4,
          letterSpacing: ".02em",
        }}
      >
        {plan.name}
      </div>
      <div
        style={{
          fontSize: 12,
          color: plan.highlight ? "#BFDBFE" : "#94A3B8",
          marginBottom: 14,
          lineHeight: 1.4,
          minHeight: 32,
        }}
      >
        {plan.tagline}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 4 }}>
        <span
          style={{
            fontSize: 32,
            fontWeight: 800,
            color: plan.highlight ? "#fff" : "#0F172A",
            letterSpacing: "-0.02em",
          }}
        >
          {plan.priceLabel ?? formatPrice(price)}
        </span>
        {showPeriod && (
          <span style={{ fontSize: 13, color: plan.highlight ? "#93C5FD" : "#94A3B8" }}>/ 月</span>
        )}
      </div>
      <div
        style={{
          fontSize: 11,
          color: plan.highlight ? "#BFDBFE" : "#94A3B8",
          marginBottom: 16,
          minHeight: 16,
        }}
      >
        {annual && price && price > 0 ? "按年付折算" : showPeriod ? "按月付" : ""}
      </div>
      <p
        style={{
          fontSize: 12.5,
          color: plan.highlight ? "#DBEAFE" : "#64748B",
          marginBottom: 20,
          lineHeight: 1.6,
          minHeight: 60,
        }}
      >
        {plan.desc}
      </p>
      {plan.planId ? (
        <CheckoutButton planId={plan.planId} label={plan.cta} highlight={plan.highlight} />
      ) : (
        <Link
          href={plan.ctaHref ?? "/contact"}
          style={{
            display: "block",
            textAlign: "center",
            padding: "11px 0",
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 700,
            textDecoration: "none",
            background: plan.highlight ? "#fff" : "#EEF2FF",
            color: "#1E3A8A",
            marginBottom: 20,
          }}
        >
          {plan.cta}
        </Link>
      )}
      <ul style={{ margin: 0, padding: 0, listStyle: "none", flex: 1 }}>
        {plan.features.map((f) => (
          <li
            key={f}
            style={{
              fontSize: 12.5,
              color: plan.highlight ? "#DBEAFE" : "#475569",
              marginBottom: 9,
              display: "flex",
              alignItems: "flex-start",
              gap: 8,
              lineHeight: 1.5,
            }}
          >
            <span
              style={{
                color: plan.highlight ? "#60A5FA" : "#2563EB",
                flexShrink: 0,
                marginTop: 1,
                fontSize: 11,
              }}
            >
              ✓
            </span>
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}
