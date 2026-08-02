import { cn } from "@/lib/utils/cn";

export function Divider({ className, orientation = "horizontal" }: { className?: string; orientation?: "horizontal" | "vertical" }) {
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={cn(
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        "bg-[var(--color-border-default)]",
        className,
      )}
    />
  );
}
