"use client";

import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<string, { label: string; color: string; pulse: boolean }> = {
  running: { label: "Running", color: "bg-green-500", pulse: true },
  idle: { label: "Idle", color: "bg-gray-500", pulse: false },
  error: { label: "Error", color: "bg-red-500", pulse: false },
  completed: { label: "Done", color: "bg-blue-500", pulse: false },
};

export function AgentStatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.idle;

  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className="relative flex h-2 w-2">
        {config.pulse && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping",
              config.color
            )}
          />
        )}
        <span
          className={cn("relative inline-flex rounded-full h-2 w-2", config.color)}
        />
      </span>
      {config.label}
    </span>
  );
}
