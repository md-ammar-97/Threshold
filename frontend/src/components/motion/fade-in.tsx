import { motion } from "motion/react";
import type { ReactNode } from "react";

import { usePrefersReducedMotion } from "@/components/motion/reduced-motion";
import { motionTokens } from "@/components/motion/motion-tokens";

/** design.md §39.1 — page/section content fades in and translates 6px
 * upward; reduced motion drops the translate and shortens the fade. */
export function FadeIn({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  const reduced = usePrefersReducedMotion();

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: reduced ? 0 : 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: reduced ? motionTokens.duration.instant : motionTokens.duration.standard,
        ease: motionTokens.ease.enter,
        delay: reduced ? 0 : delay,
      }}
    >
      {children}
    </motion.div>
  );
}
