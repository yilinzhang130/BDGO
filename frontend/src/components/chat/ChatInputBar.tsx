"use client";

import { useEffect, useRef } from "react";
import {
  filterCommands,
  SlashCommandPopup,
  type SlashCommand,
} from "@/components/ui/SlashCommandPopup";

/**
 * The composite input area at the bottom of the chat page:
 *   - attachment chips row
 *   - file picker button
 *   - textarea with auto-resize + slash-command keyboard navigation
 *   - send button
 *
 * Parent owns all state (input text, attachments, streaming flag, slash
 * command list). This component just wires events through.
 */
export function ChatInputBar({
  input,
  onInputChange,
  attachments,
  onRemoveAttachment,
  onPickFile,
  uploading,
  isStreaming,
  slashParsing,
  onSend,
  slashCommands,
  slashActiveIndex,
  onSlashActiveIndexChange,
  onSlashSelect,
  slashServicesError,
  slashServicesLoading,
  onRetrySlashServices,
}: {
  input: string;
  onInputChange: (v: string) => void;
  attachments: string[];
  onRemoveAttachment: (f: string) => void;
  onPickFile: (file: File) => void;
  uploading: boolean;
  isStreaming: boolean;
  slashParsing: boolean;
  onSend: () => void;
  slashCommands: SlashCommand[];
  slashActiveIndex: number;
  onSlashActiveIndexChange: (i: number | ((prev: number) => number)) => void;
  onSlashSelect: (cmd: SlashCommand) => void;
  // Surfaced from useSlashCommand so the popup can show "load failed +
  // retry" instead of silently degrading to slug-only display.
  slashServicesError?: string | null;
  slashServicesLoading?: boolean;
  onRetrySlashServices?: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const slashQuery = input.startsWith("/") ? input.slice(1).split(/\s/)[0] : null;
  const slashOpen = slashQuery !== null && !isStreaming;
  const filtered = slashQuery === null ? [] : filterCommands(slashCommands, slashQuery);

  // Auto-resize textarea to fit content (capped at 140px).
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 140) + "px";
    }
  }, [input]);

  // Clamp active slash index when list shrinks.
  useEffect(() => {
    if (slashActiveIndex >= filtered.length && filtered.length > 0) {
      onSlashActiveIndexChange(0);
    }
  }, [filtered.length, slashActiveIndex, onSlashActiveIndexChange]);

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input-container">
        {attachments.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.4rem",
              padding: "0.3rem 0.35rem 0.5rem",
            }}
          >
            {attachments.map((f) => (
              <div key={f} className="attachment-chip">
                <span>
                  {"\uD83D\uDCCE"} {f}
                </span>
                <button onClick={() => onRemoveAttachment(f)} className="attachment-chip-remove">
                  {"\u00D7"}
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="chat-input-bar">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.pptx,.ppt,.docx,.doc"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onPickFile(f);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || isStreaming}
            title="Attach file"
            className="chat-attach-btn"
          >
            {uploading ? "\u2026" : "\uD83D\uDCCE"}
          </button>

          <div style={{ flex: 1, position: "relative" }}>
            {slashOpen && (
              <SlashCommandPopup
                commands={filtered}
                activeIndex={slashActiveIndex}
                onSelect={onSlashSelect}
                onHover={onSlashActiveIndexChange}
                servicesError={slashServicesError}
                servicesLoading={slashServicesLoading}
                onRetryServices={onRetrySlashServices}
              />
            )}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (slashOpen && filtered.length > 0) {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    onSlashActiveIndexChange((i) => (i + 1) % filtered.length);
                    return;
                  }
                  if (e.key === "ArrowUp") {
                    e.preventDefault();
                    onSlashActiveIndexChange((i) => (i - 1 + filtered.length) % filtered.length);
                    return;
                  }
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onSlashSelect(filtered[slashActiveIndex]);
                    return;
                  }
                  if (e.key === "Tab") {
                    e.preventDefault();
                    onSlashSelect(filtered[slashActiveIndex]);
                    return;
                  }
                  if (e.key === "Escape") {
                    e.preventDefault();
                    onInputChange("");
                    return;
                  }
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (input.startsWith("/")) return;
                  if (input.trim() && !isStreaming) onSend();
                }
              }}
              placeholder={
                slashParsing
                  ? "解析参数中…"
                  : attachments.length > 0
                    ? "Ask about the attached files..."
                    : "Ask anything, or type / for report commands..."
              }
              disabled={isStreaming || slashParsing}
              rows={1}
              style={{ width: "100%" }}
            />
          </div>

          <button
            onClick={onSend}
            disabled={!input.trim() || isStreaming || input.startsWith("/")}
            className="chat-send-btn"
          >
            {isStreaming ? "\u2026" : "\u2191"}
          </button>
        </div>
      </div>
    </div>
  );
}
