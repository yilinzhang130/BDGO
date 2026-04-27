"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { generateReport, fetchReportStatus } from "@/lib/api";
import { useSellAsset } from "../layout";

// ─── types ────────────────────────────────────────────────────

type Stage = "idle" | "running" | "done" | "error";

// ─── useGenerate ──────────────────────────────────────────────

function useGenerate(slug: string) {
  const [stage, setStage] = useState<Stage>("idle");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generate = useCallback(
    async (params: Record<string, unknown>) => {
      setStage("running");
      setResult(null);
      setError(null);
      try {
        const resp = await generateReport(slug, params);
        if (resp.status === "completed") {
          setResult(resp.result?.markdown ?? "");
          setStage("done");
          return;
        }
        const taskId = resp.task_id;
        const poll = async () => {
          try {
            const s = await fetchReportStatus(taskId);
            if (s.status === "completed") {
              setResult(s.result?.markdown ?? "");
              setStage("done");
            } else if (s.status === "failed") {
              setError(s.error || "生成失败");
              setStage("error");
            } else {
              setTimeout(poll, 2000);
            }
          } catch (e) {
            setError(e instanceof Error ? e.message : "轮询失败");
            setStage("error");
          }
        };
        setTimeout(poll, 1500);
      } catch (e) {
        setError(e instanceof Error ? e.message : "生成失败");
        setStage("error");
      }
    },
    [slug],
  );

  const reset = useCallback(() => {
    setStage("idle");
    setResult(null);
    setError(null);
  }, []);

  return { stage, result, error, generate, reset };
}

// ─── ResultBox ────────────────────────────────────────────────

function ResultBox({ markdown, onReset }: { markdown: string; onReset: () => void }) {
  const copy = () => void navigator.clipboard.writeText(markdown);
  const printPdf = () => {
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(
      `<pre style="font-family:monospace;white-space:pre-wrap;padding:24px">${markdown.replace(/</g, "&lt;")}</pre>`,
    );
    w.document.close();
    w.print();
  };

  return (
    <div style={{ marginTop: 12 }}>
      <div
        style={{
          background: "#F8FAFF",
          border: "1px solid #E8EFFE",
          borderRadius: 8,
          padding: "12px 14px",
          fontSize: 12,
          color: "#334155",
          lineHeight: 1.65,
          maxHeight: 280,
          overflowY: "auto",
          whiteSpace: "pre-wrap",
          fontFamily: "ui-monospace, monospace",
        }}
      >
        {markdown}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <Btn variant="ghost" onClick={copy}>
          复制
        </Btn>
        <Btn variant="ghost" onClick={printPdf}>
          导出 PDF
        </Btn>
        <Btn variant="ghost" onClick={onReset}>
          重置
        </Btn>
      </div>
    </div>
  );
}

// ─── TimelineCard ─────────────────────────────────────────────

interface TimelineCardProps {
  step: number;
  title: string;
  subtitle?: string;
  isLast?: boolean;
  defaultOpen?: boolean;
  children?: React.ReactNode;
}

