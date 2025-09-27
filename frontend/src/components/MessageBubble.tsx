import { useState } from "react";
import clsx from "clsx";

type Citation = {
  title: string;
  url: string;
};

export type Message = {
  id: string;
  role: "user" | "agent";
  agent?: string;
  content: string;
  citations?: Citation[];
  correlationId?: string;
  meta?: Record<string, unknown>;
  route?: string;
  timestamp: string;
};

type Props = {
  message: Message;
};

const agentLabels: Record<string, string> = {
  knowledge: "Knowledge Agent",
  support: "Support Agent",
  custom: "Custom Agent",
  slack: "Slack Agent",
  redirect: "Redirect",
};

const roleDecorations: Record<string, { bubble: string; accent: string; alignment: string; wrapper: string }> = {
  user: {
    wrapper: "items-end",
    alignment: "text-right",
    bubble:
      "bg-gradient-to-br from-gold/80 via-gold to-amber-400 text-midnight shadow-lg shadow-amber-500/20",
    accent: "text-xs font-semibold uppercase tracking-[0.3em] text-amber-200/70",
  },
  agent: {
    wrapper: "items-start",
    alignment: "text-left",
    bubble: "bg-slate-900/80 border border-white/10 text-slate-100",
    accent: "text-xs font-semibold uppercase tracking-[0.3em] text-slate-400",
  },
};

function MessageBubble({ message }: Props): JSX.Element {
  const [copied, setCopied] = useState(false);
  const decoration = roleDecorations[message.role];
  const agentLabel = message.agent ? agentLabels[message.agent] ?? message.agent : "You";
  const routeLabel = message.route ? `via ${message.route}` : undefined;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.warn("Clipboard copy failed", err);
    }
  };

  return (
    <div className={clsx("flex w-full", decoration.wrapper)}>
      <div className={clsx("max-w-[80%] space-y-3", decoration.alignment)}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col items-start">
            <span className={decoration.accent}>{agentLabel}</span>
            {message.role === "agent" && routeLabel && (
              <span className="text-[10px] uppercase tracking-[0.3em] text-slate-500">{routeLabel}</span>
            )}
          </div>
          {message.role === "agent" && (
            <button
              type="button"
              onClick={handleCopy}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.3em] text-slate-200 transition hover:border-gold/40 hover:text-gold"
            >
              {copied ? "Copiado" : "Copiar"}
            </button>
          )}
        </div>
        <div className={clsx("whitespace-pre-wrap rounded-3xl px-5 py-4 text-sm leading-relaxed shadow-xl", decoration.bubble)}>
          {message.content}
        </div>
        {message.citations && message.citations.length > 0 && (
          <ol className="list-inside list-decimal space-y-1 text-xs text-slate-300">
            {message.citations.map((citation, index) => (
              <li key={`${message.id}-citation-${index}`}>
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-gold underline-offset-2 hover:underline"
                >
                  {citation.title || citation.url}
                </a>
              </li>
            ))}
          </ol>
        )}
        {message.role === "agent" && message.correlationId && (
          <div className="text-[10px] uppercase tracking-[0.3em] text-slate-500">
            correlation: <span className="text-slate-300">{message.correlationId}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default MessageBubble;
