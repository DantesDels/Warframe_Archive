<script setup>
/**
 * Carte d'un chunk sémantique (remplace l'affichage page monolithique).
 *   • header `[Titre de Page] › [Titre de Section]`;
 *   • badges de score par canal (Cosine vert > 0.7, Orange > 0.4);
 *   • snippet plein texte hautes-lumières (termes exacts > 0.7 valeur);
 *   • contenu complet + grille de métadonnées sur dépliage;
 *   • volet débogueur extensible par résultat quand le mode est actif.
 */
import { computed, ref } from 'vue'

import { highlightTerms } from '../utils/highlight.js'
import MetadataTable from './MetadataTable.vue'
import RagDebugger from './RagDebugger.vue'

const props = defineProps({
  hit: { type: Object, required: true },
  terms: { type: Array, default: () => [] },
  debug: { type: Boolean, default: false },
  payload: { type: Object, default: null },
})

const expanded = ref(false)
const debugOpen = ref(false)

function formatScore(value) {
  if (value === null || value === undefined) return '—'
  return value.toFixed(2)
}

function badgeClass(value) {
  if (value === null || value === undefined) return ''
  if (value >= 0.7) return 'hi'     // confiance élevée (vert)
  if (value >= 0.4) return 'mid'    // confiance moyenne (orange)
  return 'lo'                       // faible (gris)
}

const hasSnippet = computed(() => {
  const headline = (props.hit.headline || '').trim()
  return headline.length > 0
})

const snippetHtml = computed(() => {
  if (hasSnippet.value) return highlightTerms(props.hit.headline, props.terms)
  return highlightTerms(props.hit.content.slice(0, 240) + '…', props.terms)
})

const contentHtml = computed(() => highlightTerms(props.hit.content, props.terms))

/** Surligne le chunk dans le contexte du payload (audit par résultat). */
const focusInPayload = computed(() => {
  return props.hit.content.replace(/\s+/g, ' ').slice(0, 70)
})
</script>

<template>
  <article class="result-card">
    <header class="result-head">
      <div class="result-crumbs">
        <span class="result-page">{{ hit.page_title }}</span>
        <span v-if="hit.section" class="result-sep">›</span>
        <span v-if="hit.section" class="result-section">{{ hit.section }}</span>
      </div>
      <div class="result-badges">
        <span
          v-if="hit.cosine_score !== null && hit.cosine_score !== undefined"
          class="score-badge"
          :class="badgeClass(hit.cosine_score)"
          title="Similarité sémantique (pgvector cosine)"
        >Cosine {{ formatScore(hit.cosine_score) }}</span>
        <span
          v-if="hit.ts_score !== null && hit.ts_score !== undefined"
          class="score-badge"
          :class="badgeClass(hit.ts_score)"
          title="Rang plein texte (PostgreSQL ts_rank, normalisé)"
        >TSVector {{ formatScore(hit.ts_score) }}</span>
        <button
          class="result-expand"
          type="button"
          :aria-expanded="String(expanded)"
          @click="expanded = !expanded"
        >{{ expanded ? 'Réduire' : 'Détail' }}</button>
      </div>
    </header>

    <div class="result-snippet" v-html="snippetHtml"></div>

    <div v-if="expanded" class="result-content" v-html="contentHtml"></div>
    <div v-if="expanded">
      <MetadataTable :metadata="hit.metadata" />
    </div>

    <div v-if="debug && payload" class="result-debug">
      <button
        class="debug-toggle-btn"
        type="button"
        @click="debugOpen = !debugOpen"
      >{{ debugOpen ? '▾ Masquer' : '▸ Voir' }} le payload LLM — chunk {{ hit.chunk_id }}</button>
      <RagDebugger
        v-if="debugOpen"
        :payload="payload"
        :terms="terms"
        :focus="focusInPayload"
      />
    </div>
  </article>
</template>