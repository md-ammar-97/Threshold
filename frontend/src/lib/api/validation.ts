import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";

export interface EvaluationMetric {
  metric_key: string;
  dimension_key: string | null;
  numeric_value: number | null;
  json_value: Record<string, unknown> | null;
  sample_count: number;
  calculation_version: string;
}

export interface ReleaseGateDecision {
  release_profile: string;
  status: string;
  zero_tolerance_failures: string[];
  metric_failures: string[];
}

export interface EvaluationRun {
  id: string;
  evaluation_dataset_id: string;
  status: string;
  items_evaluated: number;
  items_failed: number;
  created_at: string;
  completed_at: string | null;
  metrics: EvaluationMetric[];
  release_gate: ReleaseGateDecision | null;
}

export interface EvaluationTypeSummary {
  evaluation_type: string;
  latest_run: EvaluationRun | null;
}

export interface ValidationSummary {
  classification: EvaluationTypeSummary;
  retrieval: EvaluationTypeSummary;
  theme: EvaluationTypeSummary;
  grounding: EvaluationTypeSummary;
}

export function useValidationSummary() {
  return useQuery({
    queryKey: ["validation-summary"],
    queryFn: () => apiClient.get<ValidationSummary>("/api/v1/validation/summary"),
  });
}

export interface ReviewQueueItem {
  object_type: string;
  object_id: string;
  excerpt: string;
  dimension_key: string;
  dimension_display_name: string;
  label_key: string;
  label_display_name: string;
  confidence: number;
  previous_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface ReviewQueueList {
  total_matching: number;
  limit: number;
  offset: number;
  items: ReviewQueueItem[];
}

/** Phase A of the review queue (design.md §32.4) — only `analysis_label`
 * is implemented so far; see `mellow-strolling-thimble.md` for the
 * remaining-phase roadmap (feedback_relevance, feedback_analysis, theme,
 * theme_membership, insight, insight_evidence, answer_finding,
 * answer_citation). */
export function useReviewQueue(objectType: string = "analysis_label") {
  return useQuery({
    queryKey: ["review-queue", objectType],
    queryFn: () =>
      apiClient.get<ReviewQueueList>(`/api/v1/validation/reviews?object_type=${objectType}`),
  });
}

export interface SubmitReviewRequest {
  object_type: string;
  object_id: string;
  decision: "accepted" | "edited" | "rejected" | "needs_second_review";
  previous_snapshot: Record<string, unknown>;
  edited_snapshot?: Record<string, unknown>;
  reason_code?: string;
  notes?: string;
}

export interface ReviewDecision {
  id: string;
  object_type: string;
  object_id: string;
  decision: string;
  reason_code: string | null;
  notes: string | null;
  created_at: string;
}

export function useSubmitReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmitReviewRequest) =>
      apiClient.post<ReviewDecision>("/api/v1/validation/reviews", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["review-queue"] }),
  });
}
