"use client";

/**
 * Outreach workspace page — Phase 1, P1-3.
 *
 * Replaces the chat-embedded /outreach slash output. Users land here from
 * the sidebar to triage their BD outreach pipeline:
 *   - status / search filters at the top
 *   - paginated event list (newest first), one row per event
 *   - clicking a row expands a thread panel showing same-counterparty events
 *
 * Compose / paste-reply / batch-email flows live in subsequent PRs and
 * will deep-link into this page.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  deleteOutreachEvent,
  fetchOutreachEvents,
  type OutreachEvent,
  type OutreachListResponse,
} from "@/lib/api";
import { errorMessage } from "@/lib/format";
import { ImportReplyModal } from "@/components/outreach/ImportReplyModal";

// Status filter options. Empty value = "All".
const STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "sent", label: "已发送" },
  { value: "replied", label: "已回复" },
  { value: "meeting", label: "会议中" },
  { value: "cda_signed", label: "CDA 已签" },
  { value: "ts_signed", label: "TS 已签" },
  { value: "definitive_signed", label: "正式签约" },
  { value: "passed", label: "已 pass" },
  { value: "dead", label: "已终止" },
];

const STATUS_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  sent: { bg: "#DBEAFE", color: "#1E40AF", label: "Sent" },
  replied: { bg: "#DCFCE7", color: "#166534", label: "Replied" },
  meeting: { bg: "#FEF3C7", color: "#92400E", label: "Meeting" },
  cda_signed: { bg: "#E0E7FF", color: "#3730A3", label: "CDA" },
  ts_signed: { bg: "#FCE7F3", color: "#9F1239", label: "TS" },
  definitive_signed: { bg: "#D1FAE5", color: "#065F46", label: "Closed" },
  passed: { bg: "#F3F4F6", color: "#4B5563", label: "Pass" },
  dead: { bg: "#FEE2E2", color: "#991B1B", label: "Dead" },
};

function formatDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(0, 10);
}

export default function OutreachPage() {
  const router = useRouter();
  const [data, setData] = useState<OutreachListResponse | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 50;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [importReplyOpen, setImportReplyOpen] = useState(false);
  const [importReplyCompany, setImportReplyCompany] = useState<string | undefined>(undefined);

  // Debounce the search box so we don't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { page, page_size: pageSize };
      if (status) params.status = status;
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
      const res = await fetchOutreachEvents(params);
      setData(res);
    } catch (e: unknown) {
      setError(errorMessage(e, "加载 outreach 失败"));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, status, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("确认删除这条 outreach 记录？此操作不可撤销。")) return;
    try {
      await deleteOutreachEvent(id);
      void load();
    } catch (err: unknown) {
      alert(errorMessage(err, "删除失败"));
    }
  };

  const rows = data?.data ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;

  // Group events by company for the expanded thread view.
  const sameCompanyEvents = useMemo(() => {
    if (expandedId === null) return [];
    const target = rows.find((r) => r.id === expandedId);
    if (!target) return [];
    return rows.filter((r) => r.to_company === target.to_company);
  }, [expandedId, rows]);

  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", padding: "32px 24px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        {/* Header */}
        <div
          style={{
            marginBottom: 24,
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
          }}
        >
          <div>
            <h1
              style={{
                fontSize: 28,
                fontWeight: 700,
                color: "#0F172A",
                margin: "0 0 6px",
                letterSpacing: "-0.01em",
              }}
            >
              Outreach 工作台
            </h1>
            <p style={{ fontSize: 14, color: "#64748B", margin: 0 }}>
              BD 外联 pipeline · 共 {total} 条记录
            </p>
          </div>
          <button
            onClick={() => router.push("/chat?context=outreach")}
            style={{
              padding: "7px 14px",
              fontSize: 13,
              border: "1px solid #E2E8F0",
              borderRadius: 8,
              background: "#fff",
              color: "#334155",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            💬 在 chat 里讨论
          </button>
        </div>

        {/* Filters */}
        <div
          style={{
            display: "flex",
            gap: 12,
            marginBottom: 16,
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索公司 / 联系人 / 标题 / 备注…"
            style={{
              flex: 1,
              minWidth: 240,
              padding: "9px 14px",
              border: "1px solid #E2E8F0",
              borderRadius: 8,
              fontSize: 14,
              background: "#fff",
            }}
          />
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            style={{
              padding: "9px 14px",
              border: "1px solid #E2E8F0",
              borderRadius: 8,
              fontSize: 14,
              background: "#fff",
              cursor: "pointer",
            }}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <button
            onClick={() => router.push("/outreach/compose")}
            style={{
              padding: "9px 16px",
              border: "none",
              borderRadius: 8,
              background: "#2563EB",
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            + Compose
          </button>
          <button
            onClick={() => {
              setImportReplyCompany(undefined);
              setImportReplyOpen(true);
            }}
            style={{
              padding: "9px 16px",
              border: "1px solid #CBD5E1",
              borderRadius: 8,
              background: "#fff",
              color: "#0F172A",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            + 导入回信
          </button>
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              padding: "12px 16px",
              background: "#FEF2F2",
              border: "1px solid #FCA5A5",
              borderRadius: 8,
              color: "#991B1B",
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}

        {/* Table */}
        <div
          style={{
            background: "#fff",
            border: "1px solid #E8EFFE",
            borderRadius: 12,
            overflow: "hidden",
            boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "100px 1fr 1fr 100px 120px 80px",
              padding: "12px 18px",
              background: "#F8FAFC",
              borderBottom: "1px solid #E2E8F0",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "#64748B",
            }}
          >
            <div>日期</div>
            <div>对手 / 联系人</div>
            <div>资产 / 主题</div>
            <div>状态</div>
            <div>更新</div>
            <div></div>
          </div>

          {loading && rows.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>加载中…</div>
          ) : rows.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>
              {debouncedSearch || status
                ? "没有匹配的记录。试试清除筛选。"
                : "你还没有任何 outreach 记录。下个版本会加 “Compose” 按钮直接发起。"}
            </div>
          ) : (
            rows.map((row) => (
              <OutreachRow
                key={row.id}
                row={row}
                expanded={expandedId === row.id}
                onToggle={() => setExpandedId(expandedId === row.id ? null : row.id)}
                onDelete={(e) => handleDelete(row.id, e)}
                threadEvents={
                  expandedId === row.id ? sameCompanyEvents.filter((e) => e.id !== row.id) : []
                }
                onImportReply={(company) => {
                  setImportReplyCompany(company);
                  setImportReplyOpen(true);
                }}
              />
            ))
          )}
        </div>

        <ImportReplyModal
          open={importReplyOpen}
          onClose={() => setImportReplyOpen(false)}
          onArchived={() => void load()}
          defaultCompany={importReplyCompany}
        />

        {/* Pagination */}
        {totalPages > 1 && (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: 12,
              marginTop: 20,
              fontSize: 13,
              color: "#64748B",
            }}
          >
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              style={paginationBtnStyle(page === 1)}
            >
              ← 上一页
            </button>
            <span>
              第 {page} / {totalPages} 页
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              style={paginationBtnStyle(page === totalPages)}
            >
              下一页 →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Row component (top-level so React.memo could be added later)
// ─────────────────────────────────────────────────────────────

interface RowProps {
  row: OutreachEvent;
  expanded: boolean;
  onToggle: () => void;
  onDelete: (e: React.MouseEvent) => void;
  threadEvents: OutreachEvent[];
  onImportReply: (company: string) => void;
}

function OutreachRow({ row, expanded, onToggle, onDelete, threadEvents, onImportReply }: RowProps) {
  const router = useRouter();
  const badge = STATUS_BADGE[row.status] || {
    bg: "#F3F4F6",
    color: "#4B5563",
    label: row.status,
  };
  return (
    <>
      <div
        onClick={onToggle}
        style={{
          display: "grid",
          gridTemplateColumns: "100px 1fr 1fr 100px 120px 80px",
          padding: "14px 18px",
          borderBottom: "1px solid #F1F5F9",
          cursor: "pointer",
          fontSize: 13,
          color: "#0F172A",
          alignItems: "center",
          background: expanded ? "#F8FAFC" : "transparent",
        }}
      >
        <div style={{ color: "#64748B", fontVariantNumeric: "tabular-nums" }}>
          {formatDate(row.created_at)}
        </div>
        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          <div style={{ fontWeight: 600 }}>{row.to_company}</div>
          {row.to_contact && (
            <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 2 }}>{row.to_contact}</div>
          )}
        </div>
        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {row.asset_context && <div style={{ fontWeight: 500 }}>{row.asset_context}</div>}
          {row.subject && (
            <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 2 }}>{row.subject}</div>
          )}
          {!row.asset_context && !row.subject && <div style={{ color: "#CBD5E1" }}>—</div>}
        </div>
        <div>
          <span
            style={{
              display: "inline-block",
              padding: "3px 10px",
              borderRadius: 12,
              background: badge.bg,
              color: badge.color,
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            {badge.label}
          </span>
        </div>
        <div style={{ fontSize: 11, color: "#94A3B8" }}>{row.purpose.replace(/_/g, " ")}</div>
        <div>
          <button
            onClick={onDelete}
            title="删除"
            style={{
              border: "none",
              background: "transparent",
              color: "#94A3B8",
              cursor: "pointer",
              fontSize: 14,
              padding: 4,
            }}
          >
            ✕
          </button>
        </div>
      </div>

      {/* Expanded detail panel */}
      {expanded && (
        <div
          style={{
            padding: "16px 18px 20px 18px",
            background: "#F8FAFC",
            borderBottom: "1px solid #E2E8F0",
          }}
        >
          {row.notes && (
            <div style={{ marginBottom: 12 }}>
              <div style={detailLabelStyle}>备注</div>
              <div style={detailValueStyle}>{row.notes}</div>
            </div>
          )}
          {(row.channel || row.perspective) && (
            <div style={{ display: "flex", gap: 24, marginBottom: 12 }}>
              <div>
                <div style={detailLabelStyle}>渠道</div>
                <div style={detailValueStyle}>{row.channel}</div>
              </div>
              {row.perspective && (
                <div>
                  <div style={detailLabelStyle}>视角</div>
                  <div style={detailValueStyle}>{row.perspective}</div>
                </div>
              )}
            </div>
          )}
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onImportReply(row.to_company);
              }}
              style={{
                padding: "6px 14px",
                border: "1px solid #2563EB",
                borderRadius: 7,
                background: "#fff",
                color: "#2563EB",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              + 导入回信
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                router.push(
                  `/chat?context=outreach&company=${encodeURIComponent(row.to_company)}&event_id=${row.id}`,
                );
              }}
              style={{
                padding: "6px 14px",
                fontSize: 12,
                border: "1px solid #E2E8F0",
                borderRadius: 7,
                background: "#fff",
                color: "#334155",
                cursor: "pointer",
              }}
            >
              💬 在 chat 讨论这条
            </button>
          </div>
          {threadEvents.length > 0 && (
            <div>
              <div style={detailLabelStyle}>同对手历史 ({threadEvents.length})</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 6 }}>
                {threadEvents.map((e) => (
                  <div
                    key={e.id}
                    style={{
                      fontSize: 12,
                      color: "#475569",
                      display: "flex",
                      gap: 12,
                      padding: "4px 0",
                    }}
                  >
                    <span
                      style={{ minWidth: 84, color: "#94A3B8", fontVariantNumeric: "tabular-nums" }}
                    >
                      {formatDate(e.created_at)}
                    </span>
                    <span
                      style={{ minWidth: 60, color: STATUS_BADGE[e.status]?.color || "#64748B" }}
                    >
                      {STATUS_BADGE[e.status]?.label || e.status}
                    </span>
                    <span
                      style={{
                        flex: 1,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {e.subject || e.notes || e.purpose}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// Local style helpers
// ─────────────────────────────────────────────────────────────

const detailLabelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  color: "#94A3B8",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
};

const detailValueStyle: React.CSSProperties = {
  fontSize: 13,
  color: "#0F172A",
  marginTop: 4,
  whiteSpace: "pre-wrap",
};

function paginationBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    padding: "6px 14px",
    border: "1px solid #E2E8F0",
    borderRadius: 6,
    background: disabled ? "#F8FAFC" : "#fff",
    color: disabled ? "#CBD5E1" : "#0F172A",
    fontSize: 13,
    cursor: disabled ? "not-allowed" : "pointer",
  };
}
