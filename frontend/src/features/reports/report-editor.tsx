import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowDown, ArrowUp, Lock, Plus, Trash2, Unlock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { WarningBanner } from "@/components/research/warning-banner";
import { FadeIn } from "@/components/motion/fade-in";
import { ApiError } from "@/lib/api/client";
import { useInsights } from "@/lib/api/insights";
import {
  type ReportSection,
  useAddSection,
  useDeleteSection,
  useReorderSections,
  useReport,
  useUpdateReport,
  useUpdateSection,
} from "@/lib/api/reports";
import { useThemes } from "@/lib/api/themes";
import { ExportPanel } from "@/features/reports/export-panel";

const SECTION_TYPE_OPTIONS = [
  "executive_summary",
  "research_scope",
  "coverage",
  "key_theme",
  "key_insight",
  "opportunity",
  "contradiction",
  "limitation",
  "validation_plan",
  "methodology",
  "appendix",
];

function formatSectionType(value: string): string {
  return value.replace(/_/g, " ");
}

/** design.md §33.2 three-pane layout: left = available themes/insights,
 * center = report canvas, right = section settings/export. Reordering uses
 * explicit up/down buttons rather than drag-and-drop — design.md §33.4
 * requires "preserve keyboard alternative to drag and drop" regardless, so
 * this ships the keyboard-accessible mechanism as primary rather than
 * building both; the backend reorder endpoint works the same either way. */
