"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useSessionStore } from "@/lib/sessions";
import { useAuth } from "@/components/AuthProvider";
import { parsePreferences } from "@/lib/auth";
import { SessionList } from "./SessionList";
import { SearchModal } from "./SearchModal";
import { CreditBadge } from "./CreditBadge";
import { FeedbackButton } from "./ReportButton";
import { getToken } from "@/lib/auth";
import { fetchInboxUnreadCount } from "@/lib/api";

// ---------------------------------------------------------------------------
// SVG Icons
// ---------------------------------------------------------------------------

const Icon = {
  grid: (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor">
      <rect x="1" y="1" width="6.2" height="6.2" rx="1.5" />
      <rect x="8.8" y="1" width="6.2" height="6.2" rx="1.5" />
      <rect x="1" y="8.8" width="6.2" height="6.2" rx="1.5" />
      <rect x="8.8" y="8.8" width="6.2" height="6.2" rx="1.5" />
    </svg>
  ),
  star: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinejoin="round"
    >
      <path d="M8 1.5l1.76 3.57 3.94.57-2.85 2.78.67 3.9L8 10.36l-3.52 1.96.67-3.9L2.3 5.64l3.94-.57L8 1.5z" />
    </svg>
  ),
  zap: (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor">
      <path d="M9.5 1.5 3 9h5l-1.5 5.5L14.5 7H9L9.5 1.5z" />
    </svg>
  ),
  fileText: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <path d="M4 1.5h5.5L12.5 4.5v10H4V1.5z" />
      <path d="M9.5 1.5V4.5h3" />
      <path d="M6 7h4M6 9.5h4M6 12h2" />
    </svg>
  ),
  building: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <rect x="2" y="5" width="12" height="9.5" rx="1" />
      <path d="M5.5 14.5v-4.5h5v4.5" />
      <path d="M2 5 8 2l6 3" />
    </svg>
  ),
  flask: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5.5 1.5v5L2 13.5h12L10.5 6.5v-5" />
      <path d="M4.5 1.5h7" />
      <path d="M3 10.5h10" />
    </svg>
  ),
  shield: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <path d="M8 1.5 2 4v4c0 3.5 2.67 6.7 6 7.5 3.33-.8 6-4 6-7.5V4L8 1.5z" />
    </svg>
  ),
  users: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <circle cx="5.5" cy="5" r="2.5" />
      <path d="M1 13.5c0-2.5 2-4.5 4.5-4.5" />
      <circle cx="11" cy="6.5" r="2" />
      <path d="M14.5 13.5c0-2-1.35-3.5-3.5-3.5" />
    </svg>
  ),
  handshake: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M1 5.5l4.5 1.5L8 5l2.5 2L15 5.5" />
      <path d="M1 5.5c0 3.5 3 6 7 6s7-2.5 7-6" />
      <path d="M8 5V2" />
    </svg>
  ),
  newspaper: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <rect x="1.5" y="2" width="13" height="12" rx="1.5" />
      <path d="M5 6.5h6M5 9h6M5 11.5h3" />
    </svg>
  ),
  clock: (
    <svg
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 5v3.5l2.5 1.5" />
    </svg>
  ),
  logout: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h3" />
      <path d="M10.5 11l3.5-3-3.5-3" />
      <path d="M14 8H6" />
    </svg>
  ),
  plus: (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
    >
      <path d="M8 3v10M3 8h10" />
    </svg>
  ),
  presentation: (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="1.5" y="2" width="13" height="9" rx="1.5" />
      <path d="M8 11v3M5.5 14h5" />
      <path d="M4.5 5.5h7M4.5 8h5" />
    </svg>
  ),
  chevronRight: (
    <svg
      width="13"
      height="13"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <path d="M6 4l4 4-4 4" />
    </svg>
  ),
};

// ---------------------------------------------------------------------------
// Logo — inline SVG mark + wordmark (no image file dependency)
// ---------------------------------------------------------------------------

