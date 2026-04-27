"use client";

import { useState, useEffect, useCallback, useRef, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { useSellAsset } from "../layout";
import { generateReport, fetchReportStatus, createOutreachEvent } from "@/lib/api";
import { errorMessage } from "@/lib/format";

// ─── Types ────────────────────────────────────────────────────────────────────

type Phase = "Preclinical" | "Phase 1" | "Phase 2" | "Phase 3" | "Filed";
type Preference = "deal_size" | "治疗领域" | "地区";

interface BuyerRow {
  rank: number;
  company: string;
  score: string;
  reason: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseBuyerTable(markdown: string): BuyerRow[] {
  const rows: BuyerRow[] = [];
  for (const line of markdown.split("\n")) {
    if (!line.trim().startsWith("|")) continue;
    const cells = line
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cells.length >= 4 && /^\d+$/.test(cells[0])) {
      rows.push({
        rank: Number(cells[0]),
        company: cells[1],
        score: cells[2],
        reason: cells[3],
      });
    }
  }
  return rows;
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const label: CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 500,
  color: "#374151",
  marginBottom: 6,
};
const inputStyle: CSSProperties = {
  padding: "9px 12px",
  border: "1px solid #E2E8F0",
  borderRadius: 8,
  fontSize: 14,
  width: "100%",
  boxSizing: "border-box",
  outline: "none",
  background: "#fff",
};
const field: CSSProperties = { marginBottom: 16 };
const btnBase: CSSProperties = {
  border: "none",
  borderRadius: 8,
  cursor: "pointer",
  fontWeight: 600,
};
const TH: CSSProperties = {
  padding: "10px 14px",
  textAlign: "left",
  fontSize: 12,
  fontWeight: 700,
  color: "#64748B",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};
const TD: CSSProperties = { padding: "12px 14px", fontSize: 13 };

// ─── Component ────────────────────────────────────────────────────────────────

export default function BuyersTabPage() {
  const { asset, loading: assetLoading } = useSellAsset();
  const router = useRouter();

  const [target, setTarget] = useState("");
  const [indication, setIndication] = useState("");
  const [phase, setPhase] = useState<Phase>("Phase 2");
  const [topN, setTopN] = useState(10);
  const [preference, setPreference] = useState<Preference>("deal_size");

  const [stage, setStage] = useState<"form" | "running" | "done" | "error">("form");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [buyers, setBuyers] = useState<BuyerRow[]>([]);
  const [markdown, setMarkdown] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [addingOutreach, setAddingOutreach] = useState<Record<string, boolean>>({});

  // One-shot prefill: set target from asset entity_key on first load
  const prefillDone = useRef(false);
  useEffect(() => {
    if (!prefillDone.current && asset?.entity_key) {
      prefillDone.current = true;
      setTarget(asset.entity_key);
    }
  }, [asset?.entity_key]);

  // Polling loop
  useEffect(() => {
    if (stage !== "running" || !taskId) return;
    let alive = true;

    const poll = async () => {
      try {
        const status = await fetchReportStatus(taskId);
        if (!alive) return;
        if (status.progress_log?.length) setProgressLog(status.progress_log);
        if (status.status === "completed") {
          const md = status.result?.markdown ?? "";
          setMarkdown(md);
          setBuyers(parseBuyerTable(md));
          setStage("done");
        } else if (status.status === "failed") {
          setErr(status.error ?? "匹配失败");
          setStage("error");
        } else {
          setTimeout(poll, 2000);
        }
      } catch (e) {
        if (alive) {
          setErr(errorMessage(e, "状态查询失败"));
          setStage("error");
        }
      }
    };

    setTimeout(poll, 1500);
    return () => {
      alive = false;
    };
  }, [stage, taskId]);

  const handleRun = useCallback(async () => {
    if (!target.trim() || !indication.trim()) {
      setErr("请填写靶点和适应症");
      return;
    }
    setErr(null);
    setProgressLog([]);
    setBuyers([]);
    setMarkdown("");
    try {
      const resp = await generateReport("buyer-matching", {
        target: target.trim(),
        indication: indication.trim(),
        phase,
        top_n: topN,
        preference,
      });
      setTaskId(resp.task_id);
      if (resp.status === "completed") {
        const md = resp.result?.markdown ?? "";
        setMarkdown(md);
        setBuyers(parseBuyerTable(md));
        setStage("done");
      } else {
        setStage("running");
      }
    } catch (e) {
      setErr(errorMessage(e, "启动失败"));
      setStage("error");
    }
  }, [target, indication, phase, topN, preference]);

  const handleAddOutreach = useCallback(
    async (company: string) => {
      setAddingOutreach((prev) => ({ ...prev, [company]: true }));
      try {
        await createOutreachEvent({
          to_company: company,
          status: "draft",
          purpose: "cold_outreach",
          asset_context: asset?.entity_key ?? undefined,
        });
      } finally {
        setAddingOutreach((prev) => ({ ...prev, [company]: false }));
      }
    },
    [asset?.entity_key],
  );

  if (assetLoading) {
    return <div style={{ padding: 32, color: "#64748B" }}>加载中…</div>;
  }

  return (
    <div>
      {/* ── Form ─────────────────────────────────────────────────────── */}
      <div
        style={{
          background: "#fff",
          border: "1px solid #E8EFFE",
          borderRadius: 12,
          padding: 24,
          marginBottom: 24,
          boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
        }}
      >
        <h2 style={{ fontSize: 16, fontWeight: 700, color: "#0F172A", margin: "0 0 20px" }}>
          匹配买方
        </h2>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
          <div style={field}>
            <label style={label}>靶点 Target</label>
            <input
              style={inputStyle}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="e.g. KRAS G12C"
            />
          </div>
          <div style={field}>
            <label style={label}>适应症 Indication</label>
            <input
              style={inputStyle}
              value={indication}
              onChange={(e) => setIndication(e.target.value)}
              placeholder="e.g. NSCLC 一线"
            />
          </div>
          <div style={field}>
            <label style={label}>阶段 Phase</label>
            <select
              style={{ ...inputStyle, paddingRight: 8 }}
              value={phase}
              onChange={(e) => setPhase(e.target.value as Phase)}
            >
              {(["Preclinical", "Phase 1", "Phase 2", "Phase 3", "Filed"] as const).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div style={field}>
            <label style={label}>Top N（3–10）</label>
            <input
              style={inputStyle}
              type="number"
              min={3}
              max={10}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
            />
          </div>
        </div>

        <div style={field}>
          <label style={label}>偏好排序 Preference</label>
          <div style={{ display: "flex", gap: 24 }}>
            {(["deal_size", "治疗领域", "地区"] as const).map((p) => (
              <label
                key={p}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 14,
                  cursor: "pointer",
                }}
              >
                <input
                  type="radio"
                  name="preference"
                  value={p}
                  checked={preference === p}
                  onChange={() => setPreference(p)}
                />
                {p}
              </label>
            ))}
          </div>
        </div>

        {err && (
          <div
            style={{
              padding: "10px 14px",
              background: "#FEF2F2",
              border: "1px solid #FCA5A5",
              borderRadius: 8,
              color: "#991B1B",
              fontSize: 13,
              marginBottom: 12,
            }}
          >
            {err}
          </div>
        )}

        <button
          style={{
            ...btnBase,
            padding: "10px 22px",
            fontSize: 14,
            background: stage === "running" ? "#94A3B8" : "#2563EB",
            color: "#fff",
          }}
          onClick={handleRun}
          disabled={stage === "running"}
        >
          {stage === "running" ? "匹配中…" : "运行匹配"}
        </button>
      </div>

      {/* ── Progress ─────────────────────────────────────────────────── */}
      {stage === "running" && progressLog.length > 0 && (
        <div
          style={{
            background: "#F8FAFF",
            border: "1px solid #E8EFFE",
            borderRadius: 8,
            padding: 16,
            marginBottom: 24,
            fontSize: 12,
            color: "#64748B",
            lineHeight: 1.7,
          }}
        >
          {progressLog.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}

      {/* ── Buyer table ──────────────────────────────────────────────── */}
      {stage === "done" && buyers.length > 0 && (
        <div
          style={{
            background: "#fff",
            border: "1px solid #E8EFFE",
            borderRadius: 12,
            overflow: "hidden",
            marginBottom: 24,
            boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
          }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#F8FAFF" }}>
                <th style={TH}>排名</th>
                <th style={TH}>公司</th>
                <th style={TH}>匹配理由</th>
                <th style={TH}>历史 deal</th>
                <th style={TH}>操作</th>
              </tr>
            </thead>
            <tbody>
              {buyers.map((row) => (
                <tr key={row.rank} style={{ borderTop: "1px solid #F1F5F9" }}>
                  <td style={TD}>{row.rank}</td>
                  <td style={{ ...TD, fontWeight: 600, color: "#0F172A" }}>{row.company}</td>
                  <td style={{ ...TD, color: "#64748B", maxWidth: 320 }}>{row.reason}</td>
                  <td style={{ ...TD, color: "#94A3B8" }}>—</td>
                  <td style={TD}>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button
                        style={{
                          ...btnBase,
                          padding: "6px 12px",
                          fontSize: 12,
                          background: "#EFF6FF",
                          color: "#2563EB",
                        }}
                        onClick={() => void handleAddOutreach(row.company)}
                        disabled={addingOutreach[row.company]}
                      >
                        {addingOutreach[row.company] ? "…" : "+ 加入 outreach"}
                      </button>
                      <button
                        style={{
                          ...btnBase,
                          padding: "6px 12px",
                          fontSize: 12,
                          background: "#F8FAFF",
                          color: "#374151",
                          border: "1px solid #E2E8F0",
                        }}
                        onClick={() =>
                          router.push(
                            `/sell/${asset?.id}/teaser?buyer=${encodeURIComponent(row.company)}`,
                          )
                        }
                      >
                        → 生成 teaser
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Full markdown ────────────────────────────────────────────── */}
      {stage === "done" && markdown && (
        <details
          style={{
            background: "#fff",
            border: "1px solid #E8EFFE",
            borderRadius: 12,
            padding: 16,
            boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
          }}
        >
          <summary style={{ cursor: "pointer", fontSize: 13, color: "#64748B", fontWeight: 600 }}>
            查看完整分析报告
          </summary>
          <pre
            style={{
              marginTop: 12,
              fontSize: 12,
              whiteSpace: "pre-wrap",
              color: "#374151",
              lineHeight: 1.65,
            }}
          >
            {markdown}
          </pre>
        </details>
      )}
    </div>
  );
}
