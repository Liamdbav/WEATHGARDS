import { useState } from "react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { MCPServerPanel } from "./components/MCPServerPanel";
import { ScanDashboard } from "./components/ScanDashboard";
import { SettingsPage } from "./components/SettingsPage";
import { ToastProvider } from "./components/Toast";
import { ToolsPage } from "./components/ToolsPage";
import { useScan } from "./hooks/useScan";

export type View = "scan" | "tools" | "mcp" | "settings";

export default function App() {
  const { scanState, healthState, triggerScan } = useScan();
  const [view, setView] = useState<View>("scan");

  return (
    <ErrorBoundary>
      <ToastProvider>
        <Layout healthState={healthState} activeView={view} onNavigate={setView}>
          {view === "scan" && (
            <ScanDashboard
              scanState={scanState}
              healthState={healthState}
              onTrigger={triggerScan}
            />
          )}
          {view === "tools" && <ToolsPage />}
          {view === "mcp" && <MCPServerPanel />}
          {view === "settings" && <SettingsPage />}
        </Layout>
      </ToastProvider>
    </ErrorBoundary>
  );
}
