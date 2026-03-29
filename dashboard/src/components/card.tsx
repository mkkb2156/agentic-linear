import { cn } from "@/lib/utils";
import { type ReactNode } from "react";

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-4",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  action,
}: {
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h3 className="text-sm font-medium text-[var(--muted)]">{title}</h3>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <Card>
      <p className="text-xs text-[var(--muted)] mb-1">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
      {sub && <p className="text-xs text-[var(--muted)] mt-1">{sub}</p>}
    </Card>
  );
}
