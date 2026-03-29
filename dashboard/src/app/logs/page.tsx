"use client";

import { useEffect, useState } from "react";
import { getLogs, getLearningLog, type LogEntry, type LearningLog } from "@/lib/api";
import { Card, CardHeader } from "@/components/card";
import { timeAgo } from "@/lib/utils";

const LEVELS = ["", "INFO", "WARNING", "ERROR"];

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [learning, setLearning] = useState<LearningLog | null>(null);
  const [filter, setFilter] = useState({ level: "", agent_role: "" });
  const [tab, setTab] = useState<"logs" | "learning">("logs");

  useEffect(() => {
    if (tab === "logs") {
      getLogs({
        level: filter.level || undefined,
        agent_role: filter.agent_role || undefined,
        limit: 100,
      })
        .then(setLogs)
        .catch(console.error);
    } else {
      getLearningLog().then(setLearning).catch(console.error);
    }
  }, [tab, filter]);

  const levelColor: Record<string, string> = {
    INFO: "text-blue-400",
    WARNING: "text-yellow-400",
    ERROR: "text-red-400",
    DEBUG: "text-gray-400",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold">Logs</h2>
        <div className="flex gap-1 ml-auto">
          <button
            onClick={() => setTab("logs")}
            className={`px-3 py-1 text-sm rounded ${
              tab === "logs" ? "bg-[var(--accent)] text-white" : "text-[var(--muted)]"
            }`}
          >
            Agent Logs
          </button>
          <button
            onClick={() => setTab("learning")}
            className={`px-3 py-1 text-sm rounded ${
              tab === "learning" ? "bg-[var(--accent)] text-white" : "text-[var(--muted)]"
            }`}
          >
            Learning Log
          </button>
        </div>
      </div>

      {tab === "logs" ? (
        <>
          {/* Filters */}
          <div className="flex gap-3">
            <select
              value={filter.level}
              onChange={(e) => setFilter((f) => ({ ...f, level: e.target.value }))}
              className="bg-[var(--card)] border border-[var(--card-border)] rounded px-2 py-1 text-sm"
            >
              {LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l || "All Levels"}
                </option>
              ))}
            </select>
            <input
              placeholder="Filter by agent role..."
              value={filter.agent_role}
              onChange={(e) =>
                setFilter((f) => ({ ...f, agent_role: e.target.value }))
              }
              className="bg-[var(--card)] border border-[var(--card-border)] rounded px-2 py-1 text-sm flex-1 max-w-xs"
            />
          </div>

          {/* Log Entries */}
          <Card>
            {logs.length === 0 ? (
              <p className="text-sm text-[var(--muted)] py-4">
                No logs found. Logs are stored when agents execute with PostgreSQL configured.
              </p>
            ) : (
              <div className="space-y-1 font-mono text-xs">
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className="flex gap-2 py-1 border-b border-white/5 last:border-0"
                  >
                    <span className="text-[var(--muted)] w-32 shrink-0">
                      {log.created_at ? timeAgo(log.created_at) : ""}
                    </span>
                    <span
                      className={`w-16 shrink-0 ${levelColor[log.level] || ""}`}
                    >
                      {log.level}
                    </span>
                    <span className="text-[var(--muted)] w-28 shrink-0 truncate">
                      {log.agent_role}
                    </span>
                    <span className="truncate">{log.message}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      ) : (
        <Card>
          <CardHeader
            title={`Learning Log (${learning?.line_count ?? 0} entries)`}
          />
          {learning && learning.recent.length > 0 ? (
            <pre className="text-xs font-mono whitespace-pre-wrap text-[var(--muted)] max-h-[600px] overflow-auto">
              {learning.recent.join("\n")}
            </pre>
          ) : (
            <p className="text-sm text-[var(--muted)]">No learning entries yet</p>
          )}
        </Card>
      )}
    </div>
  );
}
