import { BookOpen, Trash2, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { deactivateTool, fetchActiveTools, type ActivatedTool } from "../api";

// ---------------------------------------------------------------------------
// Constellation SVG — empty state illustration
// ---------------------------------------------------------------------------

function ConstellationSvg() {
  return (
    <svg
      viewBox="0 0 120 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="h-24 w-36 opacity-70"
      aria-hidden="true"
    >
      {/* Background dim stars */}
      <circle cx="10" cy="10" r="0.8" fill="#64748B" opacity="0.4" />
      <circle cx="100" cy="8"  r="0.7" fill="#64748B" opacity="0.3" />
      <circle cx="112" cy="60" r="0.9" fill="#64748B" opacity="0.4" />
      <circle cx="5"   cy="70" r="0.6" fill="#64748B" opacity="0.3" />
      <circle cx="55"  cy="5"  r="0.7" fill="#64748B" opacity="0.25" />

      {/* Constellation lines */}
      <line x1="25" y1="20" x2="40" y2="35" stroke="#1E3A5F" strokeWidth="1" opacity="0.9" />
      <line x1="40" y1="35" x2="70" y2="15" stroke="#1E3A5F" strokeWidth="1" opacity="0.7" />
      <line x1="70" y1="15" x2="90" y2="40" stroke="#1E3A5F" strokeWidth="1" opacity="0.8" />
      <line x1="90" y1="40" x2="60" y2="58" stroke="#1E3A5F" strokeWidth="1" opacity="0.6" />
      <line x1="60" y1="58" x2="22" y2="55" stroke="#1E3A5F" strokeWidth="1" opacity="0.7" />
      <line x1="22" y1="55" x2="25" y2="20" stroke="#1E3A5F" strokeWidth="1" opacity="0.6" />
      <line x1="40" y1="35" x2="60" y2="58" stroke="#1E3A5F" strokeWidth="1" opacity="0.4" />

      {/* Constellation nodes */}
      <circle cx="25" cy="20" r="2.5" fill="#00D4FF" opacity="0.65" />
      <circle cx="70" cy="15" r="2"   fill="#00D4FF" opacity="0.5"  />
      <circle cx="90" cy="40" r="2.5" fill="#00D4FF" opacity="0.7"  />
      <circle cx="60" cy="58" r="2"   fill="#7B2FBE" opacity="0.65" />
      <circle cx="22" cy="55" r="2.5" fill="#00D4FF" opacity="0.5"  />
      <circle cx="40" cy="35" r="1.5" fill="#7B2FBE" opacity="0.45" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// ToolCard
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function ToolCard({
  tool,
  onRemove,
}: {
  tool: ActivatedTool;
  onRemove: (id: string) => void;
}) {
  const [removing, setRemoving] = useState(false);

  async function handleRemove() {
    setRemoving(true);
    try {
      await deactivateTool(tool.id);
      onRemove(tool.id);
    } catch {
      setRemoving(false);
    }
  }

  return (
    <div className="flex items-start gap-4 rounded-xl border border-wg-border bg-wg-card p-4 transition-all duration-200 hover:border-wg-cyan/20 animate-fade-in">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-wg-violet/10 mt-0.5">
        <Zap className="h-4 w-4 text-violet-400" />
      </span>

      <div className="min-w-0 flex-1">
        <p className="font-mono text-sm font-semibold text-wg-text truncate">
          {tool.tool_name}
        </p>
        <p className="mt-0.5 font-mono text-xs text-wg-muted truncate">
          cible&nbsp;:&nbsp;
          <span className="text-wg-text/80">{tool.target_name}</span>
        </p>
        <p className="mt-1 text-[10px] text-wg-muted/50">
          activé le {formatDate(tool.activated_at)}
        </p>
      </div>

      <button
        onClick={handleRemove}
        disabled={removing}
        title="Désactiver cet outil"
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-wg-border bg-wg-bg text-wg-muted transition-all duration-200 hover:border-red-500/30 hover:bg-red-500/5 hover:text-red-400 disabled:opacity-40 active:scale-95"
      >
        {removing ? (
          <span className="spinner-gradient h-3.5 w-3.5" />
        ) : (
          <Trash2 className="h-3.5 w-3.5" />
        )}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToolsPage
// ---------------------------------------------------------------------------

type PageState = "loading" | "ok" | "error";

export function ToolsPage() {
  const [tools, setTools] = useState<ActivatedTool[]>([]);
  const [state, setState] = useState<PageState>("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setState("loading");
    fetchActiveTools()
      .then((data) => {
        setTools(data);
        setState("ok");
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : String(e));
        setState("error");
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function handleRemove(id: string) {
    setTools((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {/* Header */}
      <div>
        <h2 className="flex items-center gap-2 font-mono text-sm font-semibold uppercase tracking-widest text-wg-muted">
          <Zap className="h-4 w-4 text-wg-cyan" />
          Outils MCP actifs
        </h2>
        <p className="mt-1 text-xs text-wg-muted/70">
          Outils activés exposés via le serveur MCP. Activez des outils
          depuis le&nbsp;Dashboard en cliquant sur un service détecté.
        </p>
      </div>

      {/* How-to banner */}
      <div className="rounded-xl border border-wg-cyan/20 bg-wg-cyan/5 px-5 py-4 space-y-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-3.5 w-3.5 text-wg-cyan shrink-0" />
          <p className="font-mono text-xs font-semibold uppercase tracking-widest text-wg-cyan">
            Comment intégrer un outil
          </p>
        </div>
        <ol className="space-y-1.5 text-xs text-wg-muted">
          <li className="flex gap-2">
            <span className="font-mono text-wg-cyan shrink-0">1.</span>
            <span>Lancez un scan depuis le <span className="text-wg-text font-medium">Dashboard</span>, puis cliquez sur un service détecté pour voir les outils disponibles.</span>
          </li>
          <li className="flex gap-2">
            <span className="font-mono text-wg-cyan shrink-0">2.</span>
            <span>Cliquez <span className="text-wg-text font-medium">Activer</span> sur l'outil souhaité — il apparaît alors dans cette liste.</span>
          </li>
          <li className="flex gap-2">
            <span className="font-mono text-wg-cyan shrink-0">3.</span>
            <span>Démarrez le <span className="text-wg-text font-medium">Serveur MCP</span> (onglet Serveur), copiez l'URL et le token, puis collez-les dans la configuration de votre client LLM.</span>
          </li>
          <li className="flex gap-2">
            <span className="font-mono text-wg-cyan shrink-0">4.</span>
            <span>Le LLM peut désormais appeler l'outil par son nom pour interroger vos services en temps réel.</span>
          </li>
        </ol>
      </div>

      {/* Loading */}
      {state === "loading" && (
        <div className="flex items-center gap-2 text-xs text-wg-muted">
          <span className="spinner-gradient h-3.5 w-3.5" />
          Chargement…
        </div>
      )}

      {/* Error */}
      {state === "error" && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Empty state */}
      {state === "ok" && tools.length === 0 && (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-wg-border bg-wg-card/50 py-20 text-center">
          <ConstellationSvg />
          <div className="space-y-1">
            <p className="text-sm font-medium text-wg-text">Aucun outil activé</p>
            <p className="max-w-xs text-xs text-wg-muted">
              Scannez l'environnement depuis le Dashboard, cliquez sur un service,
              puis activez les outils MCP souhaités.
            </p>
          </div>
        </div>
      )}

      {/* Tool list */}
      {state === "ok" && tools.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-wg-muted">
            <span className="font-semibold text-wg-cyan">{tools.length}</span>{" "}
            outil{tools.length > 1 ? "s" : ""} activé{tools.length > 1 ? "s" : ""}
          </p>
          {tools.map((t) => (
            <ToolCard key={t.id} tool={t} onRemove={handleRemove} />
          ))}
        </div>
      )}
    </div>
  );
}
