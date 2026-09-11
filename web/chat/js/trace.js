/**
 * Decision-trace renderer.
 * Explains interpret flags, Hindsight retain/recall, lexical store changes,
 * and dictations found this turn.
 */

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function section(title, html) {
  if (!html) return "";
  return `<div class="trace-block"><h3>${esc(title)}</h3><div class="body">${html}</div></div>`;
}

function listSection(title, items, lineFn) {
  if (!items || !items.length) return "";
  const lis = items.map((x) => `<li>${lineFn(x)}</li>`).join("");
  return section(title, `<ul>${lis}</ul>`);
}

function flagPill(label, on) {
  const cls = on ? "flag on" : "flag off";
  const state = on ? "true" : "false";
  return `<span class="${cls}" title="${esc(label)}=${state}"><span class="dot"></span>${esc(label)}: ${state}</span>`;
}

function typeTag(type) {
  if (!type) return "";
  return `<span class="type-tag">${esc(type)}</span>`;
}

function lexicalLine(m) {
  if (!m || typeof m !== "object") return esc(m);
  const alias = m.alias || (m.text || "").split("→")[0]?.trim();
  const canonical = m.canonical || (m.text || "").split("→")[1]?.trim();
  const kind = m.kind ? ` [${m.kind}]` : "";
  const id = m.id ? ` · ${m.id}` : "";
  if (alias && canonical) {
    return `${typeTag(m.type || "Lexical")}${esc(`${alias} → ${canonical}`)}${esc(kind)}${esc(id)}`;
  }
  return esc((m.text || JSON.stringify(m)).slice(0, 160));
}

function ignoredLine(m) {
  if (!m || typeof m !== "object") return esc(m);
  const why = m.reason ? ` — ${m.reason}` : "";
  return esc((m.text || "").slice(0, 120) + why);
}

function updatedLine(m) {
  if (!m || typeof m !== "object") return esc(m);
  return esc(`${m.id || "?"} → ${m.action || "updated"}`);
}

function recalledLine(m) {
  if (!m || typeof m !== "object") return esc(m);
  const text = (m.text || "").replace(/\s+/g, " ").trim();
  const short = text.length > 160 ? text.slice(0, 157) + "…" : text;
  const prov = [];
  if (m.source_dictation_id) prov.push(`dictation ${m.source_dictation_id}`);
  if (m.id) prov.push(`memory ${m.id}`);
  const provLine = prov.length ? ` · ${prov.join(" · ")}` : "";
  return `${typeTag(m.type || "Memory")}${esc(short)}${esc(provLine)}`;
}

function formatDbDelta(delta) {
  if (!delta || typeof delta !== "object") return "—";
  const parts = Object.entries(delta)
    .filter(([, value]) => value !== 0)
    .map(([key, value]) => `${key}: ${value > 0 ? "+" : ""}${value}`);
  return parts.length ? parts.join(", ") : "no change";
}

function metricsSection(metrics, clientLatencyMs) {
  if (!metrics || typeof metrics !== "object") {
    return (
      `<div class="trace-meta">Database growth, provider token usage, and cost are not emitted by the current API, so this turn cannot report them.</div>`
    );
  }
  return (
    `<div class="audit-grid" style="margin-top:8px">` +
      `<div><span>Server elapsed</span><strong>${esc(`${metrics.elapsed_ms} ms`)}</strong></div>` +
      `<div><span>Browser round-trip</span><strong>${clientLatencyMs != null ? esc(`${clientLatencyMs} ms`) : "Unavailable"}</strong></div>` +
      `<div><span>LLM calls</span><strong>${esc(metrics.llm_call_count)}</strong></div>` +
      `<div><span>Retain calls</span><strong>${esc(metrics.retain_call_count)}</strong></div>` +
      `<div><span>DB delta</span><strong>${esc(formatDbDelta(metrics.db_delta))}</strong></div>` +
      `<div><span>Est. cost (USD)</span><strong>${esc(metrics.cost_usd)}</strong></div>` +
      `</div>` +
      `<div class="trace-meta">Provider token counts are not returned by the LLM client; use llm_call_count and KIVI_ESTIMATED_*_COST_USD env vars for estimates.</div>`
  );
}

function appliedLine(p) {
  const kind = p.kind ? ` [${p.kind}]` : "";
  return esc(`${p.observed || "?"} → ${p.preferred || "?"}${kind}`);
}

function dictationLine(c) {
  const score = c.score != null ? ` score ${c.score}` : "";
  const preview = (c.formatted_preview || "").slice(0, 90);
  return esc(`${c.id} @ ${c.created_at || "?"}${score} — ${preview}`);
}

function llmOutputHtml(output) {
  if (output == null) return `<span class="trace-meta">(none)</span>`;
  const text =
    typeof output === "string" ? output : JSON.stringify(output, null, 2);
  const short = text.length > 900 ? text.slice(0, 897) + "…" : text;
  return `<pre class="llm-out">${esc(short)}</pre>`;
}

function llmCallsSection(calls) {
  if (!calls || !calls.length) {
    return section("LLM outputs", `<span class="trace-meta">No LLM steps this turn</span>`);
  }
  const blocks = calls
    .map((c) => {
      const step = c.step || "?";
      const source = c.source || "?";
      return (
        `<div class="llm-call">` +
        `<div><strong>${esc(step)}</strong> ` +
        `<span class="type-tag">${esc(source)}</span></div>` +
        llmOutputHtml(c.output) +
        `</div>`
      );
    })
    .join("");
  return section("LLM outputs", blocks);
}

