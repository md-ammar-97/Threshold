import { Check, Circle, X } from "lucide-react";

import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils/cn";

export interface RunStageItemData {
  key: string;
  label: string;
  status: "pending" | "active" | "done" | "failed";
}

/** design.md §34.4 — stage completion checkmarks + a looping indeterminate
 * indicator only for the currently-active stage (never continuous motion
 * across the whole card). */
export function RunStageStepper({ stages }: { stages: RunStageItemData[] }) {
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {stages.map((stage, index) => (
        <li key={stage.key} className="flex items-center gap-2">
          <span
            className={cn(
              "text-label-md inline-flex items-center gap-1.5 rounded-[var(--radius-full)] px-2.5 py-1",
              stage.status === "done" && "bg-[var(--color-status-success-subtle)] text-[var(--color-status-success)]",
              stage.status === "active" && "bg-[var(--color-status-info-subtle)] text-[var(--color-status-info)]",
              stage.status === "failed" && "bg-[var(--color-status-danger-subtle)] text-[var(--color-status-danger)]",
              stage.status === "pending" && "bg-[var(--color-bg-surface-subtle)] text-[var(--color-text-tertiary)]",
            )}
          >
            {stage.status === "done" ? <Icon icon={Check} size="dense" /> : null}
            {stage.status === "failed" ? <Icon icon={X} size="dense" /> : null}
            {stage.status === "active" ? <Spinner /> : null}
            {stage.status === "pending" ? <Icon icon={Circle} size="dense" /> : null}
            {stage.label}
          </span>
          {index < stages.length - 1 ? <span aria-hidden className="h-px w-4 bg-[var(--color-border-default)]" /> : null}
        </li>
      ))}
    </ol>
  );
}
