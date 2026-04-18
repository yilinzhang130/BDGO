"use client";

import { useState, useEffect, useRef } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/components/AuthProvider";
import { type ReportTask, type PlanProposal, type PlanStatus } from "@/lib/sessions";
import { downloadWithAuth } from "@/lib/download";
import { PlanCard } from "./PlanCard";

interface ToolEvent {
  type: "tool_call" | "tool_result";
  name: string;
}

interface QuickSource {
  title: string;
  url: string;
  snippet: string;
}

interface Props {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  tools?: ToolEvent[];
  attachments?: string[];
  reportTasks?: ReportTask[];
  plan?: PlanProposal;
  planStatus?: PlanStatus;
  planSelectedIds?: string[];
  quickSources?: QuickSource[];
  error?: string;
  onRetry?: () => void;
  onPlanConfirm?: (selectedIds: string[]) => void;
  onPlanSkip?: () => void;
  onPlanCancel?: () => void;
}

// ── Tool display config ──────────────────────────────────────────────
// icon + label for each backend tool
const TOOL_META: Record<string, { icon: string; label: string }> = {
  search_companies:             { icon: "🏢", label: "Searching companies" },
  get_company:                  { icon: "🏢", label: "Fetching company details" },
  search_assets:                { icon: "🧬", label: "Searching pipeline assets" },
  get_asset:                    { icon: "🧬", label: "Fetching asset details" },
  search_clinical:              { icon: "🔬", label: "Searching clinical trials" },
  search_deals:                 { icon: "🤝", label: "Searching BD deals" },
  search_patents:               { icon: "📜", label: "Searching patents" },
  get_buyer_profile:            { icon: "🎯", label: "Fetching buyer profile" },
  count_by:                     { icon: "📊", label: "Aggregating data" },
  search_global:                { icon: "🔍", label: "Global search" },
  query_treatment_guidelines:   { icon: "🏥", label: "Querying treatment landscape" },
};

function getToolMeta(name: string) {
  return TOOL_META[name] || { icon: "⚙️", label: name.replace(/_/g, " ") };
}

