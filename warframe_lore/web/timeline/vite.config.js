import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Compile les SFC Vue de la Timeline vers warframe_lore/web/static/timeline/
// (sert au Cephalon UI comme page autonome /timeline/).
export default defineConfig({
  plugins: [vue()],
  root: 'src',
  base: '/timeline/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Relatif à root (src) : warframe_lore/web/timeline/src/../../static
    // = warframe_lore/web/static/timeline (dossier servi par ApiHandler).
    outDir: '../../static/timeline',
    emptyOutDir: true,
  },
})