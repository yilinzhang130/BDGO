"use client";

import { useState, useEffect } from "react";
import { generateReport, fetchReportStatus, reportDownloadUrl } from "@/lib/api";
import { addCompletedReport, type CompletedReport } from "@/lib/reports";

interface FieldRule {
  visible_when?: Record<string, string | number | boolean | (string | number | boolean)[]>;
}

interface ReportService {
  slug: string;
  display_name: string;
  description: string;
  mode: "sync" | "async";
  estimated_seconds: number;
  input_schema: {
    type: string;
    properties: Record<string, any>;
    required?: string[];
  };
  output_formats: string[];
  field_rules?: Record<string, FieldRule>;
}

interface Props {
  service: ReportService;
  onClose: () => void;
  // When set, fires once the task has been created (async services) or
  // completed inline (sync). Caller is responsible for closing the dialog
  // and rendering progress elsewhere (e.g. as a chat message card).
  onStarted?: (info: {
    task_id: string;
    slug: string;
    estimated_seconds: number;
    params: Record<string, any>;
  }) => void;
  initialParams?: Record<string, any>;
}

const STAGE = {
  FORM: "form",
  RUNNING: "running",
  DONE: "done",
  ERROR: "error",
} as const;
type Stage = typeof STAGE[keyof typeof STAGE];

