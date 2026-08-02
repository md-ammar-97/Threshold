import { Badge } from "@/components/ui/badge";
import { Drawer } from "@/components/ui/drawer";
import { Skeleton } from "@/components/ui/skeleton";
import { EvidenceExcerpt } from "@/components/research/evidence-excerpt";
import { SourceBadge } from "@/components/research/source-badge";
import { useEvidenceDetail } from "@/lib/api/evidence";

export interface EvidenceInspectorProps {
  recordId: string | null;
  onOpenChange: (open: boolean) => void;
}

/** Shared evidence drawer — lifted out of features/evidence/evidence-explorer.tsx
 * (previously a local, unexported component there) so the Ask workspace can
 * reuse it for citation drill-through (audit-2026-07-31.md F-14/R-8) instead
 * of stopping at a hover tooltip. */
export function EvidenceInspector({ recordId, onOpenChange }: EvidenceInspectorProps) {
  const { data, isLoading } = useEvidenceDetail(recordId);

  return (
    <Drawer open={Boolean(recordId)} onOpenChange={onOpenChange} title="Evidence detail">
      {isLoading || !data ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <div className="flex flex-col gap-4">
          <EvidenceExcerpt text={data.redacted_text} />
          <div className="flex flex-wrap gap-2">
            <SourceBadge source={data.source_connector_key} />
            <Badge tone="neutral">{data.record_type}</Badge>
            {data.language_code ? <Badge tone="neutral">{data.language_code}</Badge> : null}
          </div>
          <dl className="text-body-sm grid grid-cols-2 gap-2 text-[var(--color-text-secondary)]">
            <dt className="text-[var(--color-text-tertiary)]">Published</dt>
            <dd>{data.published_at ?? "Unknown"}</dd>
            <dt className="text-[var(--color-text-tertiary)]">Relevance</dt>
            <dd>{data.relevance_status.replace(/_/g, " ")}</dd>
            <dt className="text-[var(--color-text-tertiary)]">Quality</dt>
            <dd>{data.quality_status.replace(/_/g, " ")}</dd>
          </dl>
          {data.source_url ? (
            <a href={data.source_url} target="_blank" rel="noreferrer" className="text-body-sm text-[var(--color-text-link)]">
              Open original source ↗
            </a>
          ) : null}
        </div>
      )}
    </Drawer>
  );
}
