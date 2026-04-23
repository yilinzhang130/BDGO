import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

// Curated list of public endpoints. Source-of-truth is the @public_api
// decorator on the backend — if you add a new public endpoint there, also
// append it here so the landing copy stays accurate. For the interactive
// reference use the Swagger UI button below.
const endpoints = [
  { method: "GET", path: "/api/companies", desc: "公司列表，支持分页与关键词过滤" },
  { method: "GET", path: "/api/companies/{name}", desc: "单家公司详细信息" },
  { method: "GET", path: "/api/companies/{name}/assets", desc: "某公司的管线资产" },
  { method: "GET", path: "/api/companies/{name}/trials", desc: "某公司的临床试验" },
  { method: "GET", path: "/api/companies/{name}/deals", desc: "某公司的授权交易记录" },
  { method: "GET", path: "/api/assets", desc: "管线资产列表，支持按靶点、适应症、阶段过滤" },
  { method: "GET", path: "/api/assets/{company}/{name}", desc: "单个资产详情" },
  { method: "GET", path: "/api/clinical", desc: "临床试验数据，支持按 NCT / 公司 / 状态查询" },
  { method: "GET", path: "/api/clinical/{record_id}", desc: "单条临床记录" },
  { method: "GET", path: "/api/deals", desc: "授权交易记录，支持按年份、类型、金额过滤" },
  { method: "GET", path: "/api/deals/{name}", desc: "单笔交易详情" },
  { method: "GET", path: "/api/buyers", desc: "MNC 买方画像列表" },
  { method: "GET", path: "/api/buyers/{name}", desc: "单个 MNC 画像详情" },
  { method: "GET", path: "/api/search/global", desc: "跨表全文搜索，中文双字符模糊匹配" },
];

const methodColor: Record<string, string> = {
  GET: "#059669",
  POST: "#2563EB",
  PUT: "#D97706",
  DELETE: "#DC2626",
};

