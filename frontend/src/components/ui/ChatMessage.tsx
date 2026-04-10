"use client";

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

const TOOL_LABELS: Record<string, string> = {
  search_companies: "Searching companies",
  get_company: "Fetching company details",
  search_assets: "Searching assets",
  get_asset: "Fetching asset details",
  search_clinical: "Searching clinical trials",
  search_deals: "Searching deals",
  search_patents: "Searching patents",
  get_buyer_profile: "Fetching buyer profile",
  count_by: "Counting records",
  search_global: "Global search",
};

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
                  {"\uD83D\uDCCE "} {f}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Assistant: show deduped tool indicators + markdown content
  const uniqueTools: ToolEvent[] = [];
  if (tools) {
    const seen = new Set<string>();
    for (const t of tools) {
      if (t.type === "tool_call" && !seen.has(t.name)) {
        uniqueTools.push(t);
        seen.add(t.name);
      }
    }
  }

  return (
    <div className="chat-message assistant">
      <div className="chat-bubble assistant">
        {uniqueTools.length > 0 && (
          <div className="tool-indicators">
            {uniqueTools.map((t, i) => {
              const completed = tools?.some(
                (x) => x.type === "tool_result" && x.name === t.name,
              ) ?? false;
              return (
                <div
                  key={`${t.name}-${i}`}
                  className={`tool-indicator ${completed ? "done" : "running"}`}
                >
                  <span className="tool-indicator-dot">
                    {completed ? "\u2713" : "\u25CF"}
                  </span>
                  <span>{TOOL_LABELS[t.name] || t.name}</span>
                </div>
              );
            })}
          </div>
        )}
        {content && <Markdown>{content}</Markdown>}
        {streaming && <span className="chat-cursor">|</span>}
      </div>
    </div>
  );
}
