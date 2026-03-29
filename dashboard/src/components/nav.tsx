"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: "⚡" },
  { href: "/agents", label: "Agents", icon: "🤖" },
  { href: "/metrics", label: "Metrics", icon: "📊" },
  { href: "/logs", label: "Logs", icon: "📋" },
  { href: "/memory", label: "Memory", icon: "🧠" },
  { href: "/skills", label: "Skills", icon: "📚" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="fixed left-0 top-0 h-full w-56 border-r border-[var(--card-border)] bg-[var(--card)] p-4 flex flex-col">
      <div className="mb-8">
        <h1 className="text-lg font-bold">GDS Agents</h1>
        <p className="text-xs text-[var(--muted)]">Dashboard</p>
      </div>
      <ul className="space-y-1 flex-1">
        {NAV_ITEMS.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                  active
                    ? "bg-white/10 text-white"
                    : "text-[var(--muted)] hover:text-white hover:bg-white/5"
                )}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="text-xs text-[var(--muted)] pt-4 border-t border-[var(--card-border)]">
        Drone168 Agent Platform
      </div>
    </nav>
  );
}
