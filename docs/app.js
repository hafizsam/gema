// Gema — vanilla JS, no build step. Fetches static JSON from ./data and does
// all scoring lookups client-side; the heavy work already happened offline in
// pipeline/make_puzzle.py.

const DATA_DIR = "data";

// -- normalize() must match pipeline/lexicon.py::normalize exactly, or a
// valid guess like "char koay teow" will never resolve to an entry id.
function normalize(text) {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

async function sha256Hex12(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return hex.slice(0, 12);
}

function todayIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function heatFor(rank, total, tiers) {
  const pct = rank / Math.max(total - 1, 1);
  for (const tier of tiers) {
    if (pct <= tier.max_rank_pct) return tier.name;
  }
  return tiers[tiers.length - 1].name;
}

function heatClass(name) {
  return "heat-" + normalize(name);
}

const els = {
  status: document.getElementById("status"),
  form: document.getElementById("guess-form"),
  input: document.getElementById("guess-input"),
  hint: document.getElementById("input-hint"),
  options: document.getElementById("vocab-options"),
  boardHead: document.getElementById("board-head"),
  list: document.getElementById("guess-list"),
  reveal: document.getElementById("reveal-card"),
  giveUp: document.getElementById("giveup-btn"),
  langToggle: document.getElementById("lang-toggle"),
  helpBtn: document.getElementById("help-btn"),
  helpDialog: document.getElementById("help-dialog"),
  statsBtn: document.getElementById("stats-btn"),
  statsDialog: document.getElementById("stats-dialog"),
  statsGrid: document.getElementById("stats-grid"),
};

const state = {
  date: todayIso(),
  meta: null,
  vocab: null, // id -> entry
  lookup: null, // normalized surface -> id
  puzzle: null,
  guesses: [], // [{id, term, rank, score}], sorted by rank asc
  solved: false,
  gaveUp: false,
  lang: localStorage.getItem("gema_lang") || "en",
};

function storageKey(suffix) {
  return `gema:${state.date}:${suffix}`;
}

function saveProgress() {
  localStorage.setItem(
    storageKey("progress"),
    JSON.stringify({
      guesses: state.guesses.map((g) => g.id),
      solved: state.solved,
      gaveUp: state.gaveUp,
    })
  );
}

function loadProgress() {
  const raw = localStorage.getItem(storageKey("progress"));
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function updateStreak(won) {
  const stats = JSON.parse(
    localStorage.getItem("gema_stats") ||
      '{"played":0,"wins":0,"streak":0,"maxStreak":0,"lastWinDate":null}'
  );
  const already = localStorage.getItem(storageKey("counted"));
  if (already) return stats;

  stats.played += 1;
  if (won) {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const pad = (n) => String(n).padStart(2, "0");
    const yIso = `${yesterday.getFullYear()}-${pad(yesterday.getMonth() + 1)}-${pad(
      yesterday.getDate()
    )}`;
    stats.streak = stats.lastWinDate === yIso ? stats.streak + 1 : 1;
    stats.lastWinDate = state.date;
    stats.wins += 1;
    stats.maxStreak = Math.max(stats.maxStreak, stats.streak);
  } else {
    stats.streak = 0;
  }
  localStorage.setItem("gema_stats", JSON.stringify(stats));
  localStorage.setItem(storageKey("counted"), "1");
  return stats;
}

function setStatus(message, tone = "") {
  els.status.textContent = message;
  els.status.className = "status" + (tone ? ` ${tone}` : "");
}

async function loadJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function init() {
  els.langToggle.textContent = state.lang.toUpperCase();

  let meta, vocabPayload;
  try {
    [meta, vocabPayload] = await Promise.all([
      loadJson(`${DATA_DIR}/meta.json`),
      loadJson(`${DATA_DIR}/vocab.json`),
    ]);
  } catch (err) {
    setStatus("Gagal muatkan data permainan. Cuba muat semula.", "error");
    console.error(err);
    return;
  }
  state.meta = meta;

  state.vocab = new Map(vocabPayload.entries.map((e) => [e.id, e]));
  state.lookup = new Map();
  for (const e of vocabPayload.entries) {
    state.lookup.set(normalize(e.term), e.id);
    for (const alias of e.aliases) state.lookup.set(normalize(alias), e.id);
  }
  populateDatalist(vocabPayload.entries);

  try {
    state.puzzle = await loadJson(`${DATA_DIR}/puzzles/${state.date}.json`);
  } catch (err) {
    setStatus("Belum ada teka-teki untuk hari ini.", "error");
    console.error(err);
    els.form.querySelector("button").disabled = true;
    els.input.disabled = true;
    return;
  }

  els.giveUp.hidden = false;
  restoreProgress();
  wireEvents();
  setStatus(`Teka-teki #${state.puzzle.seq} · ${state.puzzle.total} perkataan dalam senarai`);
}

function populateDatalist(entries) {
  const frag = document.createDocumentFragment();
  for (const e of entries) {
    const opt = document.createElement("option");
    opt.value = e.term;
    frag.appendChild(opt);
  }
  els.options.appendChild(frag);
}

function restoreProgress() {
  const saved = loadProgress();
  if (!saved) return;
  (async () => {
    for (const id of saved.guesses) {
      if (!state.vocab.has(id)) continue;
      await addGuess(id, { silent: true, skipSave: true });
    }
    // Re-derive the outcome from the replayed guesses rather than trusting the
    // saved flags directly: if the puzzle file for this date was regenerated
    // (e.g. the lexicon grew and the answer schedule shifted), a guess that
    // used to win may no longer have rank 0, and blindly trusting `solved`
    // would show a win banner over a board with no rank-0 guess.
    const actuallySolved = state.guesses.some((g) => g.rank === 0);
    if (!actuallySolved && !state.solved && saved.gaveUp) finishGame(false);
  })();
}

const keyCache = new Map(); // id -> hashed key for today's puzzle, memoized

async function keyForToday(id) {
  if (keyCache.has(id)) return keyCache.get(id);
  const key = await sha256Hex12(`${state.meta.salt}:${state.date}:${id}`);
  keyCache.set(id, key);
  return key;
}

function wireEvents() {
  els.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.solved || state.gaveUp) return;
    const raw = els.input.value.trim();
    if (!raw) return;
    const key = normalize(raw);
    const id = state.lookup.get(key);

    if (!id) {
      setStatus(`"${raw}" tiada dalam senarai budaya kami.`, "error");
      return;
    }
    if (state.guesses.some((g) => g.id === id)) {
      setStatus(`Sudah cuba "${state.vocab.get(id).term}".`, "error");
      els.input.value = "";
      return;
    }
    els.input.value = "";
    await addGuess(id);
  });

  els.giveUp.addEventListener("click", () => {
    if (!confirm("Serah kalah dan tunjuk jawapan?")) return;
    finishGame(false);
  });

  els.langToggle.addEventListener("click", () => {
    state.lang = state.lang === "en" ? "ms" : "en";
    localStorage.setItem("gema_lang", state.lang);
    els.langToggle.textContent = state.lang.toUpperCase();
    if (!els.reveal.hidden) renderReveal();
  });

  for (const dialog of [els.helpDialog, els.statsDialog]) {
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) dialog.close();
    });
    dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
  }
  els.helpBtn.addEventListener("click", () => els.helpDialog.showModal());
  els.statsBtn.addEventListener("click", () => {
    renderStats();
    els.statsDialog.showModal();
  });
}

