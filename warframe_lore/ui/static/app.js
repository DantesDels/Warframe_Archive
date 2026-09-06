"use strict";

/* ------------------------------------------------------------------ state */
let state = {
  buckets: [],
  currentBucket: null,
  currentPageTitle: null,
  stats: null,
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
const elHtml = (tag, cls, html) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html !== undefined) node.innerHTML = html;
  return node;
};

/* Formateur d'affichage d'un titre de page.
 *
 * Ne touche QUE le rendu visuel : le titre brut reste utilisé pour le
 * routage (URL) et les requêtes API.  Supprime les suffixes/prefixes
 * techniques du wiki : ``/Transcript``, ``/Quotes`` et ``Fragment(s)/``.
 *  Ex. "Angels of the Zariman/Transcript" -> "Angels of the Zariman",
 *  "Hunhow/Quotes" -> "Hunhow", "Fragments/Cephalon" -> "Cephalon",
 *  "Fragment/Buried Debts" -> "Buried Debts".
 */
function formatDisplayName(title) {
  if (!title) return title;
  return String(title)
    .replace(/\/Transcript/gi, "")
    .replace(/\/Quotes/gi, "")
    .replace(/Fragments?\//gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

/* ------------------------------------------------------------ api helpers */
let pendingRequests = 0;
let busyTimer = null;
const apiCache = new Map();
const API_CACHE_TTL_MS = 5000;

function setBusy(busy) {
  pendingRequests = Math.max(0, pendingRequests + (busy ? 1 : -1));
  clearTimeout(busyTimer);
  if (pendingRequests > 0) {
    // L'indicateur n'apparaît que si la requête traîne (>120 ms) :
    // évite le flash visuel sur les caches/réponses locales quasi-instantanées.
    busyTimer = setTimeout(() => {
      $("#top-progress").classList.remove("hidden");
    }, 120);
  } else {
    $("#top-progress").classList.add("hidden");
  }
}

async function api(path, { cache = true } = {}) {
  if (cache && apiCache.has(path)) {
    const hit = apiCache.get(path);
    if (Date.now() < hit.expiresAt) return hit.data;
    apiCache.delete(path);
  }
  setBusy(true);
  try {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`${path} -> ${response.status}`);
    const data = await response.json();
    if (data && data.error) throw new Error(data.error);
    if (cache) {
      apiCache.set(path, { data, expiresAt: Date.now() + API_CACHE_TTL_MS });
    }
    return data;
  } finally {
    setBusy(false);
  }
}

/* --------------------------------------------------------------- media */
/* Images Public Export (voir lapin de MediaIndex). Charge utile légère
 * (titres de pages + locuteurs + représentants de bucket) récupérée à la
 * première demande, puis réutilisée par tous les rendus. */
let mediaCache = null;   // null = pas encore chargé ; {} = indisponible

async function ensureMedia() {
  if (mediaCache === null) mediaCache = await api("/api/media");
  return mediaCache && mediaCache.available ? mediaCache : null;
}

function mediaImg(filename, cls, alt) {
  const img = el("img", "media-img " + cls);
  img.loading = "lazy";
  img.decoding = "async";
  img.alt = alt || "";
  img.src = "/media/" + encodeURIComponent(filename);
  // Sans image (404, réseau) : on se retire sans casser la mise en page.
  img.addEventListener("error", () => img.remove());
  return img;
}

function mediaFor(media, speaker, title) {
  if (!media) return null;
  return media.speakers[speaker] || (title ? media.titles[title] : null) || null;
}

/* ------------------------------------------------------------- markdown */
function escapeHtml(input) {
  return input
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function isPlayerSpeaker(name) {
  return /operator|player|\btenno\b|drifter|walley|indifference/i.test(name);
}

function renderInline(text) {
  let out = escapeHtml(text);
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  out = out.replace(/^#{1,3}\s+(.*)$/gm, "<strong>$1</strong>");
  // {P1} / {P2} : marqueurs de position de page -> simple espace
  out = out.replace(/\{P\d+\}/g, " ");
  // Didascalies / conditions de script ({If ...}, {Convo ends.}) -> style
// "stage", sauf pour les instructions d'enchaînement wiki qui ne doivent
// jamais s'afficher ({If ...}, {P1}, {Convo. ends.}).
out = out.replace(/\{(?:if\s+[^{}\n]{0,300}|P\d+|convo\.?\s*ends?\.?|conversation\s+ends|end\s+conv\.?)\}/gi, "");
out = out.replace(/\{([^}\n]{1,120})\}/g, '<span class="stage">$1</span>');
  return out;
}

/* ------------------------------------------- artefacts de rendu wiki */
// Marquage spoiler ``> *_SPOILERS_* _: <raison>_`` (+ variantes) : à extraire
// du flux rendu — le composant d'avertissement lui succède.
const SPOILER_RAW_LINE = /^\s*>?\s*\*?_SPOILERS_\*?\s*_?:\s*(?<reason>.+?)_?\s*$/i;
const SPOILER_STANDALONE = /^\s*>?\s*\*?_SPOILERS_\*?\s*$/i;
// Balises magiques MediaWiki (``__TOC__`` et soeurs) : sans rendu.
const MEDIAWIKI_MAGIC = /^_{2}[A-Z_]{2,}_{2}$/;
// Lignes-pointeurs de navigation KIM (``{Continues/Same/Jump ...}``, préfixés
// ``{If ...}``, ``> **>``, ``> >``) : la réplique est déjà montrée dans la
// branche référencée -> ligne ignorée.
const KIM_POINTER_LINE = /^>[ \t]*(?:\*{1,3}[ \t]*)?(?:>[ \t]*)?(?:\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*)/i;

/* ---------------------------------------------------- blocs wikitext bruts */
const RAW_END = /^customcollapsible/i;
const RAW_BOUNDARY = /^[#>*\[\]{]/;

function isArtifactLine(raw) {
  const s = raw.trim();
  if (!s) return false;
  if (RAW_BOUNDARY.test(s)) return false;
  if (/^(customcollapsible|quotesnav|quicknav|droplocations)\b/i.test(s)) return true;
  if (/\|audio=|\|link=|\|-{1,2}\|/i.test(s)) return true;
  if (/^[^|]{1,80}\.(png|jpg|jpeg|gif|svg)(\s*\([^)]*\))?(\||$)/i.test(s)) return true;
  if (/^Wares\|/i.test(s)) return true;
  if (/transcript\|\||dialogue\|\||\|stranger\|\||editor=|blueprint=t|notlist=true/i.test(s)) return true;
  if ((s.match(/\|/g) || []).length >= 2) return true;
  return false;
}

function collectRawBlock(lines, start) {
  const run = [];
  let lastArtifact = start;
  let j = start;
  while (j < lines.length) {
    const s = lines[j].trim();
    if (s === "") { run.push(lines[j]); j++; continue; }
    if (RAW_END.test(s)) { run.push(lines[j]); j++; break; }
    if (isArtifactLine(s)) { run.push(lines[j]); lastArtifact = j; j++; continue; }
    if (RAW_BOUNDARY.test(s)) break;
    if (j - lastArtifact <= 2) { run.push(lines[j]); j++; continue; }
    break;
  }
  return { run, end: j };
}

function parseInventoryRows(run) {
  const notes = [];
  const rows = [];
  for (const raw of run) {
    const s = raw.trim();
    if (!s) continue;
    if (!s.includes("|")) { notes.push(s); continue; }
    const cells = s.split("|").map((cell) => {
      let c = cell.trim();
      const kv = c.match(/^([^=]+)=(.*)$/);
      if (kv && /^(editor|blueprint|notlist|link|audio)\b/i.test(kv[1].trim())) {
        if (/^(editor|blueprint|notlist)\b/i.test(kv[1].trim())) return "";
        c = kv[2].trim();
      }
      if (/^[^\s]+\s*\.(png|jpg|jpeg|gif|svg)(\s*\([^)]*\))?$/.test(c)) return "";
      return c;
    }).filter((c) => c !== "");
    if (cells.length === 1 && /\.(ogg|wav|mp3)$/i.test(cells[0])) {
      notes.push(`audio : ${cells[0]}`);
      continue;
    }
    if (cells.length) rows.push(cells);
  }
  return { notes, rows };
}

function rawBlockHtml(run) {
  const { notes, rows } = parseInventoryRows(run);
  const parts = [];
  if (notes.length) {
    parts.push(`<div class="raw-notes">${notes
      .map((n) => `<div>${escapeHtml(n)}</div>`).join("")}</div>`);
  }
  if (rows.length) {
    const cols = Math.max(...rows.map((r) => r.length));
    const tbody = rows.map((r) => {
      const tds = [];
      for (let c = 0; c < cols; c++) {
        tds.push(`<td>${escapeHtml(r[c] ?? "")}</td>`);
      }
      return `<tr>${tds.join("")}</tr>`;
    }).join("");
    parts.push(`<div class="raw-table-wrap">` +
      `<table class="raw-table"><tbody>${tbody}</tbody></table></div>`);
  }
  if (!parts.length) parts.push(`<pre>${run.map(escapeHtml).join("\n")}</pre>`);
  return (
    `<details class="raw-block">` +
    `<summary>Afficher / Masquer les données d'inventaire brut</summary>` +
    `<div class="raw-block-body">${parts.join("")}</div>` +
    `</details>`
  );
}

function renderBlockquote(line) {
  const body = line.replace(/^>\s?/, "");
  const m = body.match(/^\*\*(?<speaker>[^*:]+):\*\*(?<rest>.*)$/s);
  if (m) {
    const speaker = m.groups.speaker.trim();
    const cls = isPlayerSpeaker(speaker) ? "kim-player" : "kim-npc";
    const head = renderInline(speaker).trim() + ":";
    return `<blockquote class="${cls}"><strong class="speaker">${head}</strong>` +
      `<span class="text">${renderInline(m.groups.rest)}</span></blockquote>`;
  }
  const content = body.trim();
  if (!content) return "";
  // Blockquote sans locuteur = choix / réplique du joueur.
  return `<blockquote class="kim-choice">${renderInline(body)}</blockquote>`;
}

function markdownToHtml(markdown) {
  const lines = markdown.split("\n");
  const html = [];
  let listType = null;

  const closeList = () => {
    if (listType) { html.push(`</${listType}>`); listType = null; }
  };

  let i = 0;
  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trimEnd();
    if (!line) { closeList(); i++; continue; }

    // Spoiler brut (``*_SPOILERS_* _: raison_``) : supprimé, il est remplacé
    // par le composant d'avertissement placé en tête de page.
    if (SPOILER_RAW_LINE.test(line) || SPOILER_STANDALONE.test(line)) {
      i++;
      continue;
    }
    // Balise magique MediaWiki (``__TOC__``…) : aucun rendu.
    if (MEDIAWIKI_MAGIC.test(line.trim())) {
      i++;
      continue;
    }
    // Pointeur de continuation KIM (``{Continues as above from ...}``) :
    // la réplique est déjà montrée dans la branche référencée au-dessus.
    if (KIM_POINTER_LINE.test(line)) {
      i++;
      continue;
    }

    if (isArtifactLine(line)) {
      closeList();
      const block = collectRawBlock(lines, i);
      html.push(rawBlockHtml(block.run));
      i = block.end;
      continue;
    }
    if (line.startsWith(">")) {
      closeList();
      html.push(renderBlockquote(line));
      i++;
      continue;
    }
    if (line.startsWith("### ")) { closeList(); html.push(`<h3>${renderInline(line.slice(4))}</h3>`); i++; continue; }
    if (line.startsWith("## ")) { closeList(); html.push(`<h2>${renderInline(line.slice(3))}</h2>`); i++; continue; }
    if (line.startsWith("# ")) { closeList(); html.push(`<h1>${renderInline(line.slice(2))}</h1>`); i++; continue; }

    const ulMatch = line.match(/^\s*[-*]\s+(.*)$/);
    if (ulMatch) {
      if (listType !== "ul") { closeList(); html.push("<ul>"); listType = "ul"; }
      html.push(`<li>${renderInline(ulMatch[1])}</li>`);
      i++;
      continue;
    }
    const olMatch = line.match(/^\s*\d+\.\s+(.*)$/);
    if (olMatch) {
      if (listType !== "ol") { closeList(); html.push("<ol>"); listType = "ol"; }
      html.push(`<li>${renderInline(olMatch[1])}</li>`);
      i++;
      continue;
    }

    closeList();
    html.push(`<p>${renderInline(line)}</p>`);
    i++;
  }
  closeList();
  return html.join("");
}