// ── Tool Steps Panel ─────────────────────────────────────────────────
function ToolStepsPanel({ tools, isStreaming }: { tools: ToolEvent[]; isStreaming: boolean }) {
  const [expanded, setExpanded] = useState(true);

  // Build ordered list of tool steps, matching each call to its result.
  // The same tool name can appear in multiple rounds (e.g. search_companies
  // called twice), so we pair by occurrence index rather than just name.
  const uniqueTools: { name: string; completed: boolean }[] = [];
  const resultCounts: Record<string, number> = {};
  for (const t of tools) {
    if (t.type === "tool_result") {
      resultCounts[t.name] = (resultCounts[t.name] || 0) + 1;
    }
  }
  const callCounts: Record<string, number> = {};
  for (const t of tools) {
    if (t.type === "tool_call") {
      const idx = (callCounts[t.name] || 0);
      callCounts[t.name] = idx + 1;
      const completed = idx < (resultCounts[t.name] || 0);
      uniqueTools.push({ name: t.name, completed });
    }
  }

  if (uniqueTools.length === 0) return null;

  const doneCount = uniqueTools.filter((t) => t.completed).length;
  const allDone = doneCount === uniqueTools.length && !isStreaming;
  const headerLabel = allDone
    ? `Analyzed ${doneCount} data source${doneCount !== 1 ? "s" : ""}`
    : `Analyzing… ${doneCount}/${uniqueTools.length} steps`;

  return (
    <div className={`tool-steps-panel ${allDone ? "completed" : "active"}`}>
      <button
        className="tool-steps-header"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="tool-steps-header-left">
          {!allDone && <span className="tool-steps-spinner" />}
          {allDone && <span className="tool-steps-check">✓</span>}
          <span>{headerLabel}</span>
        </span>
        <span className={`tool-steps-chevron ${expanded ? "open" : ""}`}>›</span>
      </button>
      {expanded && (
        <div className="tool-steps-list">
          {uniqueTools.map((t, i) => {
            const meta = getToolMeta(t.name);
            return (
              <div
                key={`${t.name}-${i}`}
                className={`tool-step ${t.completed ? "done" : "running"}`}
              >
                <span className="tool-step-icon">{meta.icon}</span>
                <span className="tool-step-label">{meta.label}</span>
                <span className="tool-step-status">
                  {t.completed ? (
                    <span className="tool-step-done-icon">✓</span>
                  ) : (
                    <span className="tool-step-running-icon" />
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Report Task Card ─────────────────────────────────────────────────

interface ReportFile {
  format: string;
  filename: string;
}

const REPORT_LABELS: Record<string, string> = {
  disease_landscape: "疾病竞争格局",
  target_radar: "靶点雷达",
  buyer_profile: "买方画像",
  commercial_assessment: "商业化评估",
  ip_landscape: "IP景观",
  literature_review: "文献综述",
  clinical_brief: "临床指南简报",
};

function ReportTaskCard({ task_id, slug, estimated_seconds }: ReportTask) {
  const { token } = useAuth();
  const [status, setStatus] = useState<"polling" | "completed" | "failed">("polling");
  const [markdown, setMarkdown] = useState<string>("");
  const [files, setFiles] = useState<ReportFile[]>([]);
  const [expanded, setExpanded] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const doneRef = useRef(false);
  const label = REPORT_LABELS[slug] || slug.replace(/_/g, " ");

  useEffect(() => {
    const poll = async () => {
      if (doneRef.current) return;
      try {
        const res = await fetch(`/api/reports/status/${task_id}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "completed") {
          doneRef.current = true;
          setMarkdown(data.result?.markdown || "");
          setFiles(data.result?.files || []);
          setStatus("completed");
          if (pollRef.current) clearInterval(pollRef.current);
        } else if (data.status === "failed") {
          doneRef.current = true;
          setStatus("failed");
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {}
    };

    poll();
    pollRef.current = setInterval(poll, 4000);
    const timeout = setTimeout(() => {
      if (pollRef.current) clearInterval(pollRef.current);
    }, 300_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      clearTimeout(timeout);
    };
  }, [task_id, token]);

  if (status === "polling") {
    return (
      <div style={{ margin: "10px 0", padding: "12px 16px", background: "#EEF2FF", border: "1px solid #C7D2FE", borderRadius: 10, display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 14, height: 14, border: "2px solid #A5B4FC", borderTopColor: "#4F46E5", borderRadius: "50%", display: "inline-block", animation: "spin 0.8s linear infinite", flexShrink: 0 }} />
        <span style={{ fontSize: 13, color: "#4338CA", fontWeight: 500 }}>
          正在生成{label}报告…预计 {estimated_seconds} 秒
        </span>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div style={{ margin: "10px 0", padding: "12px 16px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10 }}>
        <span style={{ fontSize: 13, color: "#DC2626" }}>⚠️ 报告生成失败，请重试</span>
      </div>
    );
  }

  return (
    <div style={{ margin: "10px 0", border: "1px solid #BBF7D0", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ background: "#F0FDF4", padding: "10px 14px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "#16A34A", fontWeight: 700, fontSize: 13 }}>✓ {label}报告已生成</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {files.map((f) => (
            <button
              key={f.format}
              onClick={() => downloadWithAuth(`/api/reports/download/${task_id}/${f.format}`, f.filename)}
              style={{ fontSize: 11, fontWeight: 600, padding: "4px 10px", background: "#16A34A", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}
            >
              下载 {f.format.toUpperCase()}
            </button>
          ))}
          {markdown && (
            <button
              onClick={() => setExpanded(v => !v)}
              style={{ fontSize: 11, color: "#16A34A", background: "none", border: "1px solid #BBF7D0", borderRadius: 6, padding: "4px 10px", cursor: "pointer" }}
            >
              {expanded ? "收起预览" : "展开预览"}
            </button>
          )}
        </div>
      </div>
      {expanded && markdown && (
        <div style={{ padding: "14px 16px", maxHeight: 400, overflowY: "auto", fontSize: 13, lineHeight: 1.7 }}>
          <Markdown remarkPlugins={[remarkGfm]}>{markdown.slice(0, 3000)}</Markdown>
        </div>
      )}
    </div>
  );
}


// ── Quick-search source list (numbered [1][2]… citations) ────────────
function QuickSourcesList({ sources }: { sources: QuickSource[] }) {
  if (!sources.length) return null;
  return (
    <div style={{
      marginBottom: 10, padding: "8px 10px",
      background: "#F0FDF4", border: "1px solid #BBF7D0", borderRadius: 8,
      fontSize: 12,
    }}>
      <div style={{ color: "#059669", fontWeight: 600, marginBottom: 4 }}>
        ⚡ Quick · {sources.length} 条来源
      </div>
      <ol style={{ margin: 0, paddingLeft: 20, color: "#334155", lineHeight: 1.6 }}>
        {sources.map((s, i) => (
          <li key={i}>
            <a href={s.url} target="_blank" rel="noopener noreferrer"
               style={{ color: "#1E3A8A", textDecoration: "none" }}>
              {s.title || s.url}
            </a>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ── Error box with retry button ──────────────────────────────────────
function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div style={{
      marginTop: 8, padding: "10px 12px",
      background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 8,
      fontSize: 13, color: "#991B1B",
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
    }}>
      <span>⚠️ {message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: "4px 12px", fontSize: 12, fontWeight: 500,
            background: "#fff", color: "#991B1B",
            border: "1px solid #FECACA", borderRadius: 6, cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          🔄 重试
        </button>
      )}
    </div>
  );
}

// ── ChatMessage ──────────────────────────────────────────────────────
export function ChatMessage({
  role, content, streaming, tools, attachments, reportTasks,
  plan, planStatus, planSelectedIds, quickSources, error,
  onRetry, onPlanConfirm, onPlanSkip, onPlanCancel,
}: Props) {
  if (role === "user") {
    return (
      <div className="chat-message user">
        <div className="chat-bubble user">
          {content}
          {attachments && attachments.length > 0 && (
            <div style={{ marginTop: "0.5rem", display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
              {attachments.map((f) => (
                <span
                  key={f}
                  style={{
                    fontSize: "0.7rem",
                    padding: "0.15rem 0.45rem",
                    background: "rgba(255,255,255,0.2)",
                    borderRadius: "4px",
                  }}
                >
                  📎 {f}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  const hasTools = tools && tools.some((t) => t.type === "tool_call");

  return (
    <div className="chat-message assistant">
      <div className="chat-bubble assistant">
        {plan && (
          <PlanCard
            plan={plan}
            status={planStatus || "pending"}
            selectedIds={planSelectedIds}
            onConfirm={onPlanConfirm || (() => {})}
            onSkip={onPlanSkip || (() => {})}
            onCancel={onPlanCancel || (() => {})}
          />
        )}
        {hasTools && <ToolStepsPanel tools={tools!} isStreaming={!!streaming} />}
        {quickSources && quickSources.length > 0 && <QuickSourcesList sources={quickSources} />}
        {content && <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>}
        {reportTasks && reportTasks.map((rt) => (
          <ReportTaskCard key={rt.task_id} {...rt} />
        ))}
        {error && <ErrorBox message={error} onRetry={onRetry} />}
        {streaming && !hasTools && !plan && <span className="chat-cursor">|</span>}
      </div>
    </div>
  );
}