export function ReportGenerateDialog({ service, onClose, onStarted, initialParams }: Props) {
  const [stage, setStage] = useState<Stage>("form");
  const [params, setParams] = useState<Record<string, any>>(initialParams || {});
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  // Poll status while running
  useEffect(() => {
    if (stage !== "running" || !taskId) return;
    let alive = true;

    const poll = async () => {
      try {
        const status = await fetchReportStatus(taskId);
        if (!alive) return;
        // Only update progressLog if the content actually changed — avoids
        // re-rendering children on every 2s poll when nothing new arrived.
        const nextLog = status.progress_log || [];
        setProgressLog((prev) =>
          prev.length === nextLog.length &&
          prev.every((line, i) => line === nextLog[i])
            ? prev
            : nextLog,
        );

        if (status.status === "completed") {
          setResult(status.result);
          setStage("done");

          // Save to localStorage
          const title = deriveTitle(service, params, status.result?.meta || {});
          const completed: CompletedReport = {
            taskId,
            slug: service.slug,
            displayName: service.display_name,
            title,
            markdownPreview: (status.result?.markdown || "").slice(0, 500),
            files: status.result?.files || [],
            meta: status.result?.meta || {},
            createdAt: Date.now(),
          };
          addCompletedReport(completed);
          return;
        }
        if (status.status === "failed") {
          setErrorMsg(status.error || "Report generation failed");
          setStage("error");
          return;
        }
        // Still running — poll again
        setTimeout(poll, 2000);
      } catch (e: any) {
        setErrorMsg(e.message || "Status check failed");
        setStage("error");
      }
    };

    setTimeout(poll, 1500);
    return () => { alive = false; };
  }, [stage, taskId, service, params]);

  const handleSubmit = async () => {
    // Basic validation
    const required = service.input_schema.required || [];
    for (const field of required) {
      if (!params[field]) {
        setErrorMsg(`Missing required field: ${field}`);
        return;
      }
    }
    setErrorMsg(null);
    try {
      const resp = await generateReport(service.slug, params);
      setTaskId(resp.task_id);
      if (onStarted) {
        onStarted({
          task_id: resp.task_id,
          slug: service.slug,
          estimated_seconds: service.estimated_seconds,
          params,
        });
        return;
      }
      if (resp.status === "completed") {
        // sync mode — already done
        setResult(resp.result);
        setStage("done");
      } else {
        setStage("running");
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to start");
      setStage("error");
    }
  };

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

        {stage === STAGE.FORM && (
          <FormStage
            schema={service.input_schema}
            fieldRules={service.field_rules ?? {}}
            params={params}
            onChange={setParams}
            onSubmit={handleSubmit}
            onCancel={onClose}
            estimatedSeconds={service.estimated_seconds}
            errorMsg={errorMsg}
          />
        )}

        {stage === STAGE.RUNNING && (
          <RunningStage
            progressLog={progressLog}
            estimatedSeconds={service.estimated_seconds}
            onClose={onClose}
          />
        )}

        {stage === STAGE.DONE && result && (
          <DoneStage
            result={result}
            taskId={taskId!}
            onClose={onClose}
          />
        )}

        {stage === STAGE.ERROR && (
          <ErrorStage
            message={errorMsg || "Unknown error"}
            onRetry={() => {
              setErrorMsg(null);
              setStage("form");
            }}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Form stage — renders fields from JSON schema
// ═══════════════════════════════════════════════════════════

function FormStage({
  schema,
  fieldRules,
  params,
  onChange,
  onSubmit,
  onCancel,
  estimatedSeconds,
  errorMsg,
}: {
  schema: any;
  fieldRules: Record<string, FieldRule>;
  params: Record<string, any>;
  onChange: (p: Record<string, any>) => void;
  onSubmit: () => void;
  onCancel: () => void;
  estimatedSeconds: number;
  errorMsg: string | null;
}) {
  const properties = schema.properties || {};
  const required = schema.required || [];

  const isFieldRelevant = (fieldName: string): boolean => {
    const rule = fieldRules[fieldName];
    if (!rule?.visible_when) return true;
    for (const [discriminator, expected] of Object.entries(rule.visible_when)) {
      const current = params[discriminator];
      // Field is hidden only when the discriminator is set AND doesn't match
      if (current === undefined || current === "") return true;
      const allowed = Array.isArray(expected) ? expected : [expected];
      if (!allowed.includes(current)) return false;
    }
    return true;
  };

  return (
    <>
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "0.85rem",
          paddingRight: "0.2rem",
        }}
      >
        {Object.entries(properties).map(([name, spec]: [string, any]) => {
          if (!isFieldRelevant(name)) return null;
          const isRequired = required.includes(name);
          return (
            <FieldInput
              key={name}
              name={name}
              spec={spec}
              value={params[name]}
              onChange={(v) => onChange({ ...params, [name]: v })}
              required={isRequired}
            />
          );
        })}

        {errorMsg && (
          <div
            style={{
              color: "var(--red)",
              fontSize: "0.8rem",
              padding: "0.5rem 0.75rem",
              background: "rgba(220,38,38,0.08)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid rgba(220,38,38,0.2)",
            }}
          >
            {errorMsg}
          </div>
        )}
      </div>

      <div
        style={{
          marginTop: "1rem",
          paddingTop: "1rem",
          borderTop: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "0.75rem",
        }}
      >
        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
          ⏱ ~{estimatedSeconds}s
        </span>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={onCancel}
            style={{
              padding: "0.45rem 1rem",
              border: "1px solid var(--border-strong)",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-card)",
              color: "var(--text)",
              cursor: "pointer",
              fontSize: "0.82rem",
            }}
          >
            Cancel
          </button>
          <button
            onClick={onSubmit}
            style={{
              padding: "0.45rem 1.2rem",
              border: "none",
              borderRadius: "var(--radius-sm)",
              background: "var(--accent)",
              color: "white",
              cursor: "pointer",
              fontSize: "0.82rem",
              fontWeight: 600,
            }}
          >
            Generate
          </button>
        </div>
      </div>
    </>
  );
}

function FieldInput({
  name,
  spec,
  value,
  onChange,
  required,
}: {
  name: string;
  spec: any;
  value: any;
  onChange: (v: any) => void;
  required: boolean;
}) {
  const label = name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, " ");
  const description = spec.description || "";
  const defaultValue = spec.type === "boolean" ? spec.default ?? false : spec.default ?? "";
  const currentValue = value ?? defaultValue;

  const inputStyle: React.CSSProperties = {
    padding: "0.5rem 0.7rem",
    border: "1px solid var(--border-strong)",
    borderRadius: "var(--radius-sm)",
    fontSize: "0.85rem",
    background: "var(--bg-input)",
    color: "var(--text)",
    fontFamily: "inherit",
    width: "100%",
  };

  // Boolean: checkbox laid out inline with label
  if (spec.type === "boolean") {
    const checked = currentValue === true || currentValue === "true";
    return (
      <label
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "0.55rem",
          fontSize: "0.82rem",
          color: "var(--text)",
          cursor: "pointer",
          padding: "0.25rem 0",
        }}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          style={{ marginTop: "0.2rem", cursor: "pointer", flexShrink: 0 }}
        />
        <span style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
          <span style={{ fontWeight: 600, color: "var(--text-secondary)" }}>
            {label}
            {required && <span style={{ color: "var(--red)", marginLeft: 4 }}>*</span>}
          </span>
          {description && (
            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
              {description}
            </span>
          )}
        </span>
      </label>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
      <label
        style={{
          fontSize: "0.76rem",
          fontWeight: 600,
          color: "var(--text-secondary)",
        }}
      >
        {label}
        {required && <span style={{ color: "var(--red)", marginLeft: 4 }}>*</span>}
      </label>
      {description && (
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
          {description}
        </div>
      )}
      {spec.enum ? (
        <select
          value={currentValue}
          onChange={(e) => onChange(e.target.value)}
          style={inputStyle}
        >
          <option value="">-- select --</option>
          {spec.enum.map((opt: string) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : spec.type === "integer" ? (
        <input
          type="number"
          value={currentValue}
          onChange={(e) => onChange(parseInt(e.target.value, 10) || spec.default || 0)}
          style={inputStyle}
        />
      ) : (
        <input
          type="text"
          value={currentValue}
          onChange={(e) => onChange(e.target.value)}
          style={inputStyle}
        />
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Running stage
// ═══════════════════════════════════════════════════════════

function RunningStage({
  progressLog,
  estimatedSeconds,
  onClose,
}: {
  progressLog: string[];
  estimatedSeconds: number;
  onClose: () => void;
}) {
  return (
    <div style={{ padding: "1rem 0", textAlign: "center" }}>
      <div
        style={{
          fontSize: "1.6rem",
          marginBottom: "0.75rem",
          display: "inline-block",
          animation: "spin 2s linear infinite",
        }}
      >
        ⟳
      </div>
      <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Generating...</div>
      <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
        Estimated ~{estimatedSeconds}s. You can close this dialog — it runs in the background.
      </div>

      {progressLog.length > 0 && (
        <div
          style={{
            background: "var(--bg-subtle)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "0.6rem 0.8rem",
            fontSize: "0.72rem",
            color: "var(--text-secondary)",
            textAlign: "left",
            maxHeight: 180,
            overflowY: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          {progressLog.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}

      <button
        onClick={onClose}
        style={{
          marginTop: "1rem",
          padding: "0.45rem 1rem",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-sm)",
          background: "var(--bg-card)",
          cursor: "pointer",
          fontSize: "0.82rem",
        }}
      >
        Close (continues in background)
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Done stage
// ═══════════════════════════════════════════════════════════

function DoneStage({
  result,
  taskId,
  onClose,
}: {
  result: any;
  taskId: string;
  onClose: () => void;
}) {
  const files = result.files || [];
  const markdownPreview = (result.markdown || "").slice(0, 400);

  return (
    <div style={{ padding: "0.5rem 0", display: "flex", flexDirection: "column" }}>
      <div style={{ textAlign: "center", marginBottom: "1rem" }}>
        <div style={{ fontSize: "2rem", color: "var(--green)", marginBottom: "0.3rem" }}>
          ✓
        </div>
        <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>Report Complete</div>
      </div>

      {markdownPreview && (
        <div
          style={{
            background: "var(--bg-subtle)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "0.75rem",
            fontSize: "0.78rem",
            color: "var(--text-secondary)",
            whiteSpace: "pre-wrap",
            maxHeight: 200,
            overflowY: "auto",
            lineHeight: 1.5,
            marginBottom: "1rem",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          {markdownPreview}
          {result.markdown && result.markdown.length > 400 ? "\n..." : ""}
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          justifyContent: "flex-end",
          paddingTop: "0.75rem",
          borderTop: "1px solid var(--border)",
        }}
      >
        {files.map((f: any) => (
          <a
            key={f.filename}
            href={f.download_url}
            download={f.filename}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              padding: "0.45rem 1rem",
              background: "var(--accent)",
              color: "white",
              textDecoration: "none",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.82rem",
              fontWeight: 600,
            }}
          >
            ⬇ Download .{f.format}
          </a>
        ))}
        <button
          onClick={onClose}
          style={{
            padding: "0.45rem 1rem",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-card)",
            cursor: "pointer",
            fontSize: "0.82rem",
          }}
        >
          Close
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Error stage
// ═══════════════════════════════════════════════════════════

function ErrorStage({
  message,
  onRetry,
  onClose,
}: {
  message: string;
  onRetry: () => void;
  onClose: () => void;
}) {
  return (
    <div style={{ padding: "1.5rem 0", textAlign: "center" }}>
      <div style={{ fontSize: "2rem", color: "var(--red)", marginBottom: "0.5rem" }}>
        ✕
      </div>
      <div style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Generation Failed</div>
      <div
        style={{
          fontSize: "0.78rem",
          color: "var(--text-secondary)",
          marginBottom: "1.25rem",
          padding: "0.5rem 0.75rem",
          background: "rgba(220,38,38,0.08)",
          borderRadius: "var(--radius-sm)",
          maxHeight: 120,
          overflowY: "auto",
        }}
      >
        {message}
      </div>
      <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center" }}>
        <button
          onClick={onRetry}
          style={{
            padding: "0.45rem 1rem",
            border: "none",
            borderRadius: "var(--radius-sm)",
            background: "var(--accent)",
            color: "white",
            cursor: "pointer",
            fontSize: "0.82rem",
            fontWeight: 600,
          }}
        >
          Try Again
        </button>
        <button
          onClick={onClose}
          style={{
            padding: "0.45rem 1rem",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-card)",
            cursor: "pointer",
            fontSize: "0.82rem",
          }}
        >
          Close
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Utils
// ═══════════════════════════════════════════════════════════

function deriveTitle(service: any, params: any, meta: any): string {
  if (meta.title) return meta.title;
  if (meta.topic) return meta.topic;
  if (params.topic) return params.topic;
  if (params.pmid) return `PMID ${params.pmid}`;
  if (params.doi) return params.doi;
  if (params.filename) return params.filename;
  return service.display_name;
}
