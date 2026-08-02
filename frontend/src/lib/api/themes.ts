import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";

export interface ThemeTag {
  dimension_key: string;
  dimension_display_name: string;
  label_key: string;
  label_display_name: string;
  record_count: number;
}

export interface ThemeSummary {
  id: string;
  theme_key: string;
  name: string;
  theme_type: string;
  short_summary: string;
  representative_record_count: number;
  confidence_score: number | null;
  opportunity_score: number | null;
  tags: ThemeTag[];
}

export interface EvidencePreview {
  id: string;
  excerpt: string;
  source_connector_key: string;
  published_at: string | null;
}

export interface ThemeDetail extends ThemeSummary {
  long_summary: string | null;
  theme_set_id: string;
  representative_evidence: EvidencePreview[];
  counterexample: EvidencePreview | null;
}

export interface ThemeList {
  theme_set_id: string | null;
  theme_set_status: string | null;
  analysis_run_id: string | null;
  themes: ThemeSummary[];
}

export function useThemes() {
  return useQuery({
    queryKey: ["themes"],
    queryFn: () => apiClient.get<ThemeList>("/api/v1/themes"),
  });
}

export function useTheme(themeId: string | null) {
  return useQuery({
    queryKey: ["theme", themeId],
    queryFn: () => apiClient.get<ThemeDetail>(`/api/v1/themes/${themeId}`),
    enabled: Boolean(themeId),
  });
}
