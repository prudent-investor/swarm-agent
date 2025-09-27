import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

type ServiceState = {
  status: "loading" | "ready" | "error";
  data?: unknown;
  error?: string;
};

function StatusPage(): JSX.Element {
  const [health, setHealth] = useState<ServiceState>({ status: "loading" });
  const [readiness, setReadiness] = useState<ServiceState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    const fetchStatus = async (path: string, setter: (value: ServiceState) => void) => {
      setter({ status: "loading" });
      try {
        const response = await fetch(`${API_BASE_URL}${path}`, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`${response.status} ${response.statusText}`);
        }
        const data = await response.json();
        setter({ status: "ready", data });
      } catch (err) {
        if (controller.signal.aborted) return;
        setter({ status: "error", error: err instanceof Error ? err.message : "Unknown error" });
      }
    };

    void fetchStatus("/health", setHealth);
    void fetchStatus("/readiness", setReadiness);

    return () => controller.abort();
  }, []);

  const renderCard = (title: string, state: ServiceState) => {
    const indicator =
      state.status === "loading"
        ? "bg-slate-500"
        : state.status === "ready"
        ? "bg-emerald-400"
        : "bg-rose-500";

    return (
      <div className="flex flex-col gap-3 rounded-3xl border border-white/10 bg-slate-950/70 p-6 shadow-2xl shadow-black/30">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">{title}</p>
            <p className="text-2xl font-semibold text-slate-100">{state.status}</p>
          </div>
          <span className={`h-3 w-3 rounded-full ${indicator}`} aria-hidden />
        </div>
        <pre className="overflow-x-auto rounded-2xl bg-black/40 p-4 text-xs text-slate-300">
          {state.data ? JSON.stringify(state.data, null, 2) : state.error ?? "Loading…"}
        </pre>
      </div>
    );
  };

  return (
    <section className="flex flex-col gap-6">
      <header className="space-y-2">
        <h2 className="text-3xl font-semibold text-gold">Operational Status</h2>
        <p className="text-sm text-slate-400">
          Quickly confirm whether the backend services are healthy and ready to receive traffic.
        </p>
      </header>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {renderCard("/health", health)}
        {renderCard("/readiness", readiness)}
      </div>
    </section>
  );
}

export default StatusPage;
