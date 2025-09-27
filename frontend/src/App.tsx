import { NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom";

import Chat from "./components/Chat";
import MetricsPage from "./pages/Metrics";
import StatusPage from "./pages/Status";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-4 py-2 rounded-full text-sm font-medium transition-colors duration-200 ${
    isActive
      ? "bg-gold text-midnight shadow-glow"
      : "text-slate-200 hover:text-gold hover:bg-white/5"
  }`;

function App(): JSX.Element {
  return (
    <Router>
      <div className="min-h-screen bg-midnight text-slate-100">
        <header className="border-b border-white/10 bg-midnight/70 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-gold/80 bg-gold/10 text-lg font-semibold text-gold">
                AW
              </div>
              <div>
                <p className="text-lg font-semibold tracking-wide text-gold">Agent Workflow</p>
                <p className="text-xs uppercase tracking-[0.4em] text-slate-400">Intelligent Support Suite</p>
              </div>
            </div>
            <nav className="flex items-center gap-3">
              <NavLink to="/" end className={navLinkClass}>
                Chat
              </NavLink>
              <NavLink to="/status" className={navLinkClass}>
                Status
              </NavLink>
              <NavLink to="/metrics" className={navLinkClass}>
                Metrics
              </NavLink>
            </nav>
          </div>
        </header>
        <main className="mx-auto flex max-w-5xl flex-1 flex-col gap-10 px-6 py-10">
          <Routes>
            <Route path="/" element={<Chat />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/metrics" element={<MetricsPage />} />
          </Routes>
        </main>
        <footer className="border-t border-white/10 py-6 text-center text-xs text-slate-500">
          © {new Date().getFullYear()} Agent Workflow. Crafted for observability, guardrails & human handoffs.
        </footer>
      </div>
    </Router>
  );
}

export default App;
