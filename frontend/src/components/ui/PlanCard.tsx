"use client";

import { useState, useMemo } from "react";
import type { PlanProposal, PlanStatus } from "@/lib/sessions";

interface Props {
  plan: PlanProposal;
  status: PlanStatus; // pending | confirmed | cancelled
  selectedIds?: string[]; // remembered selection if already confirmed
  onConfirm: (selectedStepIds: string[]) => void;
  onSkip: () => void; // run without plan constraints
  onCancel: () => void;
}

const TOOL_ICONS: Record<string, string> = {
  search_companies: "🏢",
  search_assets: "🧪",
  search_clinical: "📋",
  search_deals: "🤝",
  query_treatment_guidelines: "📖",
  tavily_search: "🌐",
  crm_aggregate: "📊",
  skill_mnc_buyer_profile: "📑",
  skill_biotech_deal_asset_evaluator: "💰",
  skill_company_analysis: "🔍",
};

function toolIcon(name: string): string {
  return TOOL_ICONS[name] || "🔧";
}

export function PlanCard({ plan, status, selectedIds, onConfirm, onSkip, onCancel }: Props) {
  // Initialize checked set from either the remembered selection (if already
  // confirmed) or the default_selected flags on each step.
  const initial = useMemo(() => {
    if (selectedIds && selectedIds.length) return new Set(selectedIds);
    return new Set(plan.steps.filter((s) => s.default_selected).map((s) => s.id));
  }, [plan.steps, selectedIds]);

  const [checked, setChecked] = useState<Set<string>>(initial);

  const readonly = status !== "pending";

  const toggle = (id: string, required: boolean) => {
    if (readonly || required) return;
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectedCount = checked.size;
  const totalSeconds = plan.steps
    .filter((s) => checked.has(s.id))
    .reduce((sum, s) => sum + (s.estimated_seconds || 0), 0);

  return (
    <div
      style={{
        border: "1px solid #CBD5E1",
        borderRadius: 10,
        background: "#F8FAFF",
        padding: "0.9rem 1rem 0.75rem",
        margin: "0.5rem 0",
        fontSize: "0.85rem",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: "1.1rem" }}>📋</span>
        <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "#0F172A" }}>{plan.title}</div>
        {status === "confirmed" && (
          <span
            style={{
              marginLeft: "auto",
              fontSize: 10,
              fontWeight: 700,
              color: "#16A34A",
              background: "#F0FDF4",
              padding: "2px 6px",
              borderRadius: 4,
            }}
          >
            已执行
          </span>
        )}
        {status === "cancelled" && (
          <span
            style={{
              marginLeft: "auto",
              fontSize: 10,
              fontWeight: 700,
              color: "#64748B",
              background: "#F1F5F9",
              padding: "2px 6px",
              borderRadius: 4,
            }}
          >
            已取消
          </span>
        )}
      </div>
      {plan.summary && (
        <div style={{ color: "#64748B", fontSize: "0.8rem", marginBottom: 10 }}>{plan.summary}</div>
      )}

      {/* Steps */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {plan.steps.map((step, idx) => {
          const isChecked = checked.has(step.id);
          return (
            <label
              key={step.id}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
                padding: "6px 8px",
                background: isChecked ? "#fff" : "#F1F5F9",
                border: `1px solid ${isChecked ? "#CBD5E1" : "#E2E8F0"}`,
                borderRadius: 6,
                cursor: readonly || step.required ? "default" : "pointer",
                opacity: readonly && !isChecked ? 0.5 : 1,
              }}
            >
              <input
                type="checkbox"
                checked={isChecked}
                disabled={readonly || step.required}
                onChange={() => toggle(step.id, step.required)}
                style={{ marginTop: 2, cursor: "inherit" }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 600, color: "#0F172A" }}>
                    {idx + 1}. {step.title}
                  </span>
                  {step.required && (
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        color: "#DC2626",
                        background: "#FEF2F2",
                        padding: "1px 5px",
                        borderRadius: 3,
                      }}
                    >
                      必选
                    </span>
                  )}
                  {step.tools_expected.length > 0 && (
                    <span style={{ fontSize: 11 }}>
                      {step.tools_expected.slice(0, 4).map((t) => (
                        <span key={t} title={t} style={{ marginLeft: 2 }}>
                          {toolIcon(t)}
                        </span>
                      ))}
                    </span>
                  )}
                  <span style={{ marginLeft: "auto", fontSize: 10, color: "#94A3B8" }}>
                    ~{step.estimated_seconds}s
                  </span>
                </div>
                {step.description && (
                  <div
                    style={{ fontSize: "0.78rem", color: "#64748B", marginTop: 2, lineHeight: 1.4 }}
                  >
                    {step.description}
                  </div>
                )}
              </div>
            </label>
          );
        })}
      </div>

      {/* Action buttons (hide when not pending) */}
      {!readonly && (
        <div
          style={{
            display: "flex",
            gap: 8,
            marginTop: 12,
            alignItems: "center",
            paddingTop: 10,
            borderTop: "1px solid #E2E8F0",
          }}
        >
          <div style={{ fontSize: 11, color: "#64748B" }}>
            已选 {selectedCount} / {plan.steps.length} 步 · 预计 ~{totalSeconds}s
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            <button
              onClick={onCancel}
              style={{
                padding: "5px 10px",
                fontSize: "0.78rem",
                background: "#F1F5F9",
                color: "#64748B",
                border: "1px solid #E2E8F0",
                borderRadius: 5,
                cursor: "pointer",
              }}
            >
              取消
            </button>
            <button
              onClick={onSkip}
              style={{
                padding: "5px 10px",
                fontSize: "0.78rem",
                background: "#fff",
                color: "#1E3A8A",
                border: "1px solid #1E3A8A",
                borderRadius: 5,
                cursor: "pointer",
              }}
              title="跳过规划，直接让 AI 自由发挥"
            >
              跳过规划
            </button>
            <button
              onClick={() => onConfirm(Array.from(checked))}
              disabled={selectedCount === 0}
              style={{
                padding: "5px 14px",
                fontSize: "0.78rem",
                fontWeight: 600,
                background: selectedCount === 0 ? "#CBD5E1" : "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: 5,
                cursor: selectedCount === 0 ? "not-allowed" : "pointer",
              }}
            >
              执行选中 ({selectedCount})
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
