<script setup>
/**
 * Timeline — page autonome du Cephalon Archive.
 * Chrome fidèle à l'archive (sidebar brand + liens), drawer mobile.
 */
import { onMounted, onUnmounted, ref } from 'vue'

import Timeline from './Timeline.vue'

const menuOpen = ref(false)
const onKeydown = (event) => {
  if (event.key === 'Escape') menuOpen.value = false
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="app" :class="{ 'sidebar-open': menuOpen }">
    <aside id="sidebar">
      <div class="brand">
        <div class="brand-logo">CA</div>
        <div>
          <div class="brand-title">Cephalon Archive</div>
          <div class="brand-sub">Warframe Lore · Timeline</div>
        </div>
      </div>

      <nav>
        <a class="nav-item" href="/">
          <span class="nav-icon">◈</span> Vue d'ensemble
        </a>
        <a class="nav-item" href="/inspector/">
          <span class="nav-icon">🔍</span> RAG Inspector
        </a>
        <span class="nav-item active" aria-current="page">
          <span class="nav-icon">✦</span> Timeline
        </span>
        <div class="nav-section">Navigation</div>
      </nav>
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
          <span class="crumb current">Timeline</span>
        </div>
        <span class="topbar-hint">Éternisme · ères, quêtes, fragments</span>
      </header>

      <Timeline />
    </main>

    <div id="sidebar-backdrop" @click="menuOpen = false"></div>
  </div>
</template>