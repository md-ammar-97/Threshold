import { Search } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EvidenceInspector } from "@/components/research/evidence-inspector";
import { SourceBadge } from "@/components/research/source-badge";
import { WarningBanner } from "@/components/research/warning-banner";
import { StaggerList } from "@/components/motion/stagger-list";
import { ApiError } from "@/lib/api/client";
import { useEvidenceList, useEvidenceSources } from "@/lib/api/evidence";

const ALL_SOURCES = "all";

export function EvidenceExplorer() {
  const [search, setSearch] = useState("");
  const [selectedSource, setSelectedSource] = useState(ALL_SOURCES);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: sourcesData } = useEvidenceSources();
  const { data, isLoading, isError, error } = useEvidenceList({
    search: search || undefined,
    sourceConnectorKey: selectedSource === ALL_SOURCES ? undefined : selectedSource,
  });

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <div>
        <h1 className="text-heading-xl">Evidence</h1>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          Search and inspect canonical feedback records.
        </p>
      </div>

      <div className="relative max-w-md">
        <Search aria-hidden className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search evidence text…"
          className="pl-9"
          aria-label="Search evidence"
        />
      </div>

      <Tabs value={selectedSource} onValueChange={setSelectedSource}>
        <TabsList className="flex-wrap">
          <TabsTrigger value={ALL_SOURCES}>All</TabsTrigger>
          {(sourcesData?.sources ?? []).map((source) => (
            <TabsTrigger key={source.key} value={source.key}>
              {source.display_name}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isError ? (
        <WarningBanner severity="error" title="Could not load evidence">
          {error instanceof ApiError ? error.message : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : null}

      {data ? (
        <>
          <p className="text-body-sm text-[var(--color-text-tertiary)]" aria-live="polite">
            {data.total_matching} matching record{data.total_matching === 1 ? "" : "s"}
          </p>

          {data.records.length === 0 ? (
            <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-default)] p-8 text-center">
              <p className="text-body-md text-[var(--color-text-secondary)]">
                {search || selectedSource !== ALL_SOURCES
                  ? "No records match this filter."
                  : "No evidence has been ingested yet."}
              </p>
            </div>
          ) : (
            <StaggerList className="flex flex-col gap-2">
              {data.records.map((record) => (
                <button
                  key={record.id}
                  type="button"
                  onClick={() => setSelectedId(record.id)}
                  className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4 text-left transition-colors hover:border-[var(--color-border-strong)]"
                >
                  <p className="text-body-md line-clamp-2">{record.excerpt}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <SourceBadge source={record.source_connector_key} />
                    {record.published_at ? (
                      <span className="text-body-sm text-[var(--color-text-tertiary)]">{record.published_at}</span>
                    ) : null}
                    {typeof record.rating_normalized === "number" ? (
                      <Badge tone="neutral">{(record.rating_normalized * 5).toFixed(1)}★</Badge>
                    ) : null}
                  </div>
                </button>
              ))}
            </StaggerList>
          )}
        </>
      ) : null}

      <EvidenceInspector recordId={selectedId} onOpenChange={(open) => !open && setSelectedId(null)} />
    </div>
  );
}
