import { useState } from "react";
import { Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { WarningBanner } from "@/components/research/warning-banner";
import { ApiError } from "@/lib/api/client";
import { type ReportExport, useCreateExport, useEmailExport } from "@/lib/api/reports";

/** design.md §33.5 export preview — Markdown and JSON only (matching the
 * backend, which documents PDF as a deferred, not-yet-renderable format).
 * "Email this report" only appears for a completed Markdown export — the
 * backend only supports emailing that format today. */
export function ExportPanel({ reportId }: { reportId: string }) {
  const createExport = useCreateExport(reportId);
  const [lastExport, setLastExport] = useState<ReportExport | null>(null);
  const [recipientEmail, setRecipientEmail] = useState("");
  const emailExport = useEmailExport(reportId, lastExport?.id ?? null);

  const runExport = (format: "markdown" | "json") => {
    createExport.mutate(format, { onSuccess: (result) => setLastExport(result) });
  };

  const handleEmail = () => {
    if (!recipientEmail.trim()) return;
    emailExport.mutate(recipientEmail.trim());
  };

  const previewText =
    lastExport?.content == null
      ? null
      : typeof lastExport.content === "string"
        ? lastExport.content
        : JSON.stringify(lastExport.content, null, 2);

  const canEmail = lastExport?.status === "completed" && lastExport.export_format === "markdown";

  return (
    <div className="flex h-fit flex-col gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4">
      <h2 className="text-heading-sm">Export</h2>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => runExport("markdown")}
          loading={createExport.isPending}
        >
          Markdown
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => runExport("json")}
          loading={createExport.isPending}
        >
          JSON
        </Button>
      </div>

      {createExport.isError ? (
        <WarningBanner severity="error" title="Export failed">
          {createExport.error instanceof ApiError
            ? createExport.error.message
            : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {lastExport && lastExport.status !== "completed" ? (
        <WarningBanner severity="caution" title={`Export ${lastExport.status}`}>
          {lastExport.failure_message ?? "The export did not complete."}
        </WarningBanner>
      ) : null}

      {previewText ? (
        <pre className="text-body-sm max-h-96 overflow-auto rounded-[var(--radius-md)] bg-[var(--color-bg-surface-subtle)] p-3">
          {previewText}
        </pre>
      ) : null}

      {canEmail ? (
        <div className="flex flex-col gap-2 border-t border-[var(--color-border-default)] pt-3">
          <label htmlFor="report-email-recipient" className="text-label-md text-[var(--color-text-secondary)]">
            Email this report
          </label>
          <div className="flex gap-2">
            <Input
              id="report-email-recipient"
              type="email"
              value={recipientEmail}
              onChange={(e) => setRecipientEmail(e.target.value)}
              placeholder="name@company.com"
              className="flex-1"
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={handleEmail}
              loading={emailExport.isPending}
              disabled={!recipientEmail.trim()}
            >
              <Icon icon={Mail} size="dense" aria-hidden />
              Send
            </Button>
          </div>

          {emailExport.isError ? (
            <WarningBanner
              severity={
                emailExport.error instanceof ApiError && emailExport.error.status === 503
                  ? "caution"
                  : "error"
              }
              title={
                emailExport.error instanceof ApiError && emailExport.error.status === 503
                  ? "Email delivery isn't configured"
                  : "Could not send email"
              }
            >
              {emailExport.error instanceof ApiError
                ? emailExport.error.message
                : "An unexpected error occurred."}
            </WarningBanner>
          ) : null}

          {emailExport.isSuccess ? (
            <p className="text-body-sm text-[var(--color-status-success)]">
              Sent to {emailExport.data.recipient_email}.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
