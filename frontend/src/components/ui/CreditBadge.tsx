"use client";

import { useCredits } from "@/lib/credits";

interface Props {
  compact?: boolean;
}

/**
 * Inline badge displaying the user's credit balance.
 * Shown in the sidebar footer. Refreshes automatically whenever the
 * shared credits store updates (which happens after each chat turn).
 */
export function CreditBadge({ compact = false }: Props) {
  const { balance } = useCredits();

  if (!balance) return null;

  const isLow = balance.balance < 500;

  return (
    <div
      title={`已使用 ${balance.total_spent.toFixed(0)} · 已获赠 ${balance.total_granted.toFixed(0)}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: compact ? "3px 8px" : "5px 10px",
        background: isLow ? "#FEF2F2" : "#F0FDF4",
        border: `1px solid ${isLow ? "#FECACA" : "#BBF7D0"}`,
        borderRadius: 8,
        fontSize: 11,
        fontWeight: 600,
        color: isLow ? "#DC2626" : "#16A34A",
        cursor: "default",
        whiteSpace: "nowrap",
      }}
    >
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.4" />
        <text x="8" y="11.5" textAnchor="middle" fontSize="9" fontWeight="bold" fill="currentColor">
          C
        </text>
      </svg>
      {compact ? `${balance.balance.toFixed(0)}` : `${balance.balance.toFixed(0)} credits`}
    </div>
  );
}
