import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ClipboardCopy,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Radio,
  Server,
  Signal,
  SignalZero,
  Square,
  Terminal,
  Wifi,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchMCPSnippets,
  fetchMCPStatus,
  startMCP,
  stopMCP,
  type MCPSnippets,
  type MCPStatus,
} from "../api";
import { useToast } from "./Toast";

const DEFAULT_PORT = 9766;
const POLL_INTERVAL_MS = 5_000;

type SnippetTab = "claude" | "opencode" | "curl";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function useCopy(timeout = 1500) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const copy = useCallback((text: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), timeout);
    });
  }, [timeout]);

  return { copied, copy };
}

function CopyButton({ text, label }: { text: string; label?: string }) {
  const { copied, copy } = useCopy();
  return (
    <button
      onClick={() => copy(text)}
      className="flex items-center gap-1.5 rounded-lg border border-wg-border bg-wg-card px-3 py-1.5 text-xs font-medium text-wg-muted transition-all duration-200 hover:border-wg-cyan/30 hover:text-wg-cyan active:scale-95"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-emerald-400" />
      ) : (
        <ClipboardCopy className="h-3.5 w-3.5" />
      )}
      {copied ? "Copié" : (label ?? "Copier")}
    </button>
  );
}

function StatusDot({ running }: { running: boolean }) {
  return (
    <span className="relative flex h-2.5 w-2.5">
      {running && (
        <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 animate-status-pulse opacity-75" />
      )}
      <span
        className={`relative inline-flex h-2.5 w-2.5 rounded-full ${running ? "bg-emerald-400" : "bg-wg-muted/40"}`}
      />
    </span>
  );
}

// ---------------------------------------------------------------------------
// Snippet tabs
// ---------------------------------------------------------------------------

const TABS: { id: SnippetTab; label: string; file: string }[] = [
  { id: "claude", label: "Claude Desktop", file: "claude_desktop_config.json" },
  { id: "opencode", label: "OpenCode", file: "~/.config/opencode/config.json" },
  { id: "curl", label: "curl (test)", file: "" },
];

