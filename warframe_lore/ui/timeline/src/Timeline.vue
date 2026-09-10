<script setup>
/** Timeline — lore Warframe "L'Éternisme" (Vue 3 + dagre en Web Worker).
 *
 * - Lazy-loading par profondeur : /api/timeline/roots puis
 *   /api/timeline?parent_id={id} au clic sur un nœud avec has_children.
 * - Layout dagre délégué à dagre.worker.js ; les positions reviennent sans
 *   bloquer l'UI (tokens incrémentaux pour ignorer les résultats périmés).
 * - Pan/Zoom via gestes natifs (pointer drag, wheel, pinch) sur le stage.
 * - Rendu 2 temps : les nouveaux nœuds sont enfants, mesurés après le patch
 *   DOM (offsetWidth/offsetHeight), puis placés par dagre avec fade-in.
 */
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, shallowRef } from 'vue'

/* ------------------------------------------------------------- état réactif */
const nodes = shallowRef(new Map())      // id -> nœud vivant {x, y, ...}
const edges = ref([])                    // liens {source, target, label, paradox}
const edgePoints = shallowRef(new Map()) // "src\0tgt" -> points de routing dagre
const loading = ref(false)
const expanding = ref(new Set())
const error = ref('')
const tip = ref(null)                    // tooltip fragment {x, y, text}
const nodeEls = new Map()                // id -> HTMLElement (mesure DOM réelle)

const view = reactive({ x: 32, y: 32, scale: 1 })
const bounds = reactive({ width: 0, height: 0 })
const stageEl = ref(null)

/* ------------------------------------------------------------ worker dagre */
const worker = new Worker(
  new URL('./workers/dagre.worker.js', import.meta.url),
  { type: 'module' },
)
let layoutToken = 0
let layoutInFlight = false
let layoutQueued = false
let layoutRetry = null
let lastPayload = null

/* Garde-fou : Chrome peut perdre le premier postMessage d'un worker module
 * (init asynchrone concurrencé par le chargement). Si aucune réponse dans le
 * délai, on re-poste le même payload (idempotent par token). */
function scheduleRetry(token) {
  clearTimeout(layoutRetry)
  layoutRetry = setTimeout(() => {
    if (layoutInFlight && token === layoutToken && lastPayload) {
      worker.postMessage(lastPayload)
      scheduleRetry(token)
    }
  }, 1000)
}

worker.onmessage = (event) => {
  const data = event.data || {}
  if (data.type === 'layout') {
    clearTimeout(layoutRetry)
    layoutInFlight = false
    if (data.token !== layoutToken) {
      // résultat périmé (une expansion a eu lieu entre-temps) : on relance.
      requestLayout()
      return
    }
    applyLayout(data.positions, data.edges || [])
    if (layoutQueued) {
      layoutQueued = false
      requestLayout()
    }
  } else if (data.type === 'error') {
    clearTimeout(layoutRetry)
    layoutInFlight = false
    error.value = data.error || 'Erreur de calcul du layout'
  }
}
worker.onerror = (event) => {
  clearTimeout(layoutRetry)
  error.value = event && event.message
    ? `Worker indisponible : ${event.message}`
    : 'Worker indisponible (chargement du module)'
}

function postLayout(token) {
  const payloadNodes = []
  nodes.value.forEach((n) => {
    payloadNodes.push({ id: n.id, width: n.width, height: n.height })
  })
  const loaded = new Set(nodes.value.keys())
  // edges.value est un ref profondément réactif : les éléments filtrés sont des
  // Proxy Vue que structuredClone ne peut pas cloner ("could not be cloned").
  // On aplatit donc chaque lién en objet brut avant envoi au worker.
  const payloadEdges = edges.value
    .filter((e) => loaded.has(e.source) && loaded.has(e.target))
    .map((e) => ({ source: e.source, target: e.target }))
  lastPayload = {
    token,
    nodes: payloadNodes,
    edges: payloadEdges,
    options: { rankdir: 'LR' },
  }
  try {
    worker.postMessage(lastPayload)
  } catch (err) {
    error.value = err && err.message ? `Envoi au worker impossible : ${err.message}` : String(err)
    return
  }
  scheduleRetry(token)
}

