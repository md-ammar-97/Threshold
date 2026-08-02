import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerList } from "@/components/motion/stagger-list";
import { InsightCard } from "@/components/research/insight-card";
import { WarningBanner } from "@/components/research/warning-banner";
import { ApiError } from "@/lib/api/client";
import { useInsights } from "@/lib/api/insights";

const ALL_INSIGHT_TYPES = "all";

function formatInsightType(insightType: string): string {
  return insightType.replace(/_/g, " ");
}

/** Mirrors features/themes/themes-explorer.tsx's exact shape — Phase 4's
 * insight-generation output existed with no UI surface at all until now
 * (audit-2026-07-31.md F-13/R-7). */
export function InsightsExplorer() {
  const { data, isLoading, isError, error } = useInsights();
  const navigate = useNavigate();
  const [selectedType, setSelectedType] = useState(ALL_INSIGHT_TYPES);

  const availableTypes = useMemo(() => {
    const types = new Set((data?.insights ?? []).map((insight) => insight.insight_type));
    return Array.from(types).sort();
  }, [data]);

  const visibleInsights = useMemo(() => {
    if (!data) return [];
    if (selectedType === ALL_INSIGHT_TYPES) return data.insights;
    return data.insights.filter((insight) => insight.insight_type === selectedType);
  }, [data, selectedType]);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <div>
        <h1 className="text-heading-xl">Insights</h1>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          Evidence-backed observations, syntheses, and product hypotheses generated from themes.
        </p>
      </div>

      {isError ? (
        <WarningBanner severity="error" title="Could not load insights">
          {error instanceof ApiError ? error.message : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : null}

      {data && data.insights.length === 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-default)] p-8 text-center">
          <p className="text-body-md text-[var(--color-text-secondary)]">
            No insight set has been produced yet. Run insight generation (Phase 4) against a synthesized
            theme set to see insights here.
          </p>
        </div>
      ) : null}

      {data && data.insights.length > 0 ? (
        <div className="max-w-xs">
          <Select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            aria-label="Filter insights by type"
          >
            <option value={ALL_INSIGHT_TYPES}>All types</option>
            {availableTypes.map((insightType) => (
              <option key={insightType} value={insightType}>
                {formatInsightType(insightType)}
              </option>
            ))}
          </Select>
        </div>
      ) : null}

      {data && data.insights.length > 0 && visibleInsights.length === 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-default)] p-8 text-center">
          <p className="text-body-md text-[var(--color-text-secondary)]">
            No insights match this filter.
          </p>
        </div>
      ) : null}

      {visibleInsights.length > 0 ? (
        <StaggerList className="flex flex-col gap-3">
          {visibleInsights.map((insight) => (
            <InsightCard
              key={insight.id}
              title={insight.title}
              insightType={insight.insight_type}
              finding={insight.finding}
              confidenceScore={insight.confidence_score}
              opportunityScore={insight.opportunity_score}
              onOpen={() => navigate(`/insights/${insight.id}`)}
            />
          ))}
        </StaggerList>
      ) : null}
    </div>
  );
}
