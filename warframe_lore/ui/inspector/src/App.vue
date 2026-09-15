<script setup>
/**
 * RAG Inspector — page autonome du Cephalon Archive.
 * Sidebar fidèle à l'interface principale : brand, retour à l'archive,
 * buckets, et le toggle « Mode Débogueur » placé SOUS la section Buckets.
 */
import { onMounted, onUnmounted, ref } from 'vue'

import HybridSearch from './components/HybridSearch.vue'
import { fetchBuckets, RagApiError } from './services/ragApi.js'

const debugMode = ref(false)
const buckets = ref([])
const bucketsError = ref('')
const bucketsLoading = ref(true)

// Drawer mobile : la topbar (burger) le pilote, la sidebar glisse par-dessus
// le contenu et le voile cliquable / Échap la referment.
const menuOpen = ref(false)
const onKeydown = (event) => {
  if (event.key === 'Escape') menuOpen.value = false
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

onMounted(async () => {
  try {
    buckets.value = await fetchBuckets()
  } catch (err) {
    bucketsError.value = err instanceof RagApiError
      ? err.message
      : 'Buckets indisponibles'
  } finally {
    bucketsLoading.value = false
  }
})
</script>

<template>
  <div class="app" :class="{ 'sidebar-open': menuOpen }">
    <aside id="sidebar">
      <div class="brand">
        <div class="brand-logo">CA</div>
        <div>
          <div class="brand-title">Cephalon Archive</div>
          <div class="brand-sub">Warframe Lore · RAG Inspector</div>
        </div>
      </div>

      <nav>
        <a class="nav-item" href="/">
          <span class="nav-icon">◈</span> Vue d'ensemble
        </a>
        <span class="nav-item active" aria-current="page">
          <span class="nav-icon">🔍</span> RAG Inspector
        </span>
        <div class="nav-section">Buckets</div>
      </nav>

      <div v-if="bucketsLoading" class="bucket-nav">
        <span class="bucket-nav-item">Chargement…</span>
      </div>
      <div v-else-if="bucketsError" class="bucket-nav">
        <span class="bucket-nav-item">{{ bucketsError }}</span>
      </div>
      <a
        v-else
        v-for="bucket in buckets"
        :key="bucket.id"
        class="bucket-nav-item"
        :href="`/`"
        :title="bucket.title"
      >
        <span>{{ bucket.title }}</span>
        <span class="bucket-count">{{ bucket.total_pages }}</span>
      </a>

      <button
        class="nav-item debug-toggle"
        :class="{ active: debugMode }"
        type="button"
        :aria-pressed="String(debugMode)"
        @click="debugMode = !debugMode"
      >
        <span class="nav-icon">🧪</span> Mode Débogueur
      </button>
      <p v-if="debugMode" class="debug-hint">
        Chaque résultat expose le payload JSON exact prêt à être envoyé au
        LLM (System Prompt formaté + chunks concaténés) : audit des fuites
        de contexte.
      </p>
    </aside>

    <main id="content">
      <header id="topbar">
        <button
          id="btn-menu"
          type="button"
          aria-label="Ouvrir le menu"
          aria-controls="sidebar"
          :aria-expanded="String(menuOpen)"
          @click="menuOpen = !menuOpen"
        >☰</button>
        <div id="breadcrumb">
          <span class="crumb">Cephalon Archive</span>
          <span class="crumb-sep">›</span>
          <span class="crumb current">RAG Inspector</span>
        </div>
        <span class="topbar-hint">Recherche hybride · cosine + Full-Text PostgreSQL</span>
      </header>

      <section class="view">
        <h1 class="view-title">Recherche sémantique hybride</h1>
        <p class="view-sub">
          Les chunks restitués (page › section) avec leurs scores par canal,
          leurs métadonnées et le payload LLM exact pour audit.
        </p>
        <HybridSearch :debug="debugMode" />
      </section>
    </main>

    <div id="sidebar-backdrop" @click="menuOpen = false"></div>
  </div>
</template>