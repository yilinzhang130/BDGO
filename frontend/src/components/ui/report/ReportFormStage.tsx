"use client";

import type { FieldRule, FieldSpec, FieldValue, FormSchema } from "./types";

const INPUT_STYLE: React.CSSProperties = {
  padding: "0.5rem 0.7rem",
  border: "1px solid var(--border-strong)",
  borderRadius: "var(--radius-sm)",
  fontSize: "0.85rem",
  background: "var(--bg-input)",
  color: "var(--text)",
  fontFamily: "inherit",
  width: "100%",
};

export function ReportFormStage({
  schema,
  fieldRules,
  params,
  onChange,
  onSubmit,
  onCancel,
  estimatedSeconds,
  errorMsg,
}: {
  schema: FormSchema;
  fieldRules: Record<string, FieldRule>;
  params: Record<string, FieldValue>;
  onChange: (p: Record<string, FieldValue>) => void;
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
        {Object.entries(properties).map(([name, spec]) => {
          if (!isFieldRelevant(name)) return null;
          return (
            <FieldInput
              key={name}
              name={name}
              spec={spec}
              value={params[name]}
              onChange={(v) => onChange({ ...params, [name]: v })}
              required={required.includes(name)}
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
          {"\u23F1 ~"}
          {estimatedSeconds}s
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
  spec: FieldSpec;
  value: FieldValue | undefined;
  onChange: (v: FieldValue) => void;
  required: boolean;
}) {
  const label = name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, " ");
  const description = spec.description || "";
  const defaultValue = spec.type === "boolean" ? (spec.default ?? false) : (spec.default ?? "");
  const currentValue = value ?? defaultValue;

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
      <label style={{ fontSize: "0.76rem", fontWeight: 600, color: "var(--text-secondary)" }}>
        {label}
        {required && <span style={{ color: "var(--red)", marginLeft: 4 }}>*</span>}
      </label>
      {description && (
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
          {description}
        </div>
      )}
      {/* Boolean was returned above, so here currentValue is string|number. */}
      {spec.enum ? (
        <select
          value={currentValue as string | number}
          onChange={(e) => onChange(e.target.value)}
          style={INPUT_STYLE}
        >
          <option value="">-- select --</option>
          {spec.enum.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : spec.type === "integer" ? (
        <input
          type="number"
          value={currentValue as string | number}
          onChange={(e) =>
            onChange(parseInt(e.target.value, 10) || (spec.default as number | undefined) || 0)
          }
          style={INPUT_STYLE}
        />
      ) : (
        <input
          type="text"
          value={currentValue as string | number}
          onChange={(e) => onChange(e.target.value)}
          style={INPUT_STYLE}
        />
      )}
    </div>
  );
}
