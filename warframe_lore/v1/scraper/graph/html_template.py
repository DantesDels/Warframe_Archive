"""Self-contained Graphify-style interactive HTML visualization (works offline)."""

# ruff: noqa: E501

# Kept as one literal so the standalone HTML asset stays editable as a whole.
HTML_TEMPLATE = """<!doctype html>
<html lang="fr" data-theme="dark">
<head>
<meta charset="utf-8">
<title>Atelier v1 — Graphe des sources</title>
<style>
  :root {
    --bg: #0f172a; --panel: #1e293b; --border: #334155; --input: #0f172a;
    --text: #f1f5f9; --text-2: #94a3b8; --muted: #64748b; --hover: #334155;
    --edge: rgba(148,163,184,0.32); --label-bg: rgba(15,23,42,0.88);
  }
  [data-theme="light"] {
    --bg: #f8fafc; --panel: #ffffff; --border: #cbd5e1; --input: #f8fafc;
    --text: #0f172a; --text-2: #475569; --muted: #64748b; --hover: #e2e8f0;
    --edge: rgba(71,85,105,0.28); --label-bg: rgba(255,255,255,0.92);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: "Segoe UI", system-ui, sans-serif;
         display: flex; height: 100vh; overflow: hidden; }
  #stage { flex: 1; position: relative; overflow: hidden; }
  canvas { width: 100%; height: 100%; display: block; cursor: grab; }
  canvas.dragging { cursor: grabbing; }
  #hud { position: absolute; top: 12px; left: 12px; display: flex; gap: 6px; z-index: 5; }
  #hud button, #theme-bar button {
    background: var(--panel); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 10px; font-size: 12px; cursor: pointer;
  }
  #hud button:hover, #theme-bar button:hover { background: var(--hover); }
  #theme-bar button.active { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
  #sidebar { width: 300px; background: var(--panel); border-left: 1px solid var(--border);
             display: flex; flex-direction: column; overflow: hidden; }
  #brand { padding: 12px 14px; border-bottom: 1px solid var(--border); font-weight: 700; font-size: 14px; }
  #theme-bar { display: flex; gap: 6px; padding: 8px 12px; border-bottom: 1px solid var(--border); }
  #theme-bar button { flex: 1; padding: 4px 0; }
  #search-wrap { padding: 10px 12px; border-bottom: 1px solid var(--border); }
  #search { width: 100%; background: var(--input); color: var(--text); border: 1px solid var(--border);
            border-radius: 6px; padding: 7px 10px; font-size: 13px; outline: none; }
  #search:focus { border-color: #38bdf8; }
  #results { max-height: 140px; overflow-y: auto; margin-top: 6px; display: none; }
  .res-item { padding: 4px 6px; border-radius: 4px; cursor: pointer; font-size: 12px;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .res-item:hover { background: var(--hover); }
  #info { padding: 12px 14px; border-bottom: 1px solid var(--border); min-height: 155px; overflow-y: auto; max-height: 260px; }
  h3 { font-size: 11px; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }
  .field { font-size: 12px; margin-bottom: 4px; word-break: break-all; }
  .field a { color: #38bdf8; text-decoration: none; }
  .field a:hover { text-decoration: underline; }
  .neighbor { display: block; padding: 3px 6px; margin: 2px 0; border-radius: 4px; font-size: 12px;
              cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
              border-left: 3px solid var(--border); }
  .neighbor:hover { background: var(--hover); }
  #legend-wrap { flex: 1; overflow-y: auto; padding: 12px 14px; }
  .legend-row { display: flex; align-items: center; gap: 8px; padding: 5px 4px; font-size: 13px; cursor: pointer; }
  .legend-row:hover { background: var(--hover); border-radius: 4px; }
  .dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
  .cnt { margin-left: auto; color: var(--text-2); font-size: 12px; }
  #stats { padding: 10px 14px; border-top: 1px solid var(--border); font-size: 12px; color: var(--text-2); }
</style>
</head>
<body>
<div id="stage">
  <div id="hud">
    <button onclick="fitView()">Ajuster la vue</button>
    <button onclick="zoomBy(1.25)">Zoom +</button>
    <button onclick="zoomBy(0.8)">Zoom &minus;</button>
    <button id="phys-btn" onclick="togglePhysics()">Figer la physique</button>
  </div>
  <canvas id="canvas"></canvas>
</div>
<div id="sidebar">
  <div id="brand">Atelier v1 — Graphe des sources</div>
  <div id="theme-bar">
    <button id="btn-dark" class="active" onclick="setTheme('dark')">Sombre</button>
    <button id="btn-light" onclick="setTheme('light')">Clair</button>
  </div>
  <div id="search-wrap">
    <input id="search" type="text" placeholder="Rechercher un nœud..." autocomplete="off">
    <div id="results"></div>
  </div>
  <div id="info">
    <h3>Détails du nœud</h3>
    <div id="info-body" style="color:var(--muted);font-size:12px">Cliquez sur un nœud pour l'inspecter.</div>
  </div>
  <div id="legend-wrap">
    <h3>Catégories</h3>
    <div id="legend"></div>
  </div>
  <div id="stats"></div>
</div>
<script>
const GRAPH = __GRAPH_DATA__;
const COLORS = {
  Universe: "#0ea5e9", Source: "#22c55e", Document: "#f59e0b", Candidate: "#a855f7",
  Person: "#ec4899", Location: "#14b8a6", Faction: "#f97316", Concept: "#6366f1",
  Timeline: "#eab308", Unknown: "#64748b"
};
const KIND_LABELS = {
  Universe: "Univers", Source: "Sources", Document: "Documents", Candidate: "Candidats",
  Person: "Personnages", Location: "Lieux", Faction: "Factions", Concept: "Concepts",
  Timeline: "Chronologie"
};
const EDGE_COLORS = {
  HAS_SOURCE: "#22c55e", PRODUCED: "#f59e0b", HAS_CANDIDATE: "#a855f7", HAS_DOCUMENT: "#64748b",
  BELONGS_TO: "#f97316", LOCATED_IN: "#14b8a6", ALLIED_WITH: "#22c55e", OPPOSES: "#ef4444",
  CREATED_BY: "#ec4899", PART_OF: "#6366f1", OCCURRED_IN: "#eab308", RELATED_TO: "#94a3b8"
};

const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const visibleKinds = {
  Universe: true, Source: true, Document: true, Candidate: true,
  Person: true, Location: true, Faction: true, Concept: true, Timeline: true, Unknown: true
};
let selectedId = null, hoveredId = null, physics = true;
let cam = { x: 0, y: 0, z: 1 };

const nodes = (GRAPH.nodes || []).map((n, i) => {
  const angle = (i * 2.39996);
  const ring = n.kind === "Universe" ? 0 : n.kind === "Source" ? 180 : n.kind === "Candidate" ? 320 : 420 + (i % 7) * 35;
  return { ...n, x: Math.cos(angle) * ring, y: Math.sin(angle) * ring, vx: 0, vy: 0, deg: 0 };
});
const byId = new Map(nodes.map(n => [n.id, n]));
const edges = (GRAPH.edges || []).filter(e => byId.has(e.source) && byId.has(e.target));
const adj = new Map(nodes.map(n => [n.id, []]));
for (const e of edges) {
  byId.get(e.source).deg++; byId.get(e.target).deg++;
  adj.get(e.source).push({ id: e.target, type: e.type });
  adj.get(e.target).push({ id: e.source, type: e.type });
}

function radiusOf(n) {
  if (n.kind === "Universe") return 20;
  if (n.kind === "Source") return Math.min(18, 11 + Math.sqrt(n.deg) * 1.4);
  return Math.min(13, 7 + Math.sqrt(n.deg) * 0.9);
}

function resize() {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = canvas.clientWidth * dpr;
  canvas.height = canvas.clientHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener("resize", () => { resize(); draw(); });
resize();

function setTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  document.getElementById("btn-dark").classList.toggle("active", t === "dark");
  document.getElementById("btn-light").classList.toggle("active", t === "light");
  draw();
}

function togglePhysics() {
  physics = !physics;
  document.getElementById("phys-btn").textContent = physics ? "Figer la physique" : "Relancer la physique";
}

function zoomBy(factor) { cam.z = Math.max(0.12, Math.min(6, cam.z * factor)); draw(); }

function fitView() {
  const vis = nodes.filter(n => visibleKinds[n.kind] !== false);
  if (!vis.length) return;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const n of vis) { minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x); minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y); }
  const w = Math.max(200, maxX - minX + 160), h = Math.max(200, maxY - minY + 160);
  cam.z = Math.max(0.15, Math.min(1.6, Math.min(canvas.clientWidth / w, canvas.clientHeight / h)));
  cam.x = (minX + maxX) / 2; cam.y = (minY + maxY) / 2;
  draw();
}

function stepPhysics() {
  const vis = nodes.filter(n => visibleKinds[n.kind] !== false);
  const maxPairs = vis.length > 350 ? 350 : vis.length;
  for (let i = 0; i < maxPairs; i++) {
    const a = vis[i];
    for (let j = i + 1; j < maxPairs; j++) {
      const b = vis[j];
      let dx = b.x - a.x, dy = b.y - a.y;
      let d2 = dx * dx + dy * dy + 25;
      const f = 2200 / d2;
      const dist = Math.sqrt(d2);
      const fx = (dx / dist) * f, fy = (dy / dist) * f;
      a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
    }
  }
  for (const e of edges) {
    const a = byId.get(e.source), b = byId.get(e.target);
    if (visibleKinds[a.kind] === false || visibleKinds[b.kind] === false) continue;
    const dx = b.x - a.x, dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const target = e.type === "HAS_SOURCE" ? 170 : 120;
    const f = (dist - target) * 0.015;
    a.vx += (dx / dist) * f; a.vy += (dy / dist) * f;
    b.vx -= (dx / dist) * f; b.vy -= (dy / dist) * f;
  }
  for (const n of vis) {
    if (n === dragNode) continue;
    n.vx = (n.vx - n.x * 0.0012) * 0.82;
    n.vy = (n.vy - n.y * 0.0012) * 0.82;
    n.x += Math.max(-18, Math.min(18, n.vx));
    n.y += Math.max(-18, Math.min(18, n.vy));
  }
}

function shortText(s, lim) { return s.length > lim ? s.slice(0, lim - 3) + "..." : s; }

function draw() {
  const styles = getComputedStyle(document.documentElement);
  ctx.fillStyle = styles.getPropertyValue("--bg");
  ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  ctx.save();
  ctx.translate(canvas.clientWidth / 2, canvas.clientHeight / 2);
  ctx.scale(cam.z, cam.z);
  ctx.translate(-cam.x, -cam.y);

  const focusId = hoveredId || selectedId;
  const focusNeighbors = new Set(focusId ? [focusId, ...(adj.get(focusId) || []).map(x => x.id)] : []);

  for (const e of edges) {
    const a = byId.get(e.source), b = byId.get(e.target);
    if (visibleKinds[a.kind] === false || visibleKinds[b.kind] === false) continue;
    const active = !focusId || (focusNeighbors.has(a.id) && focusNeighbors.has(b.id));
    ctx.strokeStyle = active ? (EDGE_COLORS[e.type] || "#94a3b8") : "rgba(100,116,139,0.12)";
    ctx.globalAlpha = active ? (focusId ? 0.85 : 0.45) : 0.15;
    ctx.lineWidth = active && focusId ? 2 / cam.z : 1.1 / cam.z;
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }
  ctx.globalAlpha = 1;

  for (const n of nodes) {
    if (visibleKinds[n.kind] === false) continue;
    const r = radiusOf(n);
    const active = !focusId || focusNeighbors.has(n.id);
    ctx.globalAlpha = active ? 1 : 0.18;
    ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = COLORS[n.kind] || "#64748b";
    ctx.fill();
    if (n.id === selectedId || n.id === hoveredId) {
      ctx.lineWidth = 2.5 / cam.z; ctx.strokeStyle = "#ffffff"; ctx.stroke();
    }
    if (cam.z > 0.55 || n.kind === "Universe" || n.kind === "Source" || n.id === selectedId || n.id === hoveredId) {
      const label = shortText(n.label || n.id, 26);
      ctx.font = `${n.kind === "Universe" ? "bold " : ""}11px "Segoe UI", sans-serif`;
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = styles.getPropertyValue("--label-bg");
      ctx.fillRect(n.x - tw / 2 - 4, n.y + r + 3, tw + 8, 16);
      ctx.fillStyle = styles.getPropertyValue("--text");
      ctx.textAlign = "center";
      ctx.fillText(label, n.x, n.y + r + 15);
    }
  }
  ctx.globalAlpha = 1;
  ctx.restore();
}

function screenToWorld(sx, sy) {
  return { x: (sx - canvas.clientWidth / 2) / cam.z + cam.x, y: (sy - canvas.clientHeight / 2) / cam.z + cam.y };
}
function hitTest(sx, sy) {
  const p = screenToWorld(sx, sy);
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i];
    if (visibleKinds[n.kind] === false) continue;
    const r = radiusOf(n) + 4 / cam.z;
    if ((p.x - n.x) ** 2 + (p.y - n.y) ** 2 <= r * r) return n;
  }
  return null;
}

let draggingPan = false, dragNode = null, last = { x: 0, y: 0 };
canvas.addEventListener("mousedown", e => {
  const hit = hitTest(e.offsetX, e.offsetY);
  last = { x: e.offsetX, y: e.offsetY };
  if (hit) { dragNode = hit; selectNode(hit.id); }
  else { draggingPan = true; canvas.classList.add("dragging"); }
});
window.addEventListener("mousemove", e => {
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  if (dragNode) { const p = screenToWorld(sx, sy); dragNode.x = p.x; dragNode.y = p.y; draw(); return; }
  if (draggingPan) { cam.x -= (sx - last.x) / cam.z; cam.y -= (sy - last.y) / cam.z; last = { x: sx, y: sy }; draw(); return; }
  const hit = hitTest(sx, sy);
  const next = hit ? hit.id : null;
  if (next !== hoveredId) { hoveredId = next; draw(); }
});
window.addEventListener("mouseup", () => { dragNode = null; draggingPan = false; canvas.classList.remove("dragging"); });
canvas.addEventListener("wheel", e => { e.preventDefault(); zoomBy(e.deltaY < 0 ? 1.15 : 0.87); }, { passive: false });

function selectNode(id) {
  selectedId = id;
  const n = byId.get(id);
  const el = document.getElementById("info-body");
  if (!n) { el.innerHTML = "Cliquez sur un nœud pour l'inspecter."; return; }
  const attrs = n.attrs || {};
  const url = attrs.location || attrs.url || "";
  let html = `<div class="field"><b>Type :</b> ${KIND_LABELS[n.kind] || n.kind}</div>`;
  html += `<div class="field"><b>Nom :</b> ${n.label}</div>`;
  if (url) html += `<div class="field"><b>URL :</b> <a href="${url}" target="_blank" rel="noopener">${url}</a></div>`;
  if (attrs.status) html += `<div class="field"><b>Statut :</b> ${attrs.status}</div>`;
  if (attrs.score !== undefined) html += `<div class="field"><b>Pertinence :</b> ${attrs.score}</div>`;
  if (attrs.aliases && attrs.aliases.length) html += `<div class="field"><b>Alias :</b> ${attrs.aliases.join(", ")}</div>`;
  if (attrs.taxonomy && attrs.taxonomy.length) html += `<div class="field"><b>Taxonomie :</b> ${attrs.taxonomy.join(", ")}</div>`;
  if (attrs.mentions !== undefined) html += `<div class="field"><b>Mentions :</b> ${attrs.mentions} (${attrs.extractor || "rules"})</div>`;
  if (attrs.chunk_ids && attrs.chunk_ids.length) html += `<div class="field"><b>Chunks :</b> ${attrs.chunk_ids.slice(0, 5).join(", ")}</div>`;
  const neigh = (adj.get(id) || []).slice(0, 20);
  if (neigh.length) {
    html += `<div class="field" style="margin-top:8px"><b>Voisins (${(adj.get(id) || []).length}) :</b></div>`;
    for (const item of neigh) {
      const target = byId.get(item.id);
      if (target) html += `<span class="neighbor" onclick="focusNode('${target.id}')">${target.label}</span>`;
    }
  }
  el.innerHTML = html;
  draw();
}

function focusNode(id) {
  const n = byId.get(id);
  if (!n) return;
  visibleKinds[n.kind] = true;
  cam.x = n.x; cam.y = n.y; cam.z = Math.max(cam.z, 1.1);
  selectNode(id);
}

const legend = document.getElementById("legend");
const counts = {};
for (const n of nodes) counts[n.kind] = (counts[n.kind] || 0) + 1;
const isSemantic = (GRAPH.meta && GRAPH.meta.mode === "knowledge") || ["Person", "Location", "Faction", "Concept", "Timeline"].some(k => counts[k] > 0);
const legendKinds = isSemantic ? ["Person", "Location", "Faction", "Concept", "Timeline"] : ["Universe", "Source", "Document", "Candidate"];
for (const kind of legendKinds) {
  const row = document.createElement("label");
  row.className = "legend-row";
  row.innerHTML = `<input type="checkbox" checked><span class="dot" style="background:${COLORS[kind]}"></span><span>${KIND_LABELS[kind]}</span><span class="cnt">${counts[kind] || 0}</span>`;
  row.querySelector("input").addEventListener("change", e => { visibleKinds[kind] = e.target.checked; draw(); });
  legend.appendChild(row);
}
document.getElementById("stats").textContent = `${nodes.length} nœuds · ${edges.length} liens`;

const searchInput = document.getElementById("search");
const results = document.getElementById("results");
searchInput.addEventListener("input", () => {
  const q = searchInput.value.trim().toLowerCase();
  results.innerHTML = "";
  if (!q) { results.style.display = "none"; return; }
  const matches = nodes.filter(n => (n.label || "").toLowerCase().includes(q) || ((n.attrs && (n.attrs.location || n.attrs.url)) || "").toLowerCase().includes(q)).slice(0, 25);
  results.style.display = matches.length ? "block" : "none";
  for (const m of matches) {
    const div = document.createElement("div");
    div.className = "res-item";
    div.textContent = `[${KIND_LABELS[m.kind] || m.kind}] ${m.label}`;
    div.onclick = () => { focusNode(m.id); results.style.display = "none"; };
    results.appendChild(div);
  }
});

let frames = 0;
function loop() {
  if (physics && frames < 260) { stepPhysics(); frames++; }
  draw();
  requestAnimationFrame(loop);
}
for (let i = 0; i < 60; i++) stepPhysics();
fitView();
loop();
</script>
</body>
</html>
"""
