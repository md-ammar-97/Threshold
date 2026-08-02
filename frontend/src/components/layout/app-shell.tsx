import type { ReactNode } from "react";

import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";

/** design.md Part II — persistent shell: sidebar + top bar + scrollable
 * content region. A skip link (§47.2) lets keyboard users jump past
 * navigation. TopBar carries the appearance toggle — it must be mounted
 * here or the toggle is unreachable regardless of how it's implemented. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="main-content" className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
