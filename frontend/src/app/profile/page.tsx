"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import { updateProfile } from "@/lib/api";
import { parsePreferences, type UserPreferences } from "@/lib/auth";

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

function Toast({ message, type, onClose }: { message: string; type: "success" | "error"; onClose: () => void }) {
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
        animation: "fadeIn 0.2s ease",
      }}
    >
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

const sectionStyle: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  padding: "28px 32px",
  marginBottom: 24,
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: 17,
  fontWeight: 600,
  color: "#111827",
  marginBottom: 4,
};

const sectionDescStyle: React.CSSProperties = {
  fontSize: 13,
  color: "#6b7280",
  marginBottom: 24,
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 500,
  color: "#374151",
  marginBottom: 6,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "9px 12px",
  fontSize: 14,
  border: "1px solid #d1d5db",
  borderRadius: 8,
  outline: "none",
  color: "#111827",
  background: "#fff",
  boxSizing: "border-box",
};

const inputReadOnlyStyle: React.CSSProperties = {
  ...inputStyle,
  background: "#f9fafb",
  color: "#6b7280",
  cursor: "not-allowed",
};

const textareaStyle: React.CSSProperties = {
  ...inputStyle,
  minHeight: 100,
  resize: "vertical" as const,
  fontFamily: "inherit",
};

const btnPrimaryStyle: React.CSSProperties = {
  padding: "9px 20px",
  fontSize: 14,
  fontWeight: 500,
  color: "#fff",
  background: "#2563eb",
  border: "none",
  borderRadius: 8,
  cursor: "pointer",
};

const btnDangerStyle: React.CSSProperties = {
  padding: "9px 20px",
  fontSize: 14,
  fontWeight: 500,
  color: "#fff",
  background: "#dc2626",
  border: "none",
  borderRadius: 8,
  cursor: "pointer",
};

const fieldRowStyle: React.CSSProperties = {
  marginBottom: 18,
};

const twoColStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 18,
};

// ---------------------------------------------------------------------------
// Toggle row
// ---------------------------------------------------------------------------