async function addGuess(id, { silent = false, skipSave = false } = {}) {
  const entry = state.vocab.get(id);
  const key = await keyForToday(id);
  const record = state.puzzle.ranks[key];
  if (!record) {
    console.error(`no rank data for ${id}`);
    return;
  }
  const [rank, score] = record;
  const guess = { id, term: entry.term, rank, score };
  state.guesses.push(guess);
  state.guesses.sort((a, b) => a.rank - b.rank);
  renderGuesses();

  if (!skipSave) saveProgress();

  if (rank === 0) {
    finishGame(true);
  } else if (!silent) {
    setStatus(`"${entry.term}" — kedudukan #${rank + 1}`, "");
  }
}

function renderGuesses() {
  els.boardHead.hidden = state.guesses.length === 0;
  els.list.innerHTML = "";
  const total = state.puzzle.total;
  for (const g of state.guesses) {
    const li = document.createElement("li");
    li.className = "guess-row" + (g.rank === 0 ? " correct" : "");
    const heat = g.rank === 0 ? "Betul" : heatFor(g.rank, total, state.meta.heatTiers);
    li.innerHTML = `
      <span class="guess-rank">#${g.rank === 0 ? "1" : g.rank + 1}</span>
      <span class="guess-term">${g.term}</span>
      <span class="guess-score">${g.score.toFixed(1)}%</span>
      <span class="heat-badge ${g.rank === 0 ? "heat-sejuk" : heatClass(heat)}"
            style="${g.rank === 0 ? "background:color-mix(in srgb, var(--ok) 25%, transparent);color:var(--ok);" : ""}">
        ${heat}
      </span>`;
    els.list.appendChild(li);
  }
}