function TimelineCard({
  step,
  title,
  subtitle,
  isLast,
  defaultOpen = false,
  children,
}: TimelineCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div style={{ display: "flex", gap: 0 }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: 40,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: "#2563EB",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 13,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {step}
        </div>
        {!isLast && <div style={{ width: 2, flex: 1, background: "#E2E8F0", minHeight: 28 }} />}
      </div>

      <div style={{ flex: 1, paddingBottom: isLast ? 0 : 16, marginLeft: 12 }}>
        <div
          style={{
            background: "#fff",
            border: "1px solid #E8EFFE",
            borderRadius: 10,
            boxShadow: "0 1px 6px rgba(30,58,138,0.04)",
            overflow: "hidden",
          }}
        >
          <button
            onClick={() => setOpen((o) => !o)}
            style={{
              width: "100%",
              textAlign: "left",
              padding: "14px 16px",
              border: "none",
              background: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#0F172A" }}>{title}</div>
              {subtitle && (
                <div style={{ fontSize: 12, color: "#64748B", marginTop: 2 }}>{subtitle}</div>
              )}
            </div>
            <span style={{ fontSize: 11, color: "#94A3B8", marginLeft: 8 }}>
              {open ? "▲" : "▼"}
            </span>
          </button>
          {open && children && (
            <div style={{ padding: "0 16px 16px", borderTop: "1px solid #F1F5F9" }}>{children}</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Btn ──────────────────────────────────────────────────────

function Btn({
  onClick,
  disabled,
  children,
  variant = "primary",
}: {
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "ghost";
}) {
  const base: React.CSSProperties = {
    padding: "7px 14px",
    fontSize: 13,
    borderRadius: 6,
    cursor: disabled ? "not-allowed" : "pointer",
    fontWeight: 500,
    border: "1px solid transparent",
    opacity: disabled ? 0.55 : 1,
  };
  const styles: Record<string, React.CSSProperties> = {
    primary: { ...base, background: "#2563EB", color: "#fff" },
    secondary: { ...base, background: "#F1F5F9", color: "#334155", borderColor: "#E2E8F0" },
    ghost: { ...base, background: "none", color: "#64748B", borderColor: "#E2E8F0" },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={styles[variant]}>
      {children}
    </button>
  );
}

// ─── Page ─────────────────────────────────────────────────────

export default function DdTabPage() {
  const { assetId } = useParams<{ assetId: string }>();
  const { asset } = useSellAsset();
  const assetCtx = [asset?.entity_key, asset?.notes].filter(Boolean).join(" — ");

  const checklist = useGenerate("dd-checklist");
  const faq = useGenerate("dd-faq");
  const meeting = useGenerate("meeting-brief");

  const [counterparty, setCounterparty] = useState("");
  const [meetingPurpose, setMeetingPurpose] = useState("initial_meeting");

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: "#0F172A", margin: "0 0 24px" }}>
        DD 准备时间线
      </h2>

      <div style={{ maxWidth: 720 }}>
        {/* 1 ── CDA 准备 */}
        <TimelineCard step={1} title="CDA 准备" subtitle="与对方签署保密协议，确定 DD 范围">
          <p style={{ fontSize: 13, color: "#64748B", margin: "12px 0 0", lineHeight: 1.65 }}>
            在数据室开放前完成 CDA / NDA 签署。建议使用双边 NDA 模板，保密期 ≥ 2
            年，范围涵盖所有披露材料。
          </p>
        </TimelineCard>

        {/* 2 ── 数据室开放 */}
        <TimelineCard step={2} title="数据室开放" subtitle="整理并向对方开放 DD 材料">
          <div style={{ marginTop: 12 }}>
            <p style={{ fontSize: 13, color: "#64748B", margin: "0 0 10px", lineHeight: 1.65 }}>
              前往数据室标签页，生成清单并上传相关文件。
            </p>
            <Link
              href={`/sell/${assetId}/dataroom`}
              style={{
                display: "inline-block",
                padding: "7px 14px",
                background: "#F1F5F9",
                color: "#334155",
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 500,
                textDecoration: "none",
                border: "1px solid #E2E8F0",
              }}
            >
              → 前往数据室
            </Link>
          </div>
        </TimelineCard>

        {/* 3 ── 对方 DD 提问 */}
        <TimelineCard
          step={3}
          title="对方 DD 提问"
          subtitle="提前准备问题清单与 FAQ，减少沟通摩擦"
          defaultOpen
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 12 }}>
            {/* DD checklist */}
            <div>
              <Btn
                onClick={() =>
                  void checklist.generate({ perspective: "seller", asset_context: assetCtx })
                }
                disabled={checklist.stage === "running" || checklist.stage === "done"}
              >
                {checklist.stage === "running" ? "生成中…" : "生成 DD checklist (seller 视角)"}
              </Btn>
              {checklist.stage === "error" && (
                <div style={{ fontSize: 12, color: "#DC2626", marginTop: 6 }}>
                  {checklist.error}
                  <button
                    onClick={checklist.reset}
                    style={{
                      marginLeft: 8,
                      fontSize: 12,
                      color: "#94A3B8",
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                    }}
                  >
                    重试
                  </button>
                </div>
              )}
              {checklist.stage === "done" && checklist.result !== null && (
                <ResultBox markdown={checklist.result} onReset={checklist.reset} />
              )}
            </div>

            {/* FAQ */}
            <div>
              <Btn
                variant="secondary"
                onClick={() => void faq.generate({ asset_context: assetCtx })}
                disabled={faq.stage === "running" || faq.stage === "done"}
              >
                {faq.stage === "running" ? "生成中…" : "预生成 FAQ"}
              </Btn>
              {faq.stage === "error" && (
                <div style={{ fontSize: 12, color: "#DC2626", marginTop: 6 }}>
                  {faq.error}
                  <button
                    onClick={faq.reset}
                    style={{
                      marginLeft: 8,
                      fontSize: 12,
                      color: "#94A3B8",
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                    }}
                  >
                    重试
                  </button>
                </div>
              )}
              {faq.stage === "done" && faq.result !== null && (
                <ResultBox markdown={faq.result} onReset={faq.reset} />
              )}
            </div>
          </div>
        </TimelineCard>

        {/* 4 ── 面对面会议 */}
        <TimelineCard step={4} title="面对面会议" subtitle="准备管理层简报和会议材料" defaultOpen>
          <div style={{ marginTop: 12 }}>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div style={{ flex: 1, minWidth: 180 }}>
                <label
                  style={{ display: "block", fontSize: 12, color: "#64748B", marginBottom: 4 }}
                >
                  对方公司
                </label>
                <input
                  type="text"
                  value={counterparty}
                  onChange={(e) => setCounterparty(e.target.value)}
                  placeholder="e.g. AstraZeneca"
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    fontSize: 13,
                    border: "1px solid #CBD5E1",
                    borderRadius: 6,
                    outline: "none",
                    boxSizing: "border-box",
                  }}
                />
              </div>
              <div style={{ flex: 1, minWidth: 180 }}>
                <label
                  style={{ display: "block", fontSize: 12, color: "#64748B", marginBottom: 4 }}
                >
                  会议类型
                </label>
                <select
                  value={meetingPurpose}
                  onChange={(e) => setMeetingPurpose(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    fontSize: 13,
                    border: "1px solid #CBD5E1",
                    borderRadius: 6,
                    outline: "none",
                    background: "#fff",
                    boxSizing: "border-box",
                  }}
                >
                  <option value="initial_meeting">首次见面</option>
                  <option value="due_diligence">深度尽调</option>
                  <option value="negotiation">条款谈判</option>
                  <option value="management_presentation">管理层路演</option>
                </select>
              </div>
            </div>

            <Btn
              onClick={() =>
                void meeting.generate({
                  counterparty,
                  meeting_purpose: meetingPurpose,
                  asset_context: assetCtx,
                })
              }
              disabled={meeting.stage === "running" || meeting.stage === "done"}
            >
              {meeting.stage === "running" ? "生成中…" : "生成 meeting-brief"}
            </Btn>
            {meeting.stage === "error" && (
              <div style={{ fontSize: 12, color: "#DC2626", marginTop: 6 }}>
                {meeting.error}
                <button
                  onClick={meeting.reset}
                  style={{
                    marginLeft: 8,
                    fontSize: 12,
                    color: "#94A3B8",
                    border: "none",
                    background: "none",
                    cursor: "pointer",
                  }}
                >
                  重试
                </button>
              </div>
            )}
            {meeting.stage === "done" && meeting.result !== null && (
              <ResultBox markdown={meeting.result} onReset={meeting.reset} />
            )}
          </div>
        </TimelineCard>

        {/* 5 ── 出决定 */}
        <TimelineCard step={5} title="出决定" subtitle="对方提交 LOI / TS 或终止流程" isLast>
          <p style={{ fontSize: 13, color: "#64748B", margin: "12px 0 0", lineHeight: 1.65 }}>
            DD 流程完成后，对方将提交意向书（LOI）或条款清单（TS）。
            请在此阶段准备好相关法律文件，并启动正式谈判流程。
          </p>
        </TimelineCard>
      </div>
    </div>
  );
}
