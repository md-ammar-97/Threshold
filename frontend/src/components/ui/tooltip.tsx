import * as RadixTooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <RadixTooltip.Provider delayDuration={300} skipDelayDuration={100}>
      {children}
    </RadixTooltip.Provider>
  );
}

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}

/** design.md §13/§47.3 — required for icon-only controls and any
 * abbreviated label (confidence, evidence role, etc.) that needs a plain-
 * language explanation. Built on Radix so keyboard focus + Escape-to-close
 * behave correctly out of the box. */
export function Tooltip({ content, children, side = "top" }: TooltipProps) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          side={side}
          sideOffset={6}
          className={cn(
            "text-body-sm z-50 max-w-64 rounded-[var(--radius-md)] border border-[var(--color-border-default)]",
            "bg-[var(--color-bg-elevated)] px-3 py-2 text-[var(--color-text-primary)] shadow-[var(--shadow-sm)]",
          )}
        >
          {content}
          <RadixTooltip.Arrow className="fill-[var(--color-bg-elevated)]" />
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
