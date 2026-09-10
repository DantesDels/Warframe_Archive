<script setup>
/**
 * RAG Debugger : révèle le payload JSON exact qui serait envoyé au LLM
 * (audit de fuite de contexte). Trois blocs : System Prompt formaté,
 * contexte concaténé (chunks), messages OpenAI prêts à envoyer — plus un
 * bouton copier le JSON brut.
 *
 * Props:
 *   payload  — objet renvoyé par /v1/search?debug=true (system/context/messages)
 *   terms    — termes de surlignage (mise en évidence dans le contexte)
 *   focus    — extrait de texte présent dans `context` à marquer (volet par chunk)
 */
import { computed, ref } from 'vue'

import { escapeHtml, highlightTerms } from '../utils/highlight.js'

const props = defineProps({
  payload: { type: Object, default: null },
  terms: { type: Array, default: () => [] },
  focus: { type: String, default: '' },
})

const copied = ref(false)
const copyTimer = ref(null)

const contextHtml = computed(() => {
  const context = (props.payload && props.payload.context) || ''
  let html = highlightTerms(context, props.terms)
  if (props.focus) {
    const safeFocus = escapeHtml(props.focus)
    html = html.replace(safeFocus, `<b>${safeFocus}</b>`)
  }
  return html
})

const messagesJson = computed(() => {
  if (!props.payload) return ''
  return JSON.stringify(props.payload.messages || [], null, 2)
})

function copyPayload() {
  if (!props.payload) return
  const json = JSON.stringify(props.payload, null, 2)
  navigator.clipboard?.writeText(json).then(() => {
    copied.value = true
    clearTimeout(copyTimer.value)
    copyTimer.value = setTimeout(() => (copied.value = false), 1500)
  })
}
</script>

<template>
  <div v-if="payload" class="debug-panel">
    <div class="debug-head">
      <span class="debug-title">PAYLOAD LLM — audit de contexte</span>
      <span v-if="copied" class="debug-copied">Copié ✓</span>
      <button class="debug-copy" type="button" @click="copyPayload">
        Copier le JSON
      </button>
    </div>

    <div class="debug-block">
      <div class="debug-block-label">System Prompt formaté</div>
      <pre class="debug-pre">{{ payload.system }}</pre>
    </div>

    <div class="debug-block">
      <div class="debug-block-label">Context (chunks concaténés)</div>
      <div class="debug-pre" v-html="contextHtml"></div>
      <div v-if="focus" class="debug-focus">
        🎯 Chunk ciblé dans le contexte ci-dessus (surbrillance <b>bleue</b>).
      </div>
    </div>

    <div class="debug-block">
      <div class="debug-block-label">Messages OpenAI (JSON)</div>
      <pre class="debug-pre debug-json">{{ messagesJson }}</pre>
    </div>
  </div>
</template>