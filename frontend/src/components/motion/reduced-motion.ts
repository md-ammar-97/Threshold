import { useEffect, useState } from "react";

function getInitialPreference(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** design.md §40 — reduced-motion is read once (lazily, avoiding an SSR
 * `window` access) and kept in sync with live OS-preference changes via a
 * subscription, so animated components can switch to instant/fade
 * fallbacks without a page reload. */
export function usePrefersReducedMotion(): boolean {
  const [prefersReduced, setPrefersReduced] = useState(getInitialPreference);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const listener = (event: MediaQueryListEvent) => setPrefersReduced(event.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);

  return prefersReduced;
}
