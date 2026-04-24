"use client";

import { useEffect, useState, useRef } from "react";
import {
  fetchReportServices,
  reportDownloadUrl,
  createShareLink,
  fetchReportTasks,
} from "@/lib/api";
import { downloadWithAuth } from "@/lib/download";
import {
  useReportsStore,
  removeCompletedReport,
  addCompletedReport,
  type CompletedReport,
} from "@/lib/reports";
import { ReportGenerateDialog } from "@/components/ui/ReportGenerateDialog";
import { useAuth } from "@/components/AuthProvider";
import { parsePreferences } from "@/lib/auth";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Link from "next/link";

interface ReportService {
  slug: string;
  display_name: string;
  description: string;
  mode: "sync" | "async";
  estimated_seconds: number;
  category: string;
  output_formats: string[];
  input_schema: any;
}

interface RunningTask {
  task_id: string;
  slug: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  params?: Record<string, any>;
}

export default function ReportsPage() {
  const { user } = useAuth();
  const showReportCards = parsePreferences(user).show_report_cards === true;
  const [services, setServices] = useState<ReportService[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ReportService | null>(null);
  const { reports } = useReportsStore();
  const [runningTasks, setRunningTasks] = useState<RunningTask[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastActiveIdsRef = useRef<string>("");
  const seenCompletedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    fetchReportServices()
      .then((data: any) => {
        setServices(data.services || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    const poll = async () => {
      try {
        const { tasks } = await fetchReportTasks();
        const active = tasks.filter((t) => t.status === "queued" || t.status === "running");
        const nextIds = active
          .map((t) => t.task_id)
          .sort()
          .join(",");
        if (nextIds !== lastActiveIdsRef.current) {
          lastActiveIdsRef.current = nextIds;
          // status was filtered above to the RunningTask-compatible subset.
          setRunningTasks(active as RunningTask[]);
        }
        const newlyCompleted = tasks.filter(
          (t) => t.status === "completed" && !seenCompletedRef.current.has(t.task_id),
        );
        newlyCompleted.forEach((t) => seenCompletedRef.current.add(t.task_id));
        // addCompletedReport ignores its argument and re-fetches from the
        // server — the cast papers over a stale signature until that
        // helper is cleaned up (see lib/reports.ts).
        if (newlyCompleted.length > 0) {
          addCompletedReport(newlyCompleted[0] as unknown as CompletedReport);
        }
      } catch {
        // ignore poll errors
      }
    };
    poll();
    pollRef.current = setInterval(poll, 5000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>Reports</h1>
      </div>

      {/* Available report services (gated by preference) */}
      {showReportCards ? (
        <section style={{ marginBottom: "2rem" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              marginBottom: "0.75rem",
            }}
          >
            <h2 style={{ fontSize: "0.95rem", margin: 0, fontWeight: 700 }}>Generate New Report</h2>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
              {services.length} {services.length === 1 ? "type" : "types"} available
            </span>
          </div>

          {loading ? (
            <div className="loading">Loading services...</div>
          ) : services.length === 0 ? (
            <div className="card">
              <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                No report services available. Check backend logs.
              </p>
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: "0.85rem",
              }}
            >
              {services.map((svc) => (
                <ServiceCard key={svc.slug} service={svc} onClick={() => setSelected(svc)} />
              ))}
            </div>
          )}
        </section>
      ) : (
        <section
          className="card"
          style={{
            marginBottom: "2rem",
            padding: "1rem 1.1rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem",
          }}
        >
          <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            报告功能已简化为 chat 内的 slash command。在对话框输入{" "}
            <code
              style={{
                background: "var(--bg-subtle)",
                padding: "1px 6px",
                borderRadius: 4,
                fontSize: "0.78rem",
              }}
            >
              /
            </code>{" "}
            查看可用命令，或直接用自然语言描述需求。
          </div>
          <Link
            href="/profile"
            style={{
              fontSize: "0.75rem",
              color: "var(--accent)",
              textDecoration: "none",
              whiteSpace: "nowrap",
              fontWeight: 500,
            }}
          >
            显示卡片 →
          </Link>
        </section>
      )}

      {/* Running tasks */}
      {runningTasks.length > 0 && (
        <section style={{ marginBottom: "2rem" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              marginBottom: "0.75rem",
            }}
          >
            <h2 style={{ fontSize: "0.95rem", margin: 0, fontWeight: 700 }}>进行中</h2>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
              {runningTasks.length} 个任务
            </span>
          </div>
          {runningTasks.map((task) => (
            <div
              key={task.task_id}
              className="card"
              style={{
                padding: "0.75rem 1rem",
                display: "flex",
                alignItems: "center",
                gap: "0.85rem",
                marginBottom: "0.5rem",
              }}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--accent)"
                strokeWidth="2.5"
                strokeLinecap="round"
                style={{
                  animation: "tool-spin 0.7s linear infinite",
                  width: 18,
                  height: 18,
                  flexShrink: 0,
                }}
              >
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: "0.87rem", fontWeight: 600, color: "var(--text)" }}>
                  {services.find((s) => s.slug === task.slug)?.display_name || task.slug}
                </div>
                <div
                  style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "0.1rem" }}
                >
                  {task.status === "queued" ? "排队中…" : "生成中…"} · {task.task_id}
                </div>
              </div>
              <span
                style={{
                  fontSize: "0.68rem",
                  fontWeight: 600,
                  padding: "0.2rem 0.55rem",
                  borderRadius: 20,
                  background: task.status === "running" ? "#dbeafe" : "#f1f5f9",
                  color: task.status === "running" ? "#1d4ed8" : "#64748b",
                }}
              >
                {task.status === "running" ? "运行中" : "排队中"}
              </span>
            </div>
          ))}
        </section>
      )}

      {/* History */}
      <section>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: "0.75rem",
          }}
        >
          <h2 style={{ fontSize: "0.95rem", margin: 0, fontWeight: 700 }}>My Reports</h2>
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
            {reports.length} saved
          </span>
        </div>

        {reports.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: "2rem 1rem" }}>
            <div style={{ fontSize: "1.8rem", marginBottom: "0.5rem", opacity: 0.4 }}>▤</div>
            <p
              style={{
                margin: 0,
                fontSize: "0.85rem",
                color: "var(--text-secondary)",
              }}
            >
              Generated reports will appear here and persist across sessions.
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            {reports.map((r) => (
              <HistoryRow key={r.taskId} report={r} />
            ))}
          </div>
        )}
      </section>

      {selected && <ReportGenerateDialog service={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Service card
// ═══════════════════════════════════════════════════════════

function ServiceCard({ service, onClick }: { service: ReportService; onClick: () => void }) {
  const categoryIcons: Record<string, string> = {
    research: "📖",
    report: "📊",
    analysis: "🔬",
  };

  return (
    <div
      className="card"
      onClick={onClick}
      style={{
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        gap: "0.55rem",
        transition: "border-color 0.15s, box-shadow 0.15s, transform 0.15s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)";
        (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-md)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
        (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-sm)";
        (e.currentTarget as HTMLElement).style.transform = "none";
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.6rem" }}>
        <div style={{ fontSize: "1.4rem", lineHeight: 1, flexShrink: 0 }}>
          {categoryIcons[service.category] || "📄"}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: "0.95rem",
              fontWeight: 700,
              color: "var(--text)",
              marginBottom: "0.2rem",
            }}
          >
            {service.display_name}
          </div>
          <div
            style={{
              fontSize: "0.76rem",
              color: "var(--text-secondary)",
              lineHeight: 1.45,
            }}
          >
            {service.description}
          </div>
        </div>
      </div>
      <div
        style={{
          display: "flex",
          gap: "0.4rem",
          paddingTop: "0.5rem",
          marginTop: "auto",
          borderTop: "1px solid var(--border-light)",
          fontSize: "0.68rem",
          color: "var(--text-muted)",
        }}
      >
        <span>⏱ ~{service.estimated_seconds}s</span>
        <span>·</span>
        <span>{service.output_formats.map((f) => `.${f}`).join(" ")}</span>
        <span>·</span>
        <span>{service.mode}</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// History row
// ═══════════════════════════════════════════════════════════

function HistoryRow({ report }: { report: CompletedReport }) {
  const age = formatAge(report.createdAt);
  const [shareState, setShareState] = useState<"idle" | "loading" | "copied">("idle");
  const [expanded, setExpanded] = useState(false);
  const [dlState, setDlState] = useState<Record<string, "idle" | "loading" | "error">>({});

  const handleDownload = async (f: { download_url: string; filename: string; format: string }) => {
    setDlState((s) => ({ ...s, [f.format]: "loading" }));
    try {
      await downloadWithAuth(f.download_url, f.filename);
      setDlState((s) => ({ ...s, [f.format]: "idle" }));
    } catch {
      setDlState((s) => ({ ...s, [f.format]: "error" }));
      setTimeout(() => setDlState((s) => ({ ...s, [f.format]: "idle" })), 3000);
    }
  };

  const handleShare = async () => {
    setShareState("loading");
    try {
      const { token } = await createShareLink(report.taskId);
      const shareUrl = `${window.location.origin}/share/${token}`;
      await navigator.clipboard.writeText(shareUrl);
      setShareState("copied");
      setTimeout(() => setShareState("idle"), 2000);
    } catch {
      setShareState("idle");
    }
  };

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* Header row */}
      <div
        style={{
          padding: "0.75rem 1rem",
          display: "flex",
          alignItems: "center",
          gap: "0.85rem",
          cursor: report.markdownPreview ? "pointer" : "default",
        }}
        onClick={() => report.markdownPreview && setExpanded((e) => !e)}
      >
        {report.markdownPreview && (
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", flexShrink: 0 }}>
            {expanded ? "▾" : "▸"}
          </span>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: "0.87rem",
              fontWeight: 600,
              color: "var(--text)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
            title={report.title}
          >
            {report.title}
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
            {report.displayName} · {age}
            {report.meta?.mode ? ` · ${String(report.meta.mode)}` : ""}
            {report.meta?.paper_count ? ` · ${String(report.meta.paper_count)} papers` : ""}
          </div>
        </div>
        <div
          style={{ display: "flex", gap: "0.35rem", flexShrink: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          {report.files.map((f) => {
            const state = dlState[f.format] || "idle";
            return (
              <button
                key={f.filename}
                onClick={() => handleDownload(f)}
                disabled={state === "loading"}
                style={{
                  padding: "0.3rem 0.7rem",
                  background: state === "error" ? "#fee2e2" : "var(--accent-light)",
                  color: state === "error" ? "#dc2626" : "var(--accent)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  border: `1px solid ${state === "error" ? "#fca5a5" : "var(--accent-light)"}`,
                  cursor: state === "loading" ? "wait" : "pointer",
                  opacity: state === "loading" ? 0.6 : 1,
                }}
              >
                {state === "loading" ? "…" : state === "error" ? "文件不存在" : `⬇ .${f.format}`}
              </button>
            );
          })}
          <button
            onClick={handleShare}
            disabled={shareState === "loading"}
            style={{
              padding: "0.3rem 0.7rem",
              background: shareState === "copied" ? "#059669" : "none",
              border: `1px solid ${shareState === "copied" ? "#059669" : "var(--border)"}`,
              color: shareState === "copied" ? "#fff" : "var(--text-muted)",
              cursor: shareState === "loading" ? "wait" : "pointer",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.72rem",
              fontWeight: 500,
              transition: "all 0.15s",
            }}
            title="Copy share link"
          >
            {shareState === "copied" ? "Copied!" : shareState === "loading" ? "..." : "🔗"}
          </button>
          <button
            onClick={() => {
              if (confirm(`Remove "${report.title}" from history? (File stays on disk.)`)) {
                removeCompletedReport(report.taskId);
              }
            }}
            style={{
              padding: "0.3rem 0.5rem",
              background: "none",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              cursor: "pointer",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.72rem",
            }}
            title="Remove from history"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Inline markdown preview */}
      {expanded && report.markdownPreview && (
        <div
          style={{
            borderTop: "1px solid var(--border-light)",
            padding: "1rem 1.25rem",
            background: "var(--bg-subtle)",
            maxHeight: "420px",
            overflowY: "auto",
            fontSize: "0.82rem",
            lineHeight: 1.65,
            color: "var(--text)",
          }}
          className="markdown-body"
        >
          <Markdown remarkPlugins={[remarkGfm]}>{report.markdownPreview}</Markdown>
          {report.markdownPreview.length >= 2000 && (
            <div
              style={{
                marginTop: "0.75rem",
                fontSize: "0.72rem",
                color: "var(--text-muted)",
                fontStyle: "italic",
              }}
            >
              — 预览截断（前2000字），完整内容请下载报告文件 —
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatAge(timestamp: number): string {
  const s = Math.floor((Date.now() - timestamp) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(timestamp).toLocaleDateString();
}
