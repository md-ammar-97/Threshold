import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ReviewQueueItemCard } from "@/components/research/review-queue-item";
import { ValidationMetricCard } from "@/components/research/validation-metric-card";
import { WarningBanner } from "@/components/research/warning-banner";
import { FadeIn } from "@/components/motion/fade-in";
import { ApiError } from "@/lib/api/client";
import { useReviewQueue, useSubmitReview, useValidationSummary } from "@/lib/api/validation";
import type { EvaluationRun, EvaluationTypeSummary } from "@/lib/api/validation";

const SECTION_LABEL: Record<string, string> = {
  classification: "Classification quality",
  retrieval: "Retrieval quality",
  theme: "Theme quality",
  grounding: "Grounding quality",
};

const GATE_TONE = { pass: "success", pass_with_conditions: "warning", fail: "danger" } as const;

function RunMetrics({ run }: { run: EvaluationRun }) {
  return (
    <div className="flex flex-col gap-3">
      {run.release_gate ? (
        <div className="flex items-center gap-2">
          <Badge tone={GATE_TONE[run.release_gate.status as keyof typeof GATE_TONE] ?? "neutral"}>
            Release gate: {run.release_gate.status.replace(/_/g, " ")}
          </Badge>
          <span className="text-body-sm text-[var(--color-text-tertiary)]">{run.release_gate.release_profile}</span>
        </div>
      ) : null}

      {run.release_gate?.zero_tolerance_failures.length ? (
        <WarningBanner severity="error" title="Zero-tolerance category failed">
          {run.release_gate.zero_tolerance_failures.join(", ")}
        </WarningBanner>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {run.metrics
          .filter((m) => m.dimension_key === null && m.numeric_value !== null)
          .map((metric) => (
            <ValidationMetricCard
              key={metric.metric_key}
              label={metric.metric_key.replace(/_/g, " ")}
              value={metric.numeric_value!.toFixed(3)}
              sampleCount={metric.sample_count}
              calculationVersion={metric.calculation_version}
            />
          ))}
      </div>

      <p className="text-body-sm text-[var(--color-text-tertiary)]">
        {run.items_evaluated} evaluated · {run.items_failed} failed · run {run.id.slice(0, 8)}
      </p>
    </div>
  );
}

function SuiteSection({ evaluationType, summary }: { evaluationType: string; summary: EvaluationTypeSummary }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-heading-md">{SECTION_LABEL[evaluationType] ?? evaluationType}</h2>
      {summary.latest_run ? (
        <RunMetrics run={summary.latest_run} />
      ) : (
        <p className="text-body-md text-[var(--color-text-tertiary)]">
          No evaluation run has been recorded for this suite yet.
        </p>
      )}
    </section>
  );
}

function ReviewQueueSection() {
  const { data, isLoading, isError, error } = useReviewQueue();
  const submitReview = useSubmitReview();

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-heading-md">Human review queue</h2>
        <p className="text-body-sm mt-1 text-[var(--color-text-tertiary)]">
          Classification labels only for now (design.md §32.4, Phase A) — other review types (themes,
          insights, answers) are planned follow-ups.
        </p>
      </div>

      {isError ? (
        <WarningBanner severity="error" title="Could not load the review queue">
          {error instanceof ApiError ? error.message : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {submitReview.isError ? (
        <WarningBanner severity="error" title="Could not submit review">
          {submitReview.error instanceof ApiError
            ? submitReview.error.message
            : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : null}

      {data && data.items.length === 0 ? (
        <p className="text-body-md text-[var(--color-text-tertiary)]">
          Nothing is currently pending review.
        </p>
      ) : null}

      {data && data.items.length > 0 ? (
        <>
          <p className="text-body-sm text-[var(--color-text-tertiary)]" aria-live="polite">
            {data.total_matching} pending
          </p>
          <div className="flex flex-col gap-3">
            {data.items.map((item) => (
              <ReviewQueueItemCard
                key={item.object_id}
                item={item}
                onSubmit={(body) => submitReview.mutate(body)}
                isSubmitting={submitReview.isPending}
              />
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}

export function ValidationWorkspace() {
  const { data, isLoading, isError, error } = useValidationSummary();

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-10">
      <div>
        <h1 className="text-heading-xl">Validation</h1>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          Research quality is inspectable, not asserted: every metric below carries its sample size, dataset
          version, and the release-gate decision it produced.
        </p>
      </div>

      {isError ? (
        <WarningBanner severity="error" title="Could not load validation summary">
          {error instanceof ApiError ? error.message : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}

      {data ? (
        <FadeIn className="flex flex-col gap-8">
          <SuiteSection evaluationType="classification" summary={data.classification} />
          <SuiteSection evaluationType="retrieval" summary={data.retrieval} />
          <SuiteSection evaluationType="theme" summary={data.theme} />
          <SuiteSection evaluationType="grounding" summary={data.grounding} />
        </FadeIn>
      ) : null}

      <ReviewQueueSection />
    </div>
  );
}
