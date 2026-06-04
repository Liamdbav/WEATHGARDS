import {
  Apple,
  LayoutDashboard,
  Monitor,
  Radio,
  Settings,
  Terminal,
  Zap,
} from "lucide-react";
import { type ReactNode } from "react";
import { type View } from "../App";
import { type HealthState } from "../hooks/useScan";
import { StatusBadge } from "./StatusBadge";

// ---------------------------------------------------------------------------
// OS badge — clickable, opens Settings
// ---------------------------------------------------------------------------

function OsBadge({
  os,
  onClick,
}: {
  os: string;
  onClick: () => void;
}) {
  const norm = os.toLowerCase();
  let Icon = Monitor;
  let label = os;

  if (norm.includes("linux")) { Icon = Terminal; label = "Linux"; }
  else if (norm.includes("darwin") || norm.includes("mac")) { Icon = Apple; label = "macOS"; }
  else if (norm.includes("windows")) { Icon = Monitor; label = "Windows"; }

  return (
    <button
      onClick={onClick}
      title="Ouvrir les paramètres"
      className="inline-flex items-center gap-1.5 rounded-lg border border-wg-border bg-wg-card px-2.5 py-1 font-mono text-xs text-wg-text transition-all duration-200 hover:border-wg-cyan/30 hover:text-wg-cyan active:scale-95"
    >
      <Icon className="h-3 w-3 text-wg-muted" />
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Sidebar nav definition
// ---------------------------------------------------------------------------

const NAV: { id: View; label: string; Icon: typeof LayoutDashboard }[] = [
  { id: "scan", label: "Dashboard", Icon: LayoutDashboard },
  { id: "tools", label: "Outils MCP", Icon: Zap },
  { id: "mcp", label: "Serveur", Icon: Radio },
  { id: "settings", label: "Configuration", Icon: Settings },
];

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

interface Props {
  children: ReactNode;
  healthState: HealthState;
  activeView: View;
  onNavigate: (v: View) => void;
}

export function Layout({ children, healthState, activeView, onNavigate }: Props) {
  const online = healthState.status === "ok";
  const os = healthState.status === "ok" ? healthState.data.os : null;

  return (
    <div className="flex h-full min-h-screen bg-wg-bg">
      {/* ── Sidebar ── */}
      <aside className="flex w-52 shrink-0 flex-col border-r border-wg-border bg-wg-bg">
        {/* Wordmark */}
        <div className="flex flex-col gap-1 border-b border-wg-border px-5 py-5">
          <div className="flex items-baseline gap-0 leading-none">
            <span className="font-mono text-lg font-light tracking-[0.15em] text-wg-text/70 uppercase">
              WEATH
            </span>
            <span className="font-mono text-lg font-bold tracking-[0.15em] text-wg-cyan uppercase">
              GARDS
            </span>
          </div>
          <span className="font-mono text-[9px] font-medium tracking-[0.3em] text-wg-muted/60 uppercase">
            Mission Control
          </span>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 px-3 py-4">
          {NAV.map(({ id, label, Icon }) => {
            const active = activeView === id;
            return (
              <button
                key={id}
                onClick={() => onNavigate(id)}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-all duration-200 ${
                  active
                    ? "bg-wg-cyan/10 border border-wg-cyan/20 text-wg-cyan shadow-[0_0_12px_rgba(0,212,255,0.18)]"
                    : "border border-transparent text-wg-muted hover:bg-wg-card hover:text-wg-text"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            );
          })}
        </nav>

        <div className="flex-1" />

        {/* Connection status */}
        <div className="border-t border-wg-border px-4 py-4">
          <div className="flex items-center gap-2">
            <StatusBadge status={online ? "running" : "stopped"} showLabel={false} />
            <span className="font-mono text-xs text-wg-muted">
              API {online ? "en ligne" : "hors ligne"}
            </span>
          </div>
          <div className="mt-1.5 flex items-center gap-1">
            <span className="font-mono text-[10px] text-wg-muted/40">WG</span>
            <span className="font-mono text-[10px] text-wg-muted/60">
              {healthState.status === "loading" ? "…" : online ? "OK" : "ERREUR"}
            </span>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-wg-border bg-wg-bg/80 px-6 backdrop-blur-md">
          <div className="flex items-center gap-2">
            <span className="h-1 w-1 rounded-full bg-wg-cyan" />
            <span className="font-mono text-xs text-wg-muted tracking-widest uppercase">
              v1.0.0
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* OS badge — click to open Settings */}
            {os && <OsBadge os={os} onClick={() => onNavigate("settings")} />}
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
