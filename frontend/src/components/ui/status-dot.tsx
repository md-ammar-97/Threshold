import { cn } from "@/lib/utils/cn";

export type StatusTone = "neutral" | "success" | "warning" | "danger" | "info";

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "bg-[var(--color-text-tertiary)]",
  success: "bg-[var(--color-status-success)]",
  warning: "bg-[var(--color-status-warning)]",
  danger: "bg-[var(--color-status-danger)]",
  info: "bg-[var(--color-status-info)]",
};

/** A dynamic-status dot (run/job/connector state). Always pair with a text
 * label at the call site — never the sole indicator (§47.6). */
export function StatusDot({ tone = "neutral", className }: { tone?: StatusTone; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 rounded-full", TONE_CLASSES[tone], className)} />;
}
