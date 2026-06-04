import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHealth, fetchScan, type HealthResponse, type ScanResult } from "../api";

export type ScanState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; data: ScanResult[]; lastFetch: Date }
  | { status: "error"; message: string };

export type HealthState =
  | { status: "loading" }
  | { status: "ok"; data: HealthResponse }
  | { status: "error"; message: string };

const POLL_INTERVAL_MS = 30_000;

export function useScan() {
  const [scanState, setScanState] = useState<ScanState>({ status: "idle" });
  const [healthState, setHealthState] = useState<HealthState>({ status: "loading" });

  const mounted = useRef(true);
  const pollingActive = useRef(false);
  const pollingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        if (mounted.current) setHealthState({ status: "ok", data });
      })
      .catch((e: unknown) => {
        if (mounted.current)
          setHealthState({
            status: "error",
            message: e instanceof Error ? e.message : String(e),
          });
      });

    return () => {
      mounted.current = false;
      pollingActive.current = false;
      if (pollingTimer.current) clearTimeout(pollingTimer.current);
    };
  }, []);

  const execScan = useCallback((): Promise<void> => {
    return fetchScan()
      .then((data) => {
        if (!mounted.current) return;
        setScanState({ status: "ok", data, lastFetch: new Date() });
      })
      .catch((e: unknown) => {
        if (!mounted.current) return;
        setScanState({
          status: "error",
          message: e instanceof Error ? e.message : String(e),
        });
        pollingActive.current = false;
      });
  }, []);

  const scheduleNext = useCallback(() => {
    if (!pollingActive.current || !mounted.current) return;
    pollingTimer.current = setTimeout(async () => {
      await execScan();
      scheduleNext();
    }, POLL_INTERVAL_MS);
  }, [execScan]);

  const triggerScan = useCallback(() => {
    if (pollingTimer.current) clearTimeout(pollingTimer.current);
    pollingActive.current = true;
    setScanState({ status: "loading" });
    void execScan().then(() => scheduleNext());
  }, [execScan, scheduleNext]);

  return { scanState, healthState, triggerScan };
}