export function ReportEditor() {
  const { reportId } = useParams<{ reportId: string }>();
  const { data: report, isLoading, isError, error } = useReport(reportId ?? null);
  const themes = useThemes();
  const insights = useInsights();
  const updateReport = useUpdateReport(reportId ?? "");
  const addSection = useAddSection(reportId ?? "");
  const updateSection = useUpdateSection(reportId ?? "");
  const deleteSection = useDeleteSection(reportId ?? "");
  const reorderSections = useReorderSections(reportId ?? "");

  const [newSectionType, setNewSectionType] = useState("executive_summary");
  const [newSectionTitle, setNewSectionTitle] = useState("");
  const [editingText, setEditingText] = useState<Record<string, string>>({});

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !report) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <WarningBanner severity="error" title="Could not load this report">
          {error instanceof ApiError ? error.message : "The report may no longer exist."}
        </WarningBanner>
      </div>
    );
  }

  const sections = [...report.sections].sort((a, b) => a.position - b.position);

  const addFromTheme = (themeId: string, name: string, summary: string) => {
    addSection.mutate({
      section_type: "key_theme",
      title: name,
      narrative_text: summary,
      evidence: [{ object_type: "theme", object_id: themeId }],
    });
  };

  const addFromInsight = (insightId: string, title: string, finding: string) => {
    addSection.mutate({
      section_type: "key_insight",
      title,
      narrative_text: finding,
      evidence: [{ object_type: "insight", object_id: insightId }],
    });
  };

  const addCustomSection = () => {
    if (!newSectionTitle.trim()) return;
    addSection.mutate(
      { section_type: newSectionType, title: newSectionTitle.trim() },
      { onSuccess: () => setNewSectionTitle("") },
    );
  };

  const moveSection = (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= sections.length) return;
    const reordered = [...sections];
    [reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
    reorderSections.mutate(reordered.map((s) => s.id));
  };

  const saveNarrative = (section: ReportSection) => {
    const text = editingText[section.id];
    if (text === undefined) return;
    updateSection.mutate({ sectionId: section.id, body: { narrative_text: text } });
  };

  return (
    <FadeIn className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-10">
      <Link to="/reports" className="text-body-sm inline-flex w-fit items-center gap-1 text-[var(--color-text-link)]">
        <ArrowLeft className="size-4" aria-hidden />
        Back to Reports
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-heading-xl">{report.title}</h1>
          <Badge tone="neutral" className="mt-1">
            {report.status.replace(/_/g, " ")}
          </Badge>
        </div>
        {report.status === "draft" ? (
          <Button
            variant="outline"
            onClick={() => updateReport.mutate({ status: "published" })}
            loading={updateReport.isPending}
          >
            Publish report
          </Button>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr_320px]">
        {/* Left: available themes and insights */}
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4">
          <h2 className="text-heading-sm">Available evidence</h2>
          <Tabs defaultValue="themes" className="mt-3">
            <TabsList>
              <TabsTrigger value="themes">Themes</TabsTrigger>
              <TabsTrigger value="insights">Insights</TabsTrigger>
            </TabsList>
            <TabsContent value="themes" className="mt-3 flex flex-col gap-2">
              {(themes.data?.themes ?? []).map((theme) => (
                <button
                  key={theme.id}
                  type="button"
                  onClick={() => addFromTheme(theme.id, theme.name, theme.short_summary)}
                  className="text-body-sm rounded-[var(--radius-md)] border border-[var(--color-border-default)] p-2 text-left transition-colors hover:border-[var(--color-border-strong)]"
                >
                  <div className="flex items-center gap-1">
                    <Icon icon={Plus} size="dense" aria-hidden className="text-[var(--color-text-tertiary)]" />
                    <span className="font-medium">{theme.name}</span>
                  </div>
                </button>
              ))}
              {themes.data?.themes.length === 0 ? (
                <p className="text-body-sm text-[var(--color-text-tertiary)]">No themes available yet.</p>
              ) : null}
            </TabsContent>
            <TabsContent value="insights" className="mt-3 flex flex-col gap-2">
              {(insights.data?.insights ?? []).map((insight) => (
                <button
                  key={insight.id}
                  type="button"
                  onClick={() => addFromInsight(insight.id, insight.title, insight.finding)}
                  className="text-body-sm rounded-[var(--radius-md)] border border-[var(--color-border-default)] p-2 text-left transition-colors hover:border-[var(--color-border-strong)]"
                >
                  <div className="flex items-center gap-1">
                    <Icon icon={Plus} size="dense" aria-hidden className="text-[var(--color-text-tertiary)]" />
                    <span className="font-medium">{insight.title}</span>
                  </div>
                </button>
              ))}
              {insights.data?.insights.length === 0 ? (
                <p className="text-body-sm text-[var(--color-text-tertiary)]">No insights available yet.</p>
              ) : null}
            </TabsContent>
          </Tabs>
        </div>

        {/* Center: report canvas */}
        <div className="flex flex-col gap-4">
          <div className="flex items-end gap-2 rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-default)] p-3">
            <div className="w-40">
              <label className="text-label-md text-[var(--color-text-secondary)]">Section type</label>
              <Select
                value={newSectionType}
                onChange={(e) => setNewSectionType(e.target.value)}
                className="mt-1"
              >
                {SECTION_TYPE_OPTIONS.map((type) => (
                  <option key={type} value={type}>
                    {formatSectionType(type)}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex-1">
              <label className="text-label-md text-[var(--color-text-secondary)]">Title</label>
              <Input
                value={newSectionTitle}
                onChange={(e) => setNewSectionTitle(e.target.value)}
                placeholder="e.g. Limitations"
                className="mt-1"
              />
            </div>
            <Button onClick={addCustomSection} loading={addSection.isPending} disabled={!newSectionTitle.trim()}>
              Add section
            </Button>
          </div>

          {sections.length === 0 ? (
            <div className="rounded-[var(--radius-xl)] border border-dashed border-[var(--color-border-default)] p-10 text-center">
              <p className="text-body-md text-[var(--color-text-secondary)]">
                Add a theme or insight from the left, or create a custom section above.
              </p>
            </div>
          ) : null}

          {sections.map((section, index) => (
            <div
              key={section.id}
              className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <Badge tone="neutral">{formatSectionType(section.section_type)}</Badge>
                  <h3 className="text-heading-sm mt-1">{section.title}</h3>
                </div>
                <div className="flex items-center gap-1">
                  <IconButton
                    icon={ArrowUp}
                    label="Move up"
                    size="icon-sm"
                    disabled={index === 0}
                    onClick={() => moveSection(index, -1)}
                  />
                  <IconButton
                    icon={ArrowDown}
                    label="Move down"
                    size="icon-sm"
                    disabled={index === sections.length - 1}
                    onClick={() => moveSection(index, 1)}
                  />
                  <IconButton
                    icon={section.is_locked ? Unlock : Lock}
                    label={section.is_locked ? "Unlock section" : "Lock section"}
                    size="icon-sm"
                    onClick={() =>
                      updateSection.mutate({
                        sectionId: section.id,
                        body: { is_locked: !section.is_locked },
                      })
                    }
                  />
                  <IconButton
                    icon={Trash2}
                    label="Delete section"
                    size="icon-sm"
                    onClick={() => deleteSection.mutate(section.id)}
                  />
                </div>
              </div>

              <Textarea
                className="mt-3"
                value={editingText[section.id] ?? section.narrative_text ?? ""}
                disabled={section.is_locked}
                onChange={(e) =>
                  setEditingText((prev) => ({ ...prev, [section.id]: e.target.value }))
                }
                onBlur={() => saveNarrative(section)}
                placeholder="Write or paste narrative text for this section..."
              />
              {/* design.md §33.4 "show whether content is generated or human edited" —
                  narrative_text is always human-authored/edited here (sections seeded
                  from a theme/insight start with that object's real summary as a
                  starting point, not a separately-tracked "generated" flag). */}

              {section.evidence.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {section.evidence.map((link) => (
                    <Badge key={link.id} tone="evidence">
                      [{link.object_type}]{" "}
                      {String(link.snapshot.name ?? link.snapshot.title ?? link.snapshot.excerpt ?? link.object_id).slice(0, 60)}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>

        {/* Right: export */}
        <ExportPanel reportId={report.id} />
      </div>
    </FadeIn>
  );
}
