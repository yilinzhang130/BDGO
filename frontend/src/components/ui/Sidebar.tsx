"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useSessionStore } from "@/lib/sessions";
import { useAuth } from "@/components/AuthProvider";
import { SessionList } from "./SessionList";

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

const DATABASE: NavItem[] = [
  { href: "/companies", label: "Companies", icon: "\u25A0" },
  { href: "/assets", label: "Assets", icon: "\u25C6" },
  { href: "/clinical", label: "Clinical", icon: "\u25CB" },
  { href: "/ip", label: "Patents", icon: "\u25C8" },
  { href: "/buyers", label: "Buyers", icon: "\u25A3" },
];

const NEWS: NavItem[] = [
  { href: "/deals", label: "Deals", icon: "\u25B6" },
];

const TOOLS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: "\u25A6" },
  { href: "/upload", label: "Upload", icon: "\u25B3" },
  { href: "/reports", label: "Reports", icon: "\u25A4" },
];

function NavGroup({ label, items }: { label: string; items: NavItem[] }) {
  const pathname = usePathname();
  return (
    <div className="nav-section">
      <div className="nav-section-label">{label}</div>
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-link ${active ? "active" : ""}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        );
      })}
    </div>
  );
}

function SidebarFooter() {
  const { user, logout } = useAuth();
  const initial = user?.name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || "U";
  const displayName = user?.name || user?.email || "User";

  return (
    <div className="sidebar-footer">
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
      <div className="user-name">{displayName}</div>
      <button
        className="icon-btn"
        aria-label="Logout"
        title="Logout"
        onClick={logout}
      >
        {"\u2192"}
      </button>
    </div>
  );
}

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { createSession } = useSessionStore();
  // Start with fallback; only show real logo after we've verified it loads
  const [logoReady, setLogoReady] = useState(false);

  useEffect(() => {
    const probe = new Image();
    probe.onload = () => { if (probe.naturalWidth > 0) setLogoReady(true); };
    probe.onerror = () => setLogoReady(false);
    probe.src = "/logo.png";
  }, []);

  const handleNewChat = () => {
    createSession();
    if (pathname !== "/chat") router.push("/chat");
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        {logoReady ? (
          <img src="/logo.png" alt="BD Go" className="sidebar-logo" />
        ) : (
          <div className="sidebar-logo-fallback">BD</div>
        )}
        <div>
          <div className="brand-title">BD Go</div>
          <div className="brand-sub">Biotech BD AI platform</div>
        </div>
      </div>

      <button className="new-chat-btn" onClick={handleNewChat}>
        <span>+</span>
        <span>New Chat</span>
      </button>

      <div className="sidebar-scroll">
        <div className="nav-section">
          <div className="nav-section-label">Recent</div>
          <SessionList />
        </div>
        <NavGroup label="Database" items={DATABASE} />
        <NavGroup label="News" items={NEWS} />
        <NavGroup label="Tools" items={TOOLS} />
      </div>

      <SidebarFooter />
    </aside>
  );
}
