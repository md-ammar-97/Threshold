import { ConfidenceIndicator } from "@/components/research/confidence-indicator";
import { KnowledgeTypeBadge, type KnowledgeType } from "@/components/research/knowledge-type-badge";
import { cn } from "@/lib/utils/cn";

export interface InsightCardProps {
  title: string;
  insightType: string;
  finding: string;
  confidenceScore?: number | null;
  opportunityScore?: number | null;
  onOpen?: () => void;
  className?: string;
}

/** Mirrors components/research/theme-card.tsx's exact shape — a bounded
 * subset of fields, never every field the API returns at once. */
export function InsightCard({
  title,
  insightType,
  finding,
  confidenceScore,
  opportunityScore,
  onOpen,
  className,
}: InsightCardProps) {
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
        <h3 className="text-heading-sm line-clamp-2">{title}</h3>
        <KnowledgeTypeBadge type={insightType as KnowledgeType} />
      </div>
      <p className="text-body-md measure-narrative mt-2 text-[var(--color-text-secondary)]">{finding}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <ConfidenceIndicator score={confidenceScore} />
        {typeof opportunityScore === "number" ? (
          <span className="text-body-sm text-[var(--color-text-tertiary)]">Opportunity {opportunityScore.toFixed(1)}</span>
        ) : null}
      </div>
    </div>
  );
}
