import { AlertTriangle, CheckCircle2, Info, OctagonAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils/cn";

export type WarningSeverity = "info" | "caution" | "error" | "resolved";

const CONFIG = {
  info: { icon: Info, classes: "border-[var(--color-status-info)] bg-[var(--color-status-info-subtle)] text-[var(--color-status-info)]" },
  caution: {
    icon: AlertTriangle,
    classes: "border-[var(--color-status-warning)] bg-[var(--color-status-warning-subtle)] text-[var(--color-status-warning)]",
  },
  error: { icon: OctagonAlert, classes: "border-[var(--color-status-danger)] bg-[var(--color-status-danger-subtle)] text-[var(--color-status-danger)]" },
  resolved: {
    icon: CheckCircle2,
    classes: "border-[var(--color-status-success)] bg-[var(--color-status-success-subtle)] text-[var(--color-status-success)]",
  },
} as const;

export interface WarningBannerProps {
  severity: WarningSeverity;
  title: string;
  children?: ReactNode;
  className?: string;
}

/** design.md §26 — warnings are structured content read in the same
 * context as the finding/answer/theme they qualify, not toast-only. */
export function WarningBanner({ severity, title, children, className }: WarningBannerProps) {
  const config = CONFIG[severity];
  return (
    <div
      role={severity === "error" ? "alert" : "status"}
      className={cn("text-body-sm flex gap-2 rounded-[var(--radius-md)] border-l-[3px] px-3 py-2.5", config.classes, className)}
    >
      <Icon icon={config.icon} size="dense" className="mt-0.5" />
      <div>
        <p className="font-medium">{title}</p>
        {children ? <div className="mt-0.5 text-[var(--color-text-secondary)]">{children}</div> : null}
      </div>
    </div>
  );
}
