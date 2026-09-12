<script setup>
/**
 * Timeline.vue — Timeline interactive du Cephalon Oracle.
 *
 * EMPILEMENT : ELK.js (layout `layered`, DOWN, INCLUDE_CHILDREN, via
 * src/lib/elk.js) surchargé par Vue Flow pour le rendu interactif :
 *   - les CLUSTERS (issus d'Obsidian : `cluster` / dossiers) deviennent des
 *     Compound Nodes (cadres "Guerre Ancienne", "1999", …) ;
 *   - les ENTITÉS (relations yaml `relations`) sont des cartes cliquables
 *     (codex_slug → fiche Codex) ;
 *   - les ARÊTES sont custom : trait plein pour `lien_chronologique`,
 *     pointillés animés pour `lien_paradoxal`, puce ambre pour les liens
 *     RECONNEXION CAUSALE (A → B → C, B masqué ⇒ A → C synthétique).
 *
 * Le calcul du graphe visible + la reconnexion vivent dans
 * `composables/useTimeline.js` (fourni par inject → boutons ✕ des nœuds).
 * Le layout ELK est lancé en promise (debounce 60 ms) ; l'UI ne bloque pas.
 */
import { inject, nextTick, onMounted, provide, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Background, BackgroundVariant } from '@vue-flow/background'
import {
  Handle,
  MarkerType,
  Position,
  VueFlow,
  useVueFlow,
} from '@vue-flow/core'

import { TIMELINE_KEY, useTimeline } from './composables/useTimeline'

const router = useRouter()
const source = import.meta.env.BASE_URL + 'graph.json'
const tl = useTimeline({ source })
provide(TIMELINE_KEY, tl)

// Déclenche le chargement du graphe une fois le composant monté (fetch de
// graph.json puis calcul du layout ELK).
onMounted(() => tl.load())

const { fitView, zoomIn, zoomOut } = useVueFlow()

const didInit = ref(false)
watch(tl.flowNodes, async (nodes) => {
  // Premier layout réussi : centrer une seule fois (les interactions
  // ultérieures ne sautent pas, le cache FLOW_EDITOR_USER est respecté).
  if (!nodes.length || didInit.value) return
  didInit.value = true
  await nextTick()
  fitView({ padding: 0.15, duration: 400 })
})

watch(tl.error, (err) => { if (err) console.warn('[Timeline]', err) })

function onNodeClick({ node }) {
  if (node.data.codex_slug) {
    router.push({ name: 'CodexEntry', params: { id: node.data.codex_slug } })
  }
}

/* ------------------------------------------------------- path (ELK puis Bézier) */
function edgePath(e) {
  if (e.data.points && e.data.points.length >= 2) {
    return e.data.points.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ')
  }
  const sx = e.sourceX
  const sy = e.sourceY
  const tx = e.targetX
  const ty = e.targetY
  const mx = (sx + tx) / 2
  return `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}`
}

function edgeClass(e) {
  if (e.data.reconnected) return 'wf-edge wf-edge--re'
  if (e.data.linkedType === 'lien_paradoxal') return 'wf-edge wf-edge--paradox'
  return 'wf-edge wf-edge--chrono'
}

function edgeLabelPos(e) {
  return { left: `${(e.sourceX + e.targetX) / 2}px`, top: `${(e.sourceY + e.targetY) / 2}px` }
}
</script>

