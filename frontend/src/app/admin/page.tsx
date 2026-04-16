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
  fetchDeals,
  type AdminUser,
  type InviteCode,
} from "@/lib/api";

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<"users" | "codes" | "deals">("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [codes, setCodes] = useState<InviteCode[]>([]);
  const [deals, setDeals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Grant credits state
  const [grantTarget, setGrantTarget] = useState<AdminUser | null>(null);
  const [grantAmount, setGrantAmount] = useState("");
  const [granting, setGranting] = useState(false);

  const isAdmin = user?.is_admin === true;

  useEffect(() => {
    if (user && !isAdmin) {
      router.replace("/chat");
    }
  }, [user, isAdmin, router]);

  useEffect(() => {
    if (!isAdmin) return;
    setLoading(true);
    if (tab === "users") {
      fetchAdminDashboard()
        .then((r) => setUsers(r.users))
        .finally(() => setLoading(false));
    } else if (tab === "codes") {
      fetchAdminInviteCodes()
        .then((r) => setCodes(r.codes))
        .finally(() => setLoading(false));
    } else if (tab === "deals") {
      fetchDeals({ limit: 200 })
        .then((r: any) => setDeals(r.data || []))
        .finally(() => setLoading(false));
    }
  }, [tab, isAdmin]);

  if (!isAdmin) return <div className="loading">Loading...</div>;

  const handleGrant = async () => {
    if (!grantTarget || !grantAmount) return;
    const amt = parseFloat(grantAmount);
    if (isNaN(amt) || amt <= 0) return;
    setGranting(true);
    try {
      await grantCredits(grantTarget.id, amt);
      // Refresh user list
      const r = await fetchAdminDashboard();
      setUsers(r.users);
      setGrantTarget(null);
      setGrantAmount("");
    } catch (e: any) {
      alert(`Failed: ${e.message}`);
    } finally {
      setGranting(false);
    }
  };

  const handleCreateCode = async () => {
    try {
      await createInviteCode(1);
      const r = await fetchAdminInviteCodes();
      setCodes(r.codes);
    } catch (e: any) {
      alert(`Failed: ${e.message}`);
    }
  };

  const handleDeleteCode = async (code: string) => {
    if (!confirm(`Delete invite code ${code}?`)) return;
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
          User management, invite codes, and system overview
        </p>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${tab === "users" ? "active" : ""}`} onClick={() => setTab("users")}>
          Users ({users.length || "..."})
        </button>
        <button className={`tab ${tab === "codes" ? "active" : ""}`} onClick={() => setTab("codes")}>
          Invite Codes ({codes.length || "..."})
        </button>
        <button className={`tab ${tab === "deals" ? "active" : ""}`} onClick={() => setTab("deals")}>
          Deals ({deals.length || "..."})
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
                  <th>Name</th>
                  <th>Email</th>
                  <th>Company</th>
                  <th>Role</th>
                  <th>Credits</th>
                  <th>Used</th>
                  <th>Registered</th>
                  <th>Last Login</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 600 }}>
                      {u.name}
                      {u.is_admin && (
                        <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 700, color: "#fff", background: "#DC2626", padding: "1px 5px", borderRadius: 4 }}>
                          ADMIN
                        </span>
                      )}
                    </td>
                    <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{u.email}</td>
                    <td>{u.company || "-"}</td>
                    <td>{u.title || "-"}</td>
                    <td>
                      <span style={{
                        fontWeight: 600,
                        color: u.credit_balance >= 500 ? "#16A34A" : u.credit_balance > 0 ? "#D97706" : "#DC2626",
                      }}>
                        {u.credit_balance.toLocaleString()}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                      {u.total_spent.toLocaleString()}
                    </td>
                    <td style={{ fontSize: "0.8rem" }}>{fmtDate(u.created_at)}</td>
                    <td style={{ fontSize: "0.8rem" }}>{fmtDate(u.last_login)}</td>
                    <td>
                      <button
                        onClick={() => { setGrantTarget(u); setGrantAmount(""); }}
                        style={{
                          padding: "0.25rem 0.6rem", fontSize: "0.75rem", fontWeight: 600,
                          background: "var(--accent)", color: "#fff", border: "none",
                          borderRadius: 5, cursor: "pointer",
                        }}
                      >
                        + Credits
                      </button>
                    </td>
                  </tr>
                ))}
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
                  Grant Credits to {grantTarget.name}
                </h3>
                <p style={{ margin: "0 0 0.5rem", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  Current balance: {grantTarget.credit_balance.toLocaleString()}
                </p>
                <input
                  type="number"
                  value={grantAmount}
                  onChange={(e) => setGrantAmount(e.target.value)}
                  placeholder="Amount (e.g. 5000)"
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
                    Cancel
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
                    {granting ? "..." : "Grant"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : tab === "codes" ? (
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
              + New Code
            </button>
          </div>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Uses</th>
                  <th>Max Uses</th>
                  <th>Created</th>
                  <th>Expires</th>
                  <th>Actions</th>
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
                    <td style={{ fontSize: "0.8rem" }}>{c.expires_at ? fmtDate(c.expires_at) : "Never"}</td>
                    <td>
                      <button
                        onClick={() => handleDeleteCode(c.code)}
                        style={{
                          padding: "0.2rem 0.5rem", fontSize: "0.75rem",
                          background: "white", color: "var(--red)", border: "1px solid var(--red)",
                          borderRadius: 4, cursor: "pointer",
                        }}
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
                {codes.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--text-secondary)" }}>No invite codes yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Deal</th>
                  <th>Type</th>
                  <th>Buyer</th>
                  <th>Seller</th>
                  <th>Asset</th>
                  <th>Upfront ($M)</th>
                  <th>Total ($M)</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {deals.map((d: any, i: number) => (
                  <tr key={d["\u4ea4\u6613\u540d\u79f0"] || i}>
                    <td style={{ fontWeight: 600 }}>{d["\u4ea4\u6613\u540d\u79f0"] || "-"}</td>
                    <td>{d["\u4ea4\u6613\u7c7b\u578b"] || "-"}</td>
                    <td>{d["\u4e70\u65b9\u516c\u53f8"] || "-"}</td>
                    <td>{d["\u5356\u65b9/\u5408\u4f5c\u65b9"] || "-"}</td>
                    <td>{d["\u8d44\u4ea7\u540d\u79f0"] || "-"}</td>
                    <td>{d["\u9996\u4ed8\u6b3e($M)"] || "-"}</td>
                    <td>{d["\u4ea4\u6613\u603b\u989d($M)"] || "-"}</td>
                    <td>{d["\u5ba3\u5e03\u65e5\u671f"] || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
