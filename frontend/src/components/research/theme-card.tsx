import { Badge } from "@/components/ui/badge";
import { ConfidenceIndicator } from "@/components/research/confidence-indicator";
import type { ThemeTag } from "@/lib/api/themes";
import { cn } from "@/lib/utils/cn";

// Bounded, matching design.md §22.3's "never every field at once" rule — a
// theme can carry tags across up to 9 taxonomy dimensions; the card shows
// only the top few by member coverage, the detail page shows the rest.
const MAX_CARD_TAGS = 3;

export interface ThemeCardProps {
  name: string;
  themeType: string;
  shortSummary: string;
  recordCount: number;
  confidenceScore?: number | null;
  opportunityScore?: number | null;
  tags?: ThemeTag[];
  onOpen?: () => void;
  className?: string;
}

/** design.md §22.3 — a theme card shows a bounded subset of the available
 * metrics (name, type, summary, count, confidence, opportunity, top tags) —
 * never every field the API returns at once. */
export function ThemeCard({
  name,
  themeType,
  shortSummary,
  recordCount,
  confidenceScore,
  opportunityScore,
  tags,
  onOpen,
  className,
}: ThemeCardProps) {
  return (
    <div
      onClick={onOpen}
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onKeyDown={onOpen ? (e) => (e.key === "Enter" || e.key === " ") && onOpen() : undefined}
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4",
        onOpen && "cursor-pointer transition-colors hover:border-[var(--color-border-strong)]",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-heading-sm line-clamp-2">{name}</h3>
        <Badge tone="neutral">{themeType.replace(/_/g, " ")}</Badge>
      </div>
      <p className="text-body-md measure-narrative mt-2 text-[var(--color-text-secondary)]">{shortSummary}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span className="text-body-sm text-[var(--color-text-tertiary)]">{recordCount} records</span>
        <ConfidenceIndicator score={confidenceScore} />
        {typeof opportunityScore === "number" ? (
          <span className="text-body-sm text-[var(--color-text-tertiary)]">Opportunity {opportunityScore.toFixed(1)}</span>
        ) : null}
      </div>
      {tags && tags.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tags.slice(0, MAX_CARD_TAGS).map((tag) => (
            <Badge key={`${tag.dimension_key}:${tag.label_key}`} tone="primary">
              {tag.label_display_name}
            </Badge>
          ))}
          {tags.length > MAX_CARD_TAGS ? (
            <span className="text-body-sm self-center text-[var(--color-text-tertiary)]">
              +{tags.length - MAX_CARD_TAGS} more
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
