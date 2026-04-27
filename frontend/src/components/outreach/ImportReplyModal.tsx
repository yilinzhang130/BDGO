"use client";

import { useState, useEffect, useRef } from "react";
import { generateReport, fetchReportStatus, createOutreachEvent } from "@/lib/api";
import { errorMessage } from "@/lib/format";

const REPLY_STATUSES = [
  { value: "replied", label: "已回复" },
  { value: "meeting", label: "会议中" },
  { value: "cda_signed", label: "CDA 已签" },
  { value: "ts_signed", label: "TS 已签" },
  { value: "passed", label: "已 pass" },
  { value: "dead", label: "已终止" },
];

interface ParsedResult {
  to_company: string;
  status: string;
  next_step: string;
  keywords: string;
  notes: string;
}

function emptyParsed(defaultCompany = ""): ParsedResult {
  return { to_company: defaultCompany, status: "replied", next_step: "", keywords: "", notes: "" };
}

interface Props {
  open: boolean;
  onClose: () => void;
  onArchived: () => void;
  defaultCompany?: string;
}

type Stage = "input" | "parsing" | "review" | "archiving";

export function ImportReplyModal({ open, onClose, onArchived, defaultCompany }: Props) {
  const [stage, setStage] = useState<Stage>("input");
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<ParsedResult>(() => emptyParsed(defaultCompany));
  const [err, setErr] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (open) {
      setStage("input");
      setText("");
      setParsed(emptyParsed(defaultCompany));
      setErr(null);
    } else {
      if (pollRef.current) clearTimeout(pollRef.current);
    }
  }, [open, defaultCompany]);

  const handleParse = async () => {
    if (!text.trim()) return;
    setStage("parsing");
    setErr(null);
    try {
      const resp = await generateReport("import-reply", { content: text });
      const taskId = resp.task_id;
      await pollUntilDone(taskId);
    } catch {
      setParsed(emptyParsed(defaultCompany));
      setStage("review");
    }
  };

  const pollUntilDone = async (taskId: string) => {
    const check = async () => {
      try {
        const s = await fetchReportStatus(taskId);
        if (s.status === "done") {
          const meta = (s.result?.meta ?? {}) as Record<string, unknown>;
          setParsed({
            to_company: String(meta.to_company ?? defaultCompany ?? ""),
            status: String(meta.status ?? "replied"),
            next_step: String(meta.next_step ?? ""),
            keywords: String(meta.keywords ?? ""),
            notes: String(meta.notes ?? ""),
          });
          setStage("review");
        } else if (s.status === "error") {
          setParsed(emptyParsed(defaultCompany));
          setStage("review");
        } else {
          pollRef.current = setTimeout(() => void check(), 3000);
        }
      } catch {
        setParsed(emptyParsed(defaultCompany));
        setStage("review");
      }
    };
    await check();
  };

  const handleArchive = async () => {
    if (!parsed.to_company.trim()) {
      setErr("对手公司不能为空");
      return;
    }
    setStage("archiving");
    setErr(null);
    try {
      await createOutreachEvent({
        to_company: parsed.to_company,
        purpose: "follow_up",
        status: parsed.status,
        notes: [
          parsed.notes,
          parsed.next_step ? `下一步：${parsed.next_step}` : "",
          parsed.keywords ? `关键词：${parsed.keywords}` : "",
        ]
          .filter(Boolean)
          .join("\n"),
      });
      onArchived();
      onClose();
    } catch (e: unknown) {
      setErr(errorMessage(e, "归档失败"));
      setStage("review");
    }
  };

  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.45)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px 16px",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 14,
          boxShadow: "0 8px 40px rgba(15,23,42,0.18)",
          width: "100%",
          maxWidth: 640,
          padding: "28px 32px",
        }}
      >
        {/* Title row */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 20,
          }}
        >
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "#0F172A", margin: 0 }}>
            导入对方回信
          </h2>
          <button
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              fontSize: 18,
              color: "#94A3B8",
              cursor: "pointer",
              padding: 4,
            }}
          >
            ✕
          </button>
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
              marginBottom: 16,
            }}
          >
            {err}
          </div>
        )}

        {/* Stage: input */}
        {(stage === "input" || stage === "parsing") && (
          <>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="在此粘贴对方的邮件正文…"
              rows={12}
              disabled={stage === "parsing"}
              style={{
                width: "100%",
                boxSizing: "border-box",
                padding: "12px 14px",
                border: "1px solid #E2E8F0",
                borderRadius: 8,
                fontSize: 13,
                fontFamily: "inherit",
                resize: "vertical",
                outline: "none",
                color: "#0F172A",
                background: stage === "parsing" ? "#F8FAFC" : "#fff",
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 16 }}>
              <button onClick={onClose} style={secondaryBtn}>
                取消
              </button>
              <button
                onClick={() => void handleParse()}
                disabled={!text.trim() || stage === "parsing"}
                style={primaryBtn(!text.trim() || stage === "parsing")}
              >
                {stage === "parsing" ? "解析中…" : "解析"}
              </button>
            </div>
          </>
        )}

        {/* Stage: review */}
        {(stage === "review" || stage === "archiving") && (
          <>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <Field label="对手公司 *">
                <input
                  value={parsed.to_company}
                  onChange={(e) => setParsed((p) => ({ ...p, to_company: e.target.value }))}
                  style={inputStyle}
                />
              </Field>
              <Field label="检测到的状态">
                <select
                  value={parsed.status}
                  onChange={(e) => setParsed((p) => ({ ...p, status: e.target.value }))}
                  style={inputStyle}
                >
                  {REPLY_STATUSES.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="下一步">
                <input
                  value={parsed.next_step}
                  onChange={(e) => setParsed((p) => ({ ...p, next_step: e.target.value }))}
                  style={inputStyle}
                />
              </Field>
              <Field label="关键词">
                <input
                  value={parsed.keywords}
                  onChange={(e) => setParsed((p) => ({ ...p, keywords: e.target.value }))}
                  style={inputStyle}
                />
              </Field>
              <Field label="备注">
                <textarea
                  value={parsed.notes}
                  onChange={(e) => setParsed((p) => ({ ...p, notes: e.target.value }))}
                  rows={3}
                  style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }}
                />
              </Field>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
              <button onClick={() => setStage("input")} style={secondaryBtn}>
                ← 重新粘贴
              </button>
              <button
                onClick={() => void handleArchive()}
                disabled={stage === "archiving"}
                style={primaryBtn(stage === "archiving")}
              >
                {stage === "archiving" ? "归档中…" : "归档"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: "#64748B",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 5,
        }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "8px 12px",
  border: "1px solid #E2E8F0",
  borderRadius: 7,
  fontSize: 13,
  color: "#0F172A",
  background: "#fff",
  outline: "none",
};

const secondaryBtn: React.CSSProperties = {
  padding: "8px 18px",
  border: "1px solid #E2E8F0",
  borderRadius: 7,
  background: "#fff",
  color: "#0F172A",
  fontSize: 13,
  cursor: "pointer",
};

function primaryBtn(disabled: boolean): React.CSSProperties {
  return {
    padding: "8px 20px",
    border: "none",
    borderRadius: 7,
    background: disabled ? "#93C5FD" : "#2563EB",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
  };
}
