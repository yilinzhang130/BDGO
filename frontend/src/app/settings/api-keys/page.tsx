"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { useAuth } from "@/components/AuthProvider";
import { fetchApiKeys, createApiKey, revokeApiKey, type ApiKeyRecord } from "@/lib/api";
import { errorMessage } from "@/lib/format";

// ---------------------------------------------------------------------------
// Styles (mirrors /profile page for visual consistency)
// ---------------------------------------------------------------------------

const pageStyle: React.CSSProperties = {
  maxWidth: 880,
  margin: "0 auto",
  padding: "48px 24px 96px",
  fontFamily: "Inter, -apple-system, sans-serif",
  color: "#111827",
};

const sectionStyle: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  padding: "28px 32px",
  marginBottom: 24,
};

const btnPrimary: React.CSSProperties = {
  padding: "9px 18px",
  fontSize: 14,
  fontWeight: 500,
  color: "#fff",
  background: "#2563eb",
  border: "none",
  borderRadius: 8,
  cursor: "pointer",
};

const btnGhost: React.CSSProperties = {
  padding: "6px 12px",
  fontSize: 13,
  fontWeight: 500,
  color: "#6b7280",
  background: "transparent",
  border: "1px solid #d1d5db",
  borderRadius: 6,
  cursor: "pointer",
};

const btnDanger: React.CSSProperties = {
  padding: "6px 12px",
  fontSize: 13,
  fontWeight: 500,
  color: "#dc2626",
  background: "#fff",
  border: "1px solid #fca5a5",
  borderRadius: 6,
  cursor: "pointer",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "9px 12px",
  fontSize: 14,
  border: "1px solid #d1d5db",
  borderRadius: 8,
  outline: "none",
  background: "#fff",
  boxSizing: "border-box",
};

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

