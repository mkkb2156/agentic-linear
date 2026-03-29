"use client";

import { useEffect, useState } from "react";
import {
  getMetrics,
  getTokenUsage,
  getCosts,
  type AggregateMetrics,
  type TokenUsage,
  type CostBreakdown,
} from "@/lib/api";
import { formatTokens, formatCost, formatDuration } from "@/lib/utils";
import { Card, CardHeader, StatCard } from "@/components/card";

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<AggregateMetrics | null>(null);
  const [tokenData, setTokenData] = useState<TokenUsage[]>([]);
  const [costs, setCosts] = useState<CostBreakdown | null>(null);
  const [period, setPeriod] = useState("day");

  useEffect(() => {
    getMetrics().then(setMetrics).catch(console.error);
    getCosts().then(setCosts).catch(console.error);
  }, []);

  useEffect(() => {
    getTokenUsage({ period, limit: 30 }).then(setTokenData).catch(console.error);
  }, [period]);

  // Aggregate token data by period for chart
  const periodTotals = tokenData.reduce<
    Record<string, { tokens: number; runs: number; cost: number }>
  >((acc, row) => {
    const key = row.period.slice(0, 10);
    if (!acc[key]) acc[key] = { tokens: 0, runs: 0, cost: 0 };
    acc[key].tokens += row.tokens;
    acc[key].runs += row.runs;
    acc[key].cost += row.cost_usd;
    return acc;
  }, {});

  const chartData = Object.entries(periodTotals)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, data]) => ({ date, ...data }));

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Metrics & Usage</h2>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Runs"
          value={metrics?.total_runs ?? 0}
          sub={`${metrics?.failed_runs ?? 0} failed`}
        />
        <StatCard
          label="Success Rate"
          value={`${((metrics?.success_rate ?? 0) * 100).toFixed(1)}%`}
        />
        <StatCard
          label="Total Tokens"
          value={metrics ? formatTokens(metrics.total_tokens) : "—"}
        />
        <StatCard
          label="Total Cost"
          value={metrics ? formatCost(metrics.estimated_cost_usd) : "—"}
          sub={metrics ? `avg ${formatDuration(metrics.avg_duration_ms)}/run` : ""}
        />
      </div>

      {/* Token Usage Chart (simple bar chart) */}
      <Card>
        <CardHeader
          title="Token Usage Over Time"
          action={
            <div className="flex gap-1">
              {["hour", "day", "week"].map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-2 py-1 text-xs rounded ${
                    period === p
                      ? "bg-[var(--accent)] text-white"
                      : "text-[var(--muted)] hover:text-white"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          }
        />
        {chartData.length === 0 ? (
          <p className="text-sm text-[var(--muted)] py-4">No data yet</p>
        ) : (
          <div className="flex items-end gap-1 h-40">
            {chartData.map((d) => {
              const maxTokens = Math.max(...chartData.map((x) => x.tokens), 1);
              const height = (d.tokens / maxTokens) * 100;
              return (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full bg-[var(--accent)] rounded-t min-h-[2px] transition-all"
                    style={{ height: `${height}%` }}
                    title={`${d.date}: ${formatTokens(d.tokens)} tokens, ${d.runs} runs, ${formatCost(d.cost)}`}
                  />
                  <span className="text-[8px] text-[var(--muted)] rotate-[-45deg] origin-top-left">
                    {d.date.slice(5)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Cost Breakdown by Agent */}
      <Card>
        <CardHeader title="Cost Breakdown by Agent" />
        {costs && Object.keys(costs.by_agent).length > 0 ? (
          <div className="space-y-2">
            {Object.entries(costs.by_agent)
              .sort(([, a], [, b]) => b.cost_usd - a.cost_usd)
              .map(([role, data]) => {
                const pct =
                  costs.total_cost_usd > 0
                    ? (data.cost_usd / costs.total_cost_usd) * 100
                    : 0;
                return (
                  <div key={role} className="flex items-center gap-3 text-sm">
                    <span className="w-36 truncate font-mono text-xs">{role}</span>
                    <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden">
                      <div
                        className="h-full bg-[var(--accent)] rounded"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-16 text-right text-xs">
                      {formatCost(data.cost_usd)}
                    </span>
                    <span className="w-20 text-right text-xs text-[var(--muted)]">
                      {formatTokens(data.tokens)}
                    </span>
                    <span className="w-12 text-right text-xs text-[var(--muted)]">
                      {data.runs} runs
                    </span>
                  </div>
                );
              })}
            <div className="border-t border-[var(--card-border)] pt-2 mt-2 text-sm font-medium text-right">
              Total: {formatCost(costs.total_cost_usd)}
            </div>
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">No cost data yet</p>
        )}
      </Card>
    </div>
  );
}
