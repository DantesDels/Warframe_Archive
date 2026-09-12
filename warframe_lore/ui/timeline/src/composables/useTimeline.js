/**
 * useTimeline.js — composable Vue 3 pour la Timeline ELK + Vue Flow.
 *
 * Responsabilités (une seule source de vérité, SOLID) :
 *   1. Charger graph.json (sortie de scripts/extractor.js) ;
 *   2. Calculer le sous-graphe visible (masquage d'éléments ET de clusters,
 *      avec héritage : masquer un cluster masque ses membres) ;
 *   3. RECONNEXION CAUSALE (cohérence diégétique) : si on masque B dans un
 *      chemin A → B → C, on synthétise le lien direct A → C (marqué
 *      `reconnected` pour le style). La borne est la visibilité, pas le nombre
 *      de sauts : BFS n'autorisant que des intermédiaires masqués ;
 *   4. Calculer le layout (ELK via `src/lib/elk.js`, promise asynchrone) et
 *      transcoder les positions absolues ELK en nœuds Vue Flow (les enfants
 *      d'un composé sont RELATIFS au parent dans Vue Flow).
 *
 * Utilisation :
 *   const tl = useTimeline({ source })
 *   tl.load() ; tl.toggleHidden('albrecht') ; tl.showAll()
 *
 * Le contexte (actions + état masqués) est fourni aux composants de nœuds
 * (Timeline.vue) par provide/inject via `TIMELINE_KEY`.
 */
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { layoutGraph } from '../lib/elk.js'

export const TIMELINE_KEY = Symbol('timeline')

const LEAF_W = 200
const LEAF_H = 76

/** Transcode les positions ELK en nœuds Vue Flow. ELK renvoie, comme Vue
 *  Flow, des positions RELATIVES pour les enfants d'un composé (cluster) et
 *  ABSOLUES pour les nœuds racine : les deux s'appliquent tels quels.
 *  NB Vue Flow 1.33 nomme la prop composé/enfant `parentNode` (pas `parentId`). */
function toFlowNodes(visibleNodes, positions) {
  return visibleNodes.map((n) => {
    const pos = positions[n.id] || { x: 0, y: 0, width: LEAF_W, height: LEAF_H }
    const byId = new Map(visibleNodes.map((o) => [o.id, o]))
    const parent = n.parentId && byId.has(n.parentId) ? n.parentId : undefined
    return {
      id: n.id,
      type: n.type === 'cluster' ? 'cluster' : 'entity',
      position: { x: pos.x, y: pos.y },
      parentNode: parent,
      extent: parent ? 'parent' : undefined,
      data: {
        id: n.id,
        label: n.label,
        year: n.year || '',
        note: n.note || '',
        codex_slug: n.codex_slug || null,
        parentNode: parent || null,
      },
      style: { width: pos.width || LEAF_W, height: pos.height || LEAF_H },
      draggable: false,
      connectable: false,
    }
  })
}

/** Recalcule les dimensions réelles (retour ELK) pour le prochain passage :
 *  premier layout approximatif (feuilles 200×76), layout suivant exact. */
function bestEffortSize(nodeId, positions, measured) {
  if (positions && positions[nodeId]) {
    return { width: positions[nodeId].width, height: positions[nodeId].height }
  }
  return measured.get(nodeId) || null
}