function BDGoLogo() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
      <svg
        width="34"
        height="34"
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ flexShrink: 0 }}
      >
        <rect width="36" height="36" rx="9" fill="#1E3A8A" />
        <circle cx="11" cy="18" r="3.5" fill="white" />
        <line
          x1="15"
          y1="18"
          x2="22.5"
          y2="18"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path d="M22 13 L29 18 L22 23 Z" fill="white" />
      </svg>
      <div>
        <div
          style={{
            fontSize: 15,
            fontWeight: 800,
            color: "#0F172A",
            lineHeight: 1.15,
            letterSpacing: "-0.01em",
          }}
        >
          BD<span style={{ fontWeight: 500 }}> Go</span>
        </div>
        <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 500, lineHeight: 1.2 }}>
          生物医药BD情报
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Nav items
// ---------------------------------------------------------------------------

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const DATABASE: NavItem[] = [
  { href: "/companies", label: "公司", icon: Icon.building },
  { href: "/assets", label: "资产", icon: Icon.flask },
  { href: "/clinical", label: "临床", icon: Icon.fileText },
  { href: "/ip", label: "专利", icon: Icon.shield },
  { href: "/buyers", label: "买方", icon: Icon.users },
];

const NEWS: NavItem[] = [{ href: "/deals", label: "交易", icon: Icon.handshake }];

const TOOLS: NavItem[] = [
  { href: "/dashboard", label: "仪表盘", icon: Icon.grid },
  { href: "/watchlist", label: "关注", icon: Icon.star },
  { href: "/catalysts", label: "催化剂", icon: Icon.zap },
  { href: "/reports", label: "报告", icon: Icon.fileText },
  { href: "/conference", label: "会议洞察", icon: Icon.presentation },
];

