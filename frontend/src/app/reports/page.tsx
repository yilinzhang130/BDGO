"use client";

import { useEffect, useState } from "react";
import { fetchReportServices, reportDownloadUrl } from "@/lib/api";
import { useReportsStore, removeCompletedReport, type CompletedReport } from "@/lib/reports";
import { ReportGenerateDialog } from "@/components/ui/ReportGenerateDialog";

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

export default function ReportsPage() {
  const [services, setServices] = useState<ReportService[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ReportService | null>(null);
  const { reports } = useReportsStore();

  useEffect(() => {
    fetchReportServices()
      .then((data: any) => {
        setServices(data.services || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>Reports</h1>
      </div>

      {/* Available report services */}
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
              <ServiceCard
                key={svc.slug}
                service={svc}
                onClick={() => setSelected(svc)}
              />
            ))}
          </div>
        )}
      </section>

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
            <div style={{ fontSize: "1.8rem", marginBottom: "0.5rem", opacity: 0.4 }}>
              ▤
            </div>
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

      {selected && (
        <ReportGenerateDialog
          service={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Service card
// ═══════════════════════════════════════════════════════════

function ServiceCard({
  service,
  onClick,
}: {
  service: ReportService;
  onClick: () => void;
}) {
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
        <span>
          {service.output_formats.map((f) => `.${f}`).join(" ")}
        </span>
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
  return (
    <div
      className="card"
      style={{
        padding: "0.75rem 1rem",
        display: "flex",
        alignItems: "center",
        gap: "0.85rem",
      }}
    >
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
        <div
          style={{
            fontSize: "0.7rem",
            color: "var(--text-muted)",
            marginTop: "0.15rem",
          }}
        >
          {report.displayName} · {age}
          {report.meta?.mode && ` · ${report.meta.mode}`}
          {report.meta?.paper_count && ` · ${report.meta.paper_count} papers`}
        </div>
      </div>
      <div style={{ display: "flex", gap: "0.35rem", flexShrink: 0 }}>
        {report.files.map((f) => (
          <a
            key={f.filename}
            href={f.download_url}
            download={f.filename}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              padding: "0.3rem 0.7rem",
              background: "var(--accent-light)",
              color: "var(--accent)",
              textDecoration: "none",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.72rem",
              fontWeight: 600,
              border: "1px solid var(--accent-light)",
            }}
          >
            ⬇ .{f.format}
          </a>
        ))}
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
  );
}

function formatAge(timestamp: number): string {
  const s = Math.floor((Date.now() - timestamp) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(timestamp).toLocaleDateString();
}
