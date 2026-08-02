import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

/** design.md §19 — one primary button per local action group; loading
 * state must preserve width (handled by keeping label mounted, just
 * dimmed, while the spinner takes the icon slot). */
const buttonVariants = cva(
  "text-label-lg inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-md)] font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-[var(--color-action-primary)] text-[var(--color-action-on-primary)] hover:bg-[var(--color-action-primary-hover)] active:bg-[var(--color-action-primary-active)]",
        secondary:
          "bg-[var(--color-bg-surface-subtle)] text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface-muted)]",
        outline:
          "border border-[var(--color-border-default)] bg-transparent text-[var(--color-text-primary)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-surface-subtle)]",
        ghost: "bg-transparent text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface-subtle)]",
        destructive:
          "bg-[var(--color-status-danger)] text-[var(--color-text-inverse)] hover:opacity-90",
        link: "bg-transparent p-0 text-[var(--color-text-link)] underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-9 px-3",
        md: "h-10 px-4",
        lg: "h-11 px-5",
        "icon-sm": "size-9",
        "icon-md": "size-10",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        aria-busy={loading}
        {...props}
      >
        {loading ? <Loader2 aria-hidden className="size-4 animate-spin motion-reduce:animate-none" /> : null}
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";
