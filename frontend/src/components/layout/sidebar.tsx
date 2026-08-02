import {
  BarChart3,
  BookOpen,
  ChevronsLeft,
  ChevronsRight,
  FileText,
  Layers,
  MessageCircleQuestion,
  PlayCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { motionTokens } from "@/components/motion/motion-tokens";
import { cn } from "@/lib/utils/cn";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: BarChart3 },
  { href: "/themes", label: "Themes", icon: Layers },
  { href: "/insights", label: "Insights", icon: Sparkles },
  { href: "/ask", label: "Ask", icon: MessageCircleQuestion },
  { href: "/evidence", label: "Evidence", icon: FileText },
  { href: "/validation", label: "Validation", icon: ShieldCheck },
  { href: "/reports", label: "Reports", icon: BookOpen },
  { href: "/runs", label: "Runs", icon: PlayCircle },
] as const;

/** design.md §15 — expanded (248px) / collapsed (72px) sidebar with a
 * 220ms width transition; active item uses a subtle tint + leading marker,
 * never a saturated pill. */
export function Sidebar() {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      data-app-shell="true"
      style={{ transitionDuration: `${motionTokens.duration.standard * 1000}ms` }}
      className={cn(
        "flex h-full flex-col border-r border-[var(--color-border-default)] bg-[var(--color-bg-surface)] transition-[width] motion-reduce:transition-none",
        collapsed ? "w-[72px]" : "w-[248px]",
      )}
    >
      <div className="flex items-center justify-between px-4 py-4">
        {!collapsed ? <span className="text-heading-sm">Discovery Engine</span> : null}
        <IconButton
          icon={collapsed ? ChevronsRight : ChevronsLeft}
          label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={() => setCollapsed((c) => !c)}
          size="icon-sm"
        />
      </div>

      <nav aria-label="Product surfaces" className="flex-1 space-y-1 px-2">
        {NAV_ITEMS.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              to={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "text-label-lg flex items-center gap-3 rounded-[var(--radius-md)] border-l-[3px] px-3 py-2 transition-colors",
                active
                  ? "border-[var(--color-action-primary)] bg-[var(--color-action-primary-subtle)] text-[var(--color-action-primary)]"
                  : "border-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-subtle)]",
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon icon={item.icon} size="nav" />
              {!collapsed ? item.label : null}
            </Link>
          );
        })}
      </nav>

      <div className="px-2 py-4">
        <Link
          to="/methodology"
          className="text-label-lg flex items-center gap-3 rounded-[var(--radius-md)] px-3 py-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-subtle)]"
          title={collapsed ? "Methodology" : undefined}
        >
          <Icon icon={BookOpen} size="nav" />
          {!collapsed ? "Methodology" : null}
        </Link>
      </div>
    </aside>
  );
}
