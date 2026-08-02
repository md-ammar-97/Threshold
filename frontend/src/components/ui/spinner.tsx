import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils/cn";

export interface SpinnerProps {
  className?: string;
  label?: string;
}

/** design.md §41 — used for incremental/region loading, never a centered
 * full-page spinner (that case uses Skeleton instead). */
export function Spinner({ className, label = "Loading" }: SpinnerProps) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <Loader2
        aria-hidden
        strokeWidth={2}
        className={cn("size-4 animate-spin text-[var(--color-text-tertiary)] motion-reduce:animate-none", className)}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
