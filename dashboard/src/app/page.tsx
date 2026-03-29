"use client";

import { useEffect, useState } from "react";
import { useAgents } from "@/hooks/use-agents";
import { getMetrics, type AggregateMetrics } from "@/lib/api";
import { formatTokens, formatCost, formatDuration, timeAgo } from "@/lib/utils";
import { Card, StatCard } from "@/components/card";
import { AgentStatusBadge } from "@/components/agent-status-badge";

export default function OverviewPage() {
  const { agents, loading } = useAgents();
  const [metrics, setMetrics] = useState<AggregateMetrics | null>(null);

  useEffect(() => {
    getMetrics().then(setMetrics).catch(console.error);
  }, []);

  const running = agents.filter((a) => a.state.status === "running");
  const errors = agents.filter((a) => a.state.status === "error");

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Overview</h2>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Active Agents"
          value={running.length}
          sub={`of ${agents.length} total`}
        />
        <StatCard
          label="Total Runs"
          value={metrics?.total_runs ?? "—"}
          sub={`${((metrics?.success_rate ?? 0) * 100).toFixed(0)}% success`}
        />
        <StatCard
          label="Tokens Used"
          value={metrics ? formatTokens(metrics.total_tokens) : "—"}
          sub={metrics ? `avg ${formatTokens(metrics.avg_tokens_per_run)}/run` : ""}
        />
        <StatCard
          label="Estimated Cost"
          value={metrics ? formatCost(metrics.estimated_cost_usd) : "—"}
          sub={metrics ? formatDuration(metrics.avg_duration_ms) + " avg" : ""}
        />
      </div>

      {/* Agent Grid */}
      <div>
        <h3 className="text-sm font-medium text-[var(--muted)] mb-3">
          Agent Status
        </h3>
        {loading ? (
          <p className="text-[var(--muted)]">Loading...</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {agents.map((agent) => (
              <Card key={agent.role} className="flex items-start gap-3">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center text-lg shrink-0"
                  style={{ backgroundColor: agent.color + "20" }}
                >
                  {agent.emoji}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">
                      {agent.name}
                    </span>
                    <AgentStatusBadge status={agent.state.status} />
                  </div>
                  {agent.state.status === "running" && (
                    <div className="text-xs text-[var(--muted)] mt-1">
                      {agent.state.issue_id} — Turn {agent.state.current_turn ?? 0}
                      {agent.state.last_tool && ` (${agent.state.last_tool})`}
                    </div>
                  )}
                  {agent.state.status === "idle" && agent.state.last_issue_id && (
                    <div className="text-xs text-[var(--muted)] mt-1">
                      Last: {agent.state.last_issue_id}
                      {agent.state.completed_at && ` — ${timeAgo(agent.state.completed_at)}`}
                    </div>
                  )}
                  {agent.state.status === "error" && (
                    <div className="text-xs text-[var(--error)] mt-1">
                      Failed: {agent.state.last_issue_id}
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Alerts */}
      {errors.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-[var(--error)] mb-3">
            Agents with Errors
          </h3>
          {errors.map((a) => (
            <Card key={a.role} className="border-[var(--error)]/30 mb-2">
              <div className="flex items-center gap-2">
                <span>{a.emoji}</span>
                <span className="font-medium text-sm">{a.name}</span>
                <span className="text-xs text-[var(--muted)]">
                  {a.state.last_summary}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
