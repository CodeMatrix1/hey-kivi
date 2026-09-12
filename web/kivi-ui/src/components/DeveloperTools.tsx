import { useMemo, useState } from "react";
import type { Conversation, DecisionTrace, QueryCase } from "../types";

type DevTab = "queries" | "traces" | "metrics";

interface DeveloperToolsProps {
  queryCases: QueryCase[];
  conversations: Conversation[];
  activeConvId: string | null;
  onTryQuery: (message: string) => void;
}

function formatTrace(trace: DecisionTrace): string {
  return JSON.stringify(trace, null, 2);
}

export function DeveloperTools({
  queryCases,
  conversations,
  activeConvId,
  onTryQuery,
}: DeveloperToolsProps) {
  const [tab, setTab] = useState<DevTab>("queries");
  const [selectedTurn, setSelectedTurn] = useState<string>("");

  const activeConv = conversations.find((c) => c.id === activeConvId) || conversations[0];
  const turns = useMemo(
    () =>
      (activeConv?.messages || [])
        .filter((m) => m.role === "assistant" && m.trace)
        .map((m, i) => ({
          id: m.id,
          label: `Turn ${i + 1}`,
          trace: m.trace!,
          metrics: m.metrics,
        })),
    [activeConv],
  );

  const currentTurn = turns.find((t) => t.id === selectedTurn) || turns[turns.length - 1];

  return (
    <div className="developer-view">
      <header className="page-header">
        <h2>Developer tools</h2>
        <p className="muted">Query library, decision traces, and turn metrics</p>
      </header>

      <div className="dev-tabs">
        {(["queries", "traces", "metrics"] as DevTab[]).map((t) => (
          <button
            key={t}
            type="button"
            className={`chip ${tab === t ? "chip-active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "queries" ? "Query Library" : t === "traces" ? "Decision Traces" : "Metrics"}
          </button>
        ))}
      </div>

      {tab === "queries" && (
        <div className="query-grid">
          {queryCases.map((q) => (
            <article key={q.id} className="query-card card">
              <span className="starter-category">{q.category}</span>
              <h4>{q.title}</h4>
              <p className="muted query-message">{q.message}</p>
              <button type="button" className="btn-secondary" onClick={() => onTryQuery(q.message)}>
                Try in chat
              </button>
            </article>
          ))}
        </div>
      )}

      {tab === "traces" && (
        <div className="trace-panel card">
          {turns.length === 0 ? (
            <p className="muted">No traces yet — send a message in chat.</p>
          ) : (
            <>
              <label>
                Turn
                <select
                  value={currentTurn?.id || ""}
                  onChange={(e) => setSelectedTurn(e.target.value)}
                >
                  {turns.map((t) => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
              </label>
              <pre className="trace-json">{formatTrace(currentTurn!.trace)}</pre>
            </>
          )}
        </div>
      )}

      {tab === "metrics" && (
        <div className="metrics-panel card">
          {turns.length === 0 ? (
            <p className="muted">No metrics yet.</p>
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th>Turn</th>
                  <th>Elapsed (ms)</th>
                  <th>LLM calls</th>
                  <th>Retain calls</th>
                  <th>Cost (USD)</th>
                </tr>
              </thead>
              <tbody>
                {turns.slice(-10).map((t) => (
                  <tr key={t.id}>
                    <td>{t.label}</td>
                    <td>{t.metrics?.elapsed_ms ?? "—"}</td>
                    <td>{t.metrics?.llm_call_count ?? "—"}</td>
                    <td>{t.metrics?.retain_call_count ?? "—"}</td>
                    <td>{t.metrics?.cost_usd?.toFixed(4) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