function ToggleRow({
  title,
  description,
  checked,
  disabled,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 0" }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>{title}</div>
        <div style={{ fontSize: 13, color: "#6b7280", marginTop: 2, maxWidth: 520 }}>{description}</div>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        style={{
          position: "relative",
          width: 44,
          height: 24,
          borderRadius: 12,
          border: "none",
          background: checked ? "#2563eb" : "#d1d5db",
          cursor: disabled ? "wait" : "pointer",
          transition: "background 0.2s",
          flexShrink: 0,
          marginLeft: 16,
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: checked ? 22 : 2,
            width: 20,
            height: 20,
            borderRadius: "50%",
            background: "#fff",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
            transition: "left 0.2s",
          }}
        />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Profile Page
// ---------------------------------------------------------------------------

export default function ProfilePage() {
  const { user, logout, updateUser } = useAuth();
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Personal info state
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [phone, setPhone] = useState("");
  const [bio, setBio] = useState("");
  const [savingPersonal, setSavingPersonal] = useState(false);

  // AI preferences state
  const [preferences, setPreferences] = useState("");
  const [savingPrefs, setSavingPrefs] = useState(false);

  // UI preferences state
  const [showDatabaseNav, setShowDatabaseNav] = useState(false);
  const [showReportCards, setShowReportCards] = useState(false);
  const [savingDisplay, setSavingDisplay] = useState(false);

  // Populate from user
  useEffect(() => {
    if (!user) return;
    setName(user.name || "");
    setCompany(user.company || "");
    setTitle(user.title || "");
    setPhone(user.phone || "");
    setBio(user.bio || "");
    const prefs = parsePreferences(user);
    setPreferences(prefs.ai_context || "");
    setShowDatabaseNav(prefs.show_database_nav === true);
    setShowReportCards(prefs.show_report_cards === true);
  }, [user]);

  const showToast = useCallback((message: string, type: "success" | "error") => {
    setToast({ message, type });
  }, []);
  const dismissToast = useCallback(() => setToast(null), []);

  const handleSavePersonal = async () => {
    setSavingPersonal(true);
    try {
      const updated = await updateProfile({ name, company, title, phone, bio });
      updateUser(updated);
      showToast("Profile updated", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to update profile", "error");
    } finally {
      setSavingPersonal(false);
    }
  };

  const handleSavePreferences = async () => {
    setSavingPrefs(true);
    try {
      let existing: UserPreferences = {};
      try { existing = JSON.parse(user?.preferences_json || "{}") as UserPreferences; } catch { /* ignore */ }
      const merged = JSON.stringify({ ...existing, ai_context: preferences });
      const updated = await updateProfile({ preferences_json: merged });
      updateUser(updated);
      showToast("AI preferences saved", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to save preferences", "error");
    } finally {
      setSavingPrefs(false);
    }
  };

  const persistPref = async <K extends keyof UserPreferences>(
    key: K,
    value: UserPreferences[K],
    revert: () => void,
    successMsg: string,
  ) => {
    setSavingDisplay(true);
    try {
      let existing: UserPreferences = {};
      try { existing = JSON.parse(preferences) as UserPreferences; } catch { /* use empty */ }
      const merged = JSON.stringify({ ...existing, [key]: value });
      const updated = await updateProfile({ preferences_json: merged });
      updateUser(updated);
      showToast(successMsg, "success");
    } catch (err: any) {
      revert();
      showToast(err.message || "Failed to save preference", "error");
    } finally {
      setSavingDisplay(false);
    }
  };

  const handleToggleDatabaseNav = (checked: boolean) => {
    setShowDatabaseNav(checked);
    persistPref(
      "show_database_nav",
      checked,
      () => setShowDatabaseNav(!checked),
      checked ? "Database navigation enabled" : "Database navigation hidden",
    );
  };

  const handleToggleReportCards = (checked: boolean) => {
    setShowReportCards(checked);
    persistPref(
      "show_report_cards",
      checked,
      () => setShowReportCards(!checked),
      checked ? "Report cards shown" : "Report cards hidden",
    );
  };

  if (!user) return null;

  const initial = user.name?.charAt(0)?.toUpperCase() || user.email?.charAt(0)?.toUpperCase() || "U";

  const memberSince = user.created_at
    ? new Date(user.created_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })
    : "Unknown";

  const lastLogin = user.last_login
    ? new Date(user.last_login).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "Unknown";

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "40px 24px 80px" }}>
      {toast && <Toast message={toast.message} type={toast.type} onClose={dismissToast} />}

      {/* Page header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#111827", margin: 0 }}>Settings</h1>
        <p style={{ fontSize: 14, color: "#6b7280", marginTop: 4 }}>Manage your account and preferences</p>
      </div>

      {/* ─── Personal Info ─── */}
      <div style={sectionStyle}>
        <div style={sectionTitleStyle}>Personal Information</div>
        <div style={sectionDescStyle}>Update your personal details and contact information.</div>

        {/* Avatar row */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
          {user.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.name}
              style={{ width: 64, height: 64, borderRadius: "50%", objectFit: "cover" }}
            />
          ) : (
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                background: "#2563eb",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
                fontWeight: 600,
              }}
            >
              {initial}
            </div>
          )}
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: "#111827" }}>{user.name}</div>
            <div style={{ fontSize: 13, color: "#6b7280" }}>{user.email}</div>
          </div>
        </div>

        <div style={twoColStyle}>
          <div style={fieldRowStyle}>
            <label style={labelStyle}>Full Name</label>
            <input style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div style={fieldRowStyle}>
            <label style={labelStyle}>Email</label>
            <input style={inputReadOnlyStyle} value={user.email} readOnly />
          </div>
        </div>

        <div style={twoColStyle}>
          <div style={fieldRowStyle}>
            <label style={labelStyle}>Company</label>
            <input style={inputStyle} value={company} onChange={(e) => setCompany(e.target.value)} placeholder="e.g. Pfizer, BeiGene" />
          </div>
          <div style={fieldRowStyle}>
            <label style={labelStyle}>Title</label>
            <input style={inputStyle} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. BD Director" />
          </div>
        </div>

        <div style={fieldRowStyle}>
          <label style={labelStyle}>Phone</label>
          <input style={inputStyle} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 (555) 000-0000" />
        </div>

        <div style={fieldRowStyle}>
          <label style={labelStyle}>Bio</label>
          <textarea
            style={textareaStyle}
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            placeholder="A short bio about yourself..."
          />
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button style={btnPrimaryStyle} onClick={handleSavePersonal} disabled={savingPersonal}>
            {savingPersonal ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      {/* ─── AI Preferences ─── */}
      <div style={sectionStyle}>
        <div style={sectionTitleStyle}>AI Preferences</div>
        <div style={sectionDescStyle}>
          Tell BD Go about your role, therapeutic area focus, and what kind of insights matter to you.
          This helps the AI personalize responses to your needs.
        </div>

        <div style={fieldRowStyle}>
          <label style={labelStyle}>About Me</label>
          <textarea
            style={{ ...textareaStyle, minHeight: 140 }}
            value={preferences}
            onChange={(e) => setPreferences(e.target.value)}
            placeholder={"Example: I'm a BD lead at a mid-size biotech focused on oncology and autoimmune. I'm primarily looking for licensing-in opportunities in Phase 2+ assets. I care about deal structure benchmarks and competitive landscape analysis."}
          />
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button style={btnPrimaryStyle} onClick={handleSavePreferences} disabled={savingPrefs}>
            {savingPrefs ? "Saving..." : "Save Preferences"}
          </button>
        </div>
      </div>

      {/* ─── UI ─── */}
      <div style={sectionStyle}>
        <div style={sectionTitleStyle}>UI</div>
        <div style={sectionDescStyle}>Toggle optional interface surfaces. Default is a minimal chat-first layout.</div>

        <ToggleRow
          title="Show report cards"
          description='Display the "Generate New Report" card grid on the Reports page. Off by default — use slash commands in chat instead.'
          checked={showReportCards}
          disabled={savingDisplay}
          onChange={handleToggleReportCards}
        />

        <div style={{ borderTop: "1px solid #f3f4f6" }} />

        <ToggleRow
          title="Show Database & Deals in sidebar"
          description="Display data tables (Companies, Assets, Clinical, Patents, Buyers, Deals) in the navigation."
          checked={showDatabaseNav}
          disabled={savingDisplay}
          onChange={handleToggleDatabaseNav}
        />

        <div style={{ borderTop: "1px solid #f3f4f6" }} />

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 0", opacity: 0.5 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>
              Dark mode <span style={{ fontSize: 11, fontWeight: 500, color: "#6b7280", marginLeft: 6 }}>Coming soon</span>
            </div>
            <div style={{ fontSize: 13, color: "#6b7280", marginTop: 2 }}>
              Switch between light and dark themes.
            </div>
          </div>
          <button
            role="switch"
            aria-checked={false}
            disabled
            style={{
              position: "relative",
              width: 44, height: 24, borderRadius: 12, border: "none",
              background: "#d1d5db", cursor: "not-allowed", flexShrink: 0, marginLeft: 16,
            }}
          >
            <span style={{ position: "absolute", top: 2, left: 2, width: 20, height: 20, borderRadius: "50%", background: "#fff", boxShadow: "0 1px 3px rgba(0,0,0,0.2)" }} />
          </button>
        </div>
      </div>

      {/* ─── Account ─── */}
      <div style={sectionStyle}>
        <div style={sectionTitleStyle}>Account</div>
        <div style={sectionDescStyle}>Account details and session management.</div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 24 }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
              Member Since
            </div>
            <div style={{ fontSize: 14, color: "#111827" }}>{memberSince}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
              Last Login
            </div>
            <div style={{ fontSize: 14, color: "#111827" }}>{lastLogin}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
              Auth Provider
            </div>
            <div style={{ fontSize: 14, color: "#111827", textTransform: "capitalize" }}>{user.provider}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
              User ID
            </div>
            <div style={{ color: "#111827", fontFamily: "monospace", fontSize: 12 }}>{user.id}</div>
          </div>
        </div>

        <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: 20 }}>
          <button style={btnDangerStyle} onClick={logout}>
            Log Out
          </button>
        </div>
      </div>
    </div>
  );
}
