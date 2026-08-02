import { CircleAlert, CircleCheck, CircleDashed, CircleMinus } from "lucide-react";

import { Icon } from "@/components/ui/icon";
import { Tooltip } from "@/components/ui/tooltip";
import { CONFIDENCE_LABEL, confidenceLevelFromScore, type ConfidenceLevel } from "@/lib/utils/confidence";
import { cn } from "@/lib/utils/cn";

const LEVEL_ICON = {
  high: CircleCheck,
  medium: CircleMinus,
  low: CircleAlert,
  unscored: CircleDashed,
} as const;

const LEVEL_CLASS: Record<ConfidenceLevel, string> = {
  high: "text-[var(--color-status-success)]",
  medium: "text-[var(--color-status-warning)]",
  low: "text-[var(--color-status-danger)]",
  unscored: "text-[var(--color-text-tertiary)]",
};

export interface ConfidenceIndicatorProps {
  level?: ConfidenceLevel;
  score?: number | null;
  explanation?: string;
  className?: string;
}

/** design.md §4.4/§21 — confidence sits beside the object it qualifies,
 * never as a single global score. Never icon-only: label + optional numeric
 * + tooltip explanation, per §47.6 color independence. */
export function ConfidenceIndicator({ level, score, explanation, className }: ConfidenceIndicatorProps) {
  const resolvedLevel = level ?? confidenceLevelFromScore(score);
  const content = (
    <span className={cn("text-label-md inline-flex items-center gap-1", LEVEL_CLASS[resolvedLevel], className)}>
      <Icon icon={LEVEL_ICON[resolvedLevel]} size="dense" />
      {CONFIDENCE_LABEL[resolvedLevel]}
      {typeof score === "number" ? <span className="text-[var(--color-text-tertiary)]">({score.toFixed(2)})</span> : null}
    </span>
  );

  if (!explanation) return content;
  return <Tooltip content={explanation}>{content}</Tooltip>;
}
