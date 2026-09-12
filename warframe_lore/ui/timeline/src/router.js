/**
 * Timeline (Cephalon Archive) — routage léger en historique de hash.
 *
 * Le build est servi sous ``/timeline/`` : ``createWebHashHistory`` garde les
 * liens réutilisables sans dépendre de la config de routes du serveur.
 *   - ``#/``                    la timeline causale
 *   - ``#/codex/:id``           fiche Codex (codex_slug d'un nœud)
 */
import { createRouter, createWebHashHistory } from 'vue-router'

import CodexEntry from './CodexEntry.vue'
import Timeline from './Timeline.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'timeline', component: Timeline },
    { path: '/codex/:id', name: 'CodexEntry', component: CodexEntry },
  ],
})