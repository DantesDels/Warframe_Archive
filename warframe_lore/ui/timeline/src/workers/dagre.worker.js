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
 *   out : { type: "layout", token, positions: { id: { x, y, width, height } } }
 */
import * as dagre from '@dagrejs/dagre'

const DEFAULTS = {
  rankdir: 'LR',
  nodesep: 44,
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
    self.postMessage({ type: 'layout', token, positions })
  } catch (err) {
    self.postMessage({
      type: 'error',
      token,
      error: err && err.message ? String(err.message) : String(err),
    })
  }
}