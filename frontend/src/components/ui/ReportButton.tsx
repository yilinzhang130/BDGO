"use client";
import { useState } from "react";
import { getToken } from "@/lib/auth";

// ── Shared modal shell ────────────────────────────────────────────────────────

interface SubmitModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  placeholder: string;
  submitColor: string;
  msg: string;
  setMsg: (v: string) => void;
  sending: boolean;
  done: boolean;
  onSubmit: () => void;
}

function SubmitModal({
  open, onClose, title, subtitle, placeholder,
  submitColor, msg, setMsg, sending, done, onSubmit,
}: SubmitModalProps) {
  if (!open) return null;
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        background: "#fff", borderRadius: 12, padding: 24, width: 420, maxWidth: "90vw",
        boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
      }} onClick={e => e.stopPropagation()}>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>{title}</div>
        {subtitle && <div style={{ fontSize: 12, color: "#64748b", marginBottom: 14 }}>{subtitle}</div>}
        {done ? (
          <div style={{ color: "#16a34a", fontWeight: 500, textAlign: "center", padding: "16px 0" }}>
            ✓ 已提交，感谢反馈
          </div>
        ) : (
          <>
            <textarea
              style={{
                width: "100%", minHeight: 100, padding: "10px 12px",
                border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 13,
                resize: "vertical", outline: "none", fontFamily: "inherit", boxSizing: "border-box",
              }}
              placeholder={placeholder}
              value={msg}
              onChange={e => setMsg(e.target.value)}
              autoFocus
            />
            <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "flex-end" }}>
              <button onClick={onClose} style={{
                padding: "7px 16px", border: "1px solid #e2e8f0", borderRadius: 7,
                background: "#fff", cursor: "pointer", fontSize: 13,
              }}>取消</button>
              <button onClick={onSubmit} disabled={sending || !msg.trim()} style={{
                padding: "7px 16px", borderRadius: 7, border: "none",
                background: msg.trim() ? submitColor : submitColor + "80",
                color: "#fff", cursor: msg.trim() ? "pointer" : "default", fontSize: 13, fontWeight: 500,
              }}>{sending ? "提交中…" : "提交"}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function useSubmitModal(endpoint: string, buildBody: (msg: string) => object) {
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async () => {
    if (!msg.trim()) return;
    setSending(true);
    try {
      await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify(buildBody(msg.trim())),
      });
      setDone(true);
      setTimeout(() => { setOpen(false); setDone(false); setMsg(""); }, 1500);
    } finally {
      setSending(false);
    }
  };

  const close = () => setOpen(false);

  return { open, setOpen, msg, setMsg, sending, done, submit, close };
}

// ── ReportButton ──────────────────────────────────────────────────────────────

interface ReportButtonProps {
  entityType: string;
  entityKey: string;
  entityUrl?: string;
}

export function ReportButton({ entityType, entityKey, entityUrl }: ReportButtonProps) {
  const modal = useSubmitModal("/api/inbox/report", msg => ({
    entity_type: entityType,
    entity_key: entityKey,
    entity_url: entityUrl || window.location.href,
    message: msg,
  }));

  return (
    <>
      <button
        onClick={() => modal.setOpen(true)}
        title="举报数据问题"
        style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          fontSize: 12, color: "#94a3b8", background: "none", border: "none",
          cursor: "pointer", padding: "2px 6px", borderRadius: 4,
        }}
      >
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <path d="M3 2v12M3 2l10 4-10 4" />
        </svg>
        举报
      </button>
      <SubmitModal
        open={modal.open}
        onClose={modal.close}
        title="举报数据问题"
        subtitle={`${entityType} · ${entityKey}`}
        placeholder="请描述数据问题，例如：公司名称有误、临床阶段已更新、交易金额错误…"
        submitColor="#ef4444"
        msg={modal.msg}
        setMsg={modal.setMsg}
        sending={modal.sending}
        done={modal.done}
        onSubmit={modal.submit}
      />
    </>
  );
}

// ── FeedbackButton ────────────────────────────────────────────────────────────

export function FeedbackButton() {
  const modal = useSubmitModal("/api/inbox/feedback", msg => ({ message: msg }));

  return (
    <>
      <button
        onClick={() => modal.setOpen(true)}
        style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          fontSize: 12, color: "#94a3b8", background: "none", border: "none",
          cursor: "pointer", padding: "4px 6px", borderRadius: 4,
          width: "100%",
        }}
      >
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 2h12v9H2z" />
          <path d="M5 13l3-2 3 2" />
          <path d="M5 6h6M5 8.5h4" />
        </svg>
        意见反馈
      </button>
      <SubmitModal
        open={modal.open}
        onClose={modal.close}
        title="意见反馈"
        subtitle="功能建议、问题报告、任何想说的话…"
        placeholder="请输入你的反馈…"
        submitColor="#1e3a8a"
        msg={modal.msg}
        setMsg={modal.setMsg}
        sending={modal.sending}
        done={modal.done}
        onSubmit={modal.submit}
      />
    </>
  );
}
