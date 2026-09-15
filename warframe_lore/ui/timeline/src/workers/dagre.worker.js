/**
 * dagre.worker.js — layout isolé dans un Web Worker.
 *
 * Le composant Vue envoie uniquement les nœuds/liens bruts + un token ;
 * le Worker exécute ``dagre.layout(g)`` en arrière-plan et renvoie les
 * coordonnées (x, y). L'UI reste 100 % fluide pendant le calcul, même
 * avec des milliers de nœuds.
 *
 * Contrat :
 *   in :  { token, nodes: [{ id, width, height }], edges: [{ source, target }] }
 *   out : { type: "layout", token, positions: { id: { x, y, width, height } },
 *           edges: [{ source, target, points: [{ x, y }, ...] }],
 *           size: { width, height } }  (dimensions totales du graphe)
 */
import * as dagre from '@dagrejs/dagre'

const DEFAULTS = {
  // Mobile-first : flux vertical (TB), les ères en haut, le détail en bas.
  rankdir: 'TB',
  nodesep: 60,
  ranksep: 120,
  edgesep: 24,
  marginx: 40,
  marginy: 40,
}

self.onmessage = (event) => {
  const { token, nodes, edges, options } = event.data || {}
  try {
    const graph = new dagre.graphlib.Graph()
    graph.setGraph({ ...DEFAULTS, ...(options || {}) })
    graph.setDefaultEdgeLabel(() => ({}))
    for (const node of nodes) {
      graph.setNode(node.id, { width: node.width, height: node.height })
    }
    for (const edge of edges) {
      graph.setEdge(edge.source, edge.target)
    }
    dagre.layout(graph)

    const positions = {}
    for (const node of nodes) {
      const point = graph.node(node.id)
      positions[node.id] = {
        x: point.x,
        y: point.y,
        width: node.width,
        height: node.height,
      }
    }
    // Routing points de chaque arête (chemin des bords de boîte) : l'UI les
    // lisse en courbes de Bézier au lieu de tracer des segments droits.
    const edgeList = []
    for (const edge of graph.edges()) {
      const pts = (graph.edge(edge).points || [])
        .map((p) => ({ x: Math.round(p.x * 10) / 10, y: Math.round(p.y * 10) / 10 }))
      edgeList.push({ source: edge.v, target: edge.w, points: pts })
    }
    // Dimensions totales du graphe (source unique de vérité pour le <svg>).
    const bounds = graph.graph()
    const size = {
      width: Math.round(bounds.width || 0),
      height: Math.round(bounds.height || 0),
    }
    self.postMessage({ type: 'layout', token, positions, edges: edgeList, size })
  } catch (err) {
    self.postMessage({
      type: 'error',
      token,
      error: err && err.message ? String(err.message) : String(err),
    })
  }
}