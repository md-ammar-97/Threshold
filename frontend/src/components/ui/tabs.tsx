import * as RadixTabs from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils/cn";

// eslint-disable-next-line react-refresh/only-export-components -- intentional Radix primitive re-export, not a component definition
export const Tabs = RadixTabs.Root;

export function TabsList({ className, ...props }: React.ComponentProps<typeof RadixTabs.List>) {
  return (
    <RadixTabs.List
      className={cn("inline-flex items-center gap-1 rounded-[var(--radius-md)] bg-[var(--color-bg-surface-subtle)] p-1", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof RadixTabs.Trigger>) {
  return (
    <RadixTabs.Trigger
      className={cn(
        "text-label-lg rounded-[var(--radius-sm)] px-3 py-1.5 text-[var(--color-text-secondary)] transition-colors",
        "data-[state=active]:bg-[var(--color-bg-surface)] data-[state=active]:text-[var(--color-text-primary)] data-[state=active]:shadow-[var(--shadow-xs)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-border-focus)]",
        className,
      )}
      {...props}
    />
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- intentional Radix primitive re-export, not a component definition
export const TabsContent = RadixTabs.Content;
