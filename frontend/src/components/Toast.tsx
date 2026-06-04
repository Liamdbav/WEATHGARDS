import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  removing: boolean;
}

interface ToastCtx {
  show: (message: string, type?: ToastType) => void;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const Ctx = createContext<ToastCtx | null>(null);

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be inside <ToastProvider>");
  return ctx;
}

// ---------------------------------------------------------------------------
// Visual toast item
// ---------------------------------------------------------------------------

const TOAST_STYLE: Record<ToastType, { border: string; icon: typeof Info; iconColor: string }> = {
  success: {
    border: "border-emerald-500/30",
    icon: CheckCircle2,
    iconColor: "text-emerald-400",
  },
  error: {
    border: "border-red-500/30",
    icon: AlertCircle,
    iconColor: "text-red-400",
  },
  info: {
    border: "border-wg-cyan/20",
    icon: Info,
    iconColor: "text-wg-cyan",
  },
};

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const { border, icon: Icon, iconColor } = TOAST_STYLE[toast.type];

  return (
    <div
      className={`
        flex items-start gap-3 rounded-xl border ${border}
        bg-wg-card/95 px-4 py-3 shadow-lg backdrop-blur-md
        transition-all duration-300
        ${toast.removing ? "translate-x-full opacity-0" : "translate-x-0 opacity-100"}
      `}
      style={{ minWidth: "280px", maxWidth: "380px" }}
    >
      <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${iconColor}`} />
      <p className="flex-1 text-xs font-medium text-wg-text leading-relaxed">
        {toast.message}
      </p>
      <button
        onClick={() => onDismiss(toast.id)}
        className="shrink-0 text-wg-muted hover:text-wg-text transition-colors"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider + container
// ---------------------------------------------------------------------------

const DISMISS_DELAY_MS = 3200;
const REMOVE_ANIM_MS = 300;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: string) => {
    // Mark as removing to trigger slide-out animation
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, removing: true } : t))
    );
    // Remove from DOM after animation
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, REMOVE_ANIM_MS);
  }, []);

  const show = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = `toast-${++counter.current}`;
      setToasts((prev) => [...prev, { id, type, message, removing: false }]);
      setTimeout(() => dismiss(id), DISMISS_DELAY_MS);
    },
    [dismiss]
  );

  return (
    <Ctx.Provider value={{ show }}>
      {children}

      {/* Fixed container — bottom-right */}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 items-end">
        {toasts.map((t) => (
          <ToastCard key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </Ctx.Provider>
  );
}
