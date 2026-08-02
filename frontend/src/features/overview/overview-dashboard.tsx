import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { MetricCard } from "@/components/research/metric-card";
import { ThemeCard } from "@/components/research/theme-card";
import { WarningBanner } from "@/components/research/warning-banner";
import { FadeIn } from "@/components/motion/fade-in";
import { useEvidenceList } from "@/lib/api/evidence";
import { useRuns } from "@/lib/api/runs";
import { useThemes } from "@/lib/api/themes";

const MAX_EMERGING_THEMES = 4;

/** design.md §27 — restrained overview: coverage/limitation context, a KPI
 * strip, and emerging themes. The Signal Field visualization (§27.4) and
 * "Recent research activity"/"Processing health" panels are deferred (no
 * session-list or per-run-detail endpoint exists yet — see
 * docs/implementationplan.md Phase 7 status note). */
export function OverviewDashboard() {
  const evidence = useEvidenceList({});
  const themes = useThemes();
  const runs = useRuns();

  const isLoading = evidence.isLoading || themes.isLoading || runs.isLoading;
  const hasNoData = !isLoading && evidence.data?.total_matching === 0;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
      <div>
        <p className="text-label-lg text-[var(--color-text-secondary)]">Instamart Discovery Engine</p>
        <h1 className="text-heading-xl mt-1">Overview</h1>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          Understand what keeps users inside familiar categories&mdash;and what gives them confidence to
          explore.
        </p>
      </div>

      {hasNoData ? (
        <WarningBanner severity="info" title="No source data has been loaded yet">
          Start first ingestion from the command line (<code className="text-code-sm">scripts/</code>) to
          populate this workspace with real evidence, themes, and answers.
        </WarningBanner>
      ) : null}

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <FadeIn className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MetricCard label="Analyzed records" value={evidence.data?.total_matching ?? 0} />
          <MetricCard label="Themes" value={themes.data?.themes.length ?? 0} />
          <MetricCard
            label="Runs recorded"
            value={runs.data?.runs.length ?? 0}
            context="Ingestion + analysis"
          />
          <MetricCard
            label="Theme set status"
            value={themes.data?.theme_set_status?.replace(/_/g, " ") ?? "None"}
          />
        </FadeIn>
      )}

      <section>
        <div className="flex items-center justify-between">
          <h2 className="text-heading-md">Emerging themes</h2>
          <Link to="/themes" className="text-body-sm text-[var(--color-text-link)]">
            View all
          </Link>
        </div>
        {themes.data && themes.data.themes.length > 0 ? (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {themes.data.themes.slice(0, MAX_EMERGING_THEMES).map((theme) => (
              <ThemeCard
                key={theme.id}
                name={theme.name}
                themeType={theme.theme_type}
                shortSummary={theme.short_summary}
                recordCount={theme.representative_record_count}
                confidenceScore={theme.confidence_score}
                opportunityScore={theme.opportunity_score}
                tags={theme.tags}
              />
            ))}
          </div>
        ) : (
          <p className="text-body-md mt-3 text-[var(--color-text-tertiary)]">
            No themes discovered yet.
          </p>
        )}
      </section>

      <section className="surface-gradient-brand rounded-[var(--radius-xl)] p-6">
        <h2 className="text-heading-md">Ask a research question</h2>
        <p className="text-body-md measure-narrative mt-1 opacity-90">
          Get an evidence-grounded answer with citations to every underlying record.
        </p>
        <Link
          to="/ask"
          className="text-label-lg mt-3 inline-flex rounded-[var(--radius-md)] bg-[var(--color-bg-surface)] px-4 py-2 text-[var(--color-action-primary)]"
        >
          Open Ask workspace
        </Link>
      </section>
    </div>
  );
}
