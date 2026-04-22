import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";
import { POSTS, TAG_COLORS } from "./posts";

export default function BlogPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      <div style={{ textAlign: "center", padding: "72px 32px 56px", maxWidth: 640, margin: "0 auto" }}>
        <div style={{ display: "inline-block", fontSize: 12, fontWeight: 700, color: "#2563EB", background: "#EEF2FF", padding: "4px 14px", borderRadius: 20, marginBottom: 20, letterSpacing: "0.05em" }}>博客</div>
        <h1 style={{ fontSize: 40, fontWeight: 800, color: "#0F172A", lineHeight: 1.2, margin: "0 0 16px" }}>产品动态与 BD 方法论</h1>
        <p style={{ fontSize: 17, color: "#64748B", lineHeight: 1.7, margin: 0 }}>
          BD Go 的版本更新、使用技巧与行业观察。每次重大更新都会同步一篇博客。
        </p>
      </div>

      <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 32px 80px", display: "flex", flexDirection: "column", gap: 20 }}>
        {POSTS.map((p) => {
          const tc = TAG_COLORS[p.tag];
          return (
            <Link key={p.slug} href={`/blog/${p.slug}`} style={{ textDecoration: "none", color: "inherit" }}>
              <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #E8EFFE", padding: "28px", boxShadow: "0 2px 12px rgba(30,58,138,0.04)", cursor: "pointer", transition: "box-shadow 0.15s, transform 0.15s" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: tc.color, background: tc.bg, padding: "2px 10px", borderRadius: 12 }}>{p.tag}</span>
                  <span style={{ fontSize: 12, color: "#94A3B8" }}>{p.date}</span>
                  <span style={{ fontSize: 12, color: "#94A3B8" }}>· {p.readTime}阅读</span>
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 700, color: "#0F172A", margin: "0 0 10px", lineHeight: 1.4 }}>{p.title}</h3>
                <p style={{ fontSize: 14, color: "#64748B", lineHeight: 1.7, margin: 0 }}>{p.summary}</p>
              </div>
            </Link>
          );
        })}

        <div style={{ background: "#F8FAFF", border: "1px dashed #CBD5E1", borderRadius: 16, padding: "24px", textAlign: "center" }}>
          <div style={{ fontSize: 13, color: "#64748B", margin: 0 }}>
            更多内容整理中。订阅更新请联系 <a href="mailto:product@bdgo.ai" style={{ color: "#2563EB", textDecoration: "none" }}>product@bdgo.ai</a>。
          </div>
        </div>
      </div>
    </div>
  );
}
