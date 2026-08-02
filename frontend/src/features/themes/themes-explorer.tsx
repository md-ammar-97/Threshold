import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerList } from "@/components/motion/stagger-list";
import { ThemeCard } from "@/components/research/theme-card";
import { WarningBanner } from "@/components/research/warning-banner";
import { ApiError } from "@/lib/api/client";
import { useThemes } from "@/lib/api/themes";

const ALL_THEME_TYPES = "all";

function formatThemeType(themeType: string): string {
  return themeType.replace(/_/g, " ");
}

/** design.md §28 — ranked list is the default view; comparison mode and the
 * visual-grid view are deferred (see docs/implementationplan.md Phase 7
 * status note). */
export function ThemesExplorer() {
  const { data, isLoading, isError, error } = useThemes();
  const navigate = useNavigate();
  const [selectedType, setSelectedType] = useState(ALL_THEME_TYPES);

  const availableTypes = useMemo(() => {
    const types = new Set((data?.themes ?? []).map((theme) => theme.theme_type));
    return Array.from(types).sort();
  }, [data]);

  const visibleThemes = useMemo(() => {
    if (!data) return [];
    if (selectedType === ALL_THEME_TYPES) return data.themes;
    return data.themes.filter((theme) => theme.theme_type === selectedType);
  }, [data, selectedType]);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <div>
        <h1 className="text-heading-xl">Themes</h1>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          Recurring patterns across evidence, ranked by opportunity score.
        </p>
      </div>

      {isError ? (
        <WarningBanner severity="error" title="Could not load themes">
          {error instanceof ApiError ? error.message : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : null}

      {data && data.themes.length === 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-default)] p-8 text-center">
          <p className="text-body-md text-[var(--color-text-secondary)]">
            No theme set has been produced yet. Run clustering (Phase 3) against ingested evidence to see
            themes here.
          </p>
        </div>
      ) : null}

      {data && data.themes.length > 0 ? (
        <div className="max-w-xs">
          <Select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            aria-label="Filter themes by type"
          >
            <option value={ALL_THEME_TYPES}>All types</option>
            {availableTypes.map((themeType) => (
              <option key={themeType} value={themeType}>
                {formatThemeType(themeType)}
              </option>
            ))}
          </Select>
        </div>
      ) : null}

      {data && data.themes.length > 0 && visibleThemes.length === 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-default)] p-8 text-center">
          <p className="text-body-md text-[var(--color-text-secondary)]">
            No themes match this filter.
          </p>
        </div>
      ) : null}

      {visibleThemes.length > 0 ? (
        <StaggerList className="flex flex-col gap-3">
          {visibleThemes.map((theme) => (
            <ThemeCard
              key={theme.id}
              name={theme.name}
              themeType={theme.theme_type}
              shortSummary={theme.short_summary}
              recordCount={theme.representative_record_count}
              confidenceScore={theme.confidence_score}
              opportunityScore={theme.opportunity_score}
              tags={theme.tags}
              onOpen={() => navigate(`/themes/${theme.id}`)}
            />
          ))}
        </StaggerList>
      ) : null}
    </div>
  );
}
