"use client";

import { useRouter } from "next/navigation";
import type { ContextEntity } from "@/lib/sessions";

const TYPE_LABELS: Record<string, string> = {
  company: "Company",
  asset: "Asset",
  clinical: "Trial",
  deal: "Deal",
  patent: "Patent",
  buyer: "Buyer",
};

const TYPE_COLORS: Record<string, string> = {
  company: "var(--accent)",
  asset: "#7C3AED",
  clinical: "#0EA5E9",
  deal: "#059669",
  patent: "#D97706",
  buyer: "#DB2777",
};

interface Props {
  entity: ContextEntity;
  onRemove: () => void;
}

export function ContextCard({ entity, onRemove }: Props) {
  const router = useRouter();
  const accent = TYPE_COLORS[entity.entityType] || "var(--accent)";

  const handleClick = () => {
    if (entity.href) router.push(entity.href);
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onRemove();
  };

  return (
    <div className="context-card" onClick={handleClick}>
      <div className="context-card-accent" style={{ background: accent }} />
      <div className="context-card-header">
        <div className="context-card-title">{entity.title}</div>
        <span
          className="context-card-type"
          style={{
            background: `${accent}14`,
            color: accent,
          }}
        >
          {TYPE_LABELS[entity.entityType] || entity.entityType}
        </span>
      </div>
      {entity.subtitle && <div className="context-card-subtitle">{entity.subtitle}</div>}
      {entity.fields.length > 0 && (
        <div className="context-card-fields">
          {entity.fields.slice(0, 4).map((f, i) => (
            <div key={i} className="context-card-field">
              <span className="context-card-field-label">{f.label}</span>
              <span className="context-card-field-value">{f.value || "-"}</span>
            </div>
          ))}
        </div>
      )}
      <button
        className="context-card-menu"
        onClick={handleRemove}
        title="Remove from context"
        style={{ position: "absolute", top: "0.55rem", right: "0.55rem" }}
      >
        {"\u2715"}
      </button>
    </div>
  );
}
