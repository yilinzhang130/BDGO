"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchCatalysts } from "@/lib/api";

/* ─── Status helpers ─── */

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  overdue: { label: "Overdue", color: "#dc2626", bg: "#fef2f2", dot: "🔴" },
  imminent: { label: "< 30 days", color: "#d97706", bg: "#fffbeb", dot: "🟡" },
  upcoming: { label: "30–90 days", color: "#2563eb", bg: "#eff6ff", dot: "🔵" },
  far: { label: "> 90 days", color: "#6b7280", bg: "#f9fafb", dot: "⚪" },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.far;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: 9999,
        fontSize: 12,
        fontWeight: 500,
        color: cfg.color,
        backgroundColor: cfg.bg,
      }}
    >
      {cfg.dot} {cfg.label}
    </span>
  );
}

function PhaseBadge({ phase }: { phase: string }) {
  if (!phase) return null;
  const colors: Record<string, string> = {
    "Phase 3": "#059669",
    "Phase 2": "#2563eb",
    "Phase 1": "#7c3aed",
    "Pre-clinical": "#6b7280",
    Commercial: "#0d9488",
  };
  const matchedKey = Object.keys(colors).find((k) => phase.includes(k));
  const color = matchedKey ? colors[matchedKey] : "#6b7280";
  return (
    <span
      style={{
        padding: "1px 6px",
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 500,
        color,
        border: `1px solid ${color}33`,
        backgroundColor: `${color}0d`,
      }}
    >
      {phase}
    </span>
  );
}

/* ─── Stat card ─── */
function StatCard({
  label,
  value,
  color,
  active,
  onClick,
}: {
  label: string;
  value: number;
  color: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        minWidth: 120,
        padding: "16px 20px",
        borderRadius: 12,
        border: active ? `2px solid ${color}` : "1px solid #e5e7eb",
        background: active ? `${color}0a` : "#fff",
        cursor: "pointer",
        textAlign: "left",
        transition: "all 0.15s",
      }}
    >
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value.toLocaleString()}</div>
      <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>{label}</div>
    </button>
  );
}

/* ─── Event row ─── */
function EventRow({ event, onClick }: { event: any; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: "grid",
        gridTemplateColumns: "110px 1fr 140px 100px 90px",
        gap: 12,
        padding: "12px 16px",
        borderBottom: "1px solid #f3f4f6",
        cursor: "pointer",
        transition: "background 0.1s",
        alignItems: "center",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "#f9fafb")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      {/* Date */}
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#111" }}>{event.date}</div>
        <div style={{ fontSize: 11, color: "#9ca3af" }}>{event.raw_date}</div>
      </div>
      {/* Event */}
      <div>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#111", lineHeight: 1.3 }}>
          {event.event || "Milestone"}
        </div>
        <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
          <span style={{ fontWeight: 500 }}>{event.company}</span>
          {event.asset && <span> · {event.asset}</span>}
        </div>
      </div>
      {/* Indication */}
      <div style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.3 }}>
        {(event.indication || "").slice(0, 50)}
        {(event.indication || "").length > 50 ? "…" : ""}
      </div>
      {/* Phase */}
      <div>
        <PhaseBadge phase={event.phase} />
      </div>
      {/* Status */}
      <div>
        <StatusBadge status={event.status} />
      </div>
    </div>
  );
}

/* ─── Detail panel ─── */
function DetailPanel({ event, onClose }: { event: any; onClose: () => void }) {
  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: 420,
        backgroundColor: "#fff",
        boxShadow: "-4px 0 24px rgba(0,0,0,0.1)",
        zIndex: 50,
        overflowY: "auto",
        padding: 24,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Catalyst Detail</h2>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            fontSize: 20,
            cursor: "pointer",
            color: "#6b7280",
          }}
        >
          ✕
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <StatusBadge status={event.status} />
        <PhaseBadge phase={event.phase} />
      </div>

      <div style={{ display: "grid", gap: 16 }}>
        <Field label="Event" value={event.event} />
        <Field
          label="Company"
          value={event.company}
          link={`/companies/${encodeURIComponent(event.company)}`}
        />
        <Field label="Asset" value={event.asset} />
        <Field label="Expected Date" value={`${event.date} (raw: ${event.raw_date})`} />
        <Field label="Catalyst Type" value={event.type} />
        <Field label="Certainty" value={event.certainty} />
        <Field label="Indication" value={event.indication} />
        <Field label="Data Status" value={event.data_status} />
        <Field label="Result" value={event.result} />
        {event.trial_id && <Field label="Trial ID" value={event.trial_id} />}
        {event.calendar_detail && <Field label="Full Calendar" value={event.calendar_detail} />}
      </div>
    </div>
  );
}

