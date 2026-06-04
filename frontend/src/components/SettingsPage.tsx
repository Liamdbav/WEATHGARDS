import {
  AlertTriangle,
  Box,
  Cpu,
  Loader2,
  Radio,
  Save,
  Server,
  Settings,
  Wifi,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  fetchAppSettings,
  saveAppSettings,
  type AppSettings,
} from "../api";
import { useToast } from "./Toast";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionCard({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-wg-border bg-wg-card overflow-hidden">
      {/* Card header */}
      <div className="flex items-center gap-3 border-b border-wg-border bg-wg-bg/40 px-5 py-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-wg-cyan/10">
          {icon}
        </span>
        <div>
          <p className="font-mono text-xs font-semibold uppercase tracking-widest text-wg-text">
            {title}
          </p>
          {subtitle && (
            <p className="text-xs text-wg-muted mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      <div className="px-5 py-5 space-y-5">{children}</div>
    </div>
  );
}

function FieldRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-medium text-wg-text">{label}</p>
        <div className="shrink-0">{children}</div>
      </div>
      {hint && <p className="text-xs text-wg-muted leading-relaxed">{hint}</p>}
    </div>
  );
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200 focus:outline-none ${
        checked ? "bg-wg-cyan" : "bg-wg-border"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}

function TextInput({
  value,
  onChange,
  placeholder,
  monospace,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  monospace?: boolean;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-48 rounded-lg border border-wg-border bg-wg-bg px-3 py-1.5 text-sm text-wg-text placeholder:text-wg-muted/50 focus:border-wg-cyan/40 focus:outline-none focus:ring-1 focus:ring-wg-cyan/20 transition-colors ${
        monospace ? "font-mono" : ""
      }`}
    />
  );
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  disabled,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  disabled?: boolean;
}) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      max={max}
      disabled={disabled}
      onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
      className="w-28 rounded-lg border border-wg-border bg-wg-bg px-3 py-1.5 font-mono text-sm text-wg-text focus:border-wg-cyan/40 focus:outline-none focus:ring-1 focus:ring-wg-cyan/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    />
  );
}

// ---------------------------------------------------------------------------
// SettingsPage
// ---------------------------------------------------------------------------

const DEFAULT_SETTINGS: AppSettings = {
  mcp_host: "127.0.0.1",
  mcp_port: 9766,
  mcp_transport: "streamable-http",
  network_exposed: false,
  auto_scan_interval: 30,
  scanner_toggles: { docker: true, processes: true, services: true },
};

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const { show } = useToast();

  useEffect(() => {
    fetchAppSettings()
      .then((s) => {
        setSettings(s);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  function patch(partial: Partial<AppSettings>) {
    setSettings((prev) => ({ ...prev, ...partial }));
    setDirty(true);
  }

  function patchToggles(partial: Partial<AppSettings["scanner_toggles"]>) {
    setSettings((prev) => ({
      ...prev,
      scanner_toggles: { ...prev.scanner_toggles, ...partial },
    }));
    setDirty(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const saved = await saveAppSettings(settings);
      setSettings(saved);
      setDirty(false);
      show("Paramètres sauvegardés", "success");
    } catch (e: unknown) {
      show(e instanceof Error ? e.message : "Erreur lors de la sauvegarde", "error");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-wg-muted">
        <Loader2 className="h-4 w-4 animate-spin" />
        Chargement…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {/* Page header */}
      <div>
        <h2 className="flex items-center gap-2 font-mono text-sm font-semibold uppercase tracking-widest text-wg-muted">
          <Settings className="h-4 w-4 text-wg-cyan" />
          Paramètres
        </h2>
        <p className="mt-1 text-xs text-wg-muted/70">
          Configuration persistée dans le répertoire utilisateur. Les changements
          MCP prennent effet au prochain démarrage du serveur.
        </p>
      </div>

      {/* ── MCP Server ── */}
      <SectionCard
        icon={<Radio className="h-4 w-4 text-wg-cyan" />}
        title="Serveur MCP"
        subtitle="Paramètres d'exposition réseau par défaut"
      >
        <FieldRow label="Hôte" hint="Adresse sur laquelle le serveur écoute. Préférez le toggle ci-dessous plutôt que de modifier ce champ manuellement.">
          <TextInput
            value={settings.mcp_host}
            onChange={(v) => patch({ mcp_host: v })}
            placeholder="127.0.0.1"
            monospace
          />
        </FieldRow>

        <FieldRow label="Port" hint="Numéro de port sur lequel le serveur MCP attend les connexions. Modifiez-le uniquement si ce port est déjà occupé sur votre machine.">
          <NumberInput
            value={settings.mcp_port}
            onChange={(v) => patch({ mcp_port: v })}
            min={1024}
            max={65535}
          />
        </FieldRow>

        <FieldRow label="Transport" hint="Protocole de communication utilisé par le serveur MCP. Non modifiable pour l'instant.">
          <span className="inline-flex items-center rounded-lg border border-wg-border bg-wg-bg/60 px-3 py-1.5 font-mono text-xs text-wg-muted">
            {settings.mcp_transport}
          </span>
        </FieldRow>

        <FieldRow
          label="Exposition réseau"
          hint="Rend le serveur MCP accessible aux autres machines de votre réseau. Un token d'authentification sera alors obligatoire sur chaque requête."
        >
          <Toggle
            checked={settings.network_exposed}
            onChange={(v) => patch({ network_exposed: v, mcp_host: v ? "0.0.0.0" : "127.0.0.1" })}
          />
        </FieldRow>

        {settings.network_exposed && (
          <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2.5">
            <Wifi className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
            <div className="text-xs text-amber-400 space-y-1">
              <p className="font-medium">Exposition réseau activée</p>
              <p>
                Un token Bearer sera généré et requis sur chaque requête.
                Ne partagez le token qu'avec le client LLM de confiance.
              </p>
            </div>
          </div>
        )}
      </SectionCard>

      {/* ── Scanner ── */}
      <SectionCard
        icon={<Server className="h-4 w-4 text-wg-cyan" />}
        title="Scanner"
        subtitle="Comportement du scan automatique et des sources"
      >
        <FieldRow
          label="Intervalle auto-scan"
          hint="Fréquence à laquelle l'application re-scanne automatiquement vos services. Mettez à 0 pour ne lancer le scan que manuellement."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={0}
              max={300}
              step={5}
              value={settings.auto_scan_interval}
              onChange={(e) => patch({ auto_scan_interval: parseInt(e.target.value, 10) })}
              className="w-28 accent-wg-cyan"
            />
            <span className="w-20 font-mono text-xs text-wg-text text-right">
              {settings.auto_scan_interval === 0
                ? "Désactivé"
                : `${settings.auto_scan_interval}s`}
            </span>
          </div>
        </FieldRow>

        <div className="border-t border-wg-border/50 pt-4 space-y-4">
          <p className="text-xs font-medium uppercase tracking-widest text-wg-muted">
            Sources actives
          </p>

          <FieldRow
            label="Docker"
            hint="Détecte les containers en cours d'exécution via le daemon Docker local."
          >
            <div className="flex items-center gap-2">
              <Box className="h-3.5 w-3.5 text-sky-400" />
              <Toggle
                checked={settings.scanner_toggles.docker}
                onChange={(v) => patchToggles({ docker: v })}
              />
            </div>
          </FieldRow>

          <FieldRow
            label="Processus"
            hint="Détecte les serveurs et bases de données actifs sur cette machine (nginx, postgres, redis…)."
          >
            <div className="flex items-center gap-2">
              <Cpu className="h-3.5 w-3.5 text-emerald-400" />
              <Toggle
                checked={settings.scanner_toggles.processes}
                onChange={(v) => patchToggles({ processes: v })}
              />
            </div>
          </FieldRow>

          <FieldRow
            label="Services"
            hint="Détecte les services système gérés par l'OS (systemd sur Linux, launchd sur macOS)."
          >
            <div className="flex items-center gap-2">
              <Server className="h-3.5 w-3.5 text-violet-400" />
              <Toggle
                checked={settings.scanner_toggles.services}
                onChange={(v) => patchToggles({ services: v })}
              />
            </div>
          </FieldRow>
        </div>

        {!settings.scanner_toggles.docker &&
          !settings.scanner_toggles.processes &&
          !settings.scanner_toggles.services && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2.5">
            <AlertTriangle className="h-4 w-4 shrink-0 text-red-400" />
            <p className="text-xs text-red-400">
              Toutes les sources sont désactivées — le scan retournera toujours une liste vide.
            </p>
          </div>
        )}
      </SectionCard>

      {/* Save bar */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          className="flex items-center gap-2 rounded-xl border border-wg-cyan/30 bg-wg-cyan/10 px-5 py-2.5 text-sm font-semibold text-wg-cyan transition-all duration-200 hover:border-wg-cyan/60 hover:bg-wg-cyan/20 hover:shadow-cyan-glow disabled:opacity-40 disabled:cursor-not-allowed active:scale-95"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {saving ? "Sauvegarde…" : "Sauvegarder"}
        </button>

        {dirty && !saving && (
          <p className="text-xs text-wg-muted">
            Modifications non sauvegardées
          </p>
        )}
      </div>
    </div>
  );
}
