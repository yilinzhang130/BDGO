import { LandingNav } from "@/components/LandingNav";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { DOCS_VERSION, DOCS_UPDATED, DOCS_BODY, DOCS_TOC } from "./content";

export default function DocsPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F5F4EE", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      <div
        style={{
          maxWidth: 1080,
          margin: "0 auto",
          padding: "48px 32px 80px",
          display: "grid",
          gridTemplateColumns: "220px 1fr",
          gap: 40,
        }}
      >
        {/* TOC */}
        <aside
          style={{
            position: "sticky",
            top: 80,
            alignSelf: "start",
            maxHeight: "calc(100vh - 96px)",
            overflowY: "auto",
            fontSize: 13,
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.1em",
              color: "#94A3B8",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            目录
          </div>
          <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {DOCS_TOC.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                style={{
                  fontSize: item.level === 2 ? 13 : 12,
                  paddingLeft: item.level === 3 ? 14 : 0,
                  color: item.level === 2 ? "#0F172A" : "#64748B",
                  textDecoration: "none",
                  padding: `4px 0 4px ${item.level === 3 ? 14 : 0}px`,
                  fontWeight: item.level === 2 ? 600 : 400,
                  lineHeight: 1.5,
                }}
              >
                {item.title}
              </a>
            ))}
          </nav>
        </aside>

        {/* Body */}
        <div>
          <div style={{ marginBottom: 28 }}>
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
              使用文档 · {DOCS_VERSION}
            </div>
            <h1
              style={{
                fontSize: 38,
                fontWeight: 800,
                color: "#0F172A",
                lineHeight: 1.2,
                letterSpacing: "-0.02em",
                margin: "0 0 12px",
              }}
            >
              BD Go 使用指南
            </h1>
            <p style={{ fontSize: 14, color: "#94A3B8", margin: 0 }}>
              最后更新：{DOCS_UPDATED} · 反馈建议请联系{" "}
              <a href="mailto:product@bdgo.ai" style={{ color: "#2563EB", textDecoration: "none" }}>
                product@bdgo.ai
              </a>
            </p>
          </div>

          <div
            className="markdown-body"
            style={{
              background: "#fff",
              borderRadius: 16,
              border: "1px solid #E8EFFE",
              padding: "36px 40px",
              boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
              fontSize: 14.5,
              lineHeight: 1.75,
              color: "#0F172A",
            }}
          >
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {DOCS_BODY}
            </Markdown>
          </div>
        </div>
      </div>
    </div>
  );
}
