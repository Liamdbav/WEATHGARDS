type StatusLevel = "running" | "warning" | "stopped" | "unknown";

function classify(status: string): StatusLevel {
  const s = status.toLowerCase();
  if (["running", "active", "healthy", "up"].includes(s)) return "running";
  if (["warning", "degraded", "starting", "restarting", "paused"].includes(s)) return "warning";
  if (["stopped", "exited", "dead", "failed", "inactive", "down"].includes(s)) return "stopped";
  return "unknown";
}

const LABEL_FR: Record<StatusLevel, string> = {
  running: "actif",
  warning: "dégradé",
  stopped: "arrêté",
  unknown: "inconnu",
};

const LEVEL: Record<StatusLevel, { dot: string; glow: string; text: string }> = {
  running: {
    dot: "bg-emerald-400",
    glow: "bg-emerald-400",
    text: "text-emerald-400",
  },
  warning: {
    dot: "bg-amber-400",
    glow: "bg-amber-400",
    text: "text-amber-400",
  },
  stopped: {
    dot: "bg-red-500",
    glow: "bg-red-500",
    text: "text-red-400",
  },
  unknown: {
    dot: "bg-wg-muted",
    glow: "bg-wg-muted",
    text: "text-wg-muted",
  },
};

interface Props {
  status: string;
  showLabel?: boolean;
}

export function StatusBadge({ status, showLabel = true }: Props) {
  const level = classify(status);
  const s = LEVEL[level];
  const pulse = level === "running";

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative flex h-2 w-2 shrink-0">
        {pulse && (
          <span
            className={`absolute inline-flex h-full w-full rounded-full ${s.glow} animate-status-pulse opacity-75`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${s.dot}`} />
      </span>
      {showLabel && (
        <span className={`font-mono text-xs font-medium uppercase tracking-wider ${s.text}`}>
          {LABEL_FR[level]}
        </span>
      )}
    </span>
  );
}
