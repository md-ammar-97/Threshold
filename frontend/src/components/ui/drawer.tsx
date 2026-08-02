import * as RadixDialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { IconButton } from "@/components/ui/icon-button";
import { motionTokens } from "@/components/motion/motion-tokens";
import { usePrefersReducedMotion } from "@/components/motion/reduced-motion";
import { cn } from "@/lib/utils/cn";

export interface DrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  widthClassName?: string;
}

/** design.md §25.2 (evidence inspector) / §39.3 (inspector transition).
 * Right-side panel on desktop, full-screen on mobile via responsive width.
 * Uses Radix's `forceMount` + Framer Motion `AnimatePresence` so the panel
 * slides in/out while Radix still owns focus trapping, Escape-to-close, and
 * focus restoration to the triggering element. */
export function Drawer({ open, onOpenChange, title, children, footer, widthClassName = "sm:max-w-[400px]" }: DrawerProps) {
  const reduced = usePrefersReducedMotion();

  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open ? (
          <RadixDialog.Portal forceMount>
            <RadixDialog.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-40 bg-[var(--color-bg-scrim)]"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: motionTokens.duration.fast }}
              />
            </RadixDialog.Overlay>
            <RadixDialog.Content asChild forceMount>
              <motion.div
                className={cn(
                  "fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-[var(--color-border-default)]",
                  "bg-[var(--color-bg-elevated)] shadow-[var(--shadow-md)] outline-none",
                  widthClassName,
                )}
                initial={{ opacity: 0, x: reduced ? 0 : 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: reduced ? 0 : 24 }}
                transition={{ duration: motionTokens.duration.standard, ease: motionTokens.ease.enter }}
              >
                <div className="flex items-center justify-between border-b border-[var(--color-border-default)] px-5 py-4">
                  <RadixDialog.Title className="text-heading-sm">{title}</RadixDialog.Title>
                  <RadixDialog.Close asChild>
                    <IconButton icon={X} label="Close" />
                  </RadixDialog.Close>
                </div>
                <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
                {footer ? <div className="border-t border-[var(--color-border-default)] px-5 py-4">{footer}</div> : null}
              </motion.div>
            </RadixDialog.Content>
          </RadixDialog.Portal>
        ) : null}
      </AnimatePresence>
    </RadixDialog.Root>
  );
}
