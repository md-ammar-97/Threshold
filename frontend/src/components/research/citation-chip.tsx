import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

export interface CitationChipProps {
  label: string;
  preview?: string;
  onOpen?: (label: string) => void;
  selected?: boolean;
  className?: string;
}

/** design.md §25.1 — stable evidence labels (E12/T04/I07). Hover/focus shows
 * a preview; activating opens the evidence inspector; the selected citation
 * highlights to match the finding it supports. */
export function CitationChip({ label, preview, onOpen, selected, className }: CitationChipProps) {
  const chip = (
    <button
      type="button"
      onClick={() => onOpen?.(label)}
      aria-label={`Open evidence ${label}${preview ? `: ${preview}` : ""}`}
      className={cn(
        "text-code-sm inline-flex h-6 items-center rounded-[var(--radius-sm)] border px-1.5 transition-colors",
        selected
          ? "border-[var(--color-action-primary)] bg-[var(--color-action-primary-subtle)] text-[var(--color-action-primary)]"
          : "border-[var(--color-border-default)] bg-[var(--color-bg-surface-subtle)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)]",
        className,
      )}
    >
      {label}
    </button>
  );

  return preview ? <Tooltip content={preview}>{chip}</Tooltip> : chip;
}
