import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";

export interface ReportEvidenceLink {
  id: string;
  object_type: string;
  object_id: string;
  display_order: number;
  snapshot: Record<string, unknown>;
}

export interface ReportSection {
  id: string;
  section_type: string;
  position: number;
  title: string;
  content: Record<string, unknown>;
  narrative_text: string | null;
  is_locked: boolean;
  evidence: ReportEvidenceLink[];
}

export interface ReportSummary {
  id: string;
  title: string;
  subtitle: string | null;
  status: string;
  analysis_run_id: string;
  theme_set_id: string;
  insight_set_id: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export interface ReportDetail extends ReportSummary {
  sections: ReportSection[];
}

export interface ReportList {
  reports: ReportSummary[];
}

export interface ReportExport {
  id: string;
  report_id: string;
  export_format: string;
  status: string;
  sha256: string | null;
  byte_size: number | null;
  failure_code: string | null;
  failure_message: string | null;
  created_at: string;
  completed_at: string | null;
  content: string | Record<string, unknown> | null;
}

export interface EvidenceRef {
  object_type: string;
  object_id: string;
}

const REPORTS_KEY = ["reports"];
const reportKey = (id: string) => ["report", id];

export function useReports() {
  return useQuery({
    queryKey: REPORTS_KEY,
    queryFn: () => apiClient.get<ReportList>("/api/v1/reports"),
  });
}

export function useReport(reportId: string | null) {
  return useQuery({
    queryKey: reportKey(reportId ?? ""),
    queryFn: () => apiClient.get<ReportDetail>(`/api/v1/reports/${reportId}`),
    enabled: Boolean(reportId),
  });
}

export function useCreateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; subtitle?: string }) =>
      apiClient.post<ReportDetail>("/api/v1/reports", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: REPORTS_KEY }),
  });
}

export function useUpdateReport(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { title?: string; subtitle?: string; status?: string }) =>
      apiClient.patch<ReportDetail>(`/api/v1/reports/${reportId}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: reportKey(reportId) });
      queryClient.invalidateQueries({ queryKey: REPORTS_KEY });
    },
  });
}

export function useAddSection(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      section_type: string;
      title: string;
      content?: Record<string, unknown>;
      narrative_text?: string;
      evidence?: EvidenceRef[];
    }) => apiClient.post<ReportSection>(`/api/v1/reports/${reportId}/sections`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportKey(reportId) }),
  });
}

export function useUpdateSection(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sectionId,
      body,
    }: {
      sectionId: string;
      body: {
        title?: string;
        content?: Record<string, unknown>;
        narrative_text?: string;
        is_locked?: boolean;
      };
    }) =>
      apiClient.patch<ReportSection>(
        `/api/v1/reports/${reportId}/sections/${sectionId}`,
        body,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportKey(reportId) }),
  });
}

export function useDeleteSection(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sectionId: string) =>
      apiClient.delete(`/api/v1/reports/${reportId}/sections/${sectionId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportKey(reportId) }),
  });
}

export function useReorderSections(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sectionIds: string[]) =>
      apiClient.post<ReportSection[]>(`/api/v1/reports/${reportId}/sections/reorder`, {
        section_ids: sectionIds,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportKey(reportId) }),
  });
}

export function useAddEvidence(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sectionId, ref }: { sectionId: string; ref: EvidenceRef }) =>
      apiClient.post<ReportEvidenceLink>(
        `/api/v1/reports/${reportId}/sections/${sectionId}/evidence`,
        ref,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportKey(reportId) }),
  });
}

export function useRemoveEvidence(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sectionId, linkId }: { sectionId: string; linkId: string }) =>
      apiClient.delete(
        `/api/v1/reports/${reportId}/sections/${sectionId}/evidence/${linkId}`,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportKey(reportId) }),
  });
}

export function useCreateExport(reportId: string) {
  return useMutation({
    mutationFn: (exportFormat: "markdown" | "json") =>
      apiClient.post<ReportExport>(`/api/v1/reports/${reportId}/exports`, {
        export_format: exportFormat,
      }),
  });
}

export interface EmailExportResult {
  message_id: string;
  recipient_email: string;
}

export function useEmailExport(reportId: string, exportId: string | null) {
  return useMutation({
    mutationFn: (recipientEmail: string) =>
      apiClient.post<EmailExportResult>(
        `/api/v1/reports/${reportId}/exports/${exportId}/email`,
        { recipient_email: recipientEmail },
      ),
  });
}
