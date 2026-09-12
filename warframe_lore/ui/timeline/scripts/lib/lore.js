/**
 * lib/lore.js — utilitaires partagés du pipeline Archive (seeder + extractor).
 *
 * Source unique (DRY) des règles de nommage et du contrat relationnel :
 *   slugify        → dossiers de cluster / ids (même règle côté note et graphe)
 *   relationType   → toute mention de "paradox" devient lien_paradoxal (trait
 *                    pointillé animé côté UI), sinon lien_chronologique
 *   markdownOf     → note Obsidian (Frontmatter + H1 + contenu) fidèle au
 *                    contrat d'extraction
 *
 * Chemins racines (cote projets partagée par les deux scripts) :
 *   data/seed      → sources JSON (1 fichier par lot, chargés triés)
 *   data/vault     → coffre Obsidian généré (sortie dérivée)
 */
import { fileURLToPath } from 'node:url'
import { join, resolve } from 'node:path'

export const SCRIPT_DIR = fileURLToPath(new URL('.', import.meta.url))
export const PACKAGE_DIR = resolve(SCRIPT_DIR, '..')
export const REPO_DIR = resolve(PACKAGE_DIR, '..', '..', '..', '..')
export const DATA_DIR = join(REPO_DIR, 'data')
export const SEED_DIR = join(DATA_DIR, 'seed')
export const VAULT_DIR = join(DATA_DIR, 'vault')

/** slug stable : minuscule, sans accents, alnum reliés par des tirets. */
export function slugify(value) {
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'sans-nom'
}

export const TYPE_PARADOX = 'lien_paradoxal'
export const TYPE_CHRONO = 'lien_chronologique'

/** Normalise le type relationnel : toute évocation de paradoxalité (trait
 *  pointillé animé côté UI), sinon chronologique (trait plein). */
export function relationType(typeRaw) {
  const type = String(typeRaw || '')
    .toLowerCase()
    .replace(/[-\s]+/g, '_')
  return /paradox/.test(type) ? TYPE_PARADOX : TYPE_CHRONO
}

/** Frontmatter YAML fidèle au contrat extractor.js. */
function frontmatter(entry) {
  const lines = ['---', `id: ${entry.id}`, `label: ${JSON.stringify(entry.titre)}`, `kind: ${entry.kind || 'entity'}`]
  if (entry.year) lines.push(`year: ${JSON.stringify(String(entry.year))}`)
  lines.push(`cluster: ${JSON.stringify(entry.cluster)}`)
  if (entry.relations && entry.relations.length) {
    lines.push('relations:')
    for (const rel of entry.relations) {
      lines.push(`  - cible: ${rel.cible}`, `    type: ${rel.type}`)
    }
  }
  lines.push('---')
  return lines.join('\n')
}

/** Note Obsidian complète (markdown + frontmatter) pour une entrée. */
export function markdownOf(entry) {
  return `${frontmatter(entry)}\n# ${entry.titre}\n\n${String(entry.contenu).trim()}\n`
}