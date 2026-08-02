import { Badge, type BadgeTone } from "@/components/ui/badge";
import { StatusDot, type StatusTone } from "@/components/ui/status-dot";
import { cn } from "@/lib/utils/cn";

export interface RunStatusCardProps {
  name: string;
  type: string;
  status: string;
  recordCounts?: string;
  startedAt?: string | null;
  warningCount?: number;
  className?: string;
}

const STATUS_TONE: Record<string, { dot: StatusTone; badge: BadgeTone }> = {
  completed: { dot: "success", badge: "success" },
  running: { dot: "info", badge: "info" },
  queued: { dot: "neutral", badge: "neutral" },
  created: { dot: "neutral", badge: "neutral" },
  retrying: { dot: "warning", badge: "warning" },
  partially_completed: { dot: "warning", badge: "warning" },
  failed: { dot: "danger", badge: "danger" },
  cancelled: { dot: "neutral", badge: "neutral" },
};

/** design.md §34.2 — run list row: name, type, status, counts, warnings.
 * Status never relies on the dot color alone — the badge text is required. */
export function RunStatusCard({ name, type, status, recordCounts, startedAt, warningCount, className }: RunStatusCardProps) {
  const tone = STATUS_TONE[status] ?? STATUS_TONE.created;
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4",
        className,
      )}
    >
      <StatusDot tone={tone.dot} />
      <div className="min-w-0 flex-1">
        <p className="text-body-md font-medium text-[var(--color-text-primary)]">{name}</p>
        <p className="text-body-sm text-[var(--color-text-tertiary)]">
          {type}
          {startedAt ? ` · ${startedAt}` : ""}
          {recordCounts ? ` · ${recordCounts}` : ""}
        </p>
      </div>
      {warningCount ? <Badge tone="warning">{warningCount} warning{warningCount === 1 ? "" : "s"}</Badge> : null}
      <Badge tone={tone.badge}>{status.replace(/_/g, " ")}</Badge>
    </div>
  );
}
