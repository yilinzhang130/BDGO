"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchSharedReport } from "@/lib/api";
import ReactMarkdown from "react-markdown";

interface SharedFile {
  filename: string;
  format: string;
  size: number;
  download_url: string;
}

interface SharedReport {
  title: string;
  markdown_preview: string;
  files: SharedFile[];
  created_at: string | null;
}

export default function SharePage() {
  const params = useParams();
  const token = params.token as string;
  const [report, setReport] = useState<SharedReport | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetchSharedReport(token)
      .then(setReport)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", background: "#f8fafc" }}>
        <div style={{ color: "#64748b", fontSize: 14 }}>Loading...</div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", minHeight: "100vh", background: "#f8fafc" }}>
        <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>404</div>
        <div style={{ fontSize: 16, color: "#64748b" }}>This share link is invalid or has expired.</div>
        <a href="/" style={{ marginTop: 24, color: "#1e3a8a", fontSize: 14, textDecoration: "none" }}>
          Go to BD Go &rarr;
        </a>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      {/* Header */}
      <header style={{
        background: "#fff",
        borderBottom: "1px solid #e2e8f0",
        padding: "16px 24px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <a href="/" style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none", color: "#0f172a" }}>
          <span style={{ fontWeight: 700, fontSize: 16 }}>BD Go</span>
          <span style={{ fontSize: 12, color: "#64748b" }}>Shared Report</span>
        </a>
        <div style={{ display: "flex", gap: 8 }}>
          {report.files.map((f) => (
            <a
              key={f.format}
              href={f.download_url}
              download={f.filename}
              style={{
                padding: "8px 16px",
                background: "#1e3a8a",
                color: "#fff",
                textDecoration: "none",
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              Download .{f.format}
            </a>
          ))}
        </div>
      </header>

      {/* Content */}
      <main style={{ maxWidth: 800, margin: "0 auto", padding: "40px 24px 80px" }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f172a", marginBottom: 8 }}>
          {report.title}
        </h1>
        {report.created_at && (
          <div style={{ fontSize: 13, color: "#64748b", marginBottom: 32 }}>
            Generated {new Date(report.created_at).toLocaleDateString("en-US", {
              year: "numeric", month: "long", day: "numeric",
            })}
          </div>
        )}

        {report.markdown_preview ? (
          <div
            style={{
              background: "#fff",
              border: "1px solid #e2e8f0",
              borderRadius: 12,
              padding: "28px 32px",
              fontSize: 14,
              lineHeight: 1.7,
              color: "#1e293b",
            }}
          >
            <ReactMarkdown>{report.markdown_preview}</ReactMarkdown>
            {report.markdown_preview.length >= 1990 && (
              <div style={{
                marginTop: 24,
                padding: "12px 16px",
                background: "#f1f5f9",
                borderRadius: 8,
                fontSize: 13,
                color: "#64748b",
                textAlign: "center",
              }}>
                Preview truncated. Download the full report above.
              </div>
            )}
          </div>
        ) : (
          <div style={{
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: 12,
            padding: "40px 32px",
            textAlign: "center",
            color: "#64748b",
          }}>
            No preview available. Download the report to view full content.
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{
        textAlign: "center",
        padding: "24px",
        fontSize: 12,
        color: "#94a3b8",
        borderTop: "1px solid #e2e8f0",
      }}>
        Powered by <a href="/" style={{ color: "#1e3a8a", textDecoration: "none", fontWeight: 600 }}>BD Go</a> — Biotech BD Intelligence Platform
      </footer>
    </div>
  );
}
