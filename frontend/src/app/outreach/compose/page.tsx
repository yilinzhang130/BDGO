"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import {
  generateReport,
  fetchReportStatus,
  createOutreachEvent,
  type OutreachCreateBody,
} from "@/lib/api";

interface Recipient {
  company: string;
  contact: string;
}

interface RecipientResult {
  recipient: Recipient;
  markdown: string;
}

async function pollTask(taskId: string): Promise<string> {
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const s = await fetchReportStatus(taskId);
    if (s.status === "finished") return s.result?.markdown ?? "";
    if (s.status === "failed") throw new Error(s.error ?? "任务失败");
  }
  throw new Error("超时，请重试");
}

function splitBatchMarkdown(md: string, recipients: Recipient[]): RecipientResult[] {
  const sections = md
    .split(/\n---\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (sections.length === recipients.length) {
    return sections.map((markdown, i) => ({ recipient: recipients[i], markdown }));
  }
  return recipients.map((recipient) => ({ recipient, markdown: md }));
}

const S = {
  input: {
    padding: "9px 12px",
    border: "1px solid #E2E8F0",
    borderRadius: 8,
    fontSize: 14,
    background: "#fff",
    width: "100%",
    boxSizing: "border-box" as const,
    outline: "none",
  },
  label: {
    display: "block" as const,
    fontSize: 13,
    fontWeight: 500 as const,
    color: "#374151",
    marginBottom: 6,
    marginTop: 14,
  },
  btnPrimary: {
    padding: "10px 20px",
    background: "#2563EB",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600 as const,
    cursor: "pointer",
    width: "100%",
  },
};

export default function ComposePage() {
  const router = useRouter();
  const [mode, setMode] = useState<"single" | "batch">("single");
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [chipCo, setChipCo] = useState("");
  const [chipContact, setChipContact] = useState("");
  const [asset, setAsset] = useState("");
  const [tone, setTone] = useState("initial");
  const [lang, setLang] = useState("en");
  const [freePrompt, setFreePrompt] = useState("");
  const [previewState, setPreviewState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [results, setResults] = useState<RecipientResult[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [sendState, setSendState] = useState<"idle" | "sending">("idle");
  const [errMsg, setErrMsg] = useState("");

  function switchMode(m: "single" | "batch") {
    setMode(m);
    setRecipients([]);
    setResults([]);
    setPreviewState("idle");
    setActiveTab(0);
    setErrMsg("");
  }

  function addChip() {
    const co = chipCo.trim();
    if (!co) return;
    const rec: Recipient = { company: co, contact: chipContact.trim() };
    setRecipients(mode === "single" ? [rec] : (r) => [...r, rec]);
    setChipCo("");
    setChipContact("");
  }

  function removeChip(i: number) {
    setRecipients((r) => r.filter((_, idx) => idx !== i));
  }

  async function handlePreview() {
    setPreviewState("loading");
    setErrMsg("");
    try {
      let newResults: RecipientResult[];
      if (mode === "single") {
        const rec = recipients[0];
        const { task_id } = await generateReport("outreach-email", {
          to_company: rec.company,
          to_contact: rec.contact || undefined,
          asset_context: asset || undefined,
          tone,
          language: lang,
          custom_prompt: freePrompt || undefined,
        });
        const md = await pollTask(task_id);
        newResults = [{ recipient: rec, markdown: md }];
      } else {
        const { task_id } = await generateReport("batch-outreach", {
          recipients: recipients.map((r) => ({ company: r.company, contact: r.contact })),
          asset_context: asset || undefined,
          tone,
          language: lang,
          custom_prompt: freePrompt || undefined,
        });
        const md = await pollTask(task_id);
        newResults = splitBatchMarkdown(md, recipients);
      }
      setResults(newResults);
      setActiveTab(0);
      setPreviewState("done");
    } catch (e) {
      setErrMsg(e instanceof Error ? e.message : "预览失败");
      setPreviewState("error");
    }
  }

  async function handleSend() {
    setSendState("sending");
    setErrMsg("");
    try {
      for (const { recipient, markdown } of results) {
        const subject =
          markdown.split("\n")[0].replace(/^#+\s*/, "") || `Outreach — ${recipient.company}`;
        const body: OutreachCreateBody = {
          to_company: recipient.company,
          to_contact: recipient.contact || undefined,
          status: "sent",
          purpose: "cold_outreach",
          subject,
          notes: markdown.slice(0, 500),
          asset_context: asset || undefined,
        };
        await createOutreachEvent(body);
      }
      router.push("/outreach");
    } catch (e) {
      setErrMsg(e instanceof Error ? e.message : "发送失败");
      setSendState("idle");
    }
  }

  const canAddChip = mode === "batch" || recipients.length === 0;
  const canPreview = recipients.length > 0;

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px", fontFamily: "inherit" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 28 }}>
        <button
          onClick={() => router.push("/outreach")}
          style={{
            padding: "6px 14px",
            border: "1px solid #E2E8F0",
            borderRadius: 8,
            background: "#fff",
            cursor: "pointer",
            fontSize: 13,
            color: "#374151",
          }}
        >
          ← 返回
        </button>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: "#0F172A" }}>
          Compose Outreach
        </h1>
      </div>

      <div style={{ display: "flex", gap: 28, alignItems: "flex-start" }}>
        {/* ── LEFT: Form ── */}
        <div style={{ width: 420, flexShrink: 0 }}>
          {/* Mode toggle */}
          <div
            data-testid="mode-toggle"
            style={{
              display: "flex",
              border: "1px solid #E2E8F0",
              borderRadius: 8,
              overflow: "hidden",
              marginBottom: 20,
            }}
          >
            {(["single", "batch"] as const).map((m) => (
              <button
                key={m}
                data-testid={`mode-${m}`}
                onClick={() => switchMode(m)}
                style={{
                  flex: 1,
                  padding: "9px 0",
                  background: mode === m ? "#2563EB" : "#fff",
                  color: mode === m ? "#fff" : "#374151",
                  border: "none",
                  cursor: "pointer",
                  fontSize: 14,
                  fontWeight: mode === m ? 600 : 400,
                }}
              >
                {m === "single" ? "单收件人" : "批量"}
              </button>
            ))}
          </div>

          {/* Recipient chip input */}
          <label style={S.label}>收件人</label>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <input
              data-testid="chip-company"
              value={chipCo}
              onChange={(e) => setChipCo(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addChip()}
              placeholder="公司"
              style={{ ...S.input, flex: 1 }}
            />
            <input
              data-testid="chip-contact"
              value={chipContact}
              onChange={(e) => setChipContact(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addChip()}
              placeholder="联系人"
              style={{ ...S.input, flex: 1 }}
            />
            <button
              onClick={addChip}
              disabled={!chipCo.trim() || !canAddChip}
              style={{
                padding: "9px 14px",
                background: chipCo.trim() && canAddChip ? "#2563EB" : "#E2E8F0",
                color: chipCo.trim() && canAddChip ? "#fff" : "#9CA3AF",
                border: "none",
                borderRadius: 8,
                cursor: chipCo.trim() && canAddChip ? "pointer" : "not-allowed",
                fontSize: 16,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              +
            </button>
          </div>

          {/* Chips */}
          <div
            data-testid="chips"
            style={{ display: "flex", flexWrap: "wrap", gap: 6, minHeight: 28, marginBottom: 4 }}
          >
            {recipients.map((r, i) => (
              <span
                key={i}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "4px 10px",
                  background: "#EFF6FF",
                  border: "1px solid #BFDBFE",
                  borderRadius: 20,
                  fontSize: 13,
                  color: "#1E40AF",
                }}
              >
                {r.company}
                {r.contact ? ` · ${r.contact}` : ""}
                <button
                  onClick={() => removeChip(i)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "#6B7280",
                    padding: 0,
                    lineHeight: 1,
                    fontSize: 14,
                  }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>

          {/* Asset */}
          <label style={S.label}>关联资产（可选）</label>
          <input
            value={asset}
            onChange={(e) => setAsset(e.target.value)}
            placeholder="输入资产名称…"
            style={S.input}
          />

          {/* Tone + Lang */}
          <div style={{ display: "flex", gap: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={S.label}>语调</label>
              <select value={tone} onChange={(e) => setTone(e.target.value)} style={S.input}>
                <option value="initial">Initial</option>
                <option value="follow-up">Follow-up</option>
                <option value="nudge">Nudge</option>
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={S.label}>语言</label>
              <select value={lang} onChange={(e) => setLang(e.target.value)} style={S.input}>
                <option value="en">English</option>
                <option value="zh">中文</option>
              </select>
            </div>
          </div>

          {/* Free prompt */}
          <label style={S.label}>自定义提示（可选）</label>
          <textarea
            value={freePrompt}
            onChange={(e) => setFreePrompt(e.target.value)}
            rows={4}
            placeholder="例如：重点提 XX 项目，语气偏学术…"
            style={{ ...S.input, resize: "vertical" }}
          />

          {/* Preview button */}
          <button
            data-testid="btn-preview"
            onClick={handlePreview}
            disabled={!canPreview || previewState === "loading"}
            style={{
              ...S.btnPrimary,
              marginTop: 16,
              opacity: !canPreview || previewState === "loading" ? 0.5 : 1,
              cursor: !canPreview || previewState === "loading" ? "not-allowed" : "pointer",
            }}
          >
            {previewState === "loading" ? "生成中…" : "预览"}
          </button>
        </div>

        {/* ── RIGHT: Preview ── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {errMsg && (
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
              {errMsg}
            </div>
          )}

          {previewState === "loading" && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 300,
                color: "#6B7280",
                fontSize: 14,
              }}
            >
              正在生成邮件草稿，请稍候…
            </div>
          )}

          {previewState === "done" && results.length > 0 && (
            <>
              {/* Tabs — only shown for batch with multiple results */}
              {results.length > 1 && (
                <div
                  style={{
                    display: "flex",
                    borderBottom: "2px solid #E2E8F0",
                    marginBottom: 16,
                    overflowX: "auto",
                  }}
                >
                  {results.map((r, i) => (
                    <button
                      key={i}
                      onClick={() => setActiveTab(i)}
                      style={{
                        padding: "8px 16px",
                        border: "none",
                        background: "none",
                        cursor: "pointer",
                        fontSize: 13,
                        fontWeight: activeTab === i ? 700 : 400,
                        color: activeTab === i ? "#2563EB" : "#4B5563",
                        borderBottom: `2px solid ${activeTab === i ? "#2563EB" : "transparent"}`,
                        marginBottom: -2,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {r.recipient.company}
                    </button>
                  ))}
                </div>
              )}

              {/* Markdown content */}
              <div
                style={{
                  background: "#F8FAFC",
                  border: "1px solid #E2E8F0",
                  borderRadius: 10,
                  padding: "20px 24px",
                  fontSize: 14,
                  lineHeight: 1.7,
                  minHeight: 200,
                }}
              >
                <ReactMarkdown>{results[activeTab]?.markdown ?? ""}</ReactMarkdown>
              </div>

              {/* Send button */}
              <button
                data-testid="btn-send"
                onClick={handleSend}
                disabled={sendState === "sending"}
                style={{
                  ...S.btnPrimary,
                  marginTop: 16,
                  background: "#059669",
                  opacity: sendState === "sending" ? 0.6 : 1,
                  cursor: sendState === "sending" ? "not-allowed" : "pointer",
                }}
              >
                {sendState === "sending" ? "发送中…" : "确认发送（自动 log）"}
              </button>
            </>
          )}

          {(previewState === "idle" || previewState === "error") && !errMsg && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 300,
                background: "#F8FAFC",
                border: "1px dashed #CBD5E1",
                borderRadius: 10,
                color: "#94A3B8",
                fontSize: 14,
              }}
            >
              填写左侧表单，点击「预览」生成邮件草稿
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
