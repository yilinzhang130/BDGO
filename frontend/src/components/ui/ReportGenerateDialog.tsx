"use client";

import { useState } from "react";
import { useReportPolling } from "@/hooks/useReportPolling";
import { ReportFormStage } from "./report/ReportFormStage";
import { ReportRunningStage } from "./report/ReportRunningStage";
import { ReportDoneStage } from "./report/ReportDoneStage";
import { ReportErrorStage } from "./report/ReportErrorStage";
import type { ReportService, ReportStartInfo } from "./report/types";

export type { ReportService, ReportStartInfo } from "./report/types";

interface Props {
  service: ReportService;
  onClose: () => void;
  // When set, fires once the task has been created (async services) or
  // completed inline (sync). Caller is responsible for closing the dialog
  // and rendering progress elsewhere (e.g. as a chat message card).
  onStarted?: (info: ReportStartInfo) => void;
  initialParams?: Record<string, any>;
}

export function ReportGenerateDialog({ service, onClose, onStarted, initialParams }: Props) {
  const [params, setParams] = useState<Record<string, any>>(initialParams || {});
  const { stage, progressLog, result, errorMsg, submit, retry } = useReportPolling({
    service,
    params,
    onStarted,
  });

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--bg-card)",
          borderRadius: "var(--radius-lg)",
          padding: "1.5rem",
          maxWidth: 540,
          width: "90%",
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "var(--shadow-lg)",
          border: "1px solid var(--border)",
        }}
      >
        <h3 style={{ margin: "0 0 0.3rem", fontSize: "1.05rem", fontWeight: 700 }}>
          {service.display_name}
        </h3>
        <p
          style={{
            margin: "0 0 1.25rem",
            fontSize: "0.82rem",
            color: "var(--text-secondary)",
            lineHeight: 1.5,
          }}
        >
          {service.description}
        </p>

        {stage === "form" && (
          <ReportFormStage
            schema={service.input_schema}
            fieldRules={service.field_rules ?? {}}
            params={params}
            onChange={setParams}
            onSubmit={submit}
            onCancel={onClose}
            estimatedSeconds={service.estimated_seconds}
            errorMsg={errorMsg}
          />
        )}

        {stage === "running" && (
          <ReportRunningStage
            progressLog={progressLog}
            estimatedSeconds={service.estimated_seconds}
            onClose={onClose}
          />
        )}

        {stage === "done" && result && <ReportDoneStage result={result} onClose={onClose} />}

        {stage === "error" && (
          <ReportErrorStage
            message={errorMsg || "Unknown error"}
            onRetry={retry}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}
