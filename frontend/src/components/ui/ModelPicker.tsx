"use client";

import { useEffect, useState } from "react";
import { useModels, getSelectedModel, setSelectedModel } from "@/lib/credits";

interface Props {
  /** Called whenever the user picks a different model. */
  onChange?: (modelId: string) => void;
  compact?: boolean;
}

/**
 * Small dropdown shown in the chat header. Hides itself entirely when there's
 * only one available model — no point wasting header real estate.
 */
export function ModelPicker({ onChange, compact = false }: Props) {
  const models = useModels();
  const [value, setValue] = useState<string>("");

  useEffect(() => {
    if (!models.length) return;
    const stored = getSelectedModel();
    const initial =
      stored && models.find((m) => m.id === stored && m.available)
        ? stored
        : models.find((m) => m.available)?.id || "";
    setValue(initial);
  }, [models]);

  if (models.length <= 1) return null;

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setValue(next);
    setSelectedModel(next);
    onChange?.(next);
  };

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: compact ? "4px 10px" : "6px 12px",
        background: "#F8FAFF",
        border: "1px solid #E2E8F0",
        borderRadius: 8,
        fontSize: 12,
      }}
    >
      <span style={{ color: "#64748B", fontWeight: 500 }}>模型</span>
      <select
        value={value}
        onChange={handleChange}
        style={{
          border: "none",
          background: "transparent",
          fontSize: 12,
          fontWeight: 600,
          color: "#1E3A8A",
          cursor: "pointer",
          outline: "none",
          fontFamily: "inherit",
        }}
      >
        {models.map((m) => (
          <option key={m.id} value={m.id} disabled={!m.available}>
            {m.display_name}
            {!m.available ? " (未启用)" : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
