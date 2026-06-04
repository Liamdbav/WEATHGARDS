import { AlertTriangle, RefreshCw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[WEATHGARDS] Uncaught error:", error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-wg-bg px-6">
        <div className="flex w-full max-w-md flex-col items-center gap-6 text-center animate-fade-in">
          {/* Icon */}
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10">
            <AlertTriangle className="h-7 w-7 text-red-400" />
          </div>

          {/* Heading */}
          <div className="space-y-2">
            <h1 className="font-mono text-base font-bold uppercase tracking-widest text-wg-text">
              Erreur inattendue
            </h1>
            <p className="text-xs text-wg-muted leading-relaxed">
              Un composant React a planté. Rechargez la page ou vérifiez la console pour les détails.
            </p>
          </div>

          {/* Error message */}
          {this.state.error && (
            <pre className="w-full overflow-auto rounded-xl border border-wg-border bg-wg-card px-4 py-3 font-mono text-xs text-red-400/80 text-left max-h-36 leading-relaxed">
              {this.state.error.message}
            </pre>
          )}

          {/* Reload button */}
          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 rounded-xl border border-wg-cyan/30 bg-wg-cyan/10 px-5 py-2.5 text-sm font-semibold text-wg-cyan transition-all duration-200 hover:border-wg-cyan/60 hover:bg-wg-cyan/20 hover:shadow-cyan-glow active:scale-95"
          >
            <RefreshCw className="h-4 w-4" />
            Recharger la page
          </button>
        </div>
      </div>
    );
  }
}
