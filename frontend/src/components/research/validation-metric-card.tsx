import { Tooltip } from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils/cn";

export interface ValidationMetricCardProps {
  label: string;
  value: string;
  sampleCount: number;
  calculationVersion: string;
  explanation?: string;
  passed?: boolean;
  className?: string;
}

/** design.md §32.3 — every metric must show sample size, version, and an
 * explanation; never a bare number with no denominator (edgecases.md
 * EVAL-008 small-sample warning is the caller's responsibility to surface
 * alongside this via a WarningBanner when sampleCount is low). */
export function ValidationMetricCard({
  label,
  value,
  sampleCount,
  calculationVersion,
  explanation,
  passed,
  className,
}: ValidationMetricCardProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border p-4",
        passed === false
          ? "border-[var(--color-status-danger)] bg-[var(--color-status-danger-subtle)]"
          : "border-[var(--color-border-default)] bg-[var(--color-bg-surface)]",
        className,
      )}
    >
      <div className="flex items-center gap-1">
        <p className="text-label-md text-[var(--color-text-secondary)]">{label}</p>
        {explanation ? (
          <Tooltip content={explanation}>
            <span>
              <Icon icon={Info} size="dense" className="text-[var(--color-text-tertiary)]" />
            </span>
          </Tooltip>
        ) : null}
      </div>
      <p className="text-heading-lg mt-1 tabular-nums">{value}</p>
      <p className="text-body-sm mt-1 text-[var(--color-text-tertiary)]">
        n={sampleCount} · {calculationVersion}
      </p>
    </div>
  );
}
