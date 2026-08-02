import type { LucideIcon } from "lucide-react";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Tooltip } from "@/components/ui/tooltip";

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  icon: LucideIcon;
  label: string;
  variant?: "primary" | "secondary" | "outline" | "ghost" | "destructive";
  size?: "icon-sm" | "icon-md";
}

/** design.md §19 — icon-only buttons require an accessible label and a
 * tooltip; this component makes both mandatory rather than optional. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, label, variant = "ghost", size = "icon-md", ...props }, ref) => (
    <Tooltip content={label}>
      <Button ref={ref} variant={variant} size={size} aria-label={label} {...props}>
        <Icon icon={icon} size={size === "icon-sm" ? "dense" : "control"} />
      </Button>
    </Tooltip>
  ),
);
IconButton.displayName = "IconButton";