function requestLayout() {
  if (layoutInFlight) {
    layoutQueued = true
    return
  }
  layoutInFlight = true
  layoutToken += 1
  postLayout(layoutToken)
}

function applyLayout(positions, edgePointsList) {
  const current = nodes.value
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  const known = new Set(positions ? Object.keys(positions) : [])
  current.forEach((n) => {
    if (!known.has(n.id)) return
    const p = positions[n.id]
    minX = Math.min(minX, p.x - n.width / 2)
    minY = Math.min(minY, p.y - n.height / 2)
    maxX = Math.max(maxX, p.x + n.width / 2)
    maxY = Math.max(maxY, p.y + n.height / 2)
  })
  if (minX === Infinity) return

  // Décale pour que le coin du graphe commence à 24 px (aucune coordonnée
  // négative dans le canevas). Le même décalage s'applique aux points de
  // routing des arêtes (sinon courbes et boîtes se désynchronisent).
  const dx = 24 - minX
  const dy = 24 - minY
  const pts = new Map()
  for (const ep of edgePointsList || []) {
    pts.set(
      `${ep.source}\u0000${ep.target}`,
      (ep.points || []).map((p) => ({ x: p.x + dx, y: p.y + dy })),
    )
  }

  // Remplace les records (nouveau Map -> déclenche le re-rendu du graphe).
  const next = new Map()
  current.forEach((n) => {
    const p = positions[n.id]
    next.set(
      n.id,
      p ? { ...n, x: p.x + dx, y: p.y + dy, placed: true } : n,
    )
  })
  nodes.value = next
  edgePoints.value = pts

  bounds.width = maxX - minX
  bounds.height = maxY - minY
}

/* -------------------------------------------------------------- lazy loading */
async function fetchJson(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

function makeRecord(p) {
  return {
    id: p.id,
    parent_id: p.parent_id,
    label: p.label,
    kind: p.kind,
    has_children: !!p.has_children,
    year: p.year || '',
    note: p.note || '',
    // Dimensions réelles inconnues tant que le nœud n'est pas mesuré dans le
    // DOM (rendu 2 temps) : on les lit puis on les envoie au worker dagre.
    width: 0,
    height: 0,
    measured: false,
    placed: false,
    x: 0,
    y: 0,
  }
}

function setNodeEl(el, id) {
  if (el) nodeEls.set(id, el)
  else nodeEls.delete(id)
}

/* Rendu 2 temps, phase 1 : après le patch DOM, on mesure la taille réelle de
 * chaque nœud encore non placé (offsetWidth/offsetHeight de son contenu)
 * puis on redemande un layout dagre avec ces dimensions exactes. */
function measureUnmeasured() {
  const current = nodes.value
  nodeEls.forEach((el, id) => {
    const n = current.get(id)
    if (!n || n.measured) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    if (w > 0 && h > 0) {
      n.width = w
      n.height = h
      n.measured = true
    }
  })
}

async function layout() {
  await nextTick()
  measureUnmeasured()
  requestLayout()
}

function mergeNodes(list) {
  const next = new Map(nodes.value)
  for (const p of list || []) {
    const prev = next.get(p.id)
    next.set(p.id, prev ? { ...prev, has_children: p.has_children } : makeRecord(p))
  }
  nodes.value = next
}

function mergeEdges(list) {
  const seen = new Set(edges.value.map((e) => `${e.source}\u0000${e.target}`))
  const extra = (list || [])
    .filter((e) => !seen.has(`${e.source}\u0000${e.target}`))
    .map((e) => ({
      source: e.source,
      target: e.target,
      label: e.label || '',
      paradox: !!e.paradox,
    }))
  if (extra.length) edges.value = edges.value.concat(extra)
}

async function loadRoots() {
  error.value = ''
  loading.value = true
  try {
    const payload = await fetchJson('/api/timeline/roots')
    mergeNodes(payload.nodes)
    mergeEdges(payload.edges)
    await layout()
  } catch (err) {
    error.value = err && err.message ? String(err.message) : String(err)
  } finally {
    loading.value = false
  }
}

function expand(node) {
  if (expanding.value.has(node.id)) return
  expanding.value.add(node.id)
  fetchJson(`/api/timeline?parent_id=${encodeURIComponent(node.id)}`)
    .then(async (payload) => {
      mergeNodes(payload.nodes)
      mergeEdges(payload.edges)
      const live = nodes.value.get(node.id)
      if (live) live.has_children = false
      await layout()
    })
    .catch((err) => {
      error.value = err && err.message ? String(err.message) : String(err)
    })
    .finally(() => {
      expanding.value.delete(node.id)
    })
}

/* -------------------------------------------------------------- pan / zoom */
const clampScale = (s) => Math.min(2.5, Math.max(0.3, s))

function zoomAt(factor, cx, cy) {
  const next = clampScale(view.scale * factor)
  if (cx != null) {
    const wx = (cx - view.x) / view.scale
    const wy = (cy - view.y) / view.scale
    view.x = cx - wx * next
    view.y = cy - wy * next
  }
  view.scale = next
}

/* Gestes natifs (pointer drag) — pan · zoom molette · pinch deux doigts. */
const pointers = new Map()
const pan = { active: false, lastX: 0, lastY: 0 }
const pinch = { active: false, dist0: 1, scale0: 1, cx0: 0, cy0: 0 }

function pointerDist() {
  const [a, b] = [...pointers.values()]
  return Math.hypot(a.x - b.x, a.y - b.y)
}
function pointerCenter() {
  const [a, b] = [...pointers.values()]
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
}

function onPointerDown(event) {
  const el = stageEl.value
  if (el && el.setPointerCapture) el.setPointerCapture(event.pointerId)
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pointers.size === 2) {
    pinch.active = true
    pinch.dist0 = pointerDist()
    pinch.scale0 = view.scale
    const c = pointerCenter()
    pinch.cx0 = c.x
    pinch.cy0 = c.y
  } else {
    pan.active = true
    pan.lastX = event.clientX
    pan.lastY = event.clientY
  }
}

