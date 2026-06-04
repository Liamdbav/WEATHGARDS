import { AlertCircle, Box, Cpu, Radar, RefreshCw, Server } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { type ScanResult } from "../api";
import { type HealthState, type ScanState } from "../hooks/useScan";
import { ServiceCard } from "./ServiceCard";
import { useToast } from "./Toast";
import { ToolActivationPanel } from "./ToolActivationPanel";

type FilterType = "all" | ScanResult["type"];

const FILTERS: { id: FilterType; label: string; icon: typeof Radar }[] = [
  { id: "all", label: "Tous", icon: Radar },
  { id: "docker", label: "Docker", icon: Box },
  { id: "process", label: "Processus", icon: Cpu },
  { id: "service", label: "Services", icon: Server },
];

function formatLastFetch(d: Date): string {
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return `il y a ${diff}s`;
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)}min`;
  return d.toLocaleTimeString();
}

interface Props {
  scanState: ScanState;
  healthState: HealthState;
  onTrigger: () => void;
}

export function ScanDashboard({ scanState, healthState, onTrigger }: Props) {
  const [filter, setFilter] = useState<FilterType>("all");
  const [panelTarget, setPanelTarget] = useState<ScanResult | null>(null);
  const { show } = useToast();
  const dockerToastFired = useRef(false);

  const dockerAvailable =
    healthState.status === "ok" ? healthState.data.docker_available : null;

  useEffect(() => {
    if (!dockerToastFired.current && dockerAvailable === false) {
      dockerToastFired.current = true;
      show(
        "Docker non détecté — seuls les processus et services système sont visibles.",
        "info",
      );
    }
  }, [dockerAvailable, show]);

  const allResults = scanState.status === "ok" ? scanState.data : [];
  const filtered =
    filter === "all" ? allResults : allResults.filter((r) => r.type === filter);

  const countFor = (f: FilterType) =>
    f === "all" ? allResults.length : allResults.filter((r) => r.type === f).length;

  const isLoading = scanState.status === "loading";

  return (
    <div className="flex flex-col gap-6">
      {/* Scan action bar */}
      <div className="flex flex-wrap items-center gap-4">
        <button
          onClick={onTrigger}
          disabled={isLoading}
          className="group relative inline-flex items-center gap-2.5 rounded-xl border border-wg-cyan/30 bg-wg-cyan/10 px-5 py-2.5 text-sm font-semibold text-wg-cyan transition-all duration-200 hover:border-wg-cyan/60 hover:bg-wg-cyan/20 hover:shadow-cyan-glow disabled:opacity-60 disabled:cursor-not-allowed active:scale-95"
        >
          {/* Radar rings — shown while scanning */}
          {isLoading && (
            <>
              <span className="absolute -inset-1 rounded-xl border border-wg-cyan/40 animate-radar-ping" />
              <span
                className="absolute -inset-1 rounded-xl border border-wg-cyan/20 animate-radar-ping"
                style={{ animationDelay: "0.5s" }}
              />
            </>
          )}

          {isLoading ? (
            <span className="spinner-gradient h-4 w-4" />
          ) : (
            <Radar className="h-4 w-4 transition-transform duration-200 group-hover:rotate-12" />
          )}

          {isLoading ? "Scan en cours…" : "Scanner l'environnement"}
        </button>

        {scanState.status === "ok" && (
          <div className="flex items-center gap-3 text-xs text-wg-muted">
            <span className="font-mono">
              <span className="text-wg-cyan font-semibold">{allResults.length}</span>{" "}
              {allResults.length === 1 ? "service détecté" : "services détectés"}
            </span>
            <span className="h-3 w-px bg-wg-border" />
            <span className="flex items-center gap-1">
              <RefreshCw className="h-3 w-3" />
              {formatLastFetch(scanState.lastFetch)}
            </span>
          </div>
        )}

        {scanState.status === "error" && (
          <div className="flex items-center gap-2 text-xs text-red-400">
            <AlertCircle className="h-3.5 w-3.5" />
            <span>{scanState.message}</span>
          </div>
        )}
      </div>

      {/* Docker unavailable notice */}
      {dockerAvailable === false && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-xs text-amber-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>
            Docker non détecté sur cette machine — seuls les processus et services système
            sont visibles.
          </span>
        </div>
      )}

      {/* Filters */}
      {scanState.status === "ok" && (
        <div className="flex flex-wrap gap-2">
          {FILTERS.map(({ id, label, icon: Icon }) => {
            const active = filter === id;
            const count = countFor(id);
            return (
              <button
                key={id}
                onClick={() => setFilter(id)}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                  active
                    ? "border-wg-cyan/40 bg-wg-cyan/10 text-wg-cyan"
                    : "border-wg-border bg-wg-card text-wg-muted hover:border-wg-cyan/20 hover:text-wg-text"
                }`}
              >
                <Icon className="h-3 w-3" />
                {label}
                <span
                  className={`rounded px-1 py-0.5 font-mono text-xs ${
                    active ? "bg-wg-cyan/20 text-wg-cyan" : "bg-wg-bg text-wg-muted"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Grid */}
      {scanState.status === "idle" && (
        <div className="flex flex-col items-center gap-5 rounded-xl border border-dashed border-wg-border bg-wg-card/50 py-20 text-center">
          <SpaceProbeSvg />
          <div className="space-y-1">
            <p className="text-sm font-medium text-wg-text">Aucun scan effectué</p>
            <p className="max-w-xs text-xs text-wg-muted">
              Lancez un scan pour découvrir les services actifs sur cette machine.
            </p>
          </div>
        </div>
      )}

      {scanState.status === "loading" && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {scanState.status === "ok" && filtered.length === 0 && (
        <EmptyState
          icon={<AlertCircle className="h-8 w-8 text-wg-muted/40" />}
          title="Aucun résultat"
          subtitle={
            filter === "all"
              ? "Aucun service trouvé sur cette machine."
              : `Aucun élément de type « ${
                  filter === "process" ? "processus" : filter === "service" ? "service" : filter
                } » détecté.`
          }
        />
      )}

      {scanState.status === "ok" && filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((r) => (
            <ServiceCard
              key={r.id}
              result={r}
              onActivate={(result) => setPanelTarget(result)}
            />
          ))}
        </div>
      )}

      {panelTarget !== null && (
        <ToolActivationPanel
          target={panelTarget}
          onClose={() => setPanelTarget(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Space Probe SVG — dashboard idle empty state
// ---------------------------------------------------------------------------

function SpaceProbeSvg() {
  return (
    <svg
      viewBox="0 0 120 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="h-24 w-36 opacity-70"
      aria-hidden="true"
    >
      {/* Stars */}
      <circle cx="10"  cy="15" r="1"   fill="#64748B" opacity="0.6" />
      <circle cx="45"  cy="8"  r="0.8" fill="#64748B" opacity="0.4" />
      <circle cx="90"  cy="20" r="1.2" fill="#64748B" opacity="0.7" />
      <circle cx="110" cy="5"  r="0.7" fill="#64748B" opacity="0.5" />
      <circle cx="25"  cy="65" r="0.9" fill="#64748B" opacity="0.3" />
      <circle cx="105" cy="68" r="1"   fill="#64748B" opacity="0.5" />

      {/* Solar panel — left */}
      <rect x="28" y="37" width="20" height="7" rx="1" fill="#0D1526" stroke="#1E3A5F" strokeWidth="1" />
      <line x1="34.5" y1="37" x2="34.5" y2="44" stroke="#1E3A5F" strokeWidth="0.6" />
      <line x1="41"   y1="37" x2="41"   y2="44" stroke="#1E3A5F" strokeWidth="0.6" />

      {/* Solar panel — right */}
      <rect x="72" y="37" width="20" height="7" rx="1" fill="#0D1526" stroke="#1E3A5F" strokeWidth="1" />
      <line x1="78.5" y1="37" x2="78.5" y2="44" stroke="#1E3A5F" strokeWidth="0.6" />
      <line x1="85"   y1="37" x2="85"   y2="44" stroke="#1E3A5F" strokeWidth="0.6" />

      {/* Body */}
      <rect x="48" y="33" width="24" height="15" rx="2" fill="#1E3A5F" />
      <circle cx="60" cy="40.5" r="3" fill="#00D4FF" opacity="0.35" />
      <circle cx="60" cy="40.5" r="1.5" fill="#00D4FF" opacity="0.6" />

      {/* Antenna mast */}
      <line x1="60" y1="33" x2="60" y2="18" stroke="#1E3A5F" strokeWidth="1.2" />
      {/* Dish */}
      <path d="M54 18 Q60 14 66 18" stroke="#1E3A5F" strokeWidth="1.2" fill="none" />
      <line x1="60" y1="14" x2="60" y2="18" stroke="#1E3A5F" strokeWidth="0.8" />

      {/* Signal rings */}
      <circle cx="60" cy="14" r="6"  fill="none" stroke="#00D4FF" strokeWidth="0.8" opacity="0.35" />
      <circle cx="60" cy="14" r="10" fill="none" stroke="#00D4FF" strokeWidth="0.5" opacity="0.18" />
      <circle cx="60" cy="14" r="14" fill="none" stroke="#00D4FF" strokeWidth="0.3" opacity="0.08" />
    </svg>
  );
}

function EmptyState({
  icon,
  title,
  subtitle,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-wg-border bg-wg-card/50 py-16 text-center">
      {icon}
      <p className="text-sm font-medium text-wg-text">{title}</p>
      <p className="max-w-xs text-xs text-wg-muted">{subtitle}</p>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-wg-border bg-wg-card p-4">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg shimmer-bg" />
        <div className="flex-1 space-y-1.5">
          <div className="h-3 w-3/4 rounded shimmer-bg" />
          <div className="h-2.5 w-1/2 rounded shimmer-bg" />
        </div>
      </div>
      <div className="flex gap-1.5">
        <div className="h-5 w-16 rounded-md shimmer-bg" />
        <div className="h-5 w-20 rounded-md shimmer-bg" style={{ animationDelay: "0.15s" }} />
      </div>
      <div className="mt-auto flex justify-end">
        <div className="h-7 w-32 rounded-lg shimmer-bg" style={{ animationDelay: "0.3s" }} />
      </div>
    </div>
  );
}
