<script setup>
/**
 * CodexEntry — fiche Codex d'un nœud de la timeline.
 * Vues nommées depuis la timeline : ``router.push({ name: 'CodexEntry',
 * params: { id: node.codex_slug } })``. La source du corpus Codex s'intègre
 * en suivant le même contrat (slug -> entrée).
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const slug = computed(() => route.params.id || '')
</script>

<template>
  <div class="codex">
    <div class="codex-header">
      <span class="breadcrumb-sep">Fiche Codex</span>
      <router-link class="codex-back" :to="{ name: 'timeline' }">← Timeline</router-link>
    </div>
    <div class="codex-card">
      <div class="codex-slug">{{ slug }}</div>
      <h1 class="codex-title">Entrée du Codex</h1>
      <p class="codex-lead">
        La page détaillée de « {{ slug }} » sera alimentée par le corpus du
        Codex (en cours d'intégration). Le nœud est déjà lié depuis la timeline.
      </p>
    </div>
  </div>
</template>