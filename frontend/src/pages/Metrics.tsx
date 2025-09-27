import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

type MetricsState = {
  status: "loading" | "ready" | "error";
  payload: string;
};

function MetricsPage(): JSX.Element {
  const [metrics, setMetrics] = useState<MetricsState>({ status: "loading", payload: "" });

  const loadMetrics = useCallback(async () => {
    setMetrics((prev) => ({ status: "loading", payload: prev.payload }));
    try {
      const response = await fetch(`${API_BASE_URL}/metrics`);
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      const text = await response.text();
      setMetrics({ status: "ready", payload: text });
    } catch (err) {
      setMetrics({ status: "error", payload: err instanceof Error ? err.message : "Unknown error" });
    }
  }, [API_BASE_URL]);

  useEffect(() => {
    void loadMetrics();
  }, [loadMetrics]);

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-3xl font-semibold text-gold">Real-time Observability</h2>
        <p className="text-sm text-slate-400">
          Inspect the Prometheus metrics exported by the backend and refresh to fetch the most recent snapshot.
        </p>
        <button
          type="button"
          onClick={() => void loadMetrics()}
          className="self-start rounded-full border border-gold/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-gold transition hover:bg-gold/10"
        >
          Refresh
        </button>
      </header>
      <div className="overflow-hidden rounded-3xl border border-white/10 bg-black/60 shadow-xl">
        <div className="flex items-center justify-between border-b border-white/10 bg-black/40 px-5 py-3 text-xs uppercase tracking-[0.3em] text-slate-400">
          <span>Raw Export</span>
          <span className="text-slate-500">{metrics.status}</span>
        </div>
        <pre className="max-h-[480px] overflow-auto px-5 py-6 text-xs leading-relaxed text-emerald-200">
          {metrics.payload || "Loading…"}
        </pre>
      </div>
    </section>
  );
}

export default MetricsPage;
