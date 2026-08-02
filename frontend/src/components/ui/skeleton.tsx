import { cn } from "@/lib/utils/cn";

/** design.md §41 — structural skeletons matching the final layout for
 * initial page loads; never a centered spinner for full-page data views. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-pulse rounded-[var(--radius-sm)] bg-[var(--color-bg-surface-muted)] motion-reduce:animate-none",
        className,
      )}
    />
  );
}
