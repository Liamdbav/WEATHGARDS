import { Box, Cpu, Server, Zap } from "lucide-react";
import { type ScanResult } from "../api";
import { StatusBadge } from "./StatusBadge";

const TYPE_ICON = {
  docker: Box,
  process: Cpu,
  service: Server,
} as const;

const TYPE_STYLE = {
  docker: {
    icon: "text-sky-400",
    iconBg: "bg-sky-400/10",
    badge: "bg-sky-400/10 text-sky-400 border-sky-400/20",
  },
  process: {
    icon: "text-emerald-400",
    iconBg: "bg-emerald-400/10",
    badge: "bg-emerald-400/10 text-emerald-400 border-emerald-400/20",
  },
  service: {
    icon: "text-violet-400",
    iconBg: "bg-violet-400/10",
    badge: "bg-violet-400/10 text-violet-400 border-violet-400/20",
  },
} as const;

interface Tag {
  label: string;
  value: string;
}

const TYPE_LABEL_FR: Record<ScanResult["type"], string> = {
  docker: "docker",
  process: "processus",
  service: "service",
};

function extractTags(type: ScanResult["type"], meta: Record<string, unknown>): Tag[] {
  const tags: Tag[] = [];

  if (type === "docker") {
    if (typeof meta.image === "string") tags.push({ label: "image", value: meta.image });
    if (Array.isArray(meta.ports)) {
      (meta.ports as unknown[]).slice(0, 3).forEach((p) =>
        tags.push({ label: "port", value: String(p) })
      );
    }
  } else if (type === "process") {
    if (meta.pid !== undefined) tags.push({ label: "PID", value: String(meta.pid) });
    if (typeof meta.username === "string") tags.push({ label: "util.", value: meta.username });
    if (typeof meta.cmdline === "string")
      tags.push({ label: "cmd", value: meta.cmdline.slice(0, 24) });
  } else if (type === "service") {
    if (meta.port !== undefined) tags.push({ label: "port", value: String(meta.port) });
    if (typeof meta.unit === "string") tags.push({ label: "unité", value: meta.unit });
  }

  return tags;
}

interface Props {
  result: ScanResult;
  onActivate?: (result: ScanResult) => void;
}

export function ServiceCard({ result, onActivate }: Props) {
  const Icon = TYPE_ICON[result.type] ?? Server;
  const style = TYPE_STYLE[result.type];
  const tags = extractTags(result.type, result.metadata);

  return (
    <article className="group relative flex flex-col gap-4 rounded-xl border border-wg-border bg-wg-card p-4 transition-all duration-200 hover:border-wg-cyan/30 hover:shadow-card-active">
      {/* Subtle top-edge glow on hover */}
      <span className="pointer-events-none absolute inset-x-0 top-0 h-px rounded-t-xl bg-gradient-to-r from-transparent via-wg-cyan/30 to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-100" />

      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${style.iconBg}`}>
            <Icon className={`h-4 w-4 ${style.icon}`} />
          </span>
          <div className="min-w-0">
            <p className="truncate font-mono text-sm font-semibold text-wg-text">
              {result.name}
            </p>
            <p className="text-xs text-wg-muted">{result.os_origin}</p>
          </div>
        </div>
        <StatusBadge status={result.status} />
      </div>

      {/* Type badge */}
      <div className="flex flex-wrap gap-1.5">
        <span
          className={`inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-xs font-medium uppercase tracking-wider ${style.badge}`}
        >
          {TYPE_LABEL_FR[result.type]}
        </span>
        {tags.map((t) => (
          <span
            key={`${t.label}-${t.value}`}
            className="inline-flex items-center gap-1 rounded-md border border-wg-border bg-wg-bg/60 px-2 py-0.5 font-mono text-xs text-wg-muted"
          >
            <span className="text-wg-muted/60">{t.label}:</span>
            <span className="text-wg-text/80 truncate max-w-[120px]">{t.value}</span>
          </span>
        ))}
      </div>

      {/* CTA */}
      <div className="mt-auto flex justify-end">
        <button
          onClick={() => onActivate?.(result)}
          className="flex items-center gap-1.5 rounded-lg border border-wg-cyan/20 bg-wg-cyan/5 px-3 py-1.5 text-xs font-medium text-wg-cyan transition-all duration-200 hover:border-wg-cyan/40 hover:bg-wg-cyan/10 hover:shadow-cyan-glow active:scale-95"
        >
          <Zap className="h-3 w-3" />
          Activer un outil MCP
        </button>
      </div>
    </article>
  );
}
