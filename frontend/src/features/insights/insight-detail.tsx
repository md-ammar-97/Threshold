import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ConfidenceIndicator } from "@/components/research/confidence-indicator";
import { EvidenceCard } from "@/components/research/evidence-card";
import { KnowledgeTypeBadge, type KnowledgeType } from "@/components/research/knowledge-type-badge";
import { WarningBanner } from "@/components/research/warning-banner";
import { FadeIn } from "@/components/motion/fade-in";
import { ApiError } from "@/lib/api/client";
import { useInsight } from "@/lib/api/insights";

const EVIDENCE_ROLES = ["supporting", "contradictory", "illustrative", "quantitative_context"] as const;
type EvidenceRole = (typeof EVIDENCE_ROLES)[number];

function toEvidenceRole(role: string): EvidenceRole | undefined {
  return (EVIDENCE_ROLES as readonly string[]).includes(role) ? (role as EvidenceRole) : undefined;
}

/** Mirrors features/themes/theme-detail.tsx's exact shape. */
export function InsightDetail() {
  const { insightId } = useParams<{ insightId: string }>();
  const { data: insight, isLoading, isError, error } = useInsight(insightId ?? null);

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-10">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !insight) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <WarningBanner severity="error" title="Could not load this insight">
          {error instanceof ApiError ? error.message : "The insight may no longer exist."}
        </WarningBanner>
      </div>
    );
  }

  return (
    <FadeIn className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <Link
        to="/insights"
        className="text-body-sm inline-flex w-fit items-center gap-1 text-[var(--color-text-link)]"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Back to Insights
      </Link>

      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-heading-xl">{insight.title}</h1>
          <KnowledgeTypeBadge type={insight.insight_type as KnowledgeType} />
        </div>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          {insight.finding}
        </p>
        <p className="text-body-md measure-narrative mt-2 text-[var(--color-text-secondary)]">
          {insight.interpretation}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <ConfidenceIndicator score={insight.confidence_score} />
          {typeof insight.opportunity_score === "number" ? (
            <span className="text-body-sm text-[var(--color-text-tertiary)]">
              Opportunity {insight.opportunity_score.toFixed(1)}
            </span>
          ) : null}
        </div>
      </div>

      {insight.affected_context || insight.product_implication || insight.validation_recommendation ? (
        <section className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] p-4">
          {insight.affected_context ? (
            <p className="text-body-sm text-[var(--color-text-secondary)]">
              <span className="text-label-md text-[var(--color-text-primary)]">Affected context: </span>
              {insight.affected_context}
            </p>
          ) : null}
          {insight.product_implication ? (
            <p className="text-body-sm mt-2 text-[var(--color-text-secondary)]">
              <span className="text-label-md text-[var(--color-text-primary)]">Product implication: </span>
              {insight.product_implication}
            </p>
          ) : null}
          {insight.validation_recommendation ? (
            <p className="text-body-sm mt-2 text-[var(--color-text-secondary)]">
              <span className="text-label-md text-[var(--color-text-primary)]">
                Validation recommendation:{" "}
              </span>
              {insight.validation_recommendation}
            </p>
          ) : null}
        </section>
      ) : null}

      {insight.themes.length > 0 ? (
        <section>
          <h2 className="text-heading-md">Related themes</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {insight.themes.map((link) => (
              <Link key={link.theme_id} to={`/themes/${link.theme_id}`}>
                <Badge tone="neutral">
                  {link.theme_name} · {link.relationship_type}
                </Badge>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="text-heading-md">Evidence</h2>
        <div className="mt-3 flex flex-col gap-3">
          {insight.evidence.map((evidence) => (
            <EvidenceCard
              key={evidence.id}
              excerpt={evidence.excerpt}
              source={evidence.source_connector_key}
              publishedAt={evidence.published_at}
              evidenceRole={toEvidenceRole(evidence.evidence_role)}
            />
          ))}
        </div>
      </section>
    </FadeIn>
  );
}
