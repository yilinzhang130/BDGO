"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FunnelData {
  draft_count: number;
  sent_count: number;
  replied_count: number;
  signed_count: number;
  dropped_count: number;
  draft_to_sent_rate: number;
  sent_to_replied_rate: number;
  replied_to_signed_rate: number;
  window_days: number;
}

interface SlashRow {
  slug: string;
  count: number;
}

interface SlashData {
  data: SlashRow[];
  window_days: number;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FunnelPage() {
  const { user } = useAuth();
  const router = useRouter();

  const [days, setDays] = useState(30);
  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  const [slashUsage, setSlashUsage] = useState<SlashData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = user?.is_admin === true;

  useEffect(() => {
    if (user && !isAdmin) router.replace("/chat");
  }, [user, isAdmin, router]);

  const load = useCallback(async (d: number) => {
    setLoading(true);
    setError(null);
    try {
      const [f, s] = await Promise.all([
        fetch(`/api/analytics/outreach-funnel?days=${d}`, {
          headers: authHeader(),
        }).then(throwIfNotOk),
        fetch(`/api/analytics/slash-usage?days=${d}`, {
          headers: authHeader(),
        }).then(throwIfNotOk),
      ]);
      setFunnel(await f.json());
      setSlashUsage(await s.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    void load(days);
  }, [isAdmin, days, load]);

  if (!user) return null;
  if (!isAdmin) return null;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Outreach Funnel</h1>
            <p className="text-sm text-gray-500 mt-1">
              Baseline metrics — P1-9 / workspace refactor pre-measurement
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">Window</label>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="text-sm border border-gray-300 rounded px-2 py-1"
            >
              <option value={7}>7 days</option>
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-gray-400 text-sm">Loading…</div>
        ) : (
          <>
            {/* Funnel cards */}
            {funnel && (
              <div>
                <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
                  Outreach Funnel — last {funnel.window_days} days
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                  <FunnelCard label="Draft" count={funnel.draft_count} />
                  <FunnelCard label="Sent" count={funnel.sent_count} />
                  <FunnelCard label="Replied" count={funnel.replied_count} />
                  <FunnelCard label="Signed" count={funnel.signed_count} accent />
                  <FunnelCard label="Dropped" count={funnel.dropped_count} muted />
                </div>

                <div className="mt-4 grid grid-cols-3 gap-4">
                  <RateCard label="Draft → Sent" rate={funnel.draft_to_sent_rate} />
                  <RateCard label="Sent → Replied" rate={funnel.sent_to_replied_rate} />
                  <RateCard label="Replied → Signed" rate={funnel.replied_to_signed_rate} />
                </div>
              </div>
            )}

            {/* Slash usage table */}
            {slashUsage && (
              <div>
                <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
                  Slash Command Usage — last {slashUsage.window_days} days
                </h2>
                {slashUsage.data.length === 0 ? (
                  <p className="text-sm text-gray-400">No report history in this window.</p>
                ) : (
                  <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                          <th className="text-left px-4 py-2 text-gray-500 font-medium">
                            Slug / Alias
                          </th>
                          <th className="text-right px-4 py-2 text-gray-500 font-medium">Calls</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {slashUsage.data.map((row) => (
                          <tr key={row.slug} className="hover:bg-gray-50">
                            <td className="px-4 py-2 font-mono text-gray-700">/{row.slug}</td>
                            <td className="px-4 py-2 text-right text-gray-900 font-medium">
                              {row.count.toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FunnelCard({
  label,
  count,
  accent = false,
  muted = false,
}: {
  label: string;
  count: number;
  accent?: boolean;
  muted?: boolean;
}) {
  const bg = accent
    ? "bg-green-50 border-green-200"
    : muted
      ? "bg-gray-50 border-gray-200"
      : "bg-white border-gray-200";
  const text = accent ? "text-green-700" : muted ? "text-gray-400" : "text-gray-900";

  return (
    <div className={`border rounded-lg p-4 ${bg}`}>
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${text}`}>{count.toLocaleString()}</p>
    </div>
  );
}

function RateCard({ label, rate }: { label: string; rate: number }) {
  const pct = (rate * 100).toFixed(1);
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{pct}%</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fetch helpers (local — avoids importing the full api.ts client)
// ---------------------------------------------------------------------------

function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("auth_token") ?? sessionStorage.getItem("auth_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function throwIfNotOk(res: Response): Promise<Response> {
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res;
}
