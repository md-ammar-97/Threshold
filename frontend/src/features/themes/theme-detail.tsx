import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfidenceIndicator } from "@/components/research/confidence-indicator";
import { EvidenceCard } from "@/components/research/evidence-card";
import { WarningBanner } from "@/components/research/warning-banner";
import { FadeIn } from "@/components/motion/fade-in";
import { ApiError } from "@/lib/api/client";
import type { ThemeTag } from "@/lib/api/themes";
import { useTheme } from "@/lib/api/themes";

function groupTagsByDimension(tags: ThemeTag[]): [string, string, ThemeTag[]][] {
  const byDimension = new Map<string, { displayName: string; tags: ThemeTag[] }>();
  for (const tag of tags) {
    const existing = byDimension.get(tag.dimension_key);
    if (existing) {
      existing.tags.push(tag);
    } else {
      byDimension.set(tag.dimension_key, { displayName: tag.dimension_display_name, tags: [tag] });
    }
  }
  return Array.from(byDimension.entries()).map(([key, { displayName, tags: t }]) => [
    key,
    displayName,
    t,
  ]);
}

export function ThemeDetail() {
  const { themeId } = useParams<{ themeId: string }>();
  const { data: theme, isLoading, isError, error } = useTheme(themeId ?? null);

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-10">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !theme) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <WarningBanner severity="error" title="Could not load this theme">
          {error instanceof ApiError ? error.message : "The theme may no longer exist."}
        </WarningBanner>
      </div>
    );
  }

  return (
    <FadeIn className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <Link to="/themes" className="text-body-sm inline-flex w-fit items-center gap-1 text-[var(--color-text-link)]">
        <ArrowLeft className="size-4" aria-hidden />
        Back to Themes
      </Link>

      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-heading-xl">{theme.name}</h1>
          <Badge tone="neutral">{theme.theme_type.replace(/_/g, " ")}</Badge>
        </div>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          {theme.long_summary ?? theme.short_summary}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="text-body-sm text-[var(--color-text-tertiary)]">
            {theme.representative_record_count} records
          </span>
          <ConfidenceIndicator score={theme.confidence_score} />
          {typeof theme.opportunity_score === "number" ? (
            <span className="text-body-sm text-[var(--color-text-tertiary)]">
              Opportunity {theme.opportunity_score.toFixed(1)}
            </span>
          ) : null}
        </div>
      </div>

      {theme.tags.length > 0 ? (
        <section>
          <h2 className="text-heading-md">Classifications</h2>
          <p className="text-body-sm mt-1 text-[var(--color-text-tertiary)]">
            Taxonomy labels applied to this theme's member records, most-common first.
          </p>
          <div className="mt-3 flex flex-col gap-3">
            {groupTagsByDimension(theme.tags).map(([dimensionKey, dimensionName, tags]) => (
              <div key={dimensionKey}>
                <h3 className="text-label-md text-[var(--color-text-tertiary)]">{dimensionName}</h3>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {tags.map((tag) => (
                    <Badge key={tag.label_key} tone="primary">
                      {tag.label_display_name} ({tag.record_count})
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="text-heading-md">Representative evidence</h2>
        <div className="mt-3 flex flex-col gap-3">
          {theme.representative_evidence.map((evidence) => (
            <EvidenceCard
              key={evidence.id}
              excerpt={evidence.excerpt}
              source={evidence.source_connector_key}
              publishedAt={evidence.published_at}
            />
          ))}
        </div>
      </section>

      {theme.counterexample ? (
        <section>
          <h2 className="text-heading-md">Contradictory evidence</h2>
          <div className="mt-3">
            <EvidenceCard
              excerpt={theme.counterexample.excerpt}
              source={theme.counterexample.source_connector_key}
              publishedAt={theme.counterexample.published_at}
              evidenceRole="contradictory"
            />
          </div>
        </section>
      ) : null}
    </FadeIn>
  );
}
