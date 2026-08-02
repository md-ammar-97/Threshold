import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";

export interface InsightSummary {
  id: string;
  insight_type: string;
  title: string;
  finding: string;
  confidence_level: string;
  confidence_score: number | null;
  opportunity_score: number | null;
}

export interface InsightEvidencePreview {
  id: string;
  excerpt: string;
  evidence_role: string;
  source_connector_key: string;
  published_at: string | null;
}

export interface InsightThemeLink {
  theme_id: string;
  theme_name: string;
  relationship_type: string;
}

export interface InsightDetail extends InsightSummary {
  interpretation: string;
  affected_context: string | null;
  product_implication: string | null;
  validation_recommendation: string | null;
  insight_set_id: string;
  themes: InsightThemeLink[];
  evidence: InsightEvidencePreview[];
}

export interface InsightList {
  insight_set_id: string | null;
  insight_set_status: string | null;
  theme_set_id: string | null;
  analysis_run_id: string | null;
  insights: InsightSummary[];
}

export function useInsights() {
  return useQuery({
    queryKey: ["insights"],
    queryFn: () => apiClient.get<InsightList>("/api/v1/insights"),
  });
}

export function useInsight(insightId: string | null) {
  return useQuery({
    queryKey: ["insight", insightId],
    queryFn: () => apiClient.get<InsightDetail>(`/api/v1/insights/${insightId}`),
    enabled: Boolean(insightId),
  });
}
