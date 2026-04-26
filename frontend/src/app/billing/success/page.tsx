"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

const PLAN_NAMES: Record<string, string> = {
  team: "团队版",
  pro: "专业版",
};

function SuccessContent() {
  const params = useSearchParams();
  const plan = params.get("plan") ?? "";
  const planName = PLAN_NAMES[plan] ?? "订阅";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#F8FAFF",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "Inter, sans-serif",
        padding: "32px",
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 20,
          padding: "48px 40px",
          maxWidth: 480,
          width: "100%",
          boxShadow: "0 4px 24px rgba(30,58,138,0.08)",
          textAlign: "center",
        }}
      >
        {/* Checkmark */}
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            background: "#DCFCE7",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 24px",
          }}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <path
              d="M5 13l4 4L19 7"
              stroke="#16A34A"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        <h1
          style={{
            fontSize: 28,
            fontWeight: 800,
            color: "#0F172A",
            margin: "0 0 12px",
          }}
        >
          订阅成功！
        </h1>

        <p style={{ fontSize: 16, color: "#64748B", lineHeight: 1.6, margin: "0 0 8px" }}>
          欢迎使用 BD Go <strong style={{ color: "#1E3A8A" }}>{planName}</strong>。
        </p>
        <p style={{ fontSize: 14, color: "#94A3B8", lineHeight: 1.6, margin: "0 0 36px" }}>
          您的额度已自动充值，现在可以开始使用所有功能。
        </p>

        <Link
          href="/chat"
          style={{
            display: "inline-block",
            padding: "13px 32px",
            borderRadius: 12,
            background: "linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%)",
            color: "#fff",
            fontWeight: 700,
            fontSize: 15,
            textDecoration: "none",
            boxShadow: "0 4px 14px rgba(30,58,138,0.3)",
          }}
        >
          开始使用 →
        </Link>

        <p style={{ marginTop: 20, fontSize: 13, color: "#94A3B8" }}>
          账单问题请{" "}
          <Link href="/contact" style={{ color: "#2563EB", textDecoration: "none" }}>
            联系支持
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function BillingSuccessPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", background: "#F8FAFF" }} />}>
      <SuccessContent />
    </Suspense>
  );
}
