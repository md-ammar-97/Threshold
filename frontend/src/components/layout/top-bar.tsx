import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/layout/theme-toggle";

/** design.md §16 — sticky, visually quiet utility bar: page context on the
 * left, appearance/dataset controls on the right. Command menu (⌘K) is
 * deferred — see docs/implementationplan.md Phase 7 status note. */
export function TopBar({ children }: { children?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[var(--color-border-default)] bg-[var(--color-bg-surface)]/95 px-6 backdrop-blur">
      <div className="min-w-0">{children}</div>
      <div className="flex items-center gap-2">
        <ThemeToggle />
      </div>
    </header>
  );
}