export function createTrace(traceEl) {
  function render(trace) {
    if (!trace || typeof trace !== "object") {
      traceEl.innerHTML = `<p class="empty">No trace for this turn.</p>`;
      return;
    }

    const decision = trace.decision || "—";
    const pillClass = decision === "abstain" || decision === "answer" ? decision : "answer";

    let html = "";

    html += section(
      "Evaluation record",
      `<div class="audit-grid">` +
        `<div><span>Original input</span><strong>${esc(trace.__originalInput || "Unavailable")}</strong></div>` +
        `<div><span>User scope</span><strong>${esc(trace.__userId || "Unavailable")}</strong></div>` +
        `</div>` +
        metricsSection(trace.__metrics, trace.__clientLatencyMs)
    );

    html += section(
      "Outcome",
      `<span class="pill ${pillClass}">${esc(decision)}</span>` +
        (trace.reason
          ? `<div class="trace-meta" style="margin-top:6px">${esc(trace.reason)}</div>`
          : "")
    );

    html += section(
      "Resulting Hey Kivi behavior",
      `<div class="trace-meta">Final response from this pipeline turn</div>` +
        `<div class="behavior-reply">${esc(trace.__reply || "Unavailable")}</div>`
    );

    html += section(
      "Interpret flags",
      `<div class="flag-row">` +
        flagPill("wants_dictation", !!trace.wants_dictation) +
        flagPill("wants_cross_recall", !!trace.wants_cross_recall) +
        `</div>` +
        `<div class="trace-meta">Routes: dictation → find/polish · cross_recall → Hindsight recall</div>`
    );

    html += llmCallsSection(trace.llm_calls);

    // Lexical store
    const lexicalBits = [];
    if (trace.memories_retained && trace.memories_retained.length) {
      lexicalBits.push(
        listSection("Added to lexical store", trace.memories_retained, lexicalLine)
      );
    }
    if (trace.memories_ignored && trace.memories_ignored.length) {
      lexicalBits.push(listSection("Lexical ignored", trace.memories_ignored, ignoredLine));
    }
    if (trace.memories_updated && trace.memories_updated.length) {
      lexicalBits.push(listSection("Lexical superseded", trace.memories_updated, updatedLine));
    }
    if (trace.applied_preferences && trace.applied_preferences.length) {
      lexicalBits.push(
        listSection("Lexical applied this turn", trace.applied_preferences, appliedLine)
      );
    }
    if (trace.canonicalized_message) {
      const rawCanon = esc(trace.canonicalized_message);
      lexicalBits.push(
        section(
          "Canonicalized message",
          rawCanon +
            (trace.applied_preferences?.length
              ? `<div class="trace-meta">Aliases rewritten before retain / interpret</div>`
              : `<div class="trace-meta">No alias rewrites this turn</div>`)
        )
      );
    }
    if (lexicalBits.length) {
      html += lexicalBits.join("");
    } else {
      html += section("Lexical", `<span class="trace-meta">No lexical changes this turn</span>`);
    }

    // Semantic retain
    if (trace.semantic_retain) {
      html += section(
        "Memory created / retain attempt",
        `<div>Sent canonical source text for semantic extraction (Fact / Preference / Episode).</div>` +
          (trace.semantic_retain_preview
            ? `<div style="margin-top:6px">${esc(trace.semantic_retain_preview)}</div>`
            : "") +
          `<div class="trace-meta">Provenance: ${esc(trace.source_dictation_id || "no source dictation id")}. Hindsight’s individual extracted-memory IDs are not returned by this API.</div>`
      );
    } else {
      html += section("Memory created / retain attempt", `<span class="trace-meta">Not retained this turn</span>`);
    }

    // Recall
    if (trace.tools_used && trace.tools_used.includes("hindsight_recall")) {
      const backend = trace.retrieval_backend && trace.retrieval_backend !== "none"
        ? trace.retrieval_backend
        : "unknown";
      html += section(
        "Hindsight recall",
        `<div>Backend: <strong>${esc(backend)}</strong></div>` +
          (trace.retrieval_query
            ? `<div class="trace-meta">Query: ${esc(trace.retrieval_query)}</div>`
            : "")
      );
      const memories = trace.memories_considered || [];
      if (memories.length) {
        html += section(
          `Memory retrieved (${memories.length})`,
          `<ul>${memories.map((m) => `<li>${recalledLine(m)}</li>`).join("")}</ul>`
        );
      } else {
        html += section("Memory retrieved", `<span class="trace-meta">None matched</span>`);
      }
    }

    // Dictations
    if (trace.selected_dictation_id) {
      html += section(
        "Dictation selected",
        `<strong>${esc(trace.selected_dictation_id)}</strong>` +
          (trace.tools_used?.includes("polish_dictation")
            ? `<div class="trace-meta">Polished with optional recall context + lexical apply</div>`
            : "")
      );
    }
    if (trace.candidates && trace.candidates.length) {
      html += listSection(
        "Dictations found",
        trace.candidates.slice(0, 5),
        dictationLine
      );
    } else if (trace.wants_dictation) {
      html += section("Dictations found", `<span class="trace-meta">No matches</span>`);
    }

    if (trace.tools_used && trace.tools_used.length) {
      html += section("Tools", esc(trace.tools_used.join(" · ")));
    }

    if (trace.source_dictation_id) {
      html += section(
        "Provenance",
        `<div>Current source dictation: <code>${esc(trace.source_dictation_id)}</code></div>` +
          `<div class="trace-meta">Retrieved memory cards and selected dictations above are the evidence available to this result.</div>`
      );
    }

    traceEl.innerHTML = html || `<p class="empty">Nothing notable in this turn.</p>`;
  }

  function clear() {
    traceEl.innerHTML = `<p class="empty">Send a message to see the trace.</p>`;
  }

  return { render, clear };
}