function onPointerMove(event) {
  if (!pointers.has(event.pointerId)) return
  const prev = pointers.get(event.pointerId)
  prev.x = event.clientX
  prev.y = event.clientY
  if (pinch.active && pointers.size >= 2) {
    const dist = pointerDist()
    const next = clampScale(pinch.scale0 * (dist / pinch.dist0))
    const wx = (pinch.cx0 - view.x) / view.scale
    const wy = (pinch.cy0 - view.y) / view.scale
    view.scale = next
    view.x = pinch.cx0 - wx * next
    view.y = pinch.cy0 - wy * next
  } else if (pan.active) {
    view.x += event.clientX - pan.lastX
    view.y += event.clientY - pan.lastY
    pan.lastX = event.clientX
    pan.lastY = event.clientY
  }
}

function onPointerUp(event) {
  pointers.delete(event.pointerId)
  if (pointers.size < 2) pinch.active = false
  if (pointers.size === 0) pan.active = false
}

function onWheel(event) {
  const rect = stageEl.value?.getBoundingClientRect()
  if (!rect) return
  zoomAt(event.deltaY > 0 ? 0.92 : 1.08,
    event.clientX - rect.left, event.clientY - rect.top)
}

function zoomButtons(factor) {
  const el = stageEl.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  zoomAt(factor, rect.width / 2, rect.height / 2)
}

function resetView() {
  view.x = 32
  view.y = 32
  view.scale = 1
}

/* ---------------------------------------------------------------- rendu */
const nodeList = computed(() => [...nodes.value.values()])

const renderedEdges = computed(() => {
  const map = nodes.value
  const pts = edgePoints.value
  const out = []
  for (const e of edges.value) {
    const source = map.get(e.source)
    const target = map.get(e.target)
    if (!source || !target) continue
    out.push({
      key: `${e.source}\u0000${e.target}`,
      label: e.label || '',
      paradox: e.paradox,
      source,
      target,
      points: pts.get(`${e.source}\u0000${e.target}`) || null,
    })
  }
  return out
})

/* Courbe de Catmull-Rom convertie en Béziers cubiques : chaque point de
 * routing dagre est traversé exactement, la tangente est déduite des voisins
 * (lissée), et les extrémités touchent les bords des boîtes. */