/* ------------------------------------------------------- loading / empty */
function skeletonRows(count) {
  const rows = [];
  for (let i = 0; i < count; i++) rows.push('<div class="skeleton skeleton-row"></div>');
  return `<div class="skeleton-stack">${rows.join("")}</div>`;
}

function emptyState(message, ctaLabel, ctaAction) {
  const box = el("div", "empty-state");
  box.appendChild(el("div", "empty-icon", "🛰️"));
  box.appendChild(el("div", "empty-text", message));
  if (ctaLabel) {
    const btn = el("button", "empty-cta", ctaLabel);
    btn.addEventListener("click", ctaAction);
    box.appendChild(btn);
  }
  return box;
}

function resetSearch() {
  activeTags = [];
  const input = $("#search-input");
  input.value = "";
  renderTagChips();
  runSearch();
}

/* ---------------------------------------------------------------- badges */
function canonBadge(status) {
  if (!status) return "";
  const safe = ["canon", "speculation", "community_theory"].includes(status)
    ? status : "canon";
  const labels = { canon: "Canon", speculation: "Spéculatif", community_theory: "Théorie" };
  return `<span class="badge badge-${safe}">${labels[safe]}</span>`;
}

function badgeNode(status) {
  const html = canonBadge(status);
  if (!html) return el("span", null, "");
  const node = document.createElement("span");
  node.innerHTML = html;
  return node;
}

