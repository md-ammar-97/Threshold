import { ChevronDown } from "lucide-react";
import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

/** Native <select>, styled to match Input/Button — no Radix Select
 * dependency needed for a plain single-choice dropdown. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <div className="relative inline-block">
      <select
        ref={ref}
        // Same rationale as Input/Textarea — browser extensions inject
        // attributes into form elements before React hydrates.
        suppressHydrationWarning
        className={cn(
          "text-body-md h-10 w-full appearance-none rounded-[var(--radius-md)] border border-[var(--color-border-default)]",
          "bg-[var(--color-bg-surface)] py-2 pl-3 pr-9 text-[var(--color-text-primary)]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-border-focus)]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-[var(--color-text-tertiary)]"
      />
    </div>
  ),
);
Select.displayName = "Select";
