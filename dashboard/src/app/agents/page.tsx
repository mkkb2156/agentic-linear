"use client";

import { useEffect, useState } from "react";
import { useAgents } from "@/hooks/use-agents";
import { getAgent, getRuns, type Agent, type RunRecord } from "@/lib/api";
import { formatTokens, formatDuration, timeAgo } from "@/lib/utils";
import { Card, CardHeader } from "@/components/card";
import { AgentStatusBadge } from "@/components/agent-status-badge";

export default function AgentsPage() {
  const { agents, loading } = useAgents();
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Agent | null>(null);
  const [runs, setRuns] = useState<RunRecord[]>([]);

  useEffect(() => {
    if (!selected) return;
    getAgent(selected).then(setDetail).catch(console.error);
    getRuns({ agent_role: selected, limit: 20 }).then(setRuns).catch(console.error);
  }, [selected]);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Agents</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent List */}
        <div className="space-y-2">
          {loading ? (
            <p className="text-[var(--muted)]">Loading...</p>
          ) : (
            agents.map((agent) => (
              <button
                key={agent.role}
                onClick={() => setSelected(agent.role)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selected === agent.role
                    ? "border-[var(--accent)] bg-[var(--accent)]/10"
                    : "border-[var(--card-border)] bg-[var(--card)] hover:border-[var(--muted)]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span>{agent.emoji}</span>
                  <span className="font-medium text-sm">{agent.name}</span>
                  <span className="ml-auto">
                    <AgentStatusBadge status={agent.state.status} />
                  </span>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Agent Detail */}
        <div className="lg:col-span-2 space-y-4">
          {detail ? (
            <>
              <Card>
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="w-12 h-12 rounded-full flex items-center justify-center text-2xl"
                    style={{ backgroundColor: detail.color + "20" }}
                  >
                    {detail.emoji}
                  </div>
                  <div>
                    <h3 className="font-bold">{detail.name}</h3>
                    <p className="text-xs text-[var(--muted)]">{detail.role}</p>
                  </div>
                  <div className="ml-auto">
                    <AgentStatusBadge status={detail.state.status} />
                  </div>
                </div>

                {detail.config && (
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-[var(--muted)]">Model</p>
                      <p>{String(detail.config.model ?? "sonnet")}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--muted)]">Max Turns</p>
                      <p>{String(detail.config.max_turns ?? 15)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--muted)]">Enabled</p>
                      <p>{detail.config.enabled ? "Yes" : "No"}</p>
                    </div>
                  </div>
                )}
              </Card>

              {/* Recent Runs */}
              <Card>
                <CardHeader title="Recent Runs" />
                {runs.length === 0 ? (
                  <p className="text-sm text-[var(--muted)]">No runs yet</p>
                ) : (
                  <div className="space-y-2">
                    {runs.map((run, i) => (
                      <div
                        key={run.id ?? i}
                        className="flex items-center gap-3 p-2 rounded bg-white/5 text-sm"
                      >
                        <span
                          className={`w-2 h-2 rounded-full ${
                            run.success ? "bg-green-500" : "bg-red-500"
                          }`}
                        />
                        <span className="font-mono text-xs">{run.issue_id}</span>
                        <span className="text-[var(--muted)]">
                          {formatTokens(run.tokens_used)} tokens
                        </span>
                        <span className="text-[var(--muted)]">
                          {formatDuration(run.duration_ms)}
                        </span>
                        <span className="ml-auto text-xs text-[var(--muted)]">
                          {run.created_at
                            ? timeAgo(run.created_at)
                            : run.timestamp
                              ? timeAgo(run.timestamp)
                              : ""}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </>
          ) : (
            <Card>
              <p className="text-[var(--muted)] text-center py-8">
                Select an agent to view details
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
