/** design.md §38/§53 — shared Framer Motion tokens. Feature components must
 * import these rather than defining arbitrary durations/easings inline. */
export const motionTokens = {
  duration: {
    instant: 0.08,
    fast: 0.14,
    standard: 0.22,
    slow: 0.36,
    reveal: 0.52,
  },
  ease: {
    standard: [0.2, 0.8, 0.2, 1] as [number, number, number, number],
    enter: [0.16, 1, 0.3, 1] as [number, number, number, number],
    exit: [0.4, 0, 1, 1] as [number, number, number, number],
  },
};

export const motionSpring = {
  snappy: { type: "spring" as const, stiffness: 420, damping: 34, mass: 0.75 },
  standard: { type: "spring" as const, stiffness: 330, damping: 30, mass: 0.85 },
  gentle: { type: "spring" as const, stiffness: 220, damping: 28, mass: 1 },
};