function Field({ label, value, link }: { label: string; value?: string; link?: string }) {
  if (!value) return null;
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "#9ca3af",
          textTransform: "uppercase",
          marginBottom: 2,
        }}
      >
        {label}
      </div>
      {link ? (
        <a href={link} style={{ fontSize: 14, color: "#2563eb", textDecoration: "none" }}>
          {value}
        </a>
      ) : (
        <div style={{ fontSize: 14, color: "#111", lineHeight: 1.4 }}>{value}</div>
      )}
    </div>
  );
}

/* ─── Backdrop for detail panel ─── */
function Backdrop({ onClick }: { onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.2)",
        zIndex: 49,
      }}
    />
  );
}

/* ─── Calendar mini-heatmap ─── */
function MonthGrid({ events, year, month }: { events: any[]; year: number; month: number }) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const monthStr = `${year}-${String(month + 1).padStart(2, "0")}`;
  const dayMap: Record<number, { count: number; status: string }> = {};
  for (const e of events) {
    if (e.date.startsWith(monthStr)) {
      const day = parseInt(e.date.split("-")[2], 10);
      if (!dayMap[day]) dayMap[day] = { count: 0, status: e.status };
      dayMap[day].count++;
      // Priority: overdue > imminent > upcoming > far
      const prio = ["overdue", "imminent", "upcoming", "far"];
      if (prio.indexOf(e.status) < prio.indexOf(dayMap[day].status)) {
        dayMap[day].status = e.status;
      }
    }
  }

  const cells: JSX.Element[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(<div key={`b-${i}`} />);
  for (let d = 1; d <= daysInMonth; d++) {
    const info = dayMap[d];
    const cfg = info ? STATUS_CONFIG[info.status] : null;
    cells.push(
      <div
        key={d}
        title={info ? `${info.count} catalyst(s)` : undefined}
        style={{
          width: 28,
          height: 28,
          borderRadius: 6,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 11,
          fontWeight: info ? 600 : 400,
          color: info ? cfg!.color : "#9ca3af",
          backgroundColor: info ? cfg!.bg : "transparent",
          border: info ? `1px solid ${cfg!.color}33` : "none",
        }}
      >
        {d}
      </div>,
    );
  }

  const monthNames = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return (
    <div style={{ minWidth: 220 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6 }}>
        {monthNames[month]} {year}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 28px)", gap: 2 }}>
        {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
          <div
            key={i}
            style={{ fontSize: 10, color: "#9ca3af", textAlign: "center", fontWeight: 600 }}
          >
            {d}
          </div>
        ))}
        {cells}
      </div>
    </div>
  );
}

