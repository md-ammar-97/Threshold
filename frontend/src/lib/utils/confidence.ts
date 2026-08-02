/** design.md §21 — the API's own confidence_level is authoritative when
 * present; this mapping is only a fallback for a raw numeric score. */
export type ConfidenceLevel = "high" | "medium" | "low" | "unscored";

export function confidenceLevelFromScore(score: number | null | undefined): ConfidenceLevel {
  if (score === null || score === undefined) return "unscored";
  if (score >= 0.8) return "high";
  if (score >= 0.55) return "medium";
  return "low";
}

export const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
  unscored: "Not scored",
};
