import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

/** design.md §20.1 — default 40px height, 2px focus ring, no layout shift;
 * error state stays visible after blur until corrected (aria-invalid drives
 * the border color, so callers just pass the flag through). */
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      // Browser extensions (coupon/shopping/password-manager style) inject
      // attributes like data-sharkid into <input> elements before React
      // hydrates, causing an unavoidable client/server attribute mismatch
      // that has nothing to do with this component's own markup.
      suppressHydrationWarning
      className={cn(
        "text-body-md h-10 w-full rounded-[var(--radius-md)] border border-[var(--color-border-default)]",
        "bg-[var(--color-bg-surface)] px-3 text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-border-focus)]",
        "aria-[invalid=true]:border-[var(--color-status-danger)]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
