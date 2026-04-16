"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchAdminDashboard,
  grantCredits,
  fetchAdminInviteCodes,
  createInviteCode,
  deleteInviteCode,
  setUserActive,
  setUserAdmin,
  type AdminUser,
  type InviteCode,
} from "@/lib/api";

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<"users" | "codes">("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [codes, setCodes] = useState<InviteCode[]>([]);
  const [loading, setLoading] = useState(true);

  // Grant credits modal state
  const [grantTarget, setGrantTarget] = useState<AdminUser | null>(null);
  const [grantAmount, setGrantAmount] = useState("");
  const [granting, setGranting] = useState(false);

  const isAdmin = user?.is_admin === true;

  useEffect(() => {
    if (user && !isAdmin) {
      router.replace("/chat");
    }
  }, [user, isAdmin, router]);

  const reloadUsers = async () => {
    const r = await fetchAdminDashboard();
    setUsers(r.users);
  };

  const reloadCodes = async () => {
    const r = await fetchAdminInviteCodes();
    setCodes(r.codes);
  };

  useEffect(() => {
    if (!isAdmin) return;
    setLoading(true);
    const p = tab === "users" ? reloadUsers() : reloadCodes();
    p.finally(() => setLoading(false));
  }, [tab, isAdmin]);

  if (!isAdmin) return <div className="loading">Loading...</div>;

  const handleGrant = async () => {
    if (!grantTarget || !grantAmount) return;
    const amt = parseFloat(grantAmount);
    if (isNaN(amt) || amt <= 0) return;
    setGranting(true);
    try {
      await grantCredits(grantTarget.id, amt);
      await reloadUsers();
      setGrantTarget(null);
      setGrantAmount("");
    } catch (e: any) {
      alert(`Failed: ${e.message}`);
    } finally {
      setGranting(false);
    }
  };

  const handleToggleActive = async (u: AdminUser) => {
    const verb = u.is_active ? "停用" : "启用";
    if (!confirm(`确认${verb}用户 "${u.name}" (${u.email})?`)) return;
    try {
      await setUserActive(u.id, !u.is_active);
      await reloadUsers();
    } catch (e: any) {
      alert(`操作失败: ${e.message}`);
    }
  };

  const handleToggleAdmin = async (u: AdminUser) => {
    const verb = u.is_admin ? "撤销管理员" : "设为管理员";
    if (!confirm(`确认${verb}: "${u.name}" (${u.email})?`)) return;
    try {
      await setUserAdmin(u.id, !u.is_admin);
      await reloadUsers();
    } catch (e: any) {
      alert(`操作失败: ${e.message}`);
    }
  };

  const handleCreateCode = async () => {
    try {
      await createInviteCode(1);
      await reloadCodes();
    } catch (e: any) {
      alert(`Failed: ${e.message}`);
    }
  };

  const handleDeleteCode = async (code: string) => {
    if (!confirm(`撤销邀请码 ${code}?`)) return;
    try {
      await deleteInviteCode(code);
      setCodes((prev) => prev.filter((c) => c.code !== code));
    } catch (e: any) {
      alert(`Failed: ${e.message}`);
    }
  };

  const fmtDate = (d: string | null) => {
    if (!d) return "-";
    try {
      return new Date(d).toLocaleDateString("zh-CN", {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit",
      });
    } catch { return d; }
  };

  return (
    <div>
      <div className="detail-header">
        <h1 style={{ margin: 0 }}>Admin Dashboard</h1>
        <p style={{ margin: "0.25rem 0 0", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
          用户管理、积分发放、邀请码
        </p>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${tab === "users" ? "active" : ""}`} onClick={() => setTab("users")}>
          用户管理 ({users.length || "..."})
        </button>
        <button className={`tab ${tab === "codes" ? "active" : ""}`} onClick={() => setTab("codes")}>
          邀请码 ({codes.length || "..."})
        </button>
      </div>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : tab === "users" ? (
        <div className="card">
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>姓名</th>
                  <th>邮箱</th>
                  <th>公司</th>
                  <th>Credits</th>
                  <th>已用</th>
                  <th>注册</th>
                  <th>最后登录</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf = u.id === user!.id;
                  return (
                    <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.5 }}>
                      <td style={{ fontWeight: 600 }}>
                        {u.name}
                        {u.is_admin && (
                          <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 700, color: "#fff", background: "#DC2626", padding: "1px 5px", borderRadius: 4 }}>
                            ADMIN
                          </span>
                        )}
                        {isSelf && (
                          <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 600, color: "#2563EB" }}>
                            (你)
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{u.email}</td>
                      <td>{u.company || "-"}</td>
                      <td>
                        {u.is_admin ? (
                          <span style={{ color: "#7C3AED", fontWeight: 600 }}>\u221E</span>
                        ) : (
                          <span style={{
                            fontWeight: 600,
                            color: u.credit_balance >= 500 ? "#16A34A" : u.credit_balance > 0 ? "#D97706" : "#DC2626",
                          }}>
                            {u.credit_balance.toLocaleString()}
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                        {u.total_spent.toLocaleString()}
                      </td>
                      <td style={{ fontSize: "0.75rem" }}>{fmtDate(u.created_at)}</td>
                      <td style={{ fontSize: "0.75rem" }}>{fmtDate(u.last_login)}</td>
                      <td>
                        {u.is_active ? (
                          <span style={{ fontSize: 10, fontWeight: 600, color: "#16A34A", background: "#F0FDF4", padding: "1px 6px", borderRadius: 4 }}>
                            ACTIVE
                          </span>
                        ) : (
                          <span style={{ fontSize: 10, fontWeight: 600, color: "#64748B", background: "#F1F5F9", padding: "1px 6px", borderRadius: 4 }}>
                            BANNED
                          </span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                          {!u.is_admin && (
                            <button
                              onClick={() => { setGrantTarget(u); setGrantAmount(""); }}
                              disabled={!u.is_active}
                              style={btnStyle("accent", !u.is_active)}
                            >
                              +积分
                            </button>
                          )}
                          <button
                            onClick={() => handleToggleAdmin(u)}
                            disabled={isSelf}
                            style={btnStyle(u.is_admin ? "gray" : "purple", isSelf)}
                            title={isSelf ? "不能修改自己" : ""}
                          >
                            {u.is_admin ? "撤销Admin" : "设Admin"}
                          </button>
                          <button
                            onClick={() => handleToggleActive(u)}
                            disabled={isSelf}
                            style={btnStyle(u.is_active ? "red" : "green", isSelf)}
                            title={isSelf ? "不能停用自己" : ""}
                          >
                            {u.is_active ? "停用" : "启用"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Grant credits modal */}
          {grantTarget && (
            <div style={{
              position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
              display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
            }} onClick={() => setGrantTarget(null)}>
              <div onClick={(e) => e.stopPropagation()} style={{
                background: "#fff", borderRadius: 12, padding: "1.5rem", width: 360,
                boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
              }}>
                <h3 style={{ margin: "0 0 1rem", fontSize: "0.95rem" }}>
                  发放积分给 {grantTarget.name}
                </h3>
                <p style={{ margin: "0 0 0.5rem", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  当前余额: {grantTarget.credit_balance.toLocaleString()}
                </p>
                <input
                  type="number"
                  value={grantAmount}
                  onChange={(e) => setGrantAmount(e.target.value)}
                  placeholder="数量（例如 5000）"
                  autoFocus
                  style={{
                    width: "100%", padding: "0.6rem", fontSize: "0.9rem",
                    border: "1px solid #E2E8F0", borderRadius: 8, marginBottom: "1rem",
                    boxSizing: "border-box",
                  }}
                />
                <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                  <button
                    onClick={() => setGrantTarget(null)}
                    style={{ padding: "0.4rem 1rem", fontSize: "0.85rem", background: "#f1f5f9", border: "1px solid #e2e8f0", borderRadius: 6, cursor: "pointer" }}
                  >
                    取消
                  </button>
                  <button
                    onClick={handleGrant}
                    disabled={granting || !grantAmount || parseFloat(grantAmount) <= 0}
                    style={{
                      padding: "0.4rem 1rem", fontSize: "0.85rem", fontWeight: 600,
                      background: "var(--accent)", color: "#fff", border: "none",
                      borderRadius: 6, cursor: granting ? "not-allowed" : "pointer",
                    }}
                  >
                    {granting ? "..." : "发放"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.75rem" }}>
            <button
              onClick={handleCreateCode}
              style={{
                padding: "0.4rem 0.9rem", fontSize: "0.8rem", fontWeight: 600,
                background: "var(--accent)", color: "#fff", border: "none",
                borderRadius: 6, cursor: "pointer",
              }}
            >
              + 新建邀请码
            </button>
          </div>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>邀请码</th>
                  <th>已使用</th>
                  <th>最大次数</th>
                  <th>创建时间</th>
                  <th>过期</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {codes.map((c) => (
                  <tr key={c.code}>
                    <td style={{ fontWeight: 600, fontFamily: "monospace", letterSpacing: "0.05em" }}>
                      {c.code}
                    </td>
                    <td>
                      <span style={{ color: c.use_count >= c.max_uses ? "#DC2626" : "var(--text)" }}>
                        {c.use_count}
                      </span>
                    </td>
                    <td>{c.max_uses}</td>
                    <td style={{ fontSize: "0.8rem" }}>{fmtDate(c.created_at)}</td>
                    <td style={{ fontSize: "0.8rem" }}>{c.expires_at ? fmtDate(c.expires_at) : "永不"}</td>
                    <td>
                      <button
                        onClick={() => handleDeleteCode(c.code)}
                        style={{
                          padding: "0.2rem 0.5rem", fontSize: "0.75rem",
                          background: "white", color: "var(--red)", border: "1px solid var(--red)",
                          borderRadius: 4, cursor: "pointer",
                        }}
                      >
                        撤销
                      </button>
                    </td>
                  </tr>
                ))}
                {codes.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--text-secondary)" }}>暂无邀请码</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function btnStyle(
  variant: "accent" | "red" | "green" | "purple" | "gray",
  disabled: boolean,
): React.CSSProperties {
  const colors = {
    accent: { bg: "var(--accent)", fg: "#fff", border: "none" },
    red: { bg: "#fff", fg: "#DC2626", border: "1px solid #DC2626" },
    green: { bg: "#fff", fg: "#16A34A", border: "1px solid #16A34A" },
    purple: { bg: "#fff", fg: "#7C3AED", border: "1px solid #7C3AED" },
    gray: { bg: "#fff", fg: "#64748B", border: "1px solid #CBD5E1" },
  };
  const c = colors[variant];
  return {
    padding: "0.25rem 0.55rem", fontSize: "0.7rem", fontWeight: 600,
    background: c.bg, color: c.fg, border: c.border,
    borderRadius: 5, cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.4 : 1,
    whiteSpace: "nowrap",
  };
}