function SnippetPanel({ snippets, isRunning }: { snippets: MCPSnippets; isRunning: boolean }) {
  const [activeTab, setActiveTab] = useState<SnippetTab>("claude");
  const [showToken, setShowToken] = useState(false);

  const maskedToken = snippets.token.slice(0, 6) + "•".repeat(20) + snippets.token.slice(-4);

  const snippetText =
    activeTab === "claude"
      ? JSON.stringify(snippets.claude_desktop, null, 2)
      : activeTab === "opencode"
        ? JSON.stringify(snippets.opencode, null, 2)
        : snippets.curl;

  const currentTab = TABS.find((t) => t.id === activeTab)!;

  return (
    <div className="rounded-xl border border-wg-cyan/20 bg-wg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-mono text-xs font-medium uppercase tracking-widest text-wg-muted">
          Configuration de connexion
        </p>
        {!isRunning && (
          <span className="flex items-center gap-1.5 rounded-md border border-amber-500/20 bg-amber-500/5 px-2 py-0.5 text-xs text-amber-400">
            <SignalZero className="h-3 w-3" />
            Serveur arrêté — config basée sur les paramètres enregistrés
          </span>
        )}
      </div>

      {/* URL */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-wg-muted">Endpoint MCP</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded-lg border border-wg-border bg-wg-bg px-3 py-2 font-mono text-sm text-wg-cyan truncate">
            {snippets.url}
          </code>
          <CopyButton text={snippets.url} />
        </div>
      </div>

      {/* Token */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-wg-muted">Token d'authentification</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded-lg border border-wg-border bg-wg-bg px-3 py-2 font-mono text-sm text-wg-text truncate">
            {showToken ? snippets.token : maskedToken}
          </code>
          <button
            onClick={() => setShowToken((v) => !v)}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-wg-border bg-wg-bg text-wg-muted transition-colors hover:border-wg-cyan/30 hover:text-wg-cyan"
            title={showToken ? "Masquer" : "Révéler"}
          >
            {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
          <CopyButton text={snippets.token} label="Copier" />
        </div>
      </div>

      {/* Client tabs */}
      <div className="space-y-2">
        <div className="flex items-center gap-1 border-b border-wg-border pb-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 rounded-t-lg px-3 py-1.5 text-xs font-medium transition-all duration-150 -mb-px border-b-2 ${
                activeTab === tab.id
                  ? "border-wg-cyan text-wg-cyan bg-wg-cyan/5"
                  : "border-transparent text-wg-muted hover:text-wg-text"
              }`}
            >
              {tab.id === "curl" && <Terminal className="h-3 w-3" />}
              {tab.label}
            </button>
          ))}
        </div>

        {currentTab.file && (
          <p className="text-xs text-wg-muted/60">
            Fichier : <code className="text-wg-muted">{currentTab.file}</code>
          </p>
        )}

        <div className="relative">
          <pre className="overflow-auto rounded-lg border border-wg-border bg-wg-bg p-3 font-mono text-xs text-wg-text/80 max-h-52 leading-relaxed whitespace-pre">
            {snippetText}
          </pre>
          <div className="absolute right-2 top-2">
            <CopyButton text={snippetText} label="Copier" />
          </div>
        </div>
      </div>

      {/* Security notice */}
      <div className="flex items-center gap-2 rounded-lg border border-wg-border bg-wg-bg/40 px-3 py-2">
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
        <p className="text-xs text-wg-muted">
          Auth Bearer active · Socket Docker jamais exposé · Outils en lecture seule
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MCPServerPanel
// ---------------------------------------------------------------------------

export function MCPServerPanel() {
  const [status, setStatus] = useState<MCPStatus | null>(null);
  const [snippets, setSnippets] = useState<MCPSnippets | null>(null);
  const [exposeNetwork, setExposeNetwork] = useState(false);
  const [port, setPort] = useState(DEFAULT_PORT);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { show } = useToast();

  const refresh = useCallback(async () => {
    try {
      const [s, snip] = await Promise.all([fetchMCPStatus(), fetchMCPSnippets()]);
      setStatus(s);
      setSnippets(snip);
    } catch {
      // API unreachable — keep showing last known state
    }
  }, []);

  useEffect(() => {
    void refresh();
    pollTimer.current = setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current);
    };
  }, [refresh]);

  async function handleStart() {
    setActionLoading(true);
    setActionError(null);
    try {
      const host = exposeNetwork ? "0.0.0.0" : "127.0.0.1";
      await startMCP(host, port);
      await refresh();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStop() {
    setActionLoading(true);
    setActionError(null);
    try {
      await stopMCP();
      await refresh();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setActionLoading(false);
    }
  }

  const isRunning = status?.running ?? false;
  const isNetwork = status?.host === "0.0.0.0" || exposeNetwork;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="flex items-center gap-2 font-mono text-sm font-semibold uppercase tracking-widest text-wg-muted">
          <Radio className="h-4 w-4 text-wg-cyan" />
          Centre de transmission MCP
        </h2>
        <p className="mt-1 text-xs text-wg-muted/70">
          Expose les outils activés sur le réseau local pour qu'un LLM distant
          interroge les containers de cette machine.
        </p>
      </div>

      {/* Security warning banner — network exposure without token */}
      {status !== null && !status.token_configured && isNetwork && (
        <div className="flex items-start gap-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3">
          <AlertTriangle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-red-400">
              Exposition réseau bloquée — token absent
            </p>
            <p className="mt-0.5 text-xs text-red-400/80">
              Redémarrez WEATHGARDS pour auto-générer un token. Le serveur MCP
              refuse de démarrer en mode réseau sans authentification.
            </p>
          </div>
        </div>
      )}

      {/* Status card */}
      <div className="rounded-xl border border-wg-border bg-wg-card p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <StatusDot running={isRunning} />
            <div>
              <p className="font-mono text-sm font-semibold text-wg-text">
                {isRunning ? "Serveur MCP actif" : "Serveur MCP arrêté"}
              </p>
              {isRunning && status && (
                <p className="font-mono text-xs text-wg-muted">
                  {status.host === "0.0.0.0"
                    ? `${status.network_ip ?? "0.0.0.0"}:${status.port}`
                    : `${status.host}:${status.port}`}
                  {" · "}
                  <span className="text-wg-cyan">{status.tool_count}</span> outil
                  {status.tool_count !== 1 ? "s" : ""}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isRunning && status?.tls_enabled && (
              <div className="flex items-center gap-1.5 rounded-lg border border-wg-cyan/20 bg-wg-cyan/5 px-2.5 py-1">
                <Lock className="h-3.5 w-3.5 text-wg-cyan" />
                <span className="font-mono text-xs font-medium text-wg-cyan">TLS</span>
              </div>
            )}
            {isRunning ? (
              <div className="flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1">
                <Signal className="h-3.5 w-3.5 text-emerald-400" />
                <span className="font-mono text-xs font-medium text-emerald-400">EN LIGNE</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 rounded-lg border border-wg-border bg-wg-bg/60 px-2.5 py-1">
                <SignalZero className="h-3.5 w-3.5 text-wg-muted" />
                <span className="font-mono text-xs font-medium text-wg-muted">HORS LIGNE</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Configuration — only shown when stopped */}
      {!isRunning && (
        <div className="rounded-xl border border-wg-border bg-wg-card p-5 space-y-5">
          <p className="font-mono text-xs font-medium uppercase tracking-widest text-wg-muted">
            Configuration
          </p>

          {/* Network toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-wg-text">Exposer sur le réseau local</p>
              <p className="text-xs text-wg-muted mt-0.5">
                Rend le serveur MCP accessible aux autres machines de votre réseau (ex. un LLM sur un autre PC). Désactivé, il n'écoute que sur cette machine.
              </p>
            </div>
            <button
              onClick={() => {
                const next = !exposeNetwork;
                setExposeNetwork(next);
                if (next && status !== null && !status.token_configured) {
                  show(
                    "Aucun token configuré — le serveur refusera de démarrer en mode réseau. Redémarrez WEATHGARDS pour en générer un.",
                    "error",
                  );
                }
              }}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
                exposeNetwork ? "bg-wg-cyan" : "bg-wg-border"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 ${
                  exposeNetwork ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {/* Port */}
          <div className="flex flex-col gap-1.5">
            <div>
              <p className="text-sm font-medium text-wg-text">Port d'écoute</p>
              <p className="text-xs text-wg-muted mt-0.5">
                Numéro de port sur lequel le serveur MCP attend les connexions. Modifiez-le uniquement si ce port est déjà occupé sur votre machine.
              </p>
            </div>
            <input
              type="number"
              min={1024}
              max={65535}
              value={port}
              onChange={(e) => setPort(parseInt(e.target.value, 10) || DEFAULT_PORT)}
              className="w-28 rounded-lg border border-wg-border bg-wg-bg px-3 py-1.5 font-mono text-sm text-wg-text focus:border-wg-cyan/40 focus:outline-none focus:ring-1 focus:ring-wg-cyan/20"
            />
          </div>


          {/* Network mode warning */}
          {exposeNetwork && (
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2.5">
              <Wifi className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
              <p className="text-xs text-amber-400">
                En mode réseau, un token Bearer est généré et requis sur chaque
                requête. Copiez-le depuis la section "Connexion" après démarrage.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Action button */}
      <div className="flex items-center gap-3">
        {!isRunning ? (
          <button
            onClick={handleStart}
            disabled={actionLoading}
            className="flex items-center gap-2 rounded-xl border border-wg-cyan/30 bg-wg-cyan/10 px-5 py-2.5 text-sm font-semibold text-wg-cyan transition-all duration-200 hover:border-wg-cyan/60 hover:bg-wg-cyan/20 hover:shadow-cyan-glow disabled:opacity-50 active:scale-95"
          >
            {actionLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Server className="h-4 w-4" />
            )}
            {actionLoading ? "Démarrage…" : "Démarrer le serveur MCP"}
          </button>
        ) : (
          <button
            onClick={handleStop}
            disabled={actionLoading}
            className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/5 px-5 py-2.5 text-sm font-semibold text-red-400 transition-all duration-200 hover:border-red-500/40 hover:bg-red-500/10 disabled:opacity-50 active:scale-95"
          >
            {actionLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Square className="h-4 w-4" />
            )}
            {actionLoading ? "Arrêt…" : "Arrêter le serveur MCP"}
          </button>
        )}

        {actionError && (
          <p className="flex items-center gap-1.5 text-xs text-red-400">
            <AlertTriangle className="h-3.5 w-3.5" />
            {actionError}
          </p>
        )}
      </div>

      {/* Connection info — always visible once snippets are loaded */}
      {snippets && <SnippetPanel snippets={snippets} isRunning={isRunning} />}
    </div>
  );
}
