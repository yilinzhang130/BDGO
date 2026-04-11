"use client";

import { useEffect, useMemo, useState } from "react";
import {
  fetchOverview,
  fetchCompaniesByCountry,
  fetchCompaniesByType,
  fetchPipelineByPhase,
  fetchIndicationsTop,
  fetchDealsTimeline,
} from "@/lib/api";
import { formatNumber, COLORS } from "@/lib/utils";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  AreaChart, Area, Treemap,
} from "recharts";

export default function DashboardPage() {
  const [overview, setOverview] = useState<any>(null);
  const [byCountry, setByCountry] = useState<any[]>([]);
  const [byType, setByType] = useState<any[]>([]);
  const [byPhase, setByPhase] = useState<any[]>([]);
  const [indications, setIndications] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);

  useEffect(() => {
    fetchOverview().then(setOverview);
    fetchCompaniesByCountry().then(setByCountry);
    fetchCompaniesByType().then(setByType);
    fetchPipelineByPhase().then(setByPhase);
    fetchIndicationsTop().then(setIndications);
    fetchDealsTimeline().then(setTimeline);
  }, []);

  const indicationColorMap = useMemo(
    () => Object.fromEntries(indications.map((d, i) => [d.indication, COLORS[i % COLORS.length]])),
    [indications],
  );

  if (!overview) return <div className="loading">Loading dashboard...</div>;

  const kpis = [
    { label: "Companies", value: overview.companies },
    { label: "Assets", value: overview.assets },
    { label: "Clinical Records", value: overview.clinical_records },
    { label: "Deals", value: overview.deals },
    { label: "Active Trials", value: overview.active_trials },
    { label: "Tracked Companies", value: overview.tracked_companies },
  ];

  const phaseOrder = ["Pre-clinical", "Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3", "Phase 4", "Approved"];
  const sortedPhases = byPhase
    .filter((p) => phaseOrder.includes(p.phase))
    .toSorted((a, b) => phaseOrder.indexOf(a.phase) - phaseOrder.indexOf(b.phase));

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
      </div>

      <div className="kpi-grid">
        {kpis.map((k) => (
          <div key={k.label} className="kpi-card">
            <div className="label">{k.label}</div>
            <div className="value">{formatNumber(k.value)}</div>
          </div>
        ))}
      </div>

      <div className="charts-grid">
        {/* Company Distribution by Country */}
        <div className="chart-card">
          <h3>Companies by Country</h3>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={byCountry.slice(0, 10)}
                dataKey="count"
                nameKey="country"
                cx="50%"
                cy="50%"
                outerRadius={110}
                label={({ name, percent }: { name: string; percent: number }) =>
                  `${name} ${(percent * 100).toFixed(0)}%`
                }
                labelLine={false}
              >
                {byCountry.slice(0, 10).map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Pipeline by Clinical Phase */}
        <div className="chart-card">
          <h3>Pipeline by Clinical Phase</h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={sortedPhases} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="phase" type="category" width={100} fontSize={12} />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Top Indications */}
        <div className="chart-card">
          <h3>Top Disease Areas</h3>
          <ResponsiveContainer width="100%" height={320}>
            <Treemap
              data={indications.slice(0, 20).map((d, i) => ({
                name: d.indication,
                size: d.count,
                fill: COLORS[i % COLORS.length],
              }))}
              dataKey="size"
              nameKey="name"
              stroke="#fff"
              content={({ x, y, width, height, name, size }: any) => {
                if (width < 50 || height < 30) return null;
                return (
                  <g>
                    <rect x={x} y={y} width={width} height={height} fill={indicationColorMap[name] || "#64748b"} stroke="#fff" />
                    <text x={x + width / 2} y={y + height / 2 - 6} textAnchor="middle" fill="#fff" fontSize={11} fontWeight={600}>
                      {String(name).length > 12 ? String(name).slice(0, 12) + ".." : name}
                    </text>
                    <text x={x + width / 2} y={y + height / 2 + 10} textAnchor="middle" fill="#ffffffcc" fontSize={10}>
                      {size}
                    </text>
                  </g>
                );
              }}
            />
          </ResponsiveContainer>
        </div>

        {/* Deal Timeline */}
        <div className="chart-card">
          <h3>Deal Timeline</h3>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={timeline}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" fontSize={11} />
              <YAxis yAxisId="count" orientation="left" />
              <YAxis yAxisId="value" orientation="right" />
              <Tooltip />
              <Area yAxisId="count" type="monotone" dataKey="count" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} name="# Deals" />
              <Area yAxisId="value" type="monotone" dataKey="total_value" stroke="#10b981" fill="#10b981" fillOpacity={0.1} name="Total Value ($M)" />
              <Legend />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Company Types */}
        <div className="chart-card">
          <h3>Companies by Type</h3>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={byType}
                dataKey="count"
                nameKey="type"
                cx="50%"
                cy="50%"
                outerRadius={110}
                label={({ type, percent }) =>
                  percent > 0.03 ? `${type} ${(percent * 100).toFixed(0)}%` : ""
                }
                labelLine={false}
              >
                {byType.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