function catmullRomPath(pts) {
  let d = `M ${pts[0].x} ${pts[0].y}`
  for (let i = 0; i < pts.length - 1; i += 1) {
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const prev = pts[i - 1] || p1
    const nxt = pts[i + 2] || p2
    const c1x = p1.x + (p2.x - prev.x) / 6
    const c1y = p1.y + (p2.y - prev.y) / 6
    const c2x = p2.x - (nxt.x - p1.x) / 6
    const c2y = p2.y - (nxt.y - p1.y) / 6
    d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`
  }
  return d
}

function pathFor(e) {
  if (e.points && e.points.length >= 2) return catmullRomPath(e.points)
  // Fallback sans routing (nœud pas encore mesuré) : conique d'horizon.
  const sx = e.source.x + e.source.width / 2
  const sy = e.source.y + e.source.height / 2
  const tx = e.target.x + e.target.width / 2
  const ty = e.target.y + e.target.height / 2
  const mx = (sx + tx) / 2
  return `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}`
}

function edgeClass(e) {
  return e.paradox ? 'edge edge-paradox' : 'edge edge-sequel'
}

function nodeStyle(n) {
  // Tant que dagre n'a pas placé le nœud : invisible (opacity 0 en inline,
  // prioritaire), la position est posée par le layout suivant.
  if (!n.placed) return { opacity: 0 }
  return { left: `${n.x}px`, top: `${n.y}px` }
}

function nodeTitle(n) {
  const parts = [n.label]
  if (n.year) parts.push(n.year)
  if (n.note) parts.push(n.note)
  return parts.join(' — ')
}

/* Tooltip survol des fragments (points sans label) : position fixe dans le
 * viewport, calculée depuis la boîte du nœud au survol. */
function showTip(event, n) {
  if (n.kind !== 'fragment') return
  const rect = event.currentTarget.getBoundingClientRect()
  tip.value = { x: rect.left + rect.width / 2, y: rect.top - 8, text: nodeTitle(n) }
}

function hideTip() {
  tip.value = null
}

const canvasStyle = computed(() => ({
  transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
  width: `${bounds.width}px`,
  height: `${bounds.height}px`,
}))

/* -------------------------------------------------------------- lifecycle */
onMounted(loadRoots)
onUnmounted(() => worker.terminate())
</script>

<template>
  <div class="tl">
    <div class="tl-toolbar">
      <button class="tl-btn" type="button" title="Zoomer" @click="zoomButtons(1.2)">＋</button>
      <button class="tl-btn" type="button" title="Dézoomer" @click="zoomButtons(0.85)">−</button>
      <button class="tl-btn" type="button" title="Réinitialiser la vue" @click="resetView">⟲</button>
      <span class="tl-count">{{ nodeList.length }} nœuds</span>
    </div>

    <div
      v-if="error"
      class="tl-error"
      role="alert"
    >{{ error }} — rechargez le serveur Cephalon.</div>

    <div
      ref="stageEl"
      class="stage"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="onPointerUp"
      @wheel.prevent="onWheel"
    >
      <div v-if="loading && !nodeList.length" class="tl-caption">Chargement des ères…</div>

      <div class="canvas" :style="canvasStyle">
        <svg class="edges" :width="bounds.width" :height="bounds.height">
          <path
            v-for="e in renderedEdges"
            :key="e.key"
            :class="edgeClass(e)"
            :d="pathFor(e)"
          >
            <title>{{ e.label }}</title>
          </path>
        </svg>

        <div
          v-for="n in nodeList"
          :key="n.id"
          :ref="(el) => setNodeEl(el, n.id)"
          class="node"
          :class="`node-${n.kind}`"
          :style="nodeStyle(n)"
          :title="nodeTitle(n)"
          @pointerenter="showTip($event, n)"
          @pointerleave="hideTip"
        >
          <span v-if="n.kind !== 'fragment'" class="node-label">{{ n.label }}</span>
          <span v-else class="node-dot"></span>
          <button
            v-if="n.has_children"
            class="node-expand"
            type="button"
            :disabled="expanding.has(n.id)"
            @pointerdown.stop.prevent
            @click.stop="expand(n)"
          >{{ expanding.has(n.id) ? '…' : '+' }}</button>
        </div>
      </div>
    </div>

    <div
      v-if="tip"
      class="tl-tip"
      :style="{ left: tip.x + 'px', top: tip.y + 'px' }"
    >{{ tip.text }}</div>
  </div>
</template>