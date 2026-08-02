import { forwardRef } from "react";
import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      // Same rationale as Input — browser extensions inject attributes
      // into form elements before React hydrates.
      suppressHydrationWarning
      className={cn(
        "text-body-md min-h-24 w-full resize-y rounded-[var(--radius-md)] border border-[var(--color-border-default)]",
        "bg-[var(--color-bg-surface)] px-3 py-2 text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-border-focus)]",
        "aria-[invalid=true]:border-[var(--color-status-danger)]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";
