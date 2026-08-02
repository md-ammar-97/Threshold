import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { IconButton } from "@/components/ui/icon-button";

type Appearance = "light" | "dark";

const STORAGE_KEY = "instamart-appearance";

function applyAppearance(appearance: Appearance) {
  const root = document.documentElement;
  root.classList.remove("light", "dark");
  root.classList.add(appearance);
}

function getInitialAppearance(): Appearance {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(STORAGE_KEY) as Appearance | null;
  return stored ?? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

/** design.md §16 — top-bar theme toggle. tokens.css already defines the
 * `.dark` class overrides and an OS-preference media-query fallback; this
 * component only needs to manage the explicit user override + persistence.
 * Initial appearance is read lazily (avoiding an SSR `window` access); the
 * effect only applies the resulting DOM class, it never sets state. */
export function ThemeToggle() {
  const [appearance, setAppearance] = useState<Appearance>(getInitialAppearance);

  useEffect(() => {
    applyAppearance(appearance);
  }, [appearance]);

  function toggle() {
    const next: Appearance = appearance === "dark" ? "light" : "dark";
    setAppearance(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }

  return (
    <IconButton
      icon={appearance === "dark" ? Sun : Moon}
      label={appearance === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggle}
    />
  );
}