function Toast({
  message,
  type,
  onClose,
}: {
  message: string;
  type: "success" | "error";
  onClose: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div
      style={{
        position: "fixed",
        bottom: 32,
        right: 32,
        padding: "12px 20px",
        borderRadius: 8,
        backgroundColor: type === "success" ? "#059669" : "#dc2626",
        color: "#fff",
        fontSize: 14,
        fontWeight: 500,
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
        zIndex: 9999,
      }}
    >
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// One-time-reveal modal: the raw key is returned only at creation time and
// must be copied immediately. We show it in its own dialog to reinforce that.
// ---------------------------------------------------------------------------

function SecretRevealModal({ secret, onClose }: { secret: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked — user can still triple-click the field */
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10_000,
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: "28px 32px",
          maxWidth: 520,
          width: "90%",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
        }}
      >
        <div style={{ fontSize: 17, fontWeight: 600, color: "#111827", marginBottom: 6 }}>
          API Key 创建成功
        </div>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>
          这个 key 仅显示一次。请立即复制并妥善保管 — 关闭此窗口后将无法再次查看完整值。
        </div>

        <div
          style={{
            background: "#F8FAFC",
            border: "1px solid #E2E8F0",
            borderRadius: 8,
            padding: "12px 14px",
            fontFamily: "monospace",
            fontSize: 13,
            color: "#0F172A",
            wordBreak: "break-all",
            marginBottom: 16,
          }}
        >
          {secret}
        </div>

        <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
          <button style={btnGhost} onClick={copy}>
            {copied ? "已复制 ✓" : "复制到剪贴板"}
          </button>
          <button style={btnPrimary} onClick={onClose}>
            我已保存
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ApiKeysSettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const showToast = useCallback(
    (message: string, type: "success" | "error") => setToast({ message, type }),
    [],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { items } = await fetchApiKeys(false);
      setKeys(items);
    } catch (err: unknown) {
      showToast(errorMessage(err, "加载 API Key 列表失败"), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) {
      showToast("请先填写 Key 名称", "error");
      return;
    }
    setCreating(true);
    try {
      const res = await createApiKey(name);
      setRevealedSecret(res.key);
      setNewName("");
      setKeys((prev) => [res.record, ...prev]);
    } catch (err: unknown) {
      showToast(errorMessage(err, "创建失败"), "error");
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (k: ApiKeyRecord) => {
    if (!window.confirm(`确定吊销 "${k.name}"？已部署的客户端将立刻失效，无法恢复。`)) {
      return;
    }
    try {
      await revokeApiKey(k.id);
      // List excludes revoked by default; drop locally instead of refetching.
      setKeys((prev) => prev.filter((x) => x.id !== k.id));
      showToast("Key 已吊销", "success");
    } catch (err: unknown) {
      showToast(errorMessage(err, "吊销失败"), "error");
    }
  };

  if (authLoading || !user) {
    return (
      <div style={pageStyle}>
        <div style={{ color: "#6b7280", padding: 40, textAlign: "center" }}>加载中…</div>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <div style={{ marginBottom: 28 }}>
        <Link href="/profile" style={{ fontSize: 13, color: "#6b7280", textDecoration: "none" }}>
          ← 返回账户设置
        </Link>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: "#0F172A", margin: "10px 0 4px" }}>
          API Keys
        </h1>
        <p style={{ fontSize: 14, color: "#6b7280", margin: 0 }}>
          通过{" "}
          <code style={{ background: "#F1F5F9", padding: "1px 6px", borderRadius: 4 }}>
            X-API-Key
          </code>{" "}
          请求头访问 BD Go 数据接口。每个 key 仅在创建时显示一次，之后只保留前缀用于识别。
        </p>
      </div>

      {/* Create new key */}
      <section style={sectionStyle}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>创建新 Key</div>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 18 }}>
          名称仅用于你自己识别 — 例如 &quot;本地调试&quot;、&quot;数据管道生产&quot;、&quot;CRM
          集成&quot;。
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <input
            style={{ ...inputStyle, flex: 1 }}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="例如 本地调试"
            maxLength={100}
            disabled={creating}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleCreate();
            }}
          />
          <button
            style={{
              ...btnPrimary,
              opacity: creating ? 0.6 : 1,
              cursor: creating ? "wait" : "pointer",
            }}
            onClick={handleCreate}
            disabled={creating}
          >
            {creating ? "创建中…" : "创建"}
          </button>
        </div>
      </section>

      {/* Existing keys */}
      <section style={sectionStyle}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>我的 Keys</div>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 18 }}>
          有效 Keys — 吊销后记录仍保留，但不再通过身份验证。
        </div>

        {loading ? (
          <div style={{ color: "#6b7280", padding: 20, textAlign: "center" }}>加载中…</div>
        ) : keys.length === 0 ? (
          <div
            style={{
              color: "#6b7280",
              fontSize: 13,
              padding: "24px 0",
              textAlign: "center",
              borderTop: "1px dashed #e5e7eb",
            }}
          >
            还没有 Key。创建一个开始调用 API。
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {keys.map((k) => (
              <div
                key={k.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "14px 16px",
                  border: "1px solid #e5e7eb",
                  borderRadius: 10,
                  background: "#FAFBFC",
                }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 2 }}>
                    {k.name}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      fontFamily: "monospace",
                      color: "#6b7280",
                      marginBottom: 2,
                    }}
                  >
                    {k.key_prefix}…
                  </div>
                  <div style={{ fontSize: 11, color: "#9ca3af" }}>
                    创建于 {new Date(k.created_at).toLocaleDateString()}
                    {k.last_used_at
                      ? ` · 最后使用 ${new Date(k.last_used_at).toLocaleString()}`
                      : " · 从未使用"}
                    {k.last_used_ip ? ` · 来自 ${k.last_used_ip}` : ""}
                  </div>
                </div>
                <button style={btnDanger} onClick={() => handleRevoke(k)}>
                  吊销
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Usage snippet */}
      <section style={sectionStyle}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>使用示例</div>
        <pre
          style={{
            background: "#0F172A",
            color: "#E2E8F0",
            padding: 16,
            borderRadius: 8,
            fontSize: 13,
            fontFamily: "monospace",
            margin: 0,
            overflowX: "auto",
            whiteSpace: "pre",
          }}
        >
          {`curl https://api.bdgo.ai/api/companies \\
  -H "X-API-Key: bdgo_live_xxxxxxxx"`}
        </pre>
        <div style={{ fontSize: 12, color: "#6b7280", marginTop: 10 }}>
          支持的端点列表见{" "}
          <Link href="/api-docs" style={{ color: "#2563EB" }}>
            API 文档页
          </Link>
          。
        </div>
      </section>

      {revealedSecret && (
        <SecretRevealModal secret={revealedSecret} onClose={() => setRevealedSecret(null)} />
      )}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
