"use client";

import { useState, useEffect, useCallback } from "react";
import { runTask, fetchTaskStatus } from "@/lib/api";

interface Props {
  label: string;
  agent?: string;
  message: string;
  style?: React.CSSProperties;
  onComplete?: () => void;
}

export function AgentButton({
  label,
  agent = "company_analyst",
  message,
  style,
  onComplete,
}: Props) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [error, setError] = useState<string | null>(null);

  const pollStatus = useCallback(
    async (id: string) => {
      try {
        const result = await fetchTaskStatus(id);
        setStatus(result.status);
        if (result.status === "completed") {
          if (onComplete) onComplete();
          return;
        }
        if (result.status === "failed" || result.status === "timeout") {
          setError(result.error || "Task failed");
          return;
        }
        // Still running — poll again
        setTimeout(() => pollStatus(id), 3000);
      } catch {
        setError("Failed to check status");
      }
    },
    [onComplete],
  );

  const handleClick = async () => {
    if (status === "running" || status === "queued") return;
    setStatus("queued");
    setError(null);
    try {
      const { task_id } = await runTask(agent, message);
      setTaskId(task_id);
      setTimeout(() => pollStatus(task_id), 2000);
    } catch (e: any) {
      setError(e.message);
      setStatus("idle");
    }
  };

  const isRunning = status === "running" || status === "queued";

  const statusLabel =
    {
      idle: label,
      queued: "Queued...",
      running: "Analyzing...",
      completed: "Done!",
      failed: "Failed",
      timeout: "Timeout",
    }[status] || label;

  const bgColor =
    status === "completed"
      ? "#10b981"
      : status === "failed" || status === "timeout"
        ? "var(--red)"
        : isRunning
          ? "#94a3b8"
          : undefined;

  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-start" }}>
      <button
        onClick={handleClick}
        disabled={isRunning}
        style={{
          padding: "0.4rem 0.9rem",
          background: bgColor || style?.background || "var(--accent)",
          color: "white",
          border: "none",
          borderRadius: 6,
          cursor: isRunning ? "wait" : "pointer",
          fontSize: "0.8rem",
          fontWeight: 600,
          opacity: isRunning ? 0.8 : 1,
          ...style,
          ...(bgColor ? { background: bgColor } : {}),
        }}
      >
        {isRunning && (
          <span
            style={{
              display: "inline-block",
              marginRight: "0.4rem",
              animation: "spin 1s linear infinite",
            }}
          >
            &#9696;
          </span>
        )}
        {statusLabel}
      </button>
      {error && (
        <span style={{ fontSize: "0.7rem", color: "var(--red)", marginTop: "0.2rem" }}>
          {error}
        </span>
      )}
    </div>
  );
}
