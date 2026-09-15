/* Surlignage « termes exacts » sans jamais injecter de HTML brut :
 * le texte est d'abord échappé, puis les termes sont enroulés dans <mark>.
 * Aucune balise du corpus ne traverse (= pas d'XSS via le scraper wiki).
 * Les <b> émis par ts_headline sont volontairement ignorés : le surlignage
 * est entièrement rejoué côté client, à partir de highlight_terms.
 */
const HTML_ESCAPE = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

export function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => HTML_ESCAPE[c])
}

function escapeRegex(term) {
  return term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * @param {string} text
 * @param {string[]} terms termes exacts à mettre en évidence
 * @returns {string} HTML sûr pour v-html
 */
export function highlightTerms(text, terms) {
  const safe = escapeHtml(text)
  const kept = (terms || [])
    .filter((t) => typeof t === 'string' && /[\w\u00C0-\u017F]{3}/u.test(t))
    .sort((a, b) => b.length - a.length)
  if (!kept.length) return safe
  const pattern = new RegExp(`(${kept.map(escapeRegex).join('|')})`, 'gi')
  return safe.replace(pattern, '<mark>$1</mark>')
}