function AdminNavItem() {
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    const refresh = () =>
      fetchInboxUnreadCount()
        .then((r) => setUnread((prev) => (prev === r.count ? prev : r.count)))
        .catch(() => {});
    refresh();
    const id = setInterval(refresh, 60_000);
    return () => clearInterval(id);
  }, []);

  const active = pathname === "/admin" || pathname.startsWith("/admin/");
  return (
    <div className="nav-section">
      <div className="nav-section-label">管理员</div>
      <Link href="/admin" className={`nav-link ${active ? "active" : ""}`}>
        <span className="nav-icon">{Icon.shield}</span>
        <span>管理</span>
        {unread > 0 && (
          <span
            style={{
              marginLeft: "auto",
              fontSize: 10,
              fontWeight: 700,
              background: "#ef4444",
              color: "#fff",
              borderRadius: 10,
              padding: "1px 6px",
              lineHeight: 1.4,
            }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AIDD 立项中心 SSO button
// ---------------------------------------------------------------------------

function AiddButton() {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      const token = getToken();
      const res = await fetch(
        `/api/aidd-sso-url?redirect=${encodeURIComponent("/project-assessment")}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      if (!res.ok) throw new Error("failed");
      const { url } = await res.json();
      window.open(url, "_blank", "noopener");
    } catch {
      alert("生成跳转链接失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        width: "100%",
        padding: "8px 12px",
        margin: "4px 0",
        background: loading ? "#f3f4f6" : "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        color: loading ? "#9ca3af" : "#fff",
        border: "none",
        borderRadius: 8,
        fontSize: 13,
        fontWeight: 600,
        cursor: loading ? "not-allowed" : "pointer",
        textAlign: "left",
        transition: "opacity 0.15s",
      }}
    >
      <span style={{ fontSize: 15 }}>🧬</span>
      <span>{loading ? "跳转中…" : "立项中心 (AIDD)"}</span>
      {!loading && <span style={{ marginLeft: "auto", fontSize: 10, opacity: 0.8 }}>↗</span>}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Nav Group (collapsible section)
// ---------------------------------------------------------------------------

function NavGroup({
  label,
  items,
  defaultOpen = true,
}: {
  label: string;
  items: NavItem[];
  defaultOpen?: boolean;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="nav-section">
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "0.5rem 0.75rem 0.25rem",
          color: "var(--text-muted)",
        }}
      >
        <span
          style={{
            fontSize: "0.6rem",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          {label}
        </span>
        <span
          style={{
            color: "var(--text-muted)",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 0.15s",
            display: "flex",
          }}
        >
          {Icon.chevronRight}
        </span>
      </button>

      {open &&
        items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link key={item.href} href={item.href} className={`nav-link ${active ? "active" : ""}`}>
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

function SidebarFooter() {
  const { user, logout } = useAuth();
  const initial =
    user?.name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || "U";
  const displayName = user?.name || user?.email || "用户";
  const role = user?.title || "BD 专业人士";

  return (
    <div
      className="sidebar-footer"
      style={{ flexDirection: "column", gap: 6, alignItems: "stretch" }}
    >
      <FeedbackButton />
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Link
          href="/profile"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            textDecoration: "none",
            flex: 1,
            minWidth: 0,
          }}
        >
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={displayName}
              className="avatar"
              style={{ width: 32, height: 32, borderRadius: "50%", objectFit: "cover" }}
            />
          ) : (
            <div className="avatar">{initial}</div>
          )}
          <div className="user-info">
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div className="user-name">{displayName}</div>
              {user?.is_admin && (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    color: "#fff",
                    background: "#DC2626",
                    padding: "1px 5px",
                    borderRadius: 4,
                    letterSpacing: "0.03em",
                    flexShrink: 0,
                  }}
                >
                  ADMIN
                </span>
              )}
            </div>
            <div className="user-role" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {role}
              <CreditBadge compact />
            </div>
          </div>
        </Link>
        <button
          className="icon-btn"
          aria-label="退出"
          title="退出登录"
          onClick={logout}
          style={{ color: "var(--text-muted)", padding: "0.3rem", borderRadius: 6 }}
        >
          {Icon.logout}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { user } = useAuth();
  const { createSession } = useSessionStore();
  const prefs = parsePreferences(user);
  const showDatabase = prefs.show_database_nav === true;
  const showReports = prefs.show_report_cards === true;
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleNewChat = () => {
    createSession();
    if (pathname !== "/chat") router.push("/chat");
  };

  return (
    <>
      <aside className="sidebar">
        {/* Brand */}
        <div className="sidebar-brand">
          <BDGoLogo />
        </div>

        {/* Search */}
        <button
          className="search-trigger-btn"
          onClick={() => setSearchOpen(true)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            width: "calc(100% - 1rem)",
            margin: "0 0.5rem 0.5rem",
            padding: "0.45rem 0.75rem",
            background: "#f1f5f9",
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            cursor: "pointer",
            fontSize: "0.82rem",
            color: "#64748b",
            fontFamily: "inherit",
            textAlign: "left",
          }}
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <circle cx="6.5" cy="6.5" r="4.5" />
            <path d="M10.5 10.5l3 3" />
          </svg>
          <span style={{ flex: 1 }}>搜索…</span>
          <kbd
            style={{
              fontSize: 10,
              border: "1px solid #cbd5e1",
              borderRadius: 3,
              padding: "0 4px",
              background: "#fff",
            }}
          >
            ⌘K
          </kbd>
        </button>

        {/* New Chat */}
        <button className="new-chat-btn" onClick={handleNewChat}>
          {Icon.plus}
          <span>新建对话</span>
        </button>

        {/* Nav */}
        <div className="sidebar-scroll">
          {/* Recent sessions */}
          <div className="nav-section">
            <div className="nav-section-label">最近</div>
            <SessionList />
          </div>

          {/* Database (conditional) */}
          {showDatabase && <NavGroup label="数据库" items={DATABASE} />}
          {showDatabase && <NavGroup label="资讯" items={NEWS} />}

          {/* Tools — 仪表盘仅内部/管理员可见；报告受偏好设置控制 */}
          <NavGroup
            label="工具"
            items={TOOLS.filter((item) => {
              if (item.href === "/dashboard") return user?.is_admin || user?.is_internal;
              if (item.href === "/reports") return showReports;
              return true;
            })}
          />

          {/* AIDD 立项中心 */}
          <div className="nav-section">
            <AiddButton />
          </div>

          {/* Admin (admin only) */}
          {user?.is_admin && <AdminNavItem />}
        </div>

        <SidebarFooter />
      </aside>
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
    </>
  );
}
