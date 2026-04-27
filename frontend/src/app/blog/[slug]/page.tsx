import { LandingNav } from "@/components/LandingNav";
import Link from "next/link";
import { notFound } from "next/navigation";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { POSTS, TAG_COLORS } from "../posts";

export function generateStaticParams() {
  return POSTS.map((p) => ({ slug: p.slug }));
}

export default async function BlogPostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = POSTS.find((p) => p.slug === slug);
  if (!post) notFound();

  const tc = TAG_COLORS[post.tag];

  return (
    <div style={{ minHeight: "100vh", background: "#F5F4EE", fontFamily: "Inter, sans-serif" }}>
      <LandingNav />

      <article style={{ maxWidth: 720, margin: "0 auto", padding: "48px 32px 80px" }}>
        <Link
          href="/blog"
          style={{
            fontSize: 13,
            color: "#64748B",
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            marginBottom: 24,
          }}
        >
          ← 返回博客
        </Link>

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: tc.color,
              background: tc.bg,
              padding: "3px 10px",
              borderRadius: 12,
            }}
          >
            {post.tag}
          </span>
          <span style={{ fontSize: 12, color: "#94A3B8" }}>{post.date}</span>
          <span style={{ fontSize: 12, color: "#94A3B8" }}>· {post.readTime}阅读</span>
        </div>

        <h1
          style={{
            fontSize: 34,
            fontWeight: 800,
            color: "#0F172A",
            lineHeight: 1.25,
            letterSpacing: "-0.02em",
            margin: "0 0 32px",
          }}
        >
          {post.title}
        </h1>

        <div
          className="markdown-body"
          style={{
            background: "#fff",
            borderRadius: 16,
            border: "1px solid #E8EFFE",
            padding: "36px 40px",
            boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
            fontSize: 15,
            lineHeight: 1.75,
            color: "#0F172A",
          }}
        >
          <Markdown remarkPlugins={[remarkGfm]}>{post.body}</Markdown>
        </div>
      </article>
    </div>
  );
}
