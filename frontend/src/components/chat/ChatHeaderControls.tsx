"use client";

import type { PlanMode, SearchMode } from "@/lib/api";

/**
 * Header toolbar buttons for the chat page: search-mode segmented control,
 * plan-mode cycle button. Purely presentational — parent owns state &
 * localStorage persistence.
 */
export function ChatHeaderControls({
  searchMode,
  onSearchModeChange,
  planMode,
  onCyclePlanMode,
}: {
  searchMode: SearchMode;
  onSearchModeChange: (m: SearchMode) => void;
  planMode: PlanMode;
  onCyclePlanMode: () => void;
}) {
  return (
    <>
      <div
        role="group"
        aria-label="搜索模式"
        style={{
          display: "inline-flex", borderRadius: 8,
          border: "1px solid #E2E8F0", overflow: "hidden",
        }}
      >
        {(["agent", "quick"] as const).map((m) => {
          const on = searchMode === m;
          return (
            <button
              key={m}
              onClick={() => onSearchModeChange(m)}
              title={
                m === "agent"
                  ? "Agent · 调用工具、CRM、报告生成（复杂任务）"
                  : "Quick · Tavily搜索+总结，低延迟（查事实/新闻）"
              }
              style={{
                padding: "4px 10px", fontSize: 12, fontWeight: 500,
                background: on ? (m === "quick" ? "#ECFDF5" : "#F8FAFF") : "#fff",
                color: on ? (m === "quick" ? "#059669" : "#1E3A8A") : "#64748B",
                border: "none",
                borderRight: m === "agent" ? "1px solid #E2E8F0" : "none",
                cursor: "pointer",
              }}
            >
              {m === "agent" ? "🤖 Agent" : "⚡ Quick"}
            </button>
          );
        })}
      </div>

      <button
        onClick={onCyclePlanMode}
        title={
          planMode === "auto"
            ? "规划模式：智能判断（长任务自动先规划）"
            : planMode === "on"
              ? "规划模式：始终先出方案"
              : "规划模式：关闭（直接执行）"
        }
        style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          padding: "4px 10px", fontSize: 12, fontWeight: 500,
          background: planMode === "on" ? "#DBEAFE" : planMode === "off" ? "#F1F5F9" : "#F8FAFF",
          border: `1px solid ${planMode === "on" ? "#1E3A8A" : "#E2E8F0"}`,
          color: planMode === "on" ? "#1E3A8A" : planMode === "off" ? "#64748B" : "#475569",
          borderRadius: 8, cursor: "pointer",
        }}
      >
        📋
        <span>
          {planMode === "auto" ? "规划 · 自动" : planMode === "on" ? "规划 · 开" : "规划 · 关"}
        </span>
      </button>
    </>
  );
}
