"use client";

import Link from "next/link";
import { useState } from "react";
import { BDGoMark, LandingNav } from "@/components/LandingNav";

const BG = "#F5F4EE";
const CARD = "#FFFDF7";
const BORDER = "#DCD8CB";
const TEXT = "#1A1814";
const TEXT2 = "#52504A";
const BRAND = "#1E3A8A";
const ACCENT = "#2563EB";

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "11px 14px",
  fontSize: 14,
  border: `1px solid ${BORDER}`,
  borderRadius: 10,
  background: BG,
  color: TEXT,
  outline: "none",
  boxSizing: "border-box",
  fontFamily: "inherit",
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 700,
  color: TEXT,
  display: "block",
  marginBottom: 6,
  letterSpacing: "0.02em",
};

export default function ApplyPage() {
  const [sent, setSent] = useState(false);
  const [form, setForm] = useState({
    name: "",
    company: "",
    email: "",
    role: "",
    reason: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const subject = `[BD Go 申请试用] ${form.company} · ${form.name}`;
    const body = [
      `姓名: ${form.name}`,
      `公司: ${form.company}`,
      `邮箱: ${form.email}`,
      `职位: ${form.role}`,
      "",
      "为什么需要 BD Go：",
      form.reason,
    ].join("\n");
    window.location.href = `mailto:hello@bdgo.ai?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    setSent(true);
  };

  return (
    <div style={{ minHeight: "100vh", background: BG, fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      <div
        style={{
          maxWidth: 520,
          margin: "0 auto",
          padding: "64px 24px 80px",
        }}
      >
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              background: CARD,
              border: `1px solid ${BORDER}`,
              borderRadius: 20,
              padding: "5px 14px 5px 10px",
              marginBottom: 24,
            }}
          >
            <BDGoMark size={20} />
            <span style={{ fontSize: 12, fontWeight: 700, color: BRAND, letterSpacing: "0.04em" }}>
              申请早期访问
            </span>
          </div>

          <h1
            style={{
              fontSize: 36,
              fontWeight: 800,
              color: TEXT,
              lineHeight: 1.2,
              letterSpacing: "-0.02em",
              margin: "0 0 14px",
            }}
          >
            让判断先于信息
          </h1>
          <p style={{ fontSize: 15, color: TEXT2, lineHeight: 1.7, margin: 0 }}>
            BD Go 现在面向邀请制早期团队开放。告诉我们你的工作背景，
            我们会在 2 个工作日内回复并发送邀请码。
          </p>
        </div>

        {/* Form card */}
        <div
          style={{
            background: CARD,
            borderRadius: 20,
            border: `1px solid ${BORDER}`,
            padding: "36px 32px",
            boxShadow: "0 2px 16px rgba(26,24,20,0.06)",
          }}
        >
          {sent ? (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: "50%",
                  background: "#F0FDF4",
                  border: "1px solid #BBF7D0",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 20px",
                  fontSize: 24,
                }}
              >
                ✓
              </div>
              <h3
                style={{ fontSize: 20, fontWeight: 700, color: TEXT, margin: "0 0 10px" }}
              >
                申请已提交
              </h3>
              <p style={{ fontSize: 14, color: TEXT2, lineHeight: 1.6, margin: "0 0 24px" }}>
                我们会在 2 个工作日内审核并发送邀请码到你的邮箱。
                如有急需可直接联系{" "}
                <a href="mailto:hello@bdgo.ai" style={{ color: ACCENT }}>
                  hello@bdgo.ai
                </a>
              </p>
              <Link
                href="/"
                style={{
                  fontSize: 13,
                  color: TEXT2,
                  textDecoration: "none",
                  borderBottom: `1px solid ${BORDER}`,
                  paddingBottom: 1,
                }}
              >
                ← 返回首页
              </Link>
            </div>
          ) : (
            <form
              onSubmit={handleSubmit}
              style={{ display: "flex", flexDirection: "column", gap: 18 }}
            >
              {/* Name + Company */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={labelStyle}>姓名</label>
                  <input
                    required
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="你的姓名"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>
                    公司 / 机构{" "}
                    <span style={{ color: ACCENT, fontWeight: 400 }}>*</span>
                  </label>
                  <input
                    required
                    value={form.company}
                    onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))}
                    placeholder="公司或机构名称"
                    style={inputStyle}
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label style={labelStyle}>
                  工作邮箱 <span style={{ color: ACCENT, fontWeight: 400 }}>*</span>
                </label>
                <input
                  required
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="name@company.com"
                  style={inputStyle}
                />
              </div>

              {/* Role */}
              <div>
                <label style={labelStyle}>职位 / 角色</label>
                <input
                  value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                  placeholder="BD 总监 / 立项负责人 / CSO …"
                  style={inputStyle}
                />
              </div>

              {/* Why */}
              <div>
                <label style={labelStyle}>
                  为什么需要 BD Go？{" "}
                  <span style={{ color: ACCENT, fontWeight: 400 }}>*</span>
                </label>
                <textarea
                  required
                  value={form.reason}
                  onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
                  placeholder="描述你们团队目前的工作流、主要卡点，或你期望用 BD Go 解决什么问题……"
                  rows={5}
                  style={{ ...inputStyle, resize: "vertical", lineHeight: 1.6 }}
                />
                <div style={{ fontSize: 11, color: TEXT2, marginTop: 6, opacity: 0.7 }}>
                  越具体越好，这帮助我们优先安排与你最匹配的团队对接。
                </div>
              </div>

              {/* Submit */}
              <button
                type="submit"
                style={{
                  marginTop: 4,
                  padding: "14px 0",
                  fontSize: 14,
                  fontWeight: 700,
                  border: "none",
                  borderRadius: 10,
                  background: BRAND,
                  color: "#fff",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  letterSpacing: "0.01em",
                }}
              >
                提交申请
              </button>

              <p style={{ fontSize: 11, color: TEXT2, textAlign: "center", margin: 0, opacity: 0.7 }}>
                提交即表示同意我们的{" "}
                <Link href="/privacy" style={{ color: TEXT2 }}>
                  隐私政策
                </Link>{" "}
                与{" "}
                <Link href="/terms" style={{ color: TEXT2 }}>
                  服务条款
                </Link>
              </p>
            </form>
          )}
        </div>

        {/* Social proof */}
        <div style={{ marginTop: 32, textAlign: "center" }}>
          <p style={{ fontSize: 12, color: TEXT2, opacity: 0.6, margin: "0 0 16px" }}>
            已有来自国内外多家 biotech 和基金的 BD 团队在使用
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: 24, flexWrap: "wrap" }}>
            {["邀请制内测", "48 h 响应", "专属对接"].map((item) => (
              <div
                key={item}
                style={{
                  fontSize: 11,
                  color: TEXT2,
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  opacity: 0.75,
                }}
              >
                <span
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: BRAND,
                    display: "inline-block",
                    opacity: 0.6,
                  }}
                />
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
