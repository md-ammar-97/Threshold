import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";

export interface RunSummary {
  id: string;
  run_type: "ingestion" | "analysis";
  name: string;
  status: string;
  record_counts: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface RunList {
  runs: RunSummary[];
}

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => apiClient.get<RunList>("/api/v1/runs"),
  });
}
