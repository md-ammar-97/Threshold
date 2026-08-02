import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils/cn";

/** design.md §13 — one consistent outline icon library (Lucide) at fixed
 * sizes/stroke width so features never hand-pick arbitrary icon dimensions. */
const ICON_SIZE = {
  dense: 16,
  control: 18,
  nav: 20,
  feature: 24,
} as const;

export type IconSize = keyof typeof ICON_SIZE;

export interface IconProps {
  icon: LucideIcon;
  size?: IconSize;
  className?: string;
  "aria-hidden"?: boolean;
}

export function Icon({ icon: LucideIconComponent, size = "control", className, ...rest }: IconProps) {
  return (
    <LucideIconComponent
      size={ICON_SIZE[size]}
      strokeWidth={1.75}
      className={cn("shrink-0", className)}
      aria-hidden={rest["aria-hidden"] ?? true}
    />
  );
}
