import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Compile les SFC Vue du RAG Inspector vers warframe_lore/ui/static/inspector/
// (sert au Cephalon UI comme page autonome /inspector/).
export default defineConfig({
  plugins: [vue()],
  root: 'src',
  base: '/inspector/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Relatif à root (src) : warframe_lore/ui/inspector/src/../../static
    // = warframe_lore/ui/static/inspector (dossier servi par ApiHandler).
    outDir: '../../static/inspector',
    emptyOutDir: true,
  },
})