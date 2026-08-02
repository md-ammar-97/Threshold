import type { ReactNode } from "react";

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="text-code-sm inline-flex items-center rounded-[var(--radius-xs)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface-subtle)] px-1.5 py-0.5 text-[var(--color-text-secondary)]">
      {children}
    </kbd>
  );
}
