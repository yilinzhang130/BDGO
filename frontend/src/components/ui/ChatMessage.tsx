"use client";

import { useState } from "react";
import Markdown from "react-markdown";

interface ToolEvent {
  type: "tool_call" | "tool_result";
  name: string;
}

interface Props {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  tools?: ToolEvent[];
  attachments?: string[];
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

// ── ChatMessage ──────────────────────────────────────────────────────
export function ChatMessage({ role, content, streaming, tools, attachments }: Props) {
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
        {hasTools && <ToolStepsPanel tools={tools!} isStreaming={!!streaming} />}
        {content && <Markdown>{content}</Markdown>}
        {streaming && !content && !hasTools && <span className="chat-cursor">|</span>}
        {streaming && content && <span className="chat-cursor">|</span>}
      </div>
    </div>
  );
}
