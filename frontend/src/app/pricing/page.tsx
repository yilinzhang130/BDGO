"use client";

import Link from "next/link";
import { LandingNav } from "@/components/LandingNav";
import { CheckoutButton } from "@/components/CheckoutButton";

const plans = [
  {
    name: "团队版",
    price: "¥9,800",
    period: "/ 月",
    desc: "适合 BD 团队日常情报查询与报告生成",
    features: [
      "5 个席位",
      "全量数据库访问（公司、资产、临床、交易）",
      "AI 自然语言查询（每月 500 次）",
      "一键生成 BD 报告（7 类，每月 50 份）",
      "催化剂日历",
      "买方匹配引擎",
      "TLS 加密传输",
      "邮件支持",
    ],
    cta: "申请试用",
    planId: "team" as const,
    highlight: false,
  },
  {
    name: "专业版",
    price: "¥24,800",
    period: "/ 月",
    desc: "适合活跃交易团队，无限查询与优先支持",
    features: [
      "15 个席位",
      "全量数据库访问",
      "AI 自然语言查询（无限次）",
      "一键生成 BD 报告（7 类，无限份）",
      "催化剂日历 + 自定义提醒",
      "买方匹配引擎 + 导出",
      "报告专属分享链接",
      "关注列表 + 实时推送",
      "优先客服支持",
    ],
    cta: "申请试用",
    planId: "pro" as const,
    highlight: true,
  },
  {
    name: "企业版",
    price: "定制",
    period: "",
    desc: "大型机构、定制数据集成与私有部署",
    features: [
      "席位数量不限",
      "私有部署可选",
      "定制数据集成与 API",
      "SSO / LDAP 对接",
      "专属客户成功经理",
      "SLA 保障",
      "定制报告模板",
      "培训与入职支持",
    ],
    cta: "联系我们",
    planId: null,
    highlight: false,
  },
];

export default function PricingPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div
        style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 640, margin: "0 auto" }}
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
          }}
        >
          透明定价，按需选择
        </h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          所有版本均包含免费试用期。无隐藏费用，随时可取消。
        </p>
      </div>

      {/* Plans */}
      <div
        style={{
          maxWidth: 1080,
          margin: "0 auto",
          padding: "0 32px 80px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: 24,
          alignItems: "start",
        }}
      >
        {plans.map((p) => (
          <div
            key={p.name}
            style={{
              background: p.highlight ? "#1E3A8A" : "#fff",
              borderRadius: 20,
              border: p.highlight ? "none" : "1px solid #E8EFFE",
              padding: "32px 28px",
              boxShadow: p.highlight
                ? "0 20px 60px rgba(30,58,138,0.25)"
                : "0 2px 12px rgba(30,58,138,0.05)",
              position: "relative",
            }}
          >
            {p.highlight && (
              <div
                style={{
                  position: "absolute",
                  top: -12,
                  left: "50%",
                  transform: "translateX(-50%)",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#1E3A8A",
                  background: "#BFDBFE",
                  padding: "3px 14px",
                  borderRadius: 20,
                  whiteSpace: "nowrap",
                }}
              >
                最受欢迎
              </div>
            )}
            <div
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: p.highlight ? "#93C5FD" : "#64748B",
                marginBottom: 8,
              }}
            >
              {p.name}
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 8 }}>
              <span
                style={{ fontSize: 36, fontWeight: 800, color: p.highlight ? "#fff" : "#0F172A" }}
              >
                {p.price}
              </span>
              {p.period && (
                <span style={{ fontSize: 14, color: p.highlight ? "#93C5FD" : "#94A3B8" }}>
                  {p.period}
                </span>
              )}
            </div>
            <p
              style={{
                fontSize: 13,
                color: p.highlight ? "#BFDBFE" : "#64748B",
                marginBottom: 24,
                lineHeight: 1.6,
              }}
            >
              {p.desc}
            </p>
            {p.planId ? (
              <CheckoutButton planId={p.planId} label={p.cta} highlight={p.highlight} />
            ) : (
              <Link
                href="/contact"
                style={{
                  display: "block",
                  textAlign: "center",
                  padding: "12px 0",
                  borderRadius: 10,
                  fontSize: 14,
                  fontWeight: 700,
                  textDecoration: "none",
                  background: p.highlight ? "#fff" : "#EEF2FF",
                  color: "#1E3A8A",
                  marginBottom: 24,
                }}
              >
                {p.cta}
              </Link>
            )}
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {p.features.map((f) => (
                <li
                  key={f}
                  style={{
                    fontSize: 13,
                    color: p.highlight ? "#DBEAFE" : "#475569",
                    marginBottom: 10,
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                  }}
                >
                  <span
                    style={{
                      color: p.highlight ? "#60A5FA" : "#2563EB",
                      flexShrink: 0,
                      marginTop: 1,
                    }}
                  >
                    ✓
                  </span>
                  {f}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* FAQ note */}
      <div style={{ textAlign: "center", padding: "0 32px 80px" }}>
        <p style={{ fontSize: 14, color: "#94A3B8" }}>
          有疑问？
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
