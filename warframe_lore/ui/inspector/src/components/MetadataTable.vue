<script setup>
/**
 * Rendu dynamique des infoboxes : parse le dict JSON `metadata` (JSONB des
 * lore_chunks) en grille minimale clé → valeur, visuellement séparée du
 * texte narratif. `page_title` / `section` / `content` sont portés par la
 * carte (header), pas répétés ici.
 */
import { computed } from 'vue'

const props = defineProps({
  metadata: { type: Object, default: () => ({}) },
})

const SKIPPED_KEYS = new Set(['page_title', 'section', 'content_markdown'])

const LABELS = {
  'Header 1': 'Titre de page (H1)',
  'Header 2': 'Section (H2)',
  'Header 3': 'Sous-section (H3)',
  'Header 4': 'H4',
  speakers: 'Locuteurs',
}

function fmt(value) {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const rows = computed(() => {
  const entries = Object.entries(props.metadata)
    .filter(([key, value]) => {
      if (SKIPPED_KEYS.has(key)) return false
      if (value === null || value === undefined) return false
      if (typeof value === 'string' && !value.trim()) return false
      return true
    })
  return entries.map(([key, value]) => ({
    label: LABELS[key] || key,
    value: fmt(value),
  }))
})
</script>

<template>
  <dl v-if="rows.length" class="metadata-table" aria-label="Métadonnées du chunk">
    <template v-for="row in rows" :key="row.label">
      <dt class="metadata-key">{{ row.label }}</dt>
      <dd class="metadata-value">{{ row.value }}</dd>
    </template>
  </dl>
</template>