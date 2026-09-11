/**
 * App bootstrap: wires seed / clear / chat form to API + UI modules.
 */

import { getHealth, getStats, postChat, postSeed } from "./api.js?v=8";
import { createMessages } from "./messages.js?v=4";
import { createTrace } from "./trace.js?v=4";
import { loadQueryLibrary } from "./queries.js?v=7";

const messagesEl = document.getElementById("messages");
const traceEl = document.getElementById("trace");
const inputEl = document.getElementById("input");
const statusEl = document.getElementById("status");
const sendBtn = document.getElementById("sendBtn");
const userIdEl = document.getElementById("userId");
const shellEl = document.getElementById("appShell");
const modeDescriptionEl = document.getElementById("modeDescription");
const queryLibraryEl = document.getElementById("queryLibrary");
const libraryNoticeEl = document.getElementById("libraryImportWarning");
const statDictationsEl = document.getElementById("statDictations");
const statMemoriesEl = document.getElementById("statMemories");
const seedBtn = document.getElementById("seedBtn");

const modeCopy = {
  user: "Your personal workspace.",
  developer: "Inspect how every request becomes a response.",
  library: "Curated prompts for the imported history.",
};

const messages = createMessages(messagesEl);
const trace = createTrace(traceEl);

let queryLibrary = [];
let importReady = false;

function setBusy(busy) {
  sendBtn.disabled = busy;
  statusEl.textContent = busy ? "Thinking…" : "";
}

function userId() {
  return userIdEl.value.trim() || "golden_goose_eval_user";
}

function formatCount(value) {
  return value == null ? "—" : String(value);
}

function updateLibraryGuard(stats) {
  importReady = (stats?.dictations ?? 0) > 0;
  if (libraryNoticeEl) {
    libraryNoticeEl.hidden = importReady;
  }
  queryLibraryEl.querySelectorAll(".use-query").forEach((btn) => {
    btn.disabled = !importReady;
    btn.title = importReady
      ? ""
      : "Requires Path A snapshot or Path B import. See RUN.md if counts are zero.";
  });
}

async function refreshStats() {
  try {
    const stats = await getStats(userId());
    statDictationsEl.textContent = formatCount(stats.dictations);
    statMemoriesEl.textContent = formatCount(stats.hindsight_memories);
    updateLibraryGuard(stats);
  } catch {
    statDictationsEl.textContent = "—";
    statMemoriesEl.textContent = "—";
    updateLibraryGuard({ dictations: 0 });
  }
}

function setView(view) {
  shellEl.dataset.mode = view;
  modeDescriptionEl.textContent = modeCopy[view] || modeCopy.user;
  document.querySelectorAll(".mode-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  if (seedBtn) seedBtn.hidden = view !== "developer";
  if (view === "user") inputEl.focus();
}

function renderQueryLibrary() {
  queryLibraryEl.innerHTML = "";
  const byCategory = new Map();
  queryLibrary.forEach((item) => {
    if (!byCategory.has(item.category)) byCategory.set(item.category, []);
    byCategory.get(item.category).push(item);
  });
  byCategory.forEach((items, category) => {
    const sectionEl = document.createElement("section");
    sectionEl.className = "query-section";
    sectionEl.innerHTML = `<h3 class="query-section-title">${category}</h3>`;
    const grid = document.createElement("div");
    grid.className = "query-grid";
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "query-card";
      card.innerHTML = `
        <h4>${item.title}</h4>
        <p class="query-prompt">${item.prompt}</p>
        <div class="expected"><strong>Expected evidence</strong><p>${item.expected}</p></div>
      `;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "use-query";
      button.textContent = "Use this query";
      button.disabled = !importReady;
      button.addEventListener("click", () => {
        if (!importReady) return;
        inputEl.value = item.prompt;
        setView("user");
        inputEl.focus();
        statusEl.textContent = "Query added to the composer. Review it, then press Send.";
      });
      card.appendChild(button);
      grid.appendChild(card);
    });
    sectionEl.appendChild(grid);
    queryLibraryEl.appendChild(sectionEl);
  });
}

async function seed() {
  if (
    !window.confirm(
      "Seed demo wipes SQLite dictations for the current user and loads 3 demo rows. Never use on golden_goose_eval_user after snapshot restore. Corpus import must use a different user id (e.g. corpus_repro_user)."
    )
  ) {
    return;
  }
  setBusy(true);
  try {
    const data = await postSeed(userId());
    statusEl.textContent =
      `Seeded ${data.dictations} dictations, ${data.memories} memories (${data.memory_backend}).`;
    await refreshStats();
    messages.addMsg("bot", "Demo data loaded (developer only). See RUN.md for the reviewer path.");
  } catch (err) {
    statusEl.textContent = String(err.message || err);
  } finally {
    setBusy(false);
  }
}

if (seedBtn) {
  seedBtn.hidden = true;
  seedBtn.addEventListener("click", seed);
}
document.getElementById("clearBtn").addEventListener("click", () => {
  messages.clear();
  trace.clear();
});

document.querySelectorAll(".mode-tab").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.getElementById("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;
  messages.addMsg("user", message);
  inputEl.value = "";
  setBusy(true);
  const startedAt = performance.now();
  try {
    const data = await postChat(userId(), message);
    messages.addMsg("bot", data.reply || "(empty)");
    trace.render({
      ...data.trace,
      __originalInput: message,
      __reply: data.reply || "(empty)",
      __clientLatencyMs: Math.round(performance.now() - startedAt),
      __userId: userId(),
      __metrics: data.metrics || null,
    });
  } catch (err) {
    messages.addMsg("bot", "Error: " + (err.message || err));
  } finally {
    setBusy(false);
    void refreshStats();
    inputEl.focus();
  }
});

userIdEl.addEventListener("change", () => {
  void refreshStats();
});
userIdEl.addEventListener("blur", () => {
  void refreshStats();
});

async function bootstrap() {
  try {
    const health = await getHealth();
    if (health.default_user_id) userIdEl.value = health.default_user_id;
  } catch {
    /* offline / health unavailable */
  }
  try {
    queryLibrary = await loadQueryLibrary();
  } catch (err) {
    queryLibraryEl.innerHTML = `<p class="empty">Could not load query library: ${err.message || err}</p>`;
  }
  renderQueryLibrary();
  await refreshStats();
}

void bootstrap();