<template>
  <div class="tl">
    <div class="tl-toolbar">
      <button class="tl-btn" type="button" title="Zoomer" @click="zoomIn()">＋</button>
      <button class="tl-btn" type="button" title="Dézoomer" @click="zoomOut()">−</button>
      <button class="tl-btn" type="button" title="Recentrer le graphe" @click="fitView({ padding: 0.15, duration: 400 })">⟲</button>
      <button class="tl-btn" type="button" title="Tout afficher" :disabled="tl.hiddenCount === 0" @click="tl.showAll()">◉</button>

      <span class="tl-count">{{ tl.visibleCount }} nœuds</span>
      <span v-if="tl.hiddenCount" class="tl-muted">{{ tl.hiddenCount }} masqués</span>
      <span v-if="tl.reconnectedCount" class="tl-re" title="Liens synthétiques (cohérence diégétique)">⚡ {{ tl.reconnectedCount }} reconnexions</span>
    </div>

    <div v-if="tl.error" class="tl-error" role="alert">
      {{ tl.error }} — lancez d'abord <code>node scripts/extractor.js</code> puis rebuild.
    </div>
    <div v-else-if="tl.loading && !tl.visibleCount" class="tl-caption">Chargement du graphe…</div>

    <div class="tl-flow">
      <VueFlow
        :nodes="tl.flowNodes"
        :edges="tl.flowEdges"
        :min-zoom="0.2"
        :max-zoom="2.5"
        :nodes-draggable="false"
        :nodes-connectable="false"
        :edges-updatable="false"
        :delete-key-code="null"
        :only-render-visible-elements="true"
        @node-click="onNodeClick"
      >
        <!-- Compound Node : cluster (ère / dossier Obsidian) -->
        <template #node-cluster="{ data }">
          <div class="wf-cluster">
            <div class="wf-cluster-head">
              <span class="wf-cluster-label">{{ data.label }}</span>
              <button
                class="wf-btn"
                type="button"
                :title="tl.hidden.has(data.id) ? 'Réafficher' : 'Masquer ce cluster et ses membres'"
                @click.stop="tl.toggleHidden(data.id)"
              >{{ tl.hidden.has(data.id) ? '⏻' : '✕' }}</button>
            </div>
          </div>
        </template>

        <!-- Carte entité : label, année, aperçu, navigation Codex -->
        <template #node-entity="{ data }">
          <div class="wf-entity" :class="{ 'wf-entity--codex': data.codex_slug }">
            <div class="wf-entity-label">{{ data.label }}</div>
            <div v-if="data.year" class="wf-entity-year">{{ data.year }}</div>
            <div v-if="data.note" class="wf-entity-note">{{ data.note }}</div>
            <button class="wf-btn wf-btn--hide" type="button" title="Masquer cet élément" @click.stop="tl.toggleHidden(data.id)">✕</button>
          </div>
          <Handle type="target" :position="Position.Top" />
          <Handle type="source" :position="Position.Bottom" />
        </template>

        <!-- Arête : chronologique (plein) / paradoxale (pointillés animés) / reconnexion -->
        <template #edge-timeline="{ sourceX, sourceY, targetX, targetY, data, id }">
          <path
            :id="`e-${id}`"
            :class="edgeClass({ sourceX, sourceY, targetX, targetY, data })"
            :d="edgePath({ sourceX, sourceY, targetX, targetY, data })"
            fill="none"
            :marker-end="MarkerType.ArrowClosed"
          >
            <title>{{ data.reconnected ? 'Connexion reconstituée (élément intermédiaire masqué)' : (data.label || data.linkedType) }}</title>
          </path>
          <div
            v-if="data.label"
            class="wf-edge-label"
            :style="edgeLabelPos({ sourceX, sourceY, targetX, targetY })"
          >{{ data.label }}</div>
        </template>

        <Background :variant="BackgroundVariant.Dots" :gap="24" :size="1.6" :pattern-color="'#3a4456'" />
      </VueFlow>
    </div>

    <p class="tl-legend">
      ▲ Masquer un élément recâble la causalité (A → B → C, B masqué ⇒ liaison
      A → C conservée). Masquer un cluster masque ses membres.
    </p>
  </div>
</template>

<style scoped>
.tl {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: #10141c;
}

.tl-flow {
  flex: 1;
  min-height: 0;
  position: relative;
}

.tl-toolbar {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  padding: 8px 12px;
  border-bottom: 1px solid #1d2430;
  background: #141a25;
}

.tl-btn {
  font: inherit;
  color: #dfe6f2;
  background: #1f2736;
  border: 1px solid #2c3648;
  border-radius: 5px;
  padding: 4px 9px;
  cursor: pointer;
}