/* ─── Main page ─── */
export default function CatalystsPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [phase, setPhase] = useState("");
  const [catalystType, setCatalystType] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<any>(null);
  const [view, setView] = useState<"list" | "calendar">("list");

  const load = useCallback(() => {
    setLoading(true);
    fetchCatalysts({
      q,
      status_filter: statusFilter,
      phase,
      catalyst_type: catalystType,
      year,
      page,
      page_size: 200,
    })
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [q, statusFilter, phase, catalystType, year, page]);

  useEffect(() => {
    load();
  }, [load]);

  const stats = data?.stats || { total: 0, overdue: 0, imminent: 0, upcoming: 0, far: 0 };
  const events = data?.data || [];
  const types = data?.types || [];

  return (
    <div className="page-container" style={{ maxWidth: 1100 }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Catalyst Calendar</h1>
          <p style={{ fontSize: 14, color: "#6b7280", margin: "4px 0 0" }}>
            Track clinical milestones, data readouts, and regulatory decisions
          </p>
        </div>
        <div
          style={{ display: "flex", gap: 4, background: "#f3f4f6", borderRadius: 8, padding: 3 }}
        >
          {(["list", "calendar"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: "none",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
                background: view === v ? "#fff" : "transparent",
                color: view === v ? "#111" : "#6b7280",
                boxShadow: view === v ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              }}
            >
              {v === "list" ? "📋 List" : "📅 Calendar"}
            </button>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <StatCard
          label="Total Catalysts"
          value={stats.total}
          color="#111"
          active={statusFilter === ""}
          onClick={() => {
            setStatusFilter("");
            setPage(1);
          }}
        />
        <StatCard
          label="Overdue"
          value={stats.overdue}
          color="#dc2626"
          active={statusFilter === "overdue"}
          onClick={() => {
            setStatusFilter(statusFilter === "overdue" ? "" : "overdue");
            setPage(1);
          }}
        />
        <StatCard
          label="Imminent (< 30d)"
          value={stats.imminent}
          color="#d97706"
          active={statusFilter === "imminent"}
          onClick={() => {
            setStatusFilter(statusFilter === "imminent" ? "" : "imminent");
            setPage(1);
          }}
        />
        <StatCard
          label="Upcoming (30–90d)"
          value={stats.upcoming}
          color="#2563eb"
          active={statusFilter === "upcoming"}
          onClick={() => {
            setStatusFilter(statusFilter === "upcoming" ? "" : "upcoming");
            setPage(1);
          }}
        />
        <StatCard
          label="Far (> 90d)"
          value={stats.far}
          color="#6b7280"
          active={statusFilter === "far"}
          onClick={() => {
            setStatusFilter(statusFilter === "far" ? "" : "far");
            setPage(1);
          }}
        />
      </div>

      {/* Filters */}
      <div
        style={{
          display: "flex",
          gap: 10,
          marginBottom: 16,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <input
          type="text"
          placeholder="Search company, asset, event..."
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          style={{
            flex: 1,
            minWidth: 200,
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid #e5e7eb",
            fontSize: 14,
            outline: "none",
          }}
        />
        <select
          value={year}
          onChange={(e) => {
            setYear(Number(e.target.value));
            setPage(1);
          }}
          style={{
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid #e5e7eb",
            fontSize: 13,
          }}
        >
          {[2024, 2025, 2026, 2027, 2028, 2029, 2030].map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
        <select
          value={phase}
          onChange={(e) => {
            setPhase(e.target.value);
            setPage(1);
          }}
          style={{
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid #e5e7eb",
            fontSize: 13,
          }}
        >
          <option value="">All Phases</option>
          {["Phase 1", "Phase 2", "Phase 3", "Pre-clinical", "Commercial"].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          value={catalystType}
          onChange={(e) => {
            setCatalystType(e.target.value);
            setPage(1);
          }}
          style={{
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid #e5e7eb",
            fontSize: 13,
          }}
        >
          <option value="">All Types</option>
          {types.map((t: string) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: "#9ca3af" }}>
          Loading catalysts...
        </div>
      ) : view === "list" ? (
        <div
          style={{
            background: "#fff",
            borderRadius: 12,
            border: "1px solid #e5e7eb",
            overflow: "hidden",
          }}
        >
          {/* Table header */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "110px 1fr 140px 100px 90px",
              gap: 12,
              padding: "10px 16px",
              background: "#f9fafb",
              borderBottom: "1px solid #e5e7eb",
              fontSize: 11,
              fontWeight: 600,
              color: "#6b7280",
              textTransform: "uppercase",
            }}
          >
            <div>Date</div>
            <div>Event</div>
            <div>Indication</div>
            <div>Phase</div>
            <div>Status</div>
          </div>
          {events.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>
              No catalysts found
            </div>
          ) : (
            events.map((e: any) => <EventRow key={e.id} event={e} onClick={() => setSelected(e)} />)
          )}
          {/* Pagination */}
          {data && data.total > 200 && (
            <div style={{ display: "flex", justifyContent: "center", gap: 8, padding: 16 }}>
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid #e5e7eb",
                  cursor: "pointer",
                }}
              >
                ← Prev
              </button>
              <span style={{ padding: "6px 12px", fontSize: 13, color: "#6b7280" }}>
                Page {page} of {Math.ceil(data.total / 200)}
              </span>
              <button
                disabled={page * 200 >= data.total}
                onClick={() => setPage(page + 1)}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid #e5e7eb",
                  cursor: "pointer",
                }}
              >
                Next →
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Calendar view — 12-month grid */
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 20,
            padding: 16,
            background: "#fff",
            borderRadius: 12,
            border: "1px solid #e5e7eb",
          }}
        >
          {Array.from({ length: 12 }, (_, i) => (
            <MonthGrid key={i} events={events} year={year} month={i} />
          ))}
        </div>
      )}

      {/* Detail panel */}
      {selected && (
        <>
          <Backdrop onClick={() => setSelected(null)} />
          <DetailPanel event={selected} onClose={() => setSelected(null)} />
        </>
      )}
    </div>
  );
}
