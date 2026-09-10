/* Magique isolée : tout accès réseau à l'API ENGRAM vit ici.
 * Les composants ne connaissent ni l'URL, ni le fetch, ni le parsing —
 * ils appellent des fonctions et reçoivent des promesses.
 */
export class RagApiError extends Error {
  constructor(message, options) {
    super(message, options)
    this.name = 'RagApiError'
  }
}

// Défaut : LM Studio / ENGRAM tournent en local sur 8000.
const DEFAULT_BASE = 'http://127.0.0.1:8000'

function baseUrl() {
  return (import.meta.env.VITE_ENGRAM_BASE || DEFAULT_BASE).replace(/\/$/, '')
}

/**
 * Recherche hybride (pgvector cosine + FTS PostgreSQL).
 * @returns {Promise<object>} payload du endpoint /v1/search
 */
export async function searchHybrid(query, { limit = 12, debug = false, signal } = {}) {
  const params = new URLSearchParams({ q: query, limit: String(limit), debug: String(debug) })
  let response
  try {
    response = await fetch(`${baseUrl()}/v1/search?${params}`, { signal })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new RagApiError(
      `API ENGRAM injoignable (${baseUrl()}) — vérifier ` + 
      '`uvicorn warframe_lore.engram.api.main:app`', { cause: err })
  }
  if (!response.ok) {
    throw new RagApiError(`recherche refusée par l'API (HTTP ${response.status})`)
  }
  try {
    return await response.json()
  } catch (err) {
    throw new RagApiError('réponse illisible de l\'API (JSON invalide)', { cause: err })
  }
}

/** Liste des buckets de l'archive (nav latérale) — servie par le même origin. */
export async function fetchBuckets() {
  let response
  try {
    response = await fetch('/api/buckets')
  } catch (err) {
    throw new RagApiError('les buckets de l\'archive sont indisponibles', { cause: err })
  }
  if (!response.ok) throw new RagApiError(`buckets refusés (HTTP ${response.status})`)
  return response.json()
}