export default function ApiDocsPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      {/* Hero */}
      <div
        style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 680, margin: "0 auto" }}
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
          API 接入
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
          把 BD Go 数据
          <br />
          接入你的工作流
        </h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          REST API，X-API-Key 认证，支持 Python / Node.js / cURL，可直接在 Swagger 中试用。
        </p>

        {/* Primary CTAs */}
        <div
          style={{
            display: "flex",
            gap: 12,
            justifyContent: "center",
            marginTop: 28,
            flexWrap: "wrap",
          }}
        >
          <Link
            href="/api/public/docs"
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "#fff",
              background: "#1E3A8A",
              padding: "12px 24px",
              borderRadius: 10,
              textDecoration: "none",
            }}
          >
            打开交互式文档 →
          </Link>
          <Link
            href="/settings/api-keys"
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "#1E3A8A",
              background: "#fff",
              border: "1px solid #1E3A8A",
              padding: "11px 24px",
              borderRadius: 10,
              textDecoration: "none",
            }}
          >
            生成 API Key
          </Link>
        </div>
      </div>

      {/* Auth note */}
      <div style={{ maxWidth: 800, margin: "0 auto 40px", padding: "0 32px" }}>
        <div
          style={{
            background: "#FFF7ED",
            border: "1px solid #FED7AA",
            borderRadius: 12,
            padding: "16px 20px",
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 700, color: "#C2410C", marginBottom: 8 }}>
            认证方式
          </div>
          <div
            style={{
              fontSize: 13,
              color: "#1E3A8A",
              fontFamily: "monospace",
              background: "#F3F0FF",
              padding: "8px 12px",
              borderRadius: 8,
            }}
          >
            X-API-Key: bdgo_live_xxxxxxxx
          </div>
          <div style={{ fontSize: 12, color: "#92400E", marginTop: 10, lineHeight: 1.6 }}>
            在{" "}
            <Link href="/settings/api-keys" style={{ color: "#1E3A8A", fontWeight: 600 }}>
              账户设置 → API Keys
            </Link>{" "}
            页创建 key。完整值仅在创建时显示一次，之后只保留前缀用于识别。吊销即刻生效。
          </div>
        </div>
      </div>

      {/* Endpoints */}
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 32px 80px" }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#0F172A", marginBottom: 20 }}>
          公开端点
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {endpoints.map((ep) => (
            <div
              key={`${ep.method}-${ep.path}`}
              style={{
                background: "#fff",
                border: "1px solid #E8EFFE",
                borderRadius: 12,
                padding: "16px 20px",
                display: "flex",
                alignItems: "flex-start",
                gap: 16,
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: methodColor[ep.method] || "#374151",
                  background: "#F0FDF4",
                  padding: "3px 8px",
                  borderRadius: 6,
                  flexShrink: 0,
                  fontFamily: "monospace",
                  marginTop: 1,
                }}
              >
                {ep.method}
              </span>
              <div>
                <div
                  style={{
                    fontSize: 13,
                    fontFamily: "monospace",
                    color: "#1E3A8A",
                    marginBottom: 4,
                  }}
                >
                  {ep.path}
                </div>
                <div style={{ fontSize: 13, color: "#64748B" }}>{ep.desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Python example */}
        <div style={{ background: "#1E293B", borderRadius: 12, padding: "24px", marginTop: 40 }}>
          <div
            style={{ fontSize: 12, color: "#94A3B8", marginBottom: 12, fontFamily: "monospace" }}
          >
            示例 — Python
          </div>
          <pre
            style={{
              margin: 0,
              fontSize: 13,
              color: "#E2E8F0",
              fontFamily: "monospace",
              lineHeight: 1.6,
              overflowX: "auto",
              whiteSpace: "pre-wrap",
            }}
          >{`import requests

API_KEY = "bdgo_live_xxxxxxxx"
BASE = "https://api.bdgo.ai"

# 查询近两年 GLP-1 交易
r = requests.get(
    f"{BASE}/api/deals",
    params={"q": "GLP-1"},
    headers={"X-API-Key": API_KEY},
)
print(r.json())`}</pre>
        </div>

        {/* cURL example */}
        <div style={{ background: "#1E293B", borderRadius: 12, padding: "24px", marginTop: 16 }}>
          <div
            style={{ fontSize: 12, color: "#94A3B8", marginBottom: 12, fontFamily: "monospace" }}
          >
            示例 — cURL
          </div>
          <pre
            style={{
              margin: 0,
              fontSize: 13,
              color: "#E2E8F0",
              fontFamily: "monospace",
              lineHeight: 1.6,
              overflowX: "auto",
              whiteSpace: "pre-wrap",
            }}
          >{`curl "https://api.bdgo.ai/api/companies?q=biotech&page=1" \\
  -H "X-API-Key: bdgo_live_xxxxxxxx"`}</pre>
        </div>

        {/* Node example */}
        <div style={{ background: "#1E293B", borderRadius: 12, padding: "24px", marginTop: 16 }}>
          <div
            style={{ fontSize: 12, color: "#94A3B8", marginBottom: 12, fontFamily: "monospace" }}
          >
            示例 — Node.js (fetch)
          </div>
          <pre
            style={{
              margin: 0,
              fontSize: 13,
              color: "#E2E8F0",
              fontFamily: "monospace",
              lineHeight: 1.6,
              overflowX: "auto",
              whiteSpace: "pre-wrap",
            }}
          >{`const res = await fetch(
  "https://api.bdgo.ai/api/assets?phase=Phase%203",
  { headers: { "X-API-Key": process.env.BDGO_API_KEY } }
);
const data = await res.json();`}</pre>
        </div>

        <div style={{ textAlign: "center", marginTop: 48 }}>
          <p style={{ fontSize: 14, color: "#64748B", marginBottom: 16 }}>
            需要更高配额 / 自定义端点？
          </p>
          <Link
            href="/contact"
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "#fff",
              background: "#1E3A8A",
              padding: "12px 28px",
              borderRadius: 10,
              textDecoration: "none",
            }}
          >
            联系销售
          </Link>
        </div>
      </div>
    </div>
  );
}
