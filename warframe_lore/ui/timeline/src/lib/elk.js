/**
 * elk.js — accès central à ELK.js pour la Timeline.
 *
 * On utilise `elk.bundled.js` (usage documenté : navigateur, thread central).
 * ELK lance alors un DISPATCHER async en-thread (FakeWorker) : layout promis,
 * calcul hors main-thread de UI si voulu par appels successifs — suffisant pour
 * des graphes de l'ordre de la centaine de nœuds.
 *
 * POURQUOI PAS elk.worker.js ?
 * `elk.bundled.js` est structurellement inutilisable DANS un Web Worker : dans
 * ce contexte, l'engin GWT prend possession de `self.onmessage` et n'exporte
 * rien → son wrapper interne `require('./elk-worker.min.js').Worker` reste
 * indéfini et le constructeur ELK explose (« X is not a constructor »). Le
 * pattern « elk-api + engin séparé » déclenche une seconde erreur dans l'engin
 * en mode worker réel (`Cannot read properties of null (reading 're')`),
 * constatée hors navigateur comme dans le bundle Vite. On reste donc sur le
 * chemin principal supporté par elkjs.
 */
import elkBundled from 'elkjs/lib/elk.bundled.js'

// Interop CJS→ESM : le constructeur peut être exposé directement (`default`
// = ELKNode) ou via un emballage intermédiaire (`default.default`).
const ELK = (elkBundled.default && elkBundled.default.default) || elkBundled.default || elkBundled

export const elk = new ELK()

export const LEAF_W = 200
export const LEAF_H = 76

export const DEFAULTS = {
  // Layered + top-down + clusters (Compound Nodes) inclus dans le layout.
  'elk.algorithm': 'layered',
  'elk.direction': 'DOWN',
  'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
  // Routage orthogonal : les courbes de la timeline restent nettes (pas de
  // béziers aléatoires entre clusters), sections ELK autour des boîtes.
  'elk.edgeRouting': 'ORTHOGONAL',
  // Espacements raisonables (mobile-first) : ne pas serrer les cartes.
  'elk.spacing.nodeNode': 44,
  'elk.layered.spacing.nodeNodeBetweenLayers': 72,
  'elk.spacing.edgeNode': 28,
  'elk.spacing.edgeEdge': 14,
  'elk.padding': '[top=48,left=40,right=40,bottom=40]',
  // Les labels d'arêtes (type de lien) restent à l'horizontale au centre.
  'elk.edgeLabels.placement': 'CENTER',
  'elk.edgeLabels.placement.horizontal': 'CENTER',
  'elk.edgeLabels.placement.vertical': 'CENTER',
}

const CLUSTER_LAYOUT = {
  // Le composé est un cadre (label + padding) : laisser ELK l'agrandir
  // autour des enfants, sans remettre en cause l'alignement des couches.
  'elk.padding': '[top=42,left=20,right=20,bottom=20]',
}

export function buildElkGraph(nodes, edges) {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const childrenOf = new Map()
  for (const node of nodes) {
    const bucket = childrenOf.get(node.parentId ?? null) || []
    bucket.push(node)
    childrenOf.set(node.parentId ?? null, bucket)
  }

  const toElkNode = (node) => {
    const children = childrenOf.get(node.id)
    const sub = { id: node.id }
    if (children) {
      // Nœud composé (cluster) : on ne force PAS width/height — ELK doit
      // déduire la taille via + padding. Surtout : aucune clé `undefined`
      // au JSON (l'engin plante : `Cannot read properties of null (reading
      // 're')`). On n'émet que des clés définies.
      sub.layoutOptions = CLUSTER_LAYOUT
      sub.children = children.map(toElkNode)
    } else {
      sub.width = node.width || LEAF_W
      sub.height = node.height || LEAF_H
    }
    return sub
  }

  // Feuilles racine (SANS enfants) : un composé est porté par la boucle
  // clusters ci-dessous — sinon il serait poussé DEUX FOIS (bucket `null` +
  // boucle), ce qui crée des ids dupliqués dans le graphe ELK et fait
  // planter l'engin (`Cannot read properties of null (reading 're')`).
  const rootChildren = (childrenOf.get(null) || []).filter((n) => !childrenOf.has(n.id)).map(toElkNode)
  for (const cluster of childrenOf.keys()) {
    if (cluster === null) continue
    const node = byId.get(cluster)
    // parentId → nœud absent (ex. membre masqué) : graphe incomplet, on
    // ignore poliment au lieu de planter en lisant `.id` de `undefined`.
    if (!node || !childrenOf.get(cluster)) continue
    rootChildren.push(toElkNode(node))
  }

  return {
    id: 'root',
    layoutOptions: DEFAULTS,
    children: rootChildren,
    edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  }
}

/** Aplatit la hiérarchie ELK : positions racine absolues, celles des enfants
 *  relatives à leur parent (contrat Vue Flow identique). */
function collectPositions(elkChildren, out = {}) {
  for (const sub of elkChildren) {
    out[sub.id] = { x: sub.x || 0, y: sub.y || 0, width: sub.width || 0, height: sub.height || 0 }
    if (sub.children) collectPositions(sub.children, out)
  }
  return out
}

/** Sections ELK → polyligne unique (startPoint + bendPoints + endPoint) en
 *  éliminant les points consécutifs dupliqués. */
function edgePoints(sections) {
  const pts = []
  for (const section of sections || []) {
    if (section.startPoint) pts.push({ x: section.startPoint.x, y: section.startPoint.y })
    for (const bend of section.bendPoints || []) {
      pts.push({ x: bend.x, y: bend.y })
    }
    if (section.endPoint) pts.push({ x: section.endPoint.x, y: section.endPoint.y })
  }
  const dedup = []
  let last = null
  for (const p of pts) {
    if (!last || last.x !== p.x || last.y !== p.y) dedup.push(p)
    last = p
  }
  return dedup
}

/** Layout complet : { positions, edgePoints(par id, avec type), size }.
 *  Lève une erreur → ignorable par l'appelant. */
export async function layoutGraph(nodes, edges) {
  const graph = buildElkGraph(nodes || [], edges || [])
  const layout = await elk.layout(graph)

  let size = { width: 0, height: 0 }
  if (layout.children) {
    size = { width: layout.width || 0, height: layout.height || 0 }
  }

  const edgeByType = new Map((edges || []).map((e) => [e.id, e.type]))
  const pointsMap = {}
  for (const sub of layout.edges || []) {
    pointsMap[sub.id] = { type: edgeByType.get(sub.id) || '', points: edgePoints(sub.sections) }
  }

  return {
    positions: collectPositions(layout.children || []),
    edges: pointsMap,
    size,
  }
}