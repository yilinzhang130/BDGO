/**
 * Team API client  (P3-14)
 *
 * Covers:
 *   - Member directory
 *   - User notifications (listing, mark read)
 *   - Report teammate notify
 */

import { getToken } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function authHeaders(): HeadersInit {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  avatar_url?: string | null;
  title?: string | null;
}

export interface Notification {
  id: number;
  type: string; // 'watchlist_share' | 'report_share' | 'mention'
  title: string;
  body?: string | null;
  link_url?: string | null;
  sender_name?: string | null;
  sender_avatar?: string | null;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationsResponse {
  total: number;
  unread: number;
  items: Notification[];
}

// ── Members ──────────────────────────────────────────────────────────────────

export async function fetchTeamMembers(): Promise<TeamMember[]> {
  const res = await fetch(`${API}/api/team/members`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch members: ${res.status}`);
  return res.json();
}

// ── Notifications ─────────────────────────────────────────────────────────────

export async function fetchNotifications(
  opts: { unreadOnly?: boolean; limit?: number } = {},
): Promise<NotificationsResponse> {
  const params = new URLSearchParams();
  if (opts.unreadOnly) params.set("unread_only", "true");
  if (opts.limit) params.set("limit", String(opts.limit));
  const qs = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API}/api/team/notifications${qs}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch notifications: ${res.status}`);
  return res.json();
}

export async function fetchNotificationUnreadCount(): Promise<number> {
  const res = await fetch(`${API}/api/team/notifications/unread-count`, {
    headers: authHeaders(),
  });
  if (!res.ok) return 0;
  const data = await res.json();
  return data.count ?? 0;
}

export async function markNotificationRead(id: number): Promise<void> {
  await fetch(`${API}/api/team/notifications/${id}/read`, {
    method: "PATCH",
    headers: authHeaders(),
  });
}

export async function markAllNotificationsRead(): Promise<void> {
  await fetch(`${API}/api/team/notifications/read-all`, {
    method: "PATCH",
    headers: authHeaders(),
  });
}

// ── Watchlist sharing ─────────────────────────────────────────────────────────

export async function shareWatchlistItem(
  itemId: number,
  userId: string,
  permission: "view" | "edit" = "view",
  note?: string,
): Promise<{ share_id: number }> {
  const res = await fetch(`${API}/api/watchlist/${itemId}/share`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ user_id: userId, permission, note }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail ?? `Error ${res.status}`);
  }
  return res.json();
}

export async function fetchSharedWithMe() {
  const res = await fetch(`${API}/api/watchlist/shared`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch shared watchlist: ${res.status}`);
  return res.json();
}

// ── Report notify ─────────────────────────────────────────────────────────────

export async function notifyTeammateAboutReport(
  taskId: string,
  recipientId: string,
  note?: string,
): Promise<{ token: string; url: string }> {
  const res = await fetch(`${API}/api/reports/notify`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ task_id: taskId, recipient_id: recipientId, note }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail ?? `Error ${res.status}`);
  }
  return res.json();
}