export function useTimeline({ source }) {
  /* ------------------------------------------------------------- état (données) */
  const rawNodes = ref([]) // entités + clusters issus de graph.json
  const rawEdges = ref([]) // relations directionnelles
  const hidden = ref(new Set()) // éléments masqués (clusters ou entités)
  const loading = ref(false)
  const error = ref('')

  const flowNodes = ref([]) // nœuds Vue Flow (positions/tailles ELK appliquées)
  const flowEdges = ref([])
  const measured = new Map() // id -> {width, height} réels (rendu 2 temps)

  const visibleCount = computed(() => flowNodes.value.length)
  const hiddenCount = computed(() => hidden.value.size)
  const reconnectedCount = computed(() => flowEdges.value.filter((e) => e.data.reconnected).length)

  /* ------------------------------------------------- visibilité (héritage cluster) */
  function isVisible(node) {
    if (hidden.value.has(node.id)) return false
    if (node.parentId && hidden.value.has(node.parentId)) return false
    return true
  }

  const visibleNodes = computed(() => rawNodes.value.filter(isVisible))

  /* ----------------------------------------- reconnexion causale (cohérence diégétique) */
  const effectiveEdges = computed(() => {
    const visibleIds = new Set(visibleNodes.value.map((n) => n.id))
    const original = rawEdges.value

    const outgoing = new Map() // id -> [{ target, type, label }] (graphe complet)
    for (const e of original) {
      const list = outgoing.get(e.source) || []
      list.push({ target: e.target, type: e.type, label: e.label, id: e.id })
      outgoing.set(e.source, list)
    }

    // Liens dont les deux extrémités sont visibles : portés tels quels.
    const base = original
      .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
      .map((e) => ({
        ...e,
        reconnected: false,
        _key: `${e.source}\u0000${e.target}\u0000${e.type}\u0000${e.id}`,
      }))
    const basePairs = new Set(base.map((e) => `${e.source}\u0000${e.target}`))
    const synthesized = []
    const synthKeys = new Set()

    // BFS : on traverse UNIQUEMENT des intermédiaires masqués ; dès qu'on
    // touche un nœud visible, la chaîne est coupée (pas de relais via un
    // visible). Tout nœud visible atteint en ≥ 2 sauts produit un lien
    // direct synthétique (A → B → C, B masqué ⇒ A → C).
    const outgoingBase = outgoing
    for (const source of visibleIds) {
      const queue = [{ node: source, hop: 0, label: '', type: '' }]
      const visitedHidden = new Set()
      while (queue.length) {
        const { node, hop, label, type } = queue.shift()
        for (const link of outgoingBase.get(node) || []) {
          const nextHop = hop + 1
          const isNextVisible = visibleIds.has(link.target)
          if (isNextVisible && nextHop >= 2 && link.target !== source) {
            const pair = `${source}\u0000${link.target}`
            if (!basePairs.has(pair) && !synthKeys.has(pair)) {
              synthKeys.add(pair)
              synthesized.push({
                id: `re:${source}\u0000${link.target}`,
                source,
                target: link.target,
                type: link.type,
                label: label || '',
                reconnected: true,
                _key: `reconnected:${pair}`,
              })
            }
          } else if (!isNextVisible) {
            if (visitedHidden.has(link.target)) continue
            visitedHidden.add(link.target)
            queue.push({ node: link.target, hop: nextHop, label: label || link.label, type: link.type })
          }
        }
      }
    }

    // Ordre stable : liens réels puis reconnexions (déterministe).
    return [...base, ...synthesized].map((e) => ({ ...e, _key: undefined }))
  })

  /* ------------------------------------------------------------- layout ELK (direct) */
  let layoutTimer = null
  let disposed = false

  // Garde anti-course : seul le layout LANCÉ EN DERNIER applique ses résultats
  // (les promesses ELK ne sont pas annulables, on ignore le reste).
  let runSeq = 0

  function applyLayout(positions, edgePoints, size) {
    if (disposed) return
    flowNodes.value = toFlowNodes(visibleNodes.value, positions)
    for (const node of visibleNodes.value) {
      if (positions[node.id]) measured.set(node.id, positions[node.id])
    }

    const flow = []
    for (const e of effectiveEdges.value) {
      const pts = edgePoints[e.id] || null
      flow.push({
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'timeline',
        data: {
          label: e.label || '',
          linkedType: e.type || '',
          reconnected: !!e.reconnected,
          points: pts ? pts.points || [] : [],
        },
      })
    }
    flowEdges.value = flow
    void size
  }

  async function requestLayout() {
    const seq = ++runSeq
    const nodes = visibleNodes.value.map((n) => {
      const sizeKnown = bestEffortSize(n.id, null, measured)
      return {
        id: n.id,
        parentId: n.type === 'cluster' ? undefined : n.parentId || undefined,
        width: n.type === 'cluster' ? undefined : sizeKnown ? sizeKnown.width : LEAF_W,
        height: n.type === 'cluster' ? undefined : sizeKnown ? sizeKnown.height : LEAF_H,
      }
    })
    const edges = effectiveEdges.value.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: e.type,
    }))
    try {
      const result = await layoutGraph(nodes, edges)
      if (disposed || seq !== runSeq) return // résultat périmé ou démonté
      applyLayout(result.positions, result.edges, result.size)
    } catch (err) {
      if (disposed) return
      error.value = err && err.message ? `Layout impossible : ${err.message}` : String(err)
    }
  }

  // Debounce : un masquage rapide (clic ✕ successifs) ne re-calcule qu'une fois.
  function scheduleLayout() {
    clearTimeout(layoutTimer)
    layoutTimer = setTimeout(requestLayout, 60)
  }

  /* ------------------------------------------------- réagir au graphe visible */
  watch([visibleNodes, effectiveEdges], scheduleLayout)

  /* -------------------------------------------------------------- chargement source */
  async function load() {
    error.value = ''
    loading.value = true
    try {
      const res = await fetch(source)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const graph = await res.json()
      rawNodes.value = graph.nodes || []
      rawEdges.value = graph.edges || []
      requestLayout()
    } catch (err) {
      error.value = err && err.message ? String(err.message) : String(err)
    } finally {
      loading.value = false
    }
  }

  /* ------------------------------------------------------------------ actions UI */
  function toggleHidden(id) {
    const next = new Set(hidden.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    hidden.value = next
  }

  function showAll() {
    hidden.value = new Set()
  }

  onUnmounted(() => {
    disposed = true
    clearTimeout(layoutTimer)
  })

  // Objet RÉACTIF (et non plat) : le template ne déréférence que les refs
  // RACINE de setup() — avec un objet plat, `tl.flowNodes` serait l'objet
  // ref lui-même, et Vue Flow planterait sur `...opts.nodes` (spread d'un
  // non-itérable). reactive() déréférence les refs imbriquées d'un niveau :
  // tl.flowNodes, tl.loading, tl.visibleCount, tl.hidden, … deviennent leurs
  // valeurs réelles dans le template et pour Vue Flow.
  return reactive({
    load,
    toggleHidden,
    showAll,
    rawNodes,
    rawEdges,
    hidden,
    effectiveEdges,
    flowNodes,
    flowEdges,
    loading,
    error,
    visibleCount,
    hiddenCount,
    reconnectedCount,
  })
}