function finishGame(won) {
  state.solved = won;
  state.gaveUp = !won;
  saveProgress();
  els.input.disabled = true;
  els.form.querySelector("button").disabled = true;
  els.giveUp.hidden = true;

  const stats = updateStreak(won);
  setStatus(
    won
      ? `Tahniah! Ditemui dalam ${state.guesses.length} tekaan. 🔥 Jaringan: ${stats.streak}`
      : "Jawapan didedahkan di bawah.",
    won ? "ok" : ""
  );
  renderReveal();
}

async function findAnswerEntry() {
  const ids = [...state.vocab.keys()];
  const keys = await Promise.all(ids.map(keyForToday));
  const idx = keys.indexOf(state.puzzle.answer);
  return idx === -1 ? null : state.vocab.get(ids[idx]);
}

async function renderReveal() {
  const answer = await findAnswerEntry();
  if (!answer) return;
  els.reveal.hidden = false;
  const desc = state.lang === "en" ? answer.desc_en : answer.desc_ms;
  els.reveal.innerHTML = `
    <h2>${answer.term}</h2>
    <div class="meta">${answer.category}${answer.region ? " · " + answer.region : ""}</div>
    <p>${desc}</p>
    <button class="share-btn" id="share-btn">Kongsi keputusan</button>
  `;
  document.getElementById("share-btn").addEventListener("click", shareResult);
}

async function shareResult() {
  const total = state.puzzle.total;
  const emojiFor = (g) =>
    g.rank === 0 ? "🟩" : { Membara: "🟥", Panas: "🟧", Suam: "🟨", Sejuk: "🟦" }[
      heatFor(g.rank, total, state.meta.heatTiers)
    ];
  const rows = state.guesses.map(emojiFor).join("");
  const text = `Gema #${state.puzzle.seq} — ${
    state.solved ? state.guesses.length + "/∞" : "menyerah"
  }\n${rows}`;

  try {
    await navigator.clipboard.writeText(text);
    setStatus("Keputusan disalin ke papan klip!", "ok");
  } catch {
    setStatus(text);
  }
}

function renderStats() {
  const stats = JSON.parse(
    localStorage.getItem("gema_stats") ||
      '{"played":0,"wins":0,"streak":0,"maxStreak":0}'
  );
  const winRate = stats.played ? Math.round((100 * stats.wins) / stats.played) : 0;
  els.statsGrid.innerHTML = `
    <div><div class="num">${stats.played}</div><div class="label">Dimainkan</div></div>
    <div><div class="num">${winRate}%</div><div class="label">Kadar Menang</div></div>
    <div><div class="num">${stats.streak}</div><div class="label">Jaringan</div></div>
    <div><div class="num">${stats.maxStreak}</div><div class="label">Jaringan Terbaik</div></div>
  `;
}

init();
