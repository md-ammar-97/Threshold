import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerList } from "@/components/motion/stagger-list";
import { WarningBanner } from "@/components/research/warning-banner";
import { ApiError } from "@/lib/api/client";
import { useCreateReport, useReports } from "@/lib/api/reports";

const STATUS_TONE: Record<string, "neutral" | "info" | "success" | "warning"> = {
  draft: "neutral",
  ready_for_review: "info",
  published: "success",
  archived: "warning",
};

/** design.md §33/§42 — report list + create flow, replacing the previous
 * static "not available yet" empty state now that the report/report_section/
 * report_evidence_link/report_export tables and API exist. */
export function ReportsList() {
  const { data, isLoading, isError, error } = useReports();
  const createReport = useCreateReport();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");

  const handleCreate = () => {
    if (!title.trim()) return;
    createReport.mutate(
      { title: title.trim() },
      { onSuccess: (report) => navigate(`/reports/${report.id}`) },
    );
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <div>
        <h1 className="text-heading-xl">Reports</h1>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          Convert selected themes and insights into an executive-ready, evidence-linked report.
        </p>
      </div>

      <div className="flex items-end gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4">
        <div className="flex-1">
          <label htmlFor="new-report-title" className="text-label-md text-[var(--color-text-secondary)]">
            New report title
          </label>
          <Input
            id="new-report-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Q3 Discovery Findings"
            className="mt-1"
          />
        </div>
        <Button onClick={handleCreate} loading={createReport.isPending} disabled={!title.trim()}>
          <Icon icon={Plus} size="dense" aria-hidden />
          Create report
        </Button>
      </div>

      {createReport.isError ? (
        <WarningBanner severity="error" title="Could not create report">
          {createReport.error instanceof ApiError
            ? createReport.error.message
            : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {isError ? (
        <WarningBanner severity="error" title="Could not load reports">
          {error instanceof ApiError ? error.message : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : null}

      {data && data.reports.length === 0 ? (
        <div className="rounded-[var(--radius-xl)] border border-dashed border-[var(--color-border-default)] p-10 text-center">
          <Icon icon={FileText} size="feature" className="mx-auto text-[var(--color-text-tertiary)]" />
          <p className="text-heading-sm mt-3">No reports yet</p>
          <p className="text-body-md measure-narrative mx-auto mt-2 text-[var(--color-text-secondary)]">
            Give your first report a title above to start — you'll pick themes and insights to
            include on the next screen.
          </p>
        </div>
      ) : null}

      {data && data.reports.length > 0 ? (
        <StaggerList className="flex flex-col gap-3">
          {data.reports.map((report) => (
            <div
              key={report.id}
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/reports/${report.id}`)}
              onKeyDown={(e) =>
                (e.key === "Enter" || e.key === " ") && navigate(`/reports/${report.id}`)
              }
              className="flex cursor-pointer items-center justify-between rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4 transition-colors hover:border-[var(--color-border-strong)]"
            >
              <div>
                <h3 className="text-heading-sm">{report.title}</h3>
                {report.subtitle ? (
                  <p className="text-body-sm text-[var(--color-text-secondary)]">{report.subtitle}</p>
                ) : null}
              </div>
              <Badge tone={STATUS_TONE[report.status] ?? "neutral"}>
                {report.status.replace(/_/g, " ")}
              </Badge>
            </div>
          ))}
        </StaggerList>
      ) : null}
    </div>
  );
}
