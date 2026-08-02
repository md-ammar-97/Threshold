import { cn } from "@/lib/utils/cn";

/** design.md §8.3 — excerpts get the wider 88ch measure in detail views,
 * and must remain the visually dominant element over surrounding metadata
 * (§22.5). */
export function EvidenceExcerpt({ text, className }: { text: string; className?: string }) {
  return <p className={cn("text-body-md measure-excerpt text-[var(--color-text-primary)]", className)}>&ldquo;{text}&rdquo;</p>;
}
