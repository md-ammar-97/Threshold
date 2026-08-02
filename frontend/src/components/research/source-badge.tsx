import { Badge } from "@/components/ui/badge";

/** design.md §7.4 — source identity stays secondary to research meaning: a
 * small neutral badge, never a source-driven color system. */
export function SourceBadge({ source }: { source: string }) {
  return <Badge tone="neutral">{source}</Badge>;
}
