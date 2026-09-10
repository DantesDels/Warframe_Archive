<script setup>
/** Timeline — lore Warframe "L'Éternisme" (Vue 3 + dagre en Web Worker).
 *
 * - Lazy-loading par profondeur : /api/timeline/roots puis
 *   /api/timeline?parent_id={id} au clic sur un nœud avec has_children.
 * - Layout dagre délégué à dagre.worker.js ; les positions reviennent sans
 *   bloquer l'UI (tokens incrémentaux pour ignorer les résultats périmés).
 * - Pan/Zoom via @vueuse/gesture (drag, wheel, pinch) appliqués au stage.
 */
import { computed, onMounted, onUnmounted, reactive, ref, shallowRef } from 'vue'
import { useGesture } from '@vueuse/gesture'

const SIZES = {
  era: { width: 190, height: 58 },
  quest: { width: 168, height: 42 },
  fragment: { width: 18, height: 18 },
}

/* ------------------------------------------------------------- état réactif */
const nodes = shallowRef(new Map())      // id -> nœud vivant {x, y, ...}
const edges = ref([])                    // liens paradoxaux (2 extrémités chargées)
const loading = ref(false)
const expanding = ref(new Set())
const error = ref('')

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

worker.onmessage = (event) => {
  const data = event.data || {}
  if (data.type === 'layout') {
    layoutInFlight = false
    if (data.token !== layoutToken) {
      // résultat périmé (une expansion a eu lieu entre-temps) : on relance.
      requestLayout()
      return
    }
    applyPositions(data.positions)
    if (layoutQueued) {
      layoutQueued = false
      requestLayout()
    }
  } else if (data.type === 'error') {
    layoutInFlight = false
    error.value = data.error || 'Erreur de calcul du layout'
  }
}

function requestLayout() {
  if (layoutInFlight) {
    layoutQueued = true
    return
  }
  layoutInFlight = true
  layoutToken += 1
  const payloadNodes = []
  nodes.value.forEach((n) => {
    payloadNodes.push({ id: n.id, width: n.width, height: n.height })
  })
  const loaded = new Set(nodes.value.keys())
  const payloadEdges = edges.value.filter(
    (e) => loaded.has(e.source) && loaded.has(e.target),
  )
  worker.postMessage({
    token: layoutToken,
    nodes: payloadNodes,
    edges: payloadEdges,
    options: { rankdir: 'LR' },
  })
}

function applyPositions(positions) {
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
  // négative dans le canevas) puis remplace les records (nouveau Map →
  // déclenche le re-rendu du graphe).
  const dx = 24 - minX
  const dy = 24 - minY
  const next = new Map()
  current.forEach((n) => {
    const p = positions[n.id]
    next.set(
      n.id,
      p ? { ...n, x: p.x + dx, y: p.y + dy } : n,
    )
  })
  nodes.value = next

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
  const size = SIZES[p.kind] || SIZES.quest
  return {
    id: p.id,
    parent_id: p.parent_id,
    label: p.label,
    kind: p.kind,
    has_children: !!p.has_children,
    year: p.year || '',
    note: p.note || '',
    width: size.width,
    height: size.height,
    x: 0,
    y: 0,
  }
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
  const extra = (list || []).filter((e) => !seen.has(`${e.source}\u0000${e.target}`))
  if (extra.length) edges.value = edges.value.concat(extra)
}

async function loadRoots() {
  error.value = ''
  loading.value = true
  try {
    const payload = await fetchJson('/api/timeline/roots')
    mergeNodes(payload.nodes)
    mergeEdges(payload.edges)
    requestLayout()
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
    .then((payload) => {
      mergeNodes(payload.nodes)
      mergeEdges(payload.edges)
      const live = nodes.value.get(node.id)
      if (live) live.has_children = false
      requestLayout()
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

const bind = useGesture({
  onDrag: ({ delta, tap }) => {
    if (tap) return
    view.x += delta[0]
    view.y += delta[1]
  },
  onWheel: ({ delta, event }) => {
    const el = stageEl.value
    if (!el) return
    const rect = el.getBoundingClientRect()
    zoomAt(delta[1] > 0 ? 0.92 : 1.08,
      event.clientX - rect.left, event.clientY - rect.top)
  },
  onPinch: ({ offset }) => {
    view.scale = clampScale(offset[0] || 1)
  },
})

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
  const out = []
  for (const e of edges.value) {
    const source = map.get(e.source)
    const target = map.get(e.target)
    if (!source || !target) continue
    out.push({
      key: `${e.source}\u0000${e.target}`,
      label: e.label || '',
      source,
      target,
    })
  }
  return out
})

function pathFor(e) {
  const sx = e.source.x + e.source.width / 2
  const sy = e.source.y + e.source.height / 2
  const tx = e.target.x + e.target.width / 2
  const ty = e.target.y + e.target.height / 2
  const mx = (sx + tx) / 2
  return `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}`
}

function nodeStyle(n) {
  return {
    left: `${n.x}px`,
    top: `${n.y}px`,
    width: `${n.width}px`,
    height: `${n.height}px`,
  }
}

function nodeTitle(n) {
  const parts = [n.label]
  if (n.year) parts.push(n.year)
  if (n.note) parts.push(n.note)
  return parts.join(' — ')
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

    <div ref="stageEl" class="stage" v-bind="bind()">
      <div v-if="loading && !nodeList.length" class="tl-caption">Chargement des ères…</div>

      <div class="canvas" :style="canvasStyle">
        <svg class="edges" :width="bounds.width" :height="bounds.height">
          <path
            v-for="e in renderedEdges"
            :key="e.key"
            class="edge edge-paradox"
            :d="pathFor(e)"
          >
            <title>{{ e.label }}</title>
          </path>
        </svg>

        <div
          v-for="n in nodeList"
          :key="n.id"
          class="node"
          :class="`node-${n.kind}`"
          :style="nodeStyle(n)"
          :title="nodeTitle(n)"
        >
          <span v-if="n.kind !== 'fragment'" class="node-label">{{ n.label }}</span>
          <span v-else class="node-dot"></span>
          <button
            v-if="n.has_children"
            class="node-expand"
            type="button"
            :disabled="expanding.has(n.id)"
            @click.stop="expand(n)"
          >{{ expanding.has(n.id) ? '…' : '+' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>