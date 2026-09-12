import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Compile les SFC Vue de la Timeline vers warframe_lore/ui/static/timeline/
// (sert au Cephalon UI comme page autonome /timeline/).
export default defineConfig({
  plugins: [vue()],
  root: 'src',
  base: '/timeline/',
  // Le graphe généré par scripts/extractor.js vit dans data/timeline
  // (racine du projet) : déclaré comme "public dir" → servi en dev et copié
  // tel quel dans static/timeline/graph.json au build (pas de copie manuelle).
  publicDir: fileURLToPath(new URL('../../../data/timeline', import.meta.url)),
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Relatif à root (src) : warframe_lore/ui/timeline/src/../../static
    // = warframe_lore/ui/static/timeline (dossier servi par ApiHandler).
    outDir: '../../static/timeline',
    emptyOutDir: true,
  },
})