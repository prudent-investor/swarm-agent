import { useCallback, useEffect, useMemo, useState } from "react";
import { v4 as uuidv4 } from "uuid";

import MessageBubble, { Message } from "./MessageBubble";

const STORAGE_KEY = "agent-workflow-chat-history";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

type SendState = "idle" | "loading" | "error";

type ChatResponse = {
  agent: string;
  content: string;
  citations?: { title: string; url: string }[];
  meta?: { [key: string]: unknown; route?: string; correlation_id?: string } & Record<string, unknown>;
  correlation_id?: string;
};

type ChatError = {
  message: string;
};

function Chat(): JSX.Element {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [state, setState] = useState<SendState>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed: Message[] = JSON.parse(stored);
        setMessages(parsed);
      }
    } catch (err) {
      console.warn("Failed to load chat history", err);
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch (err) {
      console.warn("Failed to persist chat history", err);
    }
  }, [messages]);

  const canSend = useMemo(() => input.trim().length > 0 && state !== "loading", [input, state]);

  const handleNewChat = () => {
    setMessages([]);
    setError(null);
    setInput("");
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch (err) {
      console.warn("Failed to reset chat history", err);
    }
  };

  const sendMessage = useCallback(async () => {
    if (!canSend) return;

    const trimmed = input.trim();
    const userMessage: Message = {
      id: uuidv4(),
      role: "user",
      content: trimmed,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setState("loading");
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: trimmed }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as ChatError | null;
        const reason =
          data?.message ||
          (typeof (data as Record<string, unknown>)?.detail === "string"
            ? ((data as Record<string, string>).detail as string)
            : undefined) ||
          (typeof (data as Record<string, unknown>)?.error === "string"
            ? ((data as Record<string, string>).error as string)
            : undefined) ||
          `${response.status} ${response.statusText}`;
        throw new Error(reason);
      }

      const payload: ChatResponse = await response.json();
      const correlationId =
        typeof payload.correlation_id === "string"
          ? payload.correlation_id
          : typeof payload.meta?.correlation_id === "string"
          ? payload.meta?.correlation_id
          : undefined;
      const route = typeof payload.meta?.route === "string" ? payload.meta.route : undefined;
      const agentMessage: Message = {
        id: uuidv4(),
        role: "agent",
        agent: payload.agent,
        content: payload.content,
        citations: payload.citations ?? [],
        correlationId,
        meta: payload.meta ?? {},
        route,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, agentMessage]);
      setState("idle");
    } catch (err) {
      console.error(err);
      setState("error");
      setError(err instanceof Error ? err.message : "Unexpected error");
    }
  }, [API_BASE_URL, canSend, input]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void sendMessage();
  };

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3 rounded-3xl border border-white/10 bg-slate-950/60 p-6 shadow-2xl shadow-black/30 backdrop-blur-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gold">Conversational Console</h1>
            <p className="text-sm text-slate-400">
              Chat with the autonomous agents, inspect reroutes, and monitor correlation identifiers.
            </p>
          </div>
          <button
            type="button"
            onClick={handleNewChat}
            className="rounded-full border border-gold/70 px-4 py-2 text-sm font-medium text-gold transition hover:-translate-y-[1px] hover:bg-gold/10"
          >
            New chat
          </button>
        </div>
        <div className="flex max-h-[520px] flex-col gap-4 overflow-y-auto pr-2">
          {messages.length === 0 ? (
            <div className="flex h-60 items-center justify-center rounded-2xl border border-dashed border-slate-700/60 bg-slate-900/40">
              <div className="text-center text-slate-400">
                <p className="font-medium">Start a new conversation</p>
                <p className="text-sm">
                  Ask for product knowledge, support diagnostics, custom integrations, or escalate to a human agent.
                </p>
              </div>
            </div>
          ) : (
            messages.map((message) => <MessageBubble key={message.id} message={message} />)
          )}
          {state === "loading" && (
            <div className="flex justify-start">
              <div className="flex items-center gap-3 rounded-2xl bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
                <span className="h-3 w-3 animate-ping rounded-full bg-gold/80" aria-hidden />
                <span>Processing request…</span>
              </div>
            </div>
          )}
        </div>
        {error && (
          <div className="rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label htmlFor="chat-input" className="text-xs uppercase tracking-[0.3em] text-slate-500">
            Your message
          </label>
          <textarea
            id="chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Type a message…"
            rows={3}
            className="w-full resize-none rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-gold/60 focus:ring-2 focus:ring-gold/30"
          />
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">Connected to {API_BASE_URL}</p>
            <button
              type="submit"
              disabled={!canSend}
              className="rounded-full bg-gold px-5 py-2 text-sm font-semibold text-midnight transition enabled:hover:-translate-y-[1px] enabled:hover:bg-gold/90 disabled:cursor-not-allowed disabled:bg-slate-600/50 disabled:text-slate-300/60"
            >
              {state === "loading" ? "Sending…" : "Send"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default Chat;
