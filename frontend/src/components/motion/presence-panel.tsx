import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";

import { motionTokens } from "@/components/motion/motion-tokens";
import { usePrefersReducedMotion } from "@/components/motion/reduced-motion";

/** design.md §39.3 — inspector transition: slides 24px from the right and
 * fades; reduced motion collapses to a plain fade. */
export function PresencePanel({ open, children, className }: { open: boolean; children: ReactNode; className?: string }) {
  const reduced = usePrefersReducedMotion();

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0, x: reduced ? 0 : 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: reduced ? 0 : 24 }}
          transition={{ duration: motionTokens.duration.standard, ease: motionTokens.ease.enter }}
          className={className}
        >
          {children}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
