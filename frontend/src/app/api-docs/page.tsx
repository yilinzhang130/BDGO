import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";

const endpoints = [
  { method: "GET", path: "/api/companies", desc: "查询公司列表，支持分页与关键词过滤" },
  { method: "GET", path: "/api/companies/{id}", desc: "获取单家公司详细信息" },
  { method: "GET", path: "/api/assets", desc: "管线资产列表，支持按靶点、适应症、阶段过滤" },
  { method: "GET", path: "/api/clinical", desc: "临床试验数据，支持按 NCT 编号、公司、状态查询" },
  { method: "GET", path: "/api/deals", desc: "授权交易记录，支持按年份、类型、金额区间过滤" },
  { method: "POST", path: "/api/chat", desc: "AI 自然语言查询接口，流式返回（SSE）" },
  { method: "POST", path: "/api/reports/{type}", desc: "触发报告生成任务，返回 task_id" },
  { method: "GET", path: "/api/reports/tasks/{task_id}", desc: "查询报告生成进度与结果" },
  { method: "GET", path: "/api/search", desc: "跨表全文搜索，返回结构化匹配结果" },
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
          REST API + SSE 流式接口，JWT 认证，支持 Python / Node.js / cURL。
        </p>
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
          <div style={{ fontSize: 13, fontWeight: 700, color: "#C2410C", marginBottom: 4 }}>
            认证方式
          </div>
          <div
            style={{
              fontSize: 13,
              color: "#7C3AED",
              fontFamily: "monospace",
              background: "#F3F0FF",
              padding: "8px 12px",
              borderRadius: 8,
              marginTop: 8,
            }}
          >
            Authorization: Bearer {"<your_jwt_token>"}
          </div>
          <div style={{ fontSize: 12, color: "#92400E", marginTop: 8 }}>
            通过 POST /api/auth/login 获取 token。API Key 方案即将上线。
          </div>
        </div>
      </div>

      {/* Endpoints */}
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 32px 80px" }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#0F172A", marginBottom: 20 }}>
          核心端点
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {endpoints.map((ep) => (
            <div
              key={ep.path}
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

        <div style={{ background: "#1E293B", borderRadius: 12, padding: "24px", marginTop: 40 }}>
          <div
            style={{ fontSize: 12, color: "#64748B", marginBottom: 12, fontFamily: "monospace" }}
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

TOKEN = "your_jwt_token"
BASE = "https://api.bdgo.ai"

# 查询近两年 GLP-1 交易
r = requests.get(
    f"{BASE}/api/deals",
    params={"keyword": "GLP-1", "year_from": 2023},
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(r.json())`}</pre>
        </div>

        <div style={{ textAlign: "center", marginTop: 40 }}>
          <p style={{ fontSize: 14, color: "#64748B", marginBottom: 16 }}>
            需要完整 API 文档或沙盒环境？
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
            联系我们获取访问权限
          </Link>
        </div>
      </div>
    </div>
  );
}
