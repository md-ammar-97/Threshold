import { Skeleton } from "@/components/ui/skeleton";
import { RunStatusCard } from "@/components/research/run-status-card";
import { WarningBanner } from "@/components/research/warning-banner";
import { StaggerList } from "@/components/motion/stagger-list";
import { ApiError } from "@/lib/api/client";
import { useRuns } from "@/lib/api/runs";

/** design.md §34 — unified ingestion + analysis run list. Cost estimate and
 * a per-run stage-stepper detail view are deferred until a run-detail
 * endpoint exists (see docs/implementationplan.md Phase 7 status note). */
export function RunsWorkspace() {
  const { data, isLoading, isError, error } = useRuns();

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <div>
        <h1 className="text-heading-xl">Runs</h1>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          Collection and analysis progress across every ingestion and analysis run.
        </p>
      </div>

      {isError ? (
        <WarningBanner severity="error" title="Could not load runs">
          {error instanceof ApiError ? error.message : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : null}

      {data && data.runs.length === 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-default)] p-8 text-center">
          <p className="text-body-md text-[var(--color-text-secondary)]">
            No ingestion or analysis runs recorded yet. Start first ingestion to see progress here.
          </p>
        </div>
      ) : null}

      {data && data.runs.length > 0 ? (
        <StaggerList className="flex flex-col gap-2">
          {data.runs.map((run) => (
            <RunStatusCard
              key={run.id}
              name={run.name}
              type={run.run_type}
              status={run.status}
              recordCounts={run.record_counts}
              startedAt={run.started_at}
            />
          ))}
        </StaggerList>
      ) : null}
    </div>
  );
}
