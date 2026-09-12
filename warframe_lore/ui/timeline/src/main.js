import { createApp } from 'vue'

// Styles de base Vue Flow (thème sombre par nous-mêmes dans Timeline.vue).
// NB : le package @vue-flow/background embarque son CSS dans son JS (pas
// d'import *.css séparé).
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

import App from './App.vue'
import { router } from './router'
import './styles.css'

createApp(App).use(router).mount('#app')