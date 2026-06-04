import {
  Activity,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  activateTool,
  fetchCatalog,
  testTool,
  type ActivatedTool,
  type ScanResult,
  type ToolDefinition,
} from "../api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PanelState = "idle" | "loading-catalog" | "ready" | "error";

interface ToolRowState {
  activating: boolean;
  testing: boolean;
  activated: ActivatedTool | null;
  testResult: Record<string, unknown> | null;
  testError: string | null;
  expanded: boolean;
}

function initRowState(): ToolRowState {
  return {
    activating: false,
    testing: false,
    activated: null,
    testResult: null,
    testError: null,
    expanded: false,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toolsForType(
  catalog: ToolDefinition[],
  type: ScanResult["type"],
): ToolDefinition[] {
  return catalog.filter(
    (t) => t.target_type === type || t.target_type === "any",
  );
}

function syntaxColor(value: unknown): string {
  if (value === null || value === undefined) return "text-wg-muted";
  if (typeof value === "boolean") return "text-violet-400";
  if (typeof value === "number") return "text-sky-400";
  if (typeof value === "string") return "text-emerald-400";
  return "text-wg-text";
}

function ResultLine({
  k,
  value,
  depth = 0,
}: {
  k: string;
  value: unknown;
  depth?: number;
}) {
  if (Array.isArray(value)) {
    return (
      <div style={{ paddingLeft: depth * 12 }}>
        <span className="text-wg-muted">{k} : </span>
        <span className="text-wg-muted/60">[</span>
        {value.map((item, i) => (
          <div key={i} style={{ paddingLeft: 12 }} className="text-wg-text/80">
            {String(item)}
            {i < value.length - 1 && <span className="text-wg-muted">,</span>}
          </div>
        ))}
        <span className="text-wg-muted/60">]</span>
      </div>
    );
  }
  if (value !== null && typeof value === "object") {
    return (
      <div style={{ paddingLeft: depth * 12 }}>
        <span className="text-wg-muted">{k}:</span>
        {Object.entries(value as Record<string, unknown>).map(([ck, cv]) => (
          <ResultLine key={ck} k={ck} value={cv} depth={depth + 1} />
        ))}
      </div>
    );
  }
  return (
    <div style={{ paddingLeft: depth * 12 }}>
      <span className="text-wg-muted">{k}: </span>
      <span className={syntaxColor(value)}>{JSON.stringify(value)}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToolRow
// ---------------------------------------------------------------------------

function ToolRow({
  tool,
  target,
}: {
  tool: ToolDefinition;
  target: ScanResult;
}) {
  const [state, setState] = useState<ToolRowState>(initRowState);

  async function handleActivate() {
    setState((s) => ({ ...s, activating: true }));
    try {
      const entry = await activateTool(tool.name, target.name);
      setState((s) => ({ ...s, activating: false, activated: entry }));
    } catch (e) {
      setState((s) => ({ ...s, activating: false }));
    }
  }

  async function handleTest() {
    setState((s) => ({
      ...s,
      testing: true,
      testResult: null,
      testError: null,
      expanded: true,
    }));
    try {
      const result = await testTool(tool.name, target.name);
      setState((s) => ({ ...s, testing: false, testResult: result }));
    } catch (e: unknown) {
      setState((s) => ({
        ...s,
        testing: false,
        testError: e instanceof Error ? e.message : String(e),
      }));
    }
  }

  return (
    <div className="group rounded-xl border border-wg-border bg-wg-bg/60 p-4 transition-all duration-200 hover:border-wg-cyan/20">
      {/* Tool header */}
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-wg-violet/10">
          <Activity className="h-3.5 w-3.5 text-violet-400" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-sm font-semibold text-wg-text">
            {tool.name}
          </p>
          <p className="mt-0.5 text-xs text-wg-muted leading-relaxed">
            {tool.description}
          </p>
          {tool.parameters.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {tool.parameters.map((p) => (
                <span
                  key={p.name}
                  className="inline-flex items-center gap-1 rounded border border-wg-border bg-wg-card px-1.5 py-0.5 font-mono text-[10px] text-wg-muted"
                >
                  <span className={p.required ? "text-amber-400/80" : "text-wg-muted/60"}>
                    {p.name}
                  </span>
                  <span className="text-wg-muted/40">:{p.type}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div className="mt-3 flex items-center gap-2">
        {state.activated ? (
          <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Activé
          </span>
        ) : (
          <button
            onClick={handleActivate}
            disabled={state.activating}
            className="flex items-center gap-1.5 rounded-lg border border-wg-cyan/20 bg-wg-cyan/5 px-3 py-1.5 text-xs font-medium text-wg-cyan transition-all duration-200 hover:border-wg-cyan/40 hover:bg-wg-cyan/10 disabled:opacity-50"
          >
            {state.activating ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Zap className="h-3 w-3" />
            )}
            {state.activating ? "Activation…" : "Activer pour cette cible"}
          </button>
        )}

        <button
          onClick={handleTest}
          disabled={state.testing}
          className="flex items-center gap-1.5 rounded-lg border border-wg-border bg-wg-card px-3 py-1.5 text-xs font-medium text-wg-muted transition-all duration-200 hover:border-violet-400/30 hover:bg-wg-violet/5 hover:text-violet-400 disabled:opacity-50"
        >
          {state.testing ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Terminal className="h-3 w-3" />
          )}
          {state.testing ? "Test en cours…" : "Tester maintenant"}
        </button>

        {(state.testResult !== null || state.testError !== null) && (
          <button
            onClick={() => setState((s) => ({ ...s, expanded: !s.expanded }))}
            className="ml-auto flex items-center gap-1 text-xs text-wg-muted hover:text-wg-text transition-colors"
          >
            <ChevronRight
              className={`h-3.5 w-3.5 transition-transform duration-200 ${state.expanded ? "rotate-90" : ""}`}
            />
            Résultat
          </button>
        )}
      </div>

      {/* Test result */}
      {state.expanded && (state.testResult !== null || state.testError !== null) && (
        <div className="mt-3 rounded-lg border border-wg-border bg-wg-bg overflow-auto max-h-52 p-3 font-mono text-xs leading-5">
          {state.testError !== null ? (
            <span className="text-red-400">{state.testError}</span>
          ) : (
            Object.entries(state.testResult ?? {}).map(([k, v]) => (
              <ResultLine key={k} k={k} value={v} />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToolActivationPanel
// ---------------------------------------------------------------------------

interface Props {
  target: ScanResult;
  onClose: () => void;
}

export function ToolActivationPanel({ target, onClose }: Props) {
  const [state, setState] = useState<PanelState>("loading-catalog");
  const [catalog, setCatalog] = useState<ToolDefinition[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCatalog()
      .then((data) => {
        setCatalog(data);
        setState("ready");
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : String(e));
        setState("error");
      });
  }, []);

  const applicableTools = catalog.length > 0 ? toolsForType(catalog, target.type) : [];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-wg-bg/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <aside className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-wg-border bg-wg-card shadow-xl">
        {/* Header */}
        <div className="flex items-start gap-3 border-b border-wg-border px-5 py-4">
          <div className="flex-1 min-w-0">
            <p className="font-mono text-[10px] font-medium uppercase tracking-widest text-wg-muted">
              Outils MCP disponibles
            </p>
            <p className="mt-0.5 truncate font-mono text-sm font-bold text-wg-text">
              {target.name}
            </p>
            <div className="mt-1 flex items-center gap-2">
              <span className="inline-flex items-center rounded border border-wg-border bg-wg-bg px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-wg-muted">
                {target.type}
              </span>
              <span className="font-mono text-[10px] text-wg-muted/60">
                {target.os_origin}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-wg-border text-wg-muted transition-colors hover:border-red-500/30 hover:text-red-400"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {state === "loading-catalog" && (
            <div className="flex items-center gap-2 text-xs text-wg-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Chargement du catalogue…
            </div>
          )}

          {state === "error" && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-xs text-red-400">
              {error}
            </div>
          )}

          {state === "ready" && applicableTools.length === 0 && (
            <div className="rounded-xl border border-dashed border-wg-border py-10 text-center text-xs text-wg-muted">
              Aucun outil disponible pour le type «&nbsp;{target.type}&nbsp;».
            </div>
          )}

          {state === "ready" && applicableTools.length > 0 && (
            <div className="flex flex-col gap-3">
              <p className="text-xs text-wg-muted">
                <span className="font-semibold text-wg-cyan">{applicableTools.length}</span>{" "}
                outil{applicableTools.length > 1 ? "s" : ""} applicable
                {applicableTools.length > 1 ? "s" : ""} — cible&nbsp;:&nbsp;
                <span className="font-mono">{target.name}</span>
              </p>
              {applicableTools.map((tool) => (
                <ToolRow key={tool.name} tool={tool} target={target} />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-wg-border px-5 py-3">
          <p className="text-[10px] text-wg-muted/50">
            Les outils sont statiques et pré-écrits — aucun code n'est généré à l'exécution.
          </p>
        </div>
      </aside>
    </>
  );
}
