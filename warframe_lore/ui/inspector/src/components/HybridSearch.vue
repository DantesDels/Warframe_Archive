<script setup>
/**
 * HybridSearch : champ de recherche lié au « nouveau endpoint hybride » de
 * l'API (/v1/search, pgvector cosine + FTS PostgreSQL). Feedback visuel
 * réactif quand le middleware d'alias a été déclenché (chip « Alias actif »),
 * requête enrichie affichée, états chargement / erreur / vide, et liste de
 * cartes de chunks. `debug` (Mode Débogueur) est piloté par la sidebar — une
 * bascule active relance la recherche avec `debug=true`.
 */
import { ref, watch } from 'vue'

import { searchHybrid, RagApiError } from '../services/ragApi.js'
import RagDebugger from './RagDebugger.vue'
import SemanticResultCard from './SemanticResultCard.vue'

const props = defineProps({
  debug: { type: Boolean, default: false },
})

const query = ref('')
const busy = ref(false)
const error = ref('')
const result = ref(null)
const controller = ref(null)

const DEFAULT_LIMIT = 12

function cancelPending() {
  if (controller.value) controller.value.abort()
  controller.value = null
}

async function submit() {
  const q = query.value.trim()
  if (!q || busy.value) return
  cancelPending()
  busy.value = true
  error.value = ''
  controller.value = new AbortController()
  try {
    result.value = await searchHybrid(q, {
      limit: DEFAULT_LIMIT,
      debug: props.debug,
      signal: controller.value.signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') return
    result.value = null
    error.value = err instanceof RagApiError
      ? err.message
      : 'erreur inattendue lors de la recherche'
  } finally {
    controller.value = null
    busy.value = false
  }
}

function reset() {
  cancelPending()
  result.value = null
  error.value = ''
}

// Bascule du Mode Débogueur : relance la dernière recherche avec le flag
// debug (le payload LLM est frais, au prix d'un appel supplémentaire).
watch(() => props.debug, () => {
  if (result.value && !busy.value) submit()
})

defineExpose({ reset })
</script>

<template>
  <div class="search-area">
    <form class="hybrid-form" role="search" @submit.prevent="submit">
      <input
        v-model="query"
        class="hybrid-input"
        type="search"
        placeholder="Recherche sémantique hybride — ex. « Mercenaire d'Os »"
        autocomplete="off"
        spellcheck="false"
        aria-label="Requête de recherche hybride"
      />
      <button class="hybrid-submit" type="submit" :disabled="busy || !query.trim()">
        {{ busy ? 'Recherche…' : 'Rechercher' }}
      </button>
    </form>

    <div v-if="result && result.alias_active" class="alias-chips" role="status">
      <span class="alias-chip">⚡ Alias actif → {{ result.canonical }}</span>
      <span v-if="result.alias_note" class="alias-note">{{ result.alias_note }}</span>
    </div>

    <p
      v-if="result && result.search_question && result.search_question !== result.query"
      class="search-sub"
    >Requête réellement vectorisée : « {{ result.search_question }} »</p>

    <div v-if="busy" class="search-status">Recherche hybride en cours (cosine + FTS)…</div>

    <div v-if="error" class="search-error" role="alert">{{ error }}</div>

    <div v-if="result && !busy && !result.hits.length" class="search-empty">
      Aucun chunk restitué par les deux canaux pour cette requête.
    </div>

    <details v-if="result && result.debug" class="debug-global">
      <summary>Payload LLM complet (System Prompt + chunks)</summary>
      <RagDebugger :payload="result.debug" :terms="result.highlight_terms" />
    </details>

    <div v-if="result && result.hits.length" class="results">
      <SemanticResultCard
        v-for="hit in result.hits"
        :key="hit.chunk_id"
        :hit="hit"
        :terms="result.highlight_terms"
        :debug="debug"
        :payload="result.debug"
      />
      <div v-if="result.hits.length" class="results-count">
        {{ result.hits.length }} chunk{{ result.hits.length > 1 ? 's' : '' }}
      </div>
    </div>
  </div>
</template>