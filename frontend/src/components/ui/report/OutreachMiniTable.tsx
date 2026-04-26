"use client";

/**
 * OutreachMiniTable — chat-embedded interactive table for /outreach output.
 *
 * Backed by `meta.outreach_pipeline_rows` (pipeline view) or
 * `meta.outreach_thread_events` (thread view) emitted by the backend
 * OutreachListService. Falls back to the markdown preview when neither
 * is present, so older completed tasks still render correctly.
 *
 * Design intent (per "chat-first" product decision): no separate
 * dashboard route; users drill from chat by clicking rows, which fires
 * a new slash command into the existing chat input.
 */

import type { CSSProperties } from "react";

export interface PipelineRow {
  company: string;
  statuses: Record<string, number>;
  last_touched: string; // ISO
  total_events: number;
}

export interface ThreadEvent {
  event_id: string;
  ts: string; // ISO
  status: string;
  purpose: string;
  channel: string;
  to_contact: string;
  subject: string;
  notes: string;
  asset_context: string;
}

const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  sent: { bg: "#E0F2FE", fg: "#0369A1" },
  replied: { bg: "#DCFCE7", fg: "#15803D" },
  meeting: { bg: "#FEF3C7", fg: "#92400E" },
  cda_signed: { bg: "#DDD6FE", fg: "#5B21B6" },
  ts_signed: { bg: "#FCE7F3", fg: "#9D174D" },
  definitive_signed: { bg: "#D1FAE5", fg: "#065F46" },
  passed: { bg: "#F3F4F6", fg: "#6B7280" },
  dead: { bg: "#FEE2E2", fg: "#B91C1C" },
};
const FALLBACK_COLOR = { bg: "#F3F4F6", fg: "#374151" };

function StatusBadge({ status, count }: { status: string; count?: number }) {
  const c = STATUS_COLORS[status] || FALLBACK_COLOR;
  return (
    <span
      style={{
        display: "inline-block",
        background: c.bg,
        color: c.fg,
        fontSize: 10,
        fontWeight: 600,
        padding: "1px 6px",
        borderRadius: 4,
        whiteSpace: "nowrap",
      }}
    >
      {status}
      {count !== undefined ? ` ${count}` : ""}
    </span>
  );
}

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 12,
};
const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "6px 10px",
  background: "#F9FAFB",
  borderBottom: "1px solid var(--border)",
  color: "var(--text-secondary)",
  fontWeight: 600,
  fontSize: 11,
};
const tdStyle: CSSProperties = {
  padding: "6px 10px",
  borderBottom: "1px solid var(--border-light, #F3F4F6)",
  verticalAlign: "top",
};

function fmtDate(iso: string): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})(?:T(\d{2}:\d{2}))?/);
  if (!m) return iso.slice(0, 10);
  return m[2] ? `${m[1]} ${m[2]}` : m[1];
}

function PipelineTable({
  rows,
  onSuggestedCommand,
}: {
  rows: PipelineRow[];
  onSuggestedCommand?: (cmd: string) => void;
}) {
  if (!rows.length) {
    return (
      <div style={{ padding: "12px 14px", fontSize: 12, color: "var(--text-muted)" }}>
        无 outreach 记录。用 <code>/log to_company=&quot;...&quot;</code> 开始。
      </div>
    );
  }
  return (
    <table style={tableStyle}>
      <thead>
        <tr>
          <th style={thStyle}>公司</th>
          <th style={thStyle}>状态分布</th>
          <th style={thStyle}>事件</th>
          <th style={thStyle}>最后更新</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const cmd = `/outreach company="${r.company}"`;
          const clickable = !!onSuggestedCommand;
          return (
            <tr
              key={r.company}
              onClick={clickable ? () => onSuggestedCommand!(cmd) : undefined}
              style={{ cursor: clickable ? "pointer" : "default" }}
              onMouseEnter={(e) => {
                if (clickable)
                  (e.currentTarget as HTMLTableRowElement).style.background = "#F9FAFB";
              }}
              onMouseLeave={(e) => {
                if (clickable) (e.currentTarget as HTMLTableRowElement).style.background = "";
              }}
              title={clickable ? `点击查看 ${r.company} 完整线程` : undefined}
            >
              <td style={{ ...tdStyle, fontWeight: 600 }}>{r.company}</td>
              <td style={tdStyle}>
                <span style={{ display: "inline-flex", gap: 4, flexWrap: "wrap" }}>
                  {Object.entries(r.statuses).map(([s, n]) => (
                    <StatusBadge key={s} status={s} count={n} />
                  ))}
                </span>
              </td>
              <td style={{ ...tdStyle, color: "var(--text-secondary)" }}>{r.total_events}</td>
              <td style={{ ...tdStyle, color: "var(--text-secondary)" }}>
                {fmtDate(r.last_touched)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ThreadTable({ events }: { events: ThreadEvent[] }) {
  if (!events.length) {
    return (
      <div style={{ padding: "12px 14px", fontSize: 12, color: "var(--text-muted)" }}>
        无匹配的 outreach 事件。
      </div>
    );
  }
  return (
    <table style={tableStyle}>
      <thead>
        <tr>
          <th style={thStyle}>时间</th>
          <th style={thStyle}>状态</th>
          <th style={thStyle}>用途</th>
          <th style={thStyle}>联系人</th>
          <th style={thStyle}>备注</th>
        </tr>
      </thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.event_id || `${e.ts}-${e.subject}`}>
            <td style={{ ...tdStyle, whiteSpace: "nowrap", color: "var(--text-secondary)" }}>
              {fmtDate(e.ts)}
            </td>
            <td style={tdStyle}>
              <StatusBadge status={e.status} />
            </td>
            <td style={{ ...tdStyle, fontSize: 11, color: "var(--text-secondary)" }}>
              {e.purpose}
            </td>
            <td style={{ ...tdStyle, fontSize: 11 }}>{e.to_contact || "—"}</td>
            <td style={{ ...tdStyle, fontSize: 11, color: "var(--text-secondary)" }}>
              {e.notes || e.subject || "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function OutreachMiniTable({
  pipelineRows,
  threadEvents,
  onSuggestedCommand,
}: {
  pipelineRows?: PipelineRow[];
  threadEvents?: ThreadEvent[];
  onSuggestedCommand?: (cmd: string) => void;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 6,
        overflow: "hidden",
        marginBottom: 10,
      }}
    >
      {pipelineRows ? (
        <PipelineTable rows={pipelineRows} onSuggestedCommand={onSuggestedCommand} />
      ) : threadEvents ? (
        <ThreadTable events={threadEvents} />
      ) : null}
    </div>
  );
}