/* -------------------------------------------------------------- navigation */
const NAV_ITEM_VIEWS = { dashboard: "dashboard", kim: "kim", "kim-chat": "kim", recent: "recent" };

function activeNavFor(viewName) {
  return NAV_ITEM_VIEWS[viewName] || viewName;
}

function bucketTitle(bucketId) {
  const b = state.buckets.find((x) => x.id === bucketId);
  return b ? b.title : bucketId;
}

function renderBreadcrumb(segments) {
  const host = $("#breadcrumb");
  host.innerHTML = "";
  (segments || []).forEach((label, i) => {
    if (i) host.appendChild(el("span", "crumb-sep", "›"));
    const crumb = el("span", "crumb" + (i === segments.length - 1 ? " current" : ""), label);
    host.appendChild(crumb);
  });
}

function showView(name, opts = {}) {
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  const view = document.getElementById(`view-${name}`);
  if (view) view.classList.remove("hidden");
  const navName = activeNavFor(name);
  document.querySelectorAll(".nav-item[data-view], .bnav-item[data-view]").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === navName));
  document.querySelectorAll(".bucket-nav-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.bucket === (opts.bucketId || null)));
  renderBreadcrumb(opts.labels || []);
  $("#content").scrollTop = 0;
}

/* --------------------------------------------------------------- routing */
const navStack = [];

// Compteur de génération de route : chaque navigation l'incrémente.  Les
// rendus asynchrones capturent la valeur au démarrage et abandonnent si une
// navigation plus récente a eu lieu entre-temps (guarde anti-course).
let routeEpoch = 0;

function navigate(path, { push = true } = {}) {
  if (push) navStack.push(path);
  const prev = window.location.hash;
  window.location.hash = path;
  // Même URL (ex: Enter répété) -> aucun événement hashchange, on force le rendu.
  if (window.location.hash === prev) handleRoute();
}

function goBack() {
  if (navStack.length >= 2) {
    navStack.pop();
    navigate(navStack[navStack.length - 1], { push: false });
  } else {
    navigate("dashboard", { push: false });
  }
}

