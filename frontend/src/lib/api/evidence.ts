import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";

export interface EvidenceRow {
  id: string;
  excerpt: string;
  source_connector_key: string;
  record_type: string;
  published_at: string | null;
  rating_normalized: number | null;
  relevance_status: string;
  quality_status: string;
}

export interface EvidenceDetail extends EvidenceRow {
  original_text: string;
  redacted_text: string;
  language_code: string | null;
  source_url: string | null;
}

export interface EvidenceList {
  total_matching: number;
  limit: number;
  offset: number;
  records: EvidenceRow[];
}

export interface EvidenceSourceOption {
  key: string;
  display_name: string;
}

export interface EvidenceSources {
  sources: EvidenceSourceOption[];
}

export function useEvidenceList(params: { search?: string; sourceConnectorKey?: string; offset?: number }) {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.sourceConnectorKey) query.set("source_connector_key", params.sourceConnectorKey);
  if (params.offset) query.set("offset", String(params.offset));

  return useQuery({
    queryKey: ["evidence", params],
    queryFn: () => apiClient.get<EvidenceList>(`/api/v1/evidence?${query.toString()}`),
  });
}

export function useEvidenceSources() {
  return useQuery({
    queryKey: ["evidence-sources"],
    queryFn: () => apiClient.get<EvidenceSources>("/api/v1/evidence/sources"),
  });
}

export function useEvidenceDetail(recordId: string | null) {
  return useQuery({
    queryKey: ["evidence-detail", recordId],
    queryFn: () => apiClient.get<EvidenceDetail>(`/api/v1/evidence/${recordId}`),
    enabled: Boolean(recordId),
  });
}