.tl-btn:hover { background: #2a3547; }
.tl-btn:disabled { opacity: 0.4; cursor: default; }

.tl-count { margin-left: 8px; color: #aab6c8; font-size: 12px; }
.tl-muted { color: #6e7b90; font-size: 12px; }
.tl-re { color: #f2b04c; font-size: 12px; }

.tl-legend {
  position: absolute;
  left: 12px;
  bottom: 8px;
  z-index: 20;
  max-width: 480px;
  margin: 0;
  color: #64707f;
  font-size: 11px;
  line-height: 1.5;
  background: rgba(16, 20, 28, 0.82);
  padding: 5px 9px;
  border-radius: 6px;
  border: 1px solid #1d2430;
  pointer-events: none;
}

.tl-error {
  color: #ff6b6b;
  background: #2a1418;
  border: 1px solid #6b2424;
  border-radius: 6px;
  margin: 10px 12px 0;
  padding: 8px 12px;
  font-size: 13px;
}

.tl-caption {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #8b99ad;
  font-size: 14px;
  pointer-events: none;
  z-index: 5;
}

/* --------------------------------------------------------- nœud CLUSTER (composé) */
.wf-cluster {
  position: relative;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  background: rgba(29, 36, 48, 0.35);
  border: 1px solid #3d4961;
  border-radius: 12px;
}

.wf-cluster-head {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 4px 8px 4px 12px;
  background: linear-gradient(180deg, rgba(47, 59, 79, 0.9), rgba(47, 59, 79, 0.25));
  border-bottom: 1px solid #3d4961;
  border-radius: 12px 12px 0 0;
}

.wf-cluster-label {
  font-size: 12px;
  font-weight: 700;
  color: #c7d2e4;
  letter-spacing: 2px;
  text-transform: uppercase;
}

/* --------------------------------------------------------------- carte ENTITÉ */
.wf-entity {
  position: relative;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  padding: 10px 12px;
  background: #1d2838;
  border: 1px solid #33415c;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
}

.wf-entity--codex { cursor: pointer; }
.wf-entity--codex:hover { border-color: #7aa0d9; background: #21304a; }

.wf-entity-label {
  font-size: 13px;
  font-weight: 600;
  color: #e8eefb;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wf-entity-year {
  font-size: 11px;
  color: #8fb3e8;
  letter-spacing: 1px;
}

.wf-entity-note {
  font-size: 10px;
  color: #8592a8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wf-btn {
  position: absolute;
  top: 5px;
  right: 5px;
  font-size: 10px;
  line-height: 1;
  color: #9fb0c9;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid #3d4961;
  border-radius: 4px;
  padding: 3px 5px;
  cursor: pointer;
  opacity: 0.75;
}

.wf-btn:hover { opacity: 1; color: #ffd08a; }

/* ------------------------------------------------------------- arêtes custom */
.wf-edge {
  stroke-width: 1.8;
  fill: none;
}

.wf-edge--chrono {
  stroke: #5f7ea3;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.wf-edge--paradox {
  stroke: #b06ee8;
  stroke-linejoin: round;
  stroke-linecap: round;
  stroke-dasharray: 7 5;
  animation: wf-dash 1.4s linear infinite;
}

.wf-edge--re {
  stroke: #f2b04c;
  stroke-linejoin: round;
  stroke-linecap: round;
  stroke-dasharray: 3 5;
}

.wf-edge-label {
  position: absolute;
  transform: translate(-50%, -50%);
  z-index: 2;
  font-size: 10px;
  color: #a9b6ca;
  background: rgba(16, 20, 28, 0.8);
  border: 1px solid #2a3444;
  border-radius: 4px;
  padding: 1px 6px;
  pointer-events: none;
  white-space: nowrap;
}

:global(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: #33415c;
  border: 1px solid #5f7ea3;
}

@keyframes wf-dash {
  to { stroke-dashoffset: -24; }
}
</style>