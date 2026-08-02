import { motion } from "motion/react";
import type { ReactNode } from "react";

import { motionTokens } from "@/components/motion/motion-tokens";
import { usePrefersReducedMotion } from "@/components/motion/reduced-motion";

const MAX_STAGGERED_ITEMS = 8;
const MAX_STAGGER_MS = 30;

/** design.md §39.2 — list/card reveal: stagger capped at 30ms/item and at
 * most the first 8 items; the rest appear immediately (no stagger debt on
 * large result sets). */
export function StaggerList({ children, className }: { children: ReactNode[]; className?: string }) {
  const reduced = usePrefersReducedMotion();

  return (
    <div className={className}>
      {children.map((child, index) => (
        <motion.div
          key={index}
          initial={{ opacity: 0, y: reduced ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: reduced ? motionTokens.duration.instant : motionTokens.duration.standard,
            ease: motionTokens.ease.enter,
            delay: reduced || index >= MAX_STAGGERED_ITEMS ? 0 : (index * MAX_STAGGER_MS) / 1000,
          }}
        >
          {child}
        </motion.div>
      ))}
    </div>
  );
}
