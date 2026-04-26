import Link from "next/link";

export default function BillingCancelPage() {
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
        {/* X icon */}
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            background: "#FEF2F2",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 24px",
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path
              d="M18 6L6 18M6 6l12 12"
              stroke="#DC2626"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
          </svg>
        </div>

        <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0F172A", margin: "0 0 12px" }}>
          付款已取消
        </h1>
        <p style={{ fontSize: 15, color: "#64748B", lineHeight: 1.6, margin: "0 0 36px" }}>
          未完成付款，您的账户未产生任何费用。
          <br />
          如有疑问，请随时联系我们。
        </p>

        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <Link
            href="/pricing"
            style={{
              padding: "12px 24px",
              borderRadius: 10,
              background: "#EEF2FF",
              color: "#1E3A8A",
              fontWeight: 700,
              fontSize: 14,
              textDecoration: "none",
            }}
          >
            重新查看方案
          </Link>
          <Link
            href="/chat"
            style={{
              padding: "12px 24px",
              borderRadius: 10,
              background: "#1E3A8A",
              color: "#fff",
              fontWeight: 700,
              fontSize: 14,
              textDecoration: "none",
            }}
          >
            继续使用免费版
          </Link>
        </div>
      </div>
    </div>
  );
}