function handleRoute() {
  routeEpoch++;
  const hash = window.location.hash.replace(/^#/, "") || "dashboard";
  // Resynchronise la pile quand l'utilisateur utilise les boutons ← / → du navigateur.
  if (navStack[navStack.length - 1] !== hash) {
    const idx = navStack.lastIndexOf(hash);
    if (idx >= 0) navStack.length = idx + 1;
    else navStack.push(hash);
  }

  const [viewName, ...params] = hash.split("?");
  const p0 = decodeURIComponent(params[0] || "");
  const p1 = decodeURIComponent(params[1] || "");
  switch (viewName) {
    case "dashboard": renderDashboard(); showView("dashboard", { labels: ["Vue d'ensemble"] }); break;
    case "bucket":
      renderBucket(p0);
      showView("bucket", { bucketId: p0, labels: [bucketTitle(p0)] });
      break;
    case "page":
      renderPage(p0, p1);
      showView("page", { bucketId: p0, labels: [bucketTitle(p0), formatDisplayName(p1)] });
      break;
    case "kim": renderKim(); showView("kim", { labels: ["Terminal KIM"] }); break;
    case "kim-chat":
      renderKimChat(p0);
      showView("kim-chat", { labels: ["Terminal KIM", p0] });
      break;
    case "recent": renderRecent(); showView("recent", { labels: ["Récents"] }); break;
    case "search": showView("search", { labels: ["Recherche"] }); break;
    default: renderDashboard(); showView("dashboard", { labels: ["Vue d'ensemble"] });
  }
}

/* -------------------------------------------------------------- dashboard */
async function renderDashboard() {
  const epoch = routeEpoch;
  const cards = $("#stats-cards");
  if (!state.stats) {
    cards.innerHTML = skeletonRows(4);
    state.stats = await api("/api/stats");
  }
  if (epoch !== routeEpoch) return;
  const stats = state.stats;

  cards.innerHTML = "";
  const cardData = [
    { value: stats.buckets, label: "Buckets", hint: "catégories de lore" },
    { value: stats.pages, label: "Pages", hint: "documents récupérés" },
    { value: stats.kim_dialogues, label: "Dialogues KIM", hint: "conversations" },
    { value: stats.canon, label: "Canon", hint: `${stats.speculation} spéculatif` },
  ];
  for (const c of cardData) {
    const card = el("div", "stat-card");
    card.appendChild(el("div", "value", String(c.value)));
    card.appendChild(el("div", "label", c.label));
    if (c.hint) card.appendChild(el("div", "hint", c.hint));
    cards.appendChild(card);
  }

  if (stats.last_update) {
    const last = el("div", "stat-card");
    last.appendChild(el("div", "value", "🕒"));
    last.appendChild(el("div", "label", "Dernière mise à jour"));
    last.appendChild(el("div", "hint", stats.last_update.replace("T", " ").slice(0, 19)));
    cards.appendChild(last);
  }

  const bucketCards = $("#bucket-cards");
  bucketCards.innerHTML = "";
  for (const bucket of state.buckets) {
    const card = el("div", "bucket-card");
    card.appendChild(el("div", "title", bucket.title));
    const meta = el("div", "meta");
    meta.appendChild(elHtml("span", null, `<b>${bucket.total_pages}</b> pages`));
    meta.appendChild(elHtml("span", null, `<b>${bucket.canon}</b> canon`));
    if (bucket.speculation) meta.appendChild(elHtml("span", null, `<b>${bucket.speculation}</b> spéc.`));
    card.appendChild(meta);
    card.addEventListener("click", () => navigate(`bucket?${encodeURIComponent(bucket.id)}`));
    bucketCards.appendChild(card);
  }
}

/* ------------------------------------------------------------------ bucket */
async function renderBucket(bucketId) {
  const epoch = routeEpoch;
  const bucket = state.buckets.find((b) => b.id === bucketId);
  $("#bucket-title").textContent = bucket ? bucket.title : bucketId;
  const container = $("#bucket-pages");
  container.innerHTML = skeletonRows(6);
  const pages = await api(`/api/pages?bucket=${encodeURIComponent(bucketId)}`);
  if (epoch !== routeEpoch) return;
  container.innerHTML = "";
  for (const page of pages) {
    const item = el("div", "page-list-item");
    const name = el("span", "name", formatDisplayName(page.page_title));
    const date = el("span", "date", page.last_updated || "");
    item.appendChild(badgeNode(page.canon_status));
    item.appendChild(name);
    item.appendChild(date);
    item.addEventListener("click", () => navigate(`page?${encodeURIComponent(bucketId)}?${encodeURIComponent(page.page_title)}`));
    container.appendChild(item);
  }
  if (!pages.length) container.appendChild(emptyState("Aucune archive trouvée dans ce bucket."));
}

/* ------------------------------------------------------------------- page */
function b64(str) { return btoa(unescape(encodeURIComponent(str))); }
function unb64(str) { return decodeURIComponent(escape(atob(str))); }

function kimSpoilerReason(content) {
  if (!content) return null;
  for (const line of content.split("\n")) {
    const m = SPOILER_RAW_LINE.exec(line.trim());
    if (m) {
      const reason = m.groups.reason.replace(/^_+/, "").replace(/_+$/, "").trim();
      return reason || "Spoiler";
    }
    if (SPOILER_STANDALONE.test(line)) return "Spoiler";
  }
  return null;
}

function stripKimMeta(content) {
  const lines = content.split("\n");
  let i = 0;
  while (i < lines.length) {
    const s = lines[i].trim();
    if (!s || s.startsWith(">") || /_?\*?\s*SPOILERS\s*\*?/i.test(s) || /^notes:?$/i.test(s)) { i++; continue; }
    break;
  }
  return lines.slice(i).join("\n");
}

function makeSpoilerHint(reason) {
  const text = escapeHtml((reason || "Spoiler").trim());
  return elHtml("div", "spoiler-hint",
    `<div class="spoiler-icon">⚠️</div>` +
    `<div><strong>Spoiler</strong>&nbsp;: <span class="spoiler-reason">${text}</span></div>`);
}

async function renderPage(bucketId, title) {
  const epoch = routeEpoch;
  $("#page-title").textContent = formatDisplayName(title);
  const host = $("#page-content");
  host.innerHTML = skeletonRows(8);
  const page = await api(`/api/page?bucket=${encodeURIComponent(bucketId)}&title=${encodeURIComponent(title)}`);
  if (epoch !== routeEpoch) return;
  host.innerHTML = "";
  if (!page) { host.appendChild(emptyState("Page introuvable dans l'archive.")); return; }
  $("#page-badges").innerHTML = canonBadge(page.canon_status);
  const raw = page.content_markdown || "(vide)";
  const kimSig = /_?\*?\s*SPOILERS\s*\*?|^Notes:/im.test(raw);
  const content = kimSig ? stripKimMeta(raw) : raw;
  const spoiler = kimSpoilerReason(raw);
  host.innerHTML = "";
  if (spoiler) host.appendChild(makeSpoilerHint(spoiler));
  const body = el("div", "markdown");
  body.innerHTML = markdownToHtml(content);
  host.appendChild(body);
}

/* -------------------------------------------------------------------- kim */
/* Segments filtrés de la liste Terminal KIM :
 *   * Messagerie        -> pages du Terminal KIM (Kinemantik Instant Messenger)
 *   * Fables & Frontiers-> canons / épisodes F&F hors messagerie
 *   * Citations         -> pages .../Quotes (répliques de campagne)
 */
let kimSegment = "all";
let kimChatTitle = null;
let kimConvList = [];
let kimConvActive = null;

function kimSegmentOf(page) {
  if (/Fables & Frontiers/i.test(page.page_title)) return "fnf";
  if (/Kinemantik Instant Messenger\//.test(page.page_title)) return "messagerie";
  if (/\/Quotes$/.test(page.page_title)) return "quotations";
  return "other";
}

function renderKimSegments(dialogues) {
  const host = $("#kim-segments");
  host.innerHTML = "";
  const counts = { all: dialogues.length, messagerie: 0, fnf: 0, quotations: 0, other: 0 };
  for (const d of dialogues) counts[kimSegmentOf(d)] += 1;
  const defs = [
    ["all", "Tous"],
    ["messagerie", "Messagerie"],
    ["fnf", "Fables & Frontiers"],
    ["quotations", "Citations"],
  ];
  for (const [key, label] of defs) {
    const btn = el("button", "segment-btn" + (kimSegment === key ? " active" : ""));
    btn.appendChild(document.createTextNode(label));
    btn.appendChild(el("span", "segment-count", String(counts[key] || 0)));
    btn.title = `Afficher : ${label}`;
    btn.addEventListener("click", () => {
      kimSegment = key;
      renderKim();
    });
    host.appendChild(btn);
  }
}

async function renderKim() {
  const epoch = routeEpoch;
  const media = await ensureMedia();
  const container = $("#kim-list");
  container.innerHTML = skeletonRows(8);
  const dialogues = await api("/api/kim");
  if (epoch !== routeEpoch) return;
  renderKimSegments(dialogues);
  container.innerHTML = "";
  const shown = kimSegment === "all"
    ? dialogues
    : dialogues.filter((d) => kimSegmentOf(d) === kimSegment);
  for (const d of shown) {
    const item = el("div", "page-list-item kim-item");
    const thumb = media && media.titles[d.page_title];
    if (thumb) item.prepend(mediaImg(thumb, "media-thumb", d.page_title));
    const name = el("span", "name", formatDisplayName(d.page_title));
    const meta = el("span", "meta",
      `${d.conversations ? d.conversations + " conversations · " : ""}${d.line_count} lignes`);
    item.appendChild(name);
    item.appendChild(meta);
    item.addEventListener("click", () => navigate(`kim-chat?${encodeURIComponent(d.page_title)}`));
    container.appendChild(item);
  }
  if (!shown.length) container.appendChild(emptyState("Aucun dialogue dans ce segment."));
}

/* -------------------------------------------------------------- kim chat */
/* Vue détail d'un personnage KIM : les conversations (branches découpées
 * par ``_split_kim_conversations`` côté serveur) sont sélectionnables une à
 * une, à l'instar de browse.wf.  Chaque conversation alimente la messagerie,
 * le simulateur et le flowchart. */
async function renderKimChat(title) {
  const epoch = routeEpoch;
  kimChatTitle = title;
  kimConvActive = null;
  window.__flowchartInstance = null;
  window.__flowchartOpen = title;
  window.__flowchartConv = null;
  $("#kim-title").textContent = title;
  document.querySelector("#view-kim-chat .kim-header-thumb")?.remove();
  const media = await ensureMedia();
  const headerThumb = media && media.titles[title];
  if (headerThumb) {
    $("#kim-title").parentElement.insertBefore(
      mediaImg(headerThumb, "kim-header-thumb", title), $("#kim-title"));
  }
  const container = $("#kim-chat");
  container.innerHTML = skeletonRows(8);
  $("#kim-convs").innerHTML = "";
  const data = await api(`/api/kim?title=${encodeURIComponent(title)}`);
  if (epoch !== routeEpoch) return;
  kimConvList = data.conversations || [];
  renderKimConversations();
  setKimTabs("chat");
  if (kimConvList.length) {
    await selectKimConversation(kimConvList[0].id);
  } else {
    container.innerHTML = "";
    container.appendChild(emptyState("Aucune conversation détectée dans cette page."));
    kimSimCache.title = null;
  }
}

function kimRankShort(rank) {
  return (rank || "").replace(/^\s*rank\s*/i, "").trim();
}

function renderKimConversations() {
  const host = $("#kim-convs");
  host.innerHTML = "";
  if (!kimConvList.length) {
    host.classList.add("hidden");
    return;
  }
  host.classList.remove("hidden");
  for (const conversation of kimConvList) {
    const short = kimRankShort(conversation.rank);
    const label = short ? `${short} · ${conversation.title}` : conversation.title;
    const btn = el("button", "segment-btn" + (kimConvActive === conversation.id ? " active" : ""));
    btn.appendChild(document.createTextNode(label));
    btn.title = conversation.rank
      ? `${conversation.rank} — ${conversation.title}` : conversation.title;
    btn.addEventListener("click", () => selectKimConversation(conversation.id));
    host.appendChild(btn);
  }
}

async function selectKimConversation(convId) {
  const epoch = routeEpoch;
  const conversation = kimConvList.find((c) => c.id === convId);
  if (!conversation || conversation.id === kimConvActive) return;
  kimConvActive = conversation.id;
  window.__flowchartConv = conversation.id;
  // Les onglets Flowchart et Simulateur dépendent de la conversation courante.
  kimSimCache.title = null;
  kimSimFetchedTitle = null;
  stopSimAuto();
  simResetUi();
  document.querySelectorAll("#kim-sim .spoiler-hint").forEach((h) => h.remove());
  if (window.__flowchartInstance) {
    try { window.__flowchartInstance.unmount(); } catch (_) { /* déjà détruit */ }
    window.__flowchartInstance = null;
  }
  $("#kim-chart").innerHTML = "";
  renderKimConversations();
  const container = $("#kim-chat");
  container.innerHTML = skeletonRows(6);
  const data = await api(`/api/kim?title=${encodeURIComponent(kimChatTitle)}&conv=${encodeURIComponent(convId)}`);
  if (epoch !== routeEpoch) return;
  renderKimChatMessages(data.messages || [], data.spoiler || null);
}

async function renderKimChatMessages(messages, spoiler) {
  const container = $("#kim-chat");
  container.innerHTML = "";
  const media = await ensureMedia();
  const body = el("div", "chat-stack");
  messages.forEach((message, index) => {
    const player = !!message.player;
    const line = el("div", `chat-line${index % 2 ? " alt" : ""}${player ? " player" : ""}`);
    const cell = el("div", "chat-body");
    cell.appendChild(el("div", "who", player ? "Vous" : (message.speaker || "")));
    cell.appendChild(elHtml("div", "text", renderInline(message.text || "")));
    if (!player && media) {
      const f = mediaFor(media, message.speaker, kimChatTitle);
      if (f) line.appendChild(mediaImg(f, "chat-avatar", message.speaker));
    }
    line.appendChild(cell);
    body.appendChild(line);
  });
  if (!messages.length) body.appendChild(el("div", "snippet", "Aucun message."));
  if (spoiler) body.prepend(makeSpoilerHint(spoiler));
  container.appendChild(body);
}

function setKimTabs(tab) {
  document.querySelectorAll(".view-tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === tab));
  $("#kim-chat").classList.toggle("hidden", tab !== "chat");
  const chartHost = $("#kim-chart");
  chartHost.classList.toggle("hidden", tab !== "chart");
  $("#kim-sim").classList.toggle("hidden", tab !== "sim");
}

function switchKimTab(tab) {
  if (tab !== "sim") stopSimAuto();
  setKimTabs(tab);
  if (tab === "chart") {
    const title = window.__flowchartOpen || $("#kim-title").textContent;
    const conv = window.__flowchartConv || kimConvActive || "";
    const epoch = routeEpoch;
    const chartHost = $("#kim-chart");
    chartHost.innerHTML = skeletonRows(5);
    const route = `/api/graph?title=${encodeURIComponent(title)}` +
      (conv ? `&conv=${encodeURIComponent(conv)}` : "");
    api(route).then((graph) => {
      if (epoch !== routeEpoch) return;
      chartHost.innerHTML = "";
      if (window.mountFlowchart) {
        window.__flowchartInstance = mountFlowchart(chartHost, {
          nodes: graph.nodes || [],
          edges: graph.edges || [],
        });
      } else {
        chartHost.textContent = "Module flowchart non chargé.";
      }
    });
  } else if (tab === "sim") {
    openSimulator();
  }
}

/* ---------------------------------------------------------- kim simulator */
/* Marcheur séquentiel du terminal KIM :
 *   * avance réplique par réplique (bouton « Suivant » ou lecture auto) ;
 *   * s'interrompt sur une étape ``prompt`` (choix ``> >``) pour présenter
 *     les options ; le choix sélectionné est ajouté comme bulle du joueur ;
 *   * une étape terminale (``{Convo ends.}``) clôt la conversation ;
 *   * les sauts résolus (``jump_to``) déplacent le curseur avec protection
 *     anti-boucle (``seen``).
 */
let kimSimState = { title: null, cursor: 0, done: false, waiting: false, seen: new Set() };
let kimSimCache = { title: null, script: [] };
let kimSimMedia = null;
let kimSimTimer = null;
let kimSimFetchedTitle = null;

function simSetStatus(text) { $("#sim-status").textContent = text; }

function simResetUi() {
  kimSimState = { title: kimSimState.title, cursor: 0, done: false, waiting: false, seen: new Set() };
  clearInterval(kimSimTimer);
  kimSimTimer = null;
  document.querySelectorAll("#kim-sim .spoiler-hint").forEach((h) => h.remove());
  $("#sim-advance").disabled = false;
  $("#sim-auto").textContent = "Lecture";
  $("#sim-history").innerHTML = "";
  $("#sim-prompt").innerHTML = "";
  $("#sim-prompt").classList.add("hidden");
  $("#sim-end").classList.add("hidden");
  simSetStatus("");
}

function appendSimBubble(step) {
  const hist = $("#sim-history");
  const player = !!step.player;
  const line = el("div", `chat-line sim-line${player ? " player" : ""}${step.ends ? " ends" : ""}`);
  const cell = el("div", "chat-body");
  cell.appendChild(el("div", "who", player ? "Vous" : (step.speaker || "")));
  cell.appendChild(elHtml("div", "text", renderInline(step.text || "")));
  if (!player && kimSimMedia) {
    const f = mediaFor(kimSimMedia, step.speaker, kimSimCache.title);
    if (f) line.appendChild(mediaImg(f, "chat-avatar", step.speaker));
  }
  line.appendChild(cell);
  hist.appendChild(line);
  hist.scrollTop = hist.scrollHeight;
}

function simEnd() {
  kimSimState.done = true;
  kimSimState.waiting = false;
  stopSimAuto();
  $("#sim-advance").disabled = true;
  $("#sim-prompt").classList.add("hidden");
  $("#sim-end").classList.remove("hidden");
  simSetStatus("Conversation terminée.");
}

function renderSimPrompt() {
  const step = kimSimCache.script[kimSimState.cursor];
  const prompt = $("#sim-prompt");
  prompt.innerHTML = "";
  const label = el("div", "sim-prompt-label", "— Choisissez une réponse —");
  prompt.appendChild(label);
  for (const option of step.options || []) {
    const btn = el("button", "sim-option", option.text);
    btn.addEventListener("click", () => {
      kimSimState.waiting = false;
      prompt.classList.add("hidden");
      prompt.innerHTML = "";
      const chosen = { speaker: "", text: option.text, player: true, ends: !!option.ends };
      appendSimBubble(chosen);
      if (option.ends) { simEnd(); return; }
      kimSimState.cursor++;
      simNext();
    });
    prompt.appendChild(btn);
  }
  prompt.classList.remove("hidden");
  kimSimState.waiting = true;
}

/* Avance d'UNE réplique par appel (fin / prompt suivant / saut) : la lecture
 * automatique défile réplique par réplique, le bouton « Suivant » itère à la
 * main.  Un saut ``jump_to`` est exécuté comme une seule étape, sans
 * enchaîner sur la cible dans la foulée. */
function simNext() {
  if (kimSimState.done || kimSimState.waiting) return;
  const script = kimSimCache.script;
  if (kimSimState.cursor >= script.length) { simEnd(); return; }
  const step = script[kimSimState.cursor];
  if (step.jump_to != null) {
    if (kimSimState.seen.has(kimSimState.cursor)) { simEnd(); return; }
    kimSimState.seen.add(kimSimState.cursor);
    kimSimState.cursor = step.jump_to;
    return;
  }
  if (step.kind === "prompt") { renderSimPrompt(); return; }
  kimSimState.cursor++;
  appendSimBubble(step);
  if (step.ends) { simEnd(); return; }
}

function stopSimAuto() {
  if (kimSimTimer) { clearInterval(kimSimTimer); kimSimTimer = null; }
  $("#sim-auto").textContent = "Lecture";
}

function toggleSimAuto() {
  if (kimSimTimer) { stopSimAuto(); return; }
  const btn = $("#sim-auto");
  btn.textContent = "Pause";
  kimSimTimer = setInterval(() => {
    if (kimSimState.done || kimSimState.waiting) return;
    simNext();
  }, 650);
}

async function openSimulator() {
  const epoch = routeEpoch;
  const title = window.__flowchartOpen || $("#kim-title").textContent;
  const conv = window.__flowchartConv || kimConvActive || "";
  kimSimMedia = await ensureMedia();
  if (kimSimCache.title !== title) {
    simResetUi();
    simSetStatus("Chargement du script…");
    const route = `/api/kim?mode=sim&title=${encodeURIComponent(title)}` +
      (conv ? `&conv=${encodeURIComponent(conv)}` : "");
    const data = await api(route);
    if (epoch !== routeEpoch) return;
    kimSimCache = { title, script: data.script || [], spoiler: data.spoiler || null, revealed: false };
    kimSimFetchedTitle = title;
    simResetUi();
  }
  if (kimSimCache.spoiler && !$("#kim-sim").querySelector(".spoiler-hint")) {
    $("#kim-sim").prepend(makeSpoilerHint(kimSimCache.spoiler));
  }
  if (!kimSimCache.script.length) {
    $("#sim-history").appendChild(emptyState("Ce dialogue n'est pas simulable."));
    simSetStatus("Non simulable.");
    $("#sim-advance").disabled = true;
    return;
  }
  if (kimSimState.waiting || kimSimState.done || !kimSimState.cursor) simSetStatus("Prêt. Cliquez sur « Suivant » ou « Lecture ».");
}

/* ------------------------------------------------------------------ recent */
async function renderRecent() {
  const epoch = routeEpoch;
  const container = $("#recent-list");
  container.innerHTML = skeletonRows(8);
  const recent = await api("/api/recent?limit=30");
  if (epoch !== routeEpoch) return;
  container.innerHTML = "";
  for (const page of recent) {
    const item = el("div", "page-list-item");
    const name = el("span", "name", formatDisplayName(page.page_title));
    item.appendChild(badgeNode(page.canon_status));
    item.appendChild(name);
    item.appendChild(el("span", "date", page.last_updated || ""));
    const bucket = page.bucket_id;
    item.addEventListener("click", () => navigate(`page?${encodeURIComponent(bucket)}?${encodeURIComponent(page.page_title)}`));
    container.appendChild(item);
  }
  if (!recent.length) container.appendChild(emptyState("Aucune donnée dans l'archive."));
}

/* ----------------------------------------------------------------- search */
/* Omnibox : recherche plein texte + tags multiples + autocomplétion.
 *
 * Tags disponibles :
 *   * Buckets (depuis /api/buckets)  -> [Personnages], [Terminal KIM], ...
 *   * Statut canon                   -> [CANON], [SPÉCULATIF], [THÉORIE]
 *
 * Saisie ``[...]`` -> chip ajoutée, le reste devient le query libre.
 * Dropdown : pages hit (type ``title``) ou mentions (type ``content``).
 */
let activeTags = [];          // [{kind:'bucket'|'canon', id, label}]
let suggestTimer = null;
let dropdownIndex = -1;
let dropdownItems = [];

function tagForBucket(bucket) {
  return {
    kind: "bucket",
    id: bucket.id,
    label: bucket.title,
    color: bucketColor(bucket.id),
  };
}

function bucketColor(bucketId) {
  const map = {
    Lore_Personnages: "#8f7bff",      // violet
    Lore_Quetes: "#4ade80",           // vert
    Lore_Dialogues_KIM: "#22d3ee",    // cyan
    Lore_Dialogues_Quetes: "#4cc2ff", // bleu
    Lore_Dialogues_Quotes: "#4cc2ff", // bleu
    Lore_Cosmologie_Factions: "#fb923c", // orange
    Lore_Univers_Histoire: "#38bdf8",
    Lore_Fragments: "#c084fc",
    Lore_Characters: "#8f7bff",       // violet (bonus)
  };
  return map[bucketId] || "#94a3b8";
}

function canonColor(status) {
  return { canon: "#4ade80", speculation: "#fbbf24", community_theory: "#f472b6" }[status] || "#94a3b8";
}

function canonTag(status) {
  const labels = { canon: "CANON", speculation: "SPÉCULATIF", community_theory: "THÉORIE" };
  return { kind: "canon", id: status, label: labels[status] };
}

function allTagVocabulary() {
  const tags = [];
  for (const b of state.buckets) tags.push(tagForBucket(b));
  tags.push(canonTag("canon"), canonTag("speculation"), canonTag("community_theory"));
  return tags;
}

function findTagByLabel(token) {
  const normalized = token.toLowerCase().replace(/[[\]]/g, "").trim();
  return allTagVocabulary().find((t) => t.label.toLowerCase() === normalized) || null;
}

/* Parsing de la saisie : extrait les ``[...]`` comme chips, rend le reste. */
function parseTagTokens(value) {
  const tokens = value.match(/\[[^\]]*\]/g) || [];
  const without = value.replace(/\[[^\]]*\]/g, "");
  return { tokens, query: without.replace(/\s+/g, " ").trim() };
}

function renderTagChips() {
  const box = $("#omnibox-tags");
  box.innerHTML = "";
  for (const tag of activeTags) {
    const chip = el("span", "omni-tag");
    chip.style.setProperty("--tag-color", tag.color);
    chip.textContent = tag.label;
    const x = el("button", "omni-remove", "×");
    x.title = "Retirer ce filtre";
    x.addEventListener("click", () => {
      activeTags = activeTags.filter((t) => t !== tag);
      renderTagChips();
      runSearch();
    });
    chip.appendChild(x);
    box.appendChild(chip);
  }
}

/* Applique les filtres actifs + requête -> navigation vers les résultats. */
async function runSearch() {
  const epoch = routeEpoch;
  const input = $("#search-input");
  const parsed = parseTagTokens(input.value);
  const q = parsed.query;
  $("#search-term").textContent = `« ${q || "tous"} »`;
  const bucket = activeTags.find((t) => t.kind === "bucket");
  const canon = activeTags.find((t) => t.kind === "canon");
  const params = new URLSearchParams({ q });
  if (bucket) params.set("bucket", bucket.id);
  if (canon) params.set("canon", canon.id);
  $("#search-results").innerHTML = skeletonRows(10);
  const results = await api(`/api/search?${params}`);
  if (epoch !== routeEpoch) return;
  const container = $("#search-results");
  container.innerHTML = "";
  let lastGroup = null;
  for (const page of results) {
    const group = page.match_type === "title" ? "title" : "content";
    if (group !== lastGroup) {
      container.appendChild(el("div", "search-group-head",
        group === "title" ? "Pages (correspondance de titre)"
                          : "Mentions dans le contenu"));
      lastGroup = group;
    }
    const item = el("div", "page-list-item");
    const wrapper = el("div", null);
    const name = el("div", "name", formatDisplayName(page.page_title));
    const snippet = el("div", "snippet", page.snippet || "");
    wrapper.appendChild(name);
    wrapper.appendChild(snippet);
    item.appendChild(badgeNode(page.canon_status));
    item.appendChild(wrapper);
    const bucketId = page.bucket_id;
    item.addEventListener("click", () => navigate(`page?${encodeURIComponent(bucketId)}?${encodeURIComponent(page.page_title)}`));
    container.appendChild(item);
  }
  if (!results.length) {
    container.appendChild(emptyState("Aucune archive trouvée dans le réseau somatique.",
      "Réinitialiser la recherche", resetSearch));
  }
}

/* Autocomplétion : dropdown de suggestions (titres + mentions). */
async function showSuggestions() {
  const input = $("#search-input");
  const value = input.value;
  const pars = parseTagTokens(value);

  // Saisie de ``[`` : proposer le vocabulaire de tags.
  if (value.trimEnd().endsWith("[") || /^\[[\p{L}\- ]*$/u.test(value)) {
    renderTagDropdown(
      allTagVocabulary().map((t) => ({
        type: "tag",
        label: t.label,
        sub: t.kind === "bucket" ? "bucket" : "statut",
        color: t.color,
        tag: t,
      })),
      pars.query
    );
    return;
  }
  if (!pars.query) { hideDropdown(); return; }

  const items = await api(`/api/suggest?q=${encodeURIComponent(pars.query)}&limit=12`);
  renderTagDropdown(
    items.map((s) => ({
      type: s.match_type === "title" ? "page" : "mention",
      page_title: s.page_title,
      bucket_id: s.bucket_id,
      bucket: s.bucket_title,
      color: bucketColor(s.bucket_id),
      snippet: s.snippet || "",
    })),
    pars.query
  );
}

function renderTagDropdown(items, query) {
  dropdownItems = items;
  dropdownIndex = -1;
  const dd = $("#omnibox-dropdown");
  dd.innerHTML = "";
  if (!items.length) { dd.classList.add("hidden"); return; }
  let lastGroup = null;
  for (const it of items) {
    const group = it.type === "page" ? "title"
                : it.type === "mention" ? "content" : null;
    if (group && group !== lastGroup) {
      dd.appendChild(el("div", "omni-group",
        group === "title" ? "Titres de pages" : "Mentions (contenu)"));
      lastGroup = group;
    } else if (!group) {
      lastGroup = null;
    }
    const row = el("div", "omni-item");
    row.style.setProperty("--tag-color", it.color);
    if (it.type === "tag") {
      row.appendChild(el("span", "omni-tag-preview", `[${it.label}]`));
      row.appendChild(el("span", "omni-sub", it.sub + " — ajouter un filtre"));
    } else {
      const ic = el("span", "omni-type", it.type === "page" ? "⛶" : "✎");
      ic.title = it.type === "page" ? "Page" : "Mention";
      ic.style.color = it.color;
      row.appendChild(ic);
      const main = el("div", "omni-main");
      const name = el("div", "omni-title", formatDisplayName(it.page_title));
      const meta = el("div", "omni-sub", it.bucket + (it.snippet ? " · " + it.snippet : ""));
      main.appendChild(name);
      main.appendChild(meta);
      row.appendChild(main);
    }
    row.addEventListener("click", () => {
      if (it.type === "tag") {
        activeTags.push(it.tag);
        renderTagChips();
        const input = $("#search-input");
        input.value = input.value.replace(/\[[^\]]*\]/g, "");
        hideDropdown();
        runSearch();
        return;
      }
      hideDropdown();
      navigate(`page?${encodeURIComponent(it.bucket_id)}?${encodeURIComponent(it.page_title)}`);
      return;
    });
    dd.appendChild(row);
  }
  dd.classList.remove("hidden");
}

function hideDropdown() {
  $("#omnibox-dropdown").classList.add("hidden");
  $("#omnibox-dropdown").innerHTML = "";
  dropdownItems = [];
  dropdownIndex = -1;
}

function moveDropdown(delta) {
  const items = dropdownItems;
  if (!items.length) return;
  dropdownIndex = (dropdownIndex + delta + items.length) % items.length;
  document.querySelectorAll(".omni-item").forEach((r, i) =>
    r.classList.toggle("active", i === dropdownIndex));
  const sel = document.querySelector(".omni-item.active");
  if (sel) sel.scrollIntoView({ block: "nearest" });
}

function activateDropdown() {
  const items = dropdownItems;
  if (!items.length || dropdownIndex < 0) return;
  const it = items[dropdownIndex];
  document.querySelectorAll(".omni-item")[dropdownIndex].click();
}

/* ------------------------------------------------------------------- init */
async function init() {
  state.buckets = await api("/api/buckets");

  const nav = $("#bucket-nav");
  nav.innerHTML = "";
  for (const bucket of state.buckets) {
    if (bucket.id === "Lore_Dialogues_KIM") continue;
    const btn = el("button", "bucket-nav-item");
    btn.dataset.bucket = bucket.id;
    btn.appendChild(el("span", null, bucket.title));
    btn.addEventListener("click", () => navigate(`bucket?${encodeURIComponent(bucket.id)}`));
    nav.appendChild(btn);
  }

  // Sidebar navigation
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.view) navigate(btn.dataset.view);
    });
  });

  // Navigation mobile : burger off-canvas + barre inférieure.
  const body = document.body;
  const btnMenu = $("#btn-menu");
  const backdrop = $("#sidebar-backdrop");
  const setSideMenu = (open) => {
    body.classList.toggle("sidebar-open", open);
    btnMenu.setAttribute("aria-expanded", String(open));
  };
  btnMenu.addEventListener("click", () =>
    setSideMenu(!body.classList.contains("sidebar-open")));
  backdrop.addEventListener("click", () => setSideMenu(false));
  const searchInputMobile = $("#search-input");
  document.querySelectorAll("#bottom-nav .bnav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      setSideMenu(false);
      if (btn.dataset.view === "search") {
        searchInputMobile.focus();
        showSuggestions();
        return;
      }
      navigate(btn.dataset.view);
    });
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest("#btn-menu")) return;
    if (body.classList.contains("sidebar-open")) setSideMenu(false);
  });

  // Back handling (jamais de dead end : pile interne + nav navigateur)
  document.querySelectorAll(".back-btn").forEach((btn) => {
    btn.addEventListener("click", goBack);
  });

  // Back / Forward du navigateur
  window.addEventListener("hashchange", handleRoute);

  // Onglets (Messagerie / Simulateur / Flowchart) dans la vue KIM
  document.querySelectorAll(".view-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchKimTab(tab.dataset.tab));
  });

  // Contrôles du simulateur KIM
  $("#sim-advance").addEventListener("click", simNext);
  $("#sim-auto").addEventListener("click", toggleSimAuto);
  $("#sim-restart").addEventListener("click", () => { simResetUi(); simNext(); });
  $("#sim-replay").addEventListener("click", () => { simResetUi(); simNext(); });

  // Reload : purger tous les caches applicatifs (api, médias, état interne)
  // puis recharge r la page : le plus fiable pour réinitialiser listeners,
  // state et DOM (évite les doubles bindings après un "init" en doublon).
  $("#btn-reload").addEventListener("click", () => {
    window.location.reload();
  });

  // Omnibox : saisie + tags + autocomplétion
  const searchInput = $("#search-input");
  // Mode plein écran (mobile) : signalé sur <body> pour empiler au-dessus
  // de la barre inférieure (contextes de stacking indépendants).
  searchInput.addEventListener("focus", () => body.classList.add("omni-open"));
  searchInput.addEventListener("blur", () => body.classList.remove("omni-open"));
  $("#search-cancel").addEventListener("click", () => {
    hideDropdown();
    searchInput.blur();
  });
  searchInput.addEventListener("input", (event) => {
    const value = event.target.value;
    // ``[LABEL]`` complet -> chip, on nettoie la saisie.
    const parsed = parseTagTokens(value);
    for (const token of parsed.tokens) {
      const tag = findTagByLabel(token);
      if (tag && !activeTags.some((t) => t.kind === tag.kind && t.id === tag.id)) {
        activeTags.push(tag);
      }
    }
    if (parsed.tokens.length) {
      searchInput.value = parsed.query;
    }
    renderTagChips();
    hideDropdown();
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(() => {
      const current = searchInput.value;
      if (current.trim() || value.trimStart().startsWith("[")) {
        showSuggestions();
      }
    }, 180);
  });

  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideDropdown();
      searchInput.blur();
      return;
    }
    if (event.key === "ArrowDown") { moveDropdown(1); event.preventDefault(); return; }
    if (event.key === "ArrowUp") { moveDropdown(-1); event.preventDefault(); return; }
    if (event.key === "Enter") {
      event.preventDefault();
      // Choix actif dans le dropdown (navigué aux flèches) -> activation.
      // Sinon : recherche complète sur le libellé courant.
      if (dropdownIndex >= 0) { activateDropdown(); return; }
      hideDropdown();
      navigate("search");
      runSearch();
      searchInput.blur();
      return;
    }
    if (event.key === "Backspace" && !event.target.value && activeTags.length) {
      activeTags.pop();
      renderTagChips();
      runSearch();
    }
  });

  // Fermeture du dropdown quand on clique ailleurs (et du plein écran
  // mobile : un tap hors omnibox libère le focus).
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#omnibox")) {
      hideDropdown();
      if (document.activeElement === searchInput) searchInput.blur();
    }
  });

  handleRoute();
}

init();