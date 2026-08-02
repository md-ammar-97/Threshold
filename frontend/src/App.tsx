import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppQueryProvider } from "@/lib/query-client/provider";
import { EvidenceExplorer } from "@/features/evidence/evidence-explorer";
import { InsightDetail } from "@/features/insights/insight-detail";
import { InsightsExplorer } from "@/features/insights/insights-explorer";
import { OverviewDashboard } from "@/features/overview/overview-dashboard";
import { RunsWorkspace } from "@/features/pipeline-runs/runs-workspace";
import { ReportEditor } from "@/features/reports/report-editor";
import { AskWorkspace } from "@/features/research-query/ask-workspace";
import { ThemeDetail } from "@/features/themes/theme-detail";
import { ThemesExplorer } from "@/features/themes/themes-explorer";
import { ValidationWorkspace } from "@/features/validation/validation-workspace";
import MethodologyPage from "@/pages/methodology-page";
import ReportsPage from "@/pages/reports-page";

export function App() {
  return (
    <BrowserRouter>
      <AppQueryProvider>
        <TooltipProvider>
          <AppShell>
            <Routes>
              <Route path="/" element={<OverviewDashboard />} />
              <Route path="/themes" element={<ThemesExplorer />} />
              <Route path="/themes/:themeId" element={<ThemeDetail />} />
              <Route path="/insights" element={<InsightsExplorer />} />
              <Route path="/insights/:insightId" element={<InsightDetail />} />
              <Route path="/ask" element={<AskWorkspace />} />
              <Route path="/evidence" element={<EvidenceExplorer />} />
              <Route path="/validation" element={<ValidationWorkspace />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/reports/:reportId" element={<ReportEditor />} />
              <Route path="/runs" element={<RunsWorkspace />} />
              <Route path="/methodology" element={<MethodologyPage />} />
            </Routes>
          </AppShell>
        </TooltipProvider>
      </AppQueryProvider>
    </BrowserRouter>
  );
}
