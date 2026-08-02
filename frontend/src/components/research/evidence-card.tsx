import { ArrowUpRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { EvidenceExcerpt } from "@/components/research/evidence-excerpt";
import { SourceBadge } from "@/components/research/source-badge";
import { cn } from "@/lib/utils/cn";

export interface EvidenceCardProps {
  excerpt: string;
  source: string;
  publishedAt?: string | null;
  evidenceRole?: "supporting" | "contradictory" | "illustrative" | "quantitative_context";
  onOpen?: () => void;
  className?: string;
}

const ROLE_LABEL: Record<NonNullable<EvidenceCardProps["evidenceRole"]>, string> = {
  supporting: "Supporting",
  contradictory: "Contradictory",
  illustrative: "Illustrative",
  quantitative_context: "Quantitative context",
};

/** design.md §22.5 — excerpt stays visually dominant; metadata (source,
 * date, role) sits below, never overpowering the text. */
export function EvidenceCard({ excerpt, source, publishedAt, evidenceRole, onOpen, className }: EvidenceCardProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4",
        onOpen && "cursor-pointer transition-colors hover:border-[var(--color-border-strong)]",
        className,
      )}
      onClick={onOpen}
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onKeyDown={onOpen ? (e) => (e.key === "Enter" || e.key === " ") && onOpen() : undefined}
    >
      <EvidenceExcerpt text={excerpt} />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SourceBadge source={source} />
        {publishedAt ? <span className="text-body-sm text-[var(--color-text-tertiary)]">{publishedAt}</span> : null}
        {evidenceRole ? (
          <Badge tone={evidenceRole === "contradictory" ? "warning" : "neutral"}>{ROLE_LABEL[evidenceRole]}</Badge>
        ) : null}
        {onOpen ? (
          <span className="text-body-sm ml-auto inline-flex items-center gap-1 text-[var(--color-text-link)]">
            View detail
            <Icon icon={ArrowUpRight} size="dense" />
          </span>
        ) : null}
      </div>
    </div>
  );
}
