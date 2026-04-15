"use client";

import Link from "next/link";
import { useState } from "react";
import { LandingNav } from "@/components/LandingNav";

export default function ContactPage() {
  const [sent, setSent] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", company: "", message: "" });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // In production this would POST to an endpoint
    setSent(true);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 640, margin: "0 auto" }}>
        <div style={{ display: "inline-block", fontSize: 12, fontWeight: 700, color: "#2563EB", background: "#EEF2FF", padding: "4px 14px", borderRadius: 20, marginBottom: 20, letterSpacing: "0.05em" }}>联系我们</div>
        <h1 style={{ fontSize: 40, fontWeight: 800, color: "#0F172A", lineHeight: 1.2, margin: "0 0 16px" }}>我们很乐意听取<br />你的想法</h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          无论是试用咨询、定价问题还是合作意向，24 小时内回复。
        </p>
      </div>

      <div style={{ maxWidth: 960, margin: "0 auto", padding: "0 32px 80px", display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: 40 }}>
        {/* Info */}
        <div>
          <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "28px", marginBottom: 16 }}>
            <div style={{ fontSize: 20, marginBottom: 8 }}>📧</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#0F172A", marginBottom: 4 }}>邮件</div>
            <div style={{ fontSize: 13, color: "#2563EB" }}>hello@bdgo.ai</div>
          </div>
          <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "28px", marginBottom: 16 }}>
            <div style={{ fontSize: 20, marginBottom: 8 }}>💬</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#0F172A", marginBottom: 4 }}>微信</div>
            <div style={{ fontSize: 13, color: "#64748B" }}>添加微信 bdgo_support，说明来意</div>
          </div>
          <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "28px" }}>
            <div style={{ fontSize: 20, marginBottom: 8 }}>📍</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#0F172A", marginBottom: 4 }}>地址</div>
            <div style={{ fontSize: 13, color: "#64748B" }}>上海市黄浦区</div>
          </div>
        </div>

        {/* Form */}
        <div style={{ background: "#fff", borderRadius: 20, border: "1px solid #E8EFFE", padding: "36px", boxShadow: "0 4px 20px rgba(30,58,138,0.06)" }}>
          {sent ? (
            <div style={{ textAlign: "center", padding: "40px 0" }}>
              <div style={{ fontSize: 40, marginBottom: 16 }}>✅</div>
              <h3 style={{ fontSize: 20, fontWeight: 700, color: "#0F172A", margin: "0 0 8px" }}>消息已发送</h3>
              <p style={{ fontSize: 14, color: "#64748B" }}>我们会在 24 小时内回复您的邮件。</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 6 }}>姓名</label>
                  <input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="您的姓名" style={{ width: "100%", padding: "10px 12px", fontSize: 13, border: "1px solid #E2E8F0", borderRadius: 9, background: "#FAFBFF", color: "#0F172A", outline: "none", boxSizing: "border-box", fontFamily: "inherit" }} />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 6 }}>邮箱</label>
                  <input required type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="name@company.com" style={{ width: "100%", padding: "10px 12px", fontSize: 13, border: "1px solid #E2E8F0", borderRadius: 9, background: "#FAFBFF", color: "#0F172A", outline: "none", boxSizing: "border-box", fontFamily: "inherit" }} />
                </div>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 6 }}>公司（选填）</label>
                <input value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} placeholder="您的公司名称" style={{ width: "100%", padding: "10px 12px", fontSize: 13, border: "1px solid #E2E8F0", borderRadius: 9, background: "#FAFBFF", color: "#0F172A", outline: "none", boxSizing: "border-box", fontFamily: "inherit" }} />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 6 }}>留言</label>
                <textarea required value={form.message} onChange={e => setForm(f => ({ ...f, message: e.target.value }))} placeholder="请描述您的需求或问题..." rows={5} style={{ width: "100%", padding: "10px 12px", fontSize: 13, border: "1px solid #E2E8F0", borderRadius: 9, background: "#FAFBFF", color: "#0F172A", outline: "none", boxSizing: "border-box", fontFamily: "inherit", resize: "vertical" }} />
              </div>
              <button type="submit" style={{ padding: "13px 0", fontSize: 14, fontWeight: 700, border: "none", borderRadius: 10, background: "linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%)", color: "#fff", cursor: "pointer", fontFamily: "inherit" }}>
                发送消息
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
