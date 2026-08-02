import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

export type BadgeTone =
  | "neutral"
  | "primary"
  | "evidence"
  | "synthesis"
  | "discovery"
  | "warning"
  | "danger"
  | "info"
  | "success";

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: "bg-[var(--color-bg-surface-subtle)] text-[var(--color-text-secondary)]",
  primary: "bg-[var(--color-action-primary-subtle)] text-[var(--color-action-primary)]",
  evidence: "bg-[var(--color-evidence-subtle)] text-[var(--color-evidence-default)]",
  synthesis: "bg-[var(--color-synthesis-subtle)] text-[var(--color-synthesis-default)]",
  discovery: "bg-[var(--color-discovery-subtle)] text-[var(--color-discovery-default)]",
  warning: "bg-[var(--color-status-warning-subtle)] text-[var(--color-status-warning)]",
  danger: "bg-[var(--color-status-danger-subtle)] text-[var(--color-status-danger)]",
  info: "bg-[var(--color-status-info-subtle)] text-[var(--color-status-info)]",
  success: "bg-[var(--color-status-success-subtle)] text-[var(--color-status-success)]",
};

export interface BadgeProps {
  tone?: BadgeTone;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** design.md §21 — categorical badge. Tone alone never carries meaning: an
 * icon or label must always accompany it (§47.6 color independence). */
export function Badge({ tone = "neutral", icon, children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "text-label-md inline-flex items-center gap-1 rounded-[var(--radius-full)] px-2 py-0.5",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}
