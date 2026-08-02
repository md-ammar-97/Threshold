import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

export interface MetricCardProps {
  label: string;
  value: ReactNode;
  context?: string;
  className?: string;
}

/** design.md §22.2 — metric label + value + context; never a giant number
 * with no explanation of unit/denominator/timeframe. */
export function MetricCard({ label, value, context, className }: MetricCardProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4",
        className,
      )}
    >
      <p className="text-label-md text-[var(--color-text-secondary)]">{label}</p>
      <p className="text-heading-lg mt-1 tabular-nums">{value}</p>
      {context ? <p className="text-body-sm mt-1 text-[var(--color-text-tertiary)]">{context}</p> : null}
    </div>
  );
}
