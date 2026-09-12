/**
 * seedVault.js — archive suprême du Cephalon : générateur du coffre Obsidian.
 *
 * Construit data/vault/ (Markdown + YAML Frontmatter) depuis les sources JSON
 * de data/seed/ (1 fichier par lot, chargés par ordre alphabétique → ordre
 * stable et reproductible). Ajouter un lot = poser un fichier .json, aucune
 * ligne de code à changer (principe OCP).
 *
 *   lot01-empire-orokin.json               — L'Empire · le Néant · Cephalons · Dax · Concepts
 *   lot02-antagonistes-factions.json       — Leaders & factions ennemies (Corpus · Grineer · Sentients)
 *   lot03-syndicats.json                   — Syndicats & factions secondaires
 *   lot04-hubs-et-civils.json              — Hubs · collectifs · civils
 *   lot05-hex-1999.json                    — Hex · Protoframes · Technocyte 1999
 *   lot06-deimos.json                      — Faction Entrati · Deimos · Arkinis
 *   lot07-zariman.json                     — Zariman · Holdfasts · Cavalero
 *   lot08-duviri.json                      — Duviri · Paradoxe · Orowyrms
 *   lot09-bosses-creatures.json            — Boss & créatures (Grineer · Corpus · Sentients · Infestés)
 *   lot10-warframes-a.json · lot11-warframes-b.json — Warframes (59, réparties A/B)
 *
 * Contrat objet (chaque entrée JSON) :
 *   id         identifiant stable, unique, sans espaces (cible des relations)
 *   titre      intitulé affiché (→ label / H1 de la note)
 *   kind       character | event | era | faction | quest | lieu | concept | …
 *   year       étiquette temporelle libre (facultatif)
 *   cluster    nom du Compound Node (dossier de destination = slugify)
 *   relations  [{ cible: "id", type: "lien_sémantique" }]
 *              type est SEMANTIQUE : l'extracteur déduit
 *              lien_paradoxal ssi /paradox/ est contenu, sinon lien_chronologique.
 *   contenu    texte intégral de la note (¶ séparées par des lignes vides).
 *
 * Le seeder RAZ complet de data/vault puis régénère les fichiers : l'archive
 * est une sortie dérivée (reproductible). Les doublons exacts de relations
 * sont éliminés avec avertissement ; les relations vers des ids futurs (lots
 * suivants) sont conservées au YAML — l'extracteur les résout quand la cible
 * apparaît — et affichées en avertissement ici.
 *
 * Usage (racine du projet) :
 *   node warframe_lore/ui/timeline/scripts/seedVault.js
 *   node warframe_lore/ui/timeline/scripts/extractor.js        → graph.json
 */
import { mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { SEED_DIR, VAULT_DIR, markdownOf, slugify } from './lib/lore.js'

const IS_MAIN = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]

const OUTPUT_FIELDS = ['id', 'titre', 'kind', 'year', 'cluster']

/** Conserve uniquement les champs attendus (schéma minimal, tolérant en écriture).
 *  Le type relationnel reste sémantique tel quel — c'est l'extracteur qui
 *  déduit lien_paradoxal / lien_chronologique à la lecture. */
function sanitize(entry) {
  const clean = {}
  for (const field of OUTPUT_FIELDS) {
    if (entry[field] !== undefined) clean[field] = entry[field]
  }
  clean.relations = (entry.relations || [])
    .filter((rel) => typeof rel === 'object' && rel !== null && String(rel.cible || '').trim())
    .map((rel) => ({ cible: String(rel.cible).trim(), type: String(rel.type || '') }))
  clean.contenu = String(entry.contenu || '').trim()
  return clean
}

/** Charge les sources JSON de data/seed/ (triées) et dédoublonne les relations. */
export async function loadDatabase(seedDir = SEED_DIR) {
  const files = (await readdir(seedDir)).filter((name) => name.endsWith('.json')).sort()
  const warnings = []
  const database = []

  for (const file of files) {
    const entries = JSON.parse(await readFile(join(seedDir, file), 'utf8'))
    for (const raw of entries) {
      const entry = sanitize(raw)
      const seen = new Map()
      entry.relations = entry.relations.filter((rel) => {
        const key = `${rel.cible}\u0000${rel.type}`
        if (seen.has(key)) {
          warnings.push(`${file}: relation doublon supprimée sur ${entry.id} → ${rel.cible} (${rel.type})`)
          return false
        }
        seen.set(key, true)
        return true
      })
      database.push(entry)
    }
  }
  return { database, warnings }
}

/** Contrôles d'intégrité : ids dupliqués, relations réflexives, cibles absentes. */
export function audit(database) {
  const ids = new Set()
  const problems = []
  const dangling = new Set()
  const allIds = new Set(database.map((entry) => entry.id))
  for (const entry of database) {
    if (ids.has(entry.id)) problems.push(`id dupliqué : ${entry.id}`)
    ids.add(entry.id)
    for (const rel of entry.relations || []) {
      if (rel.cible === entry.id) problems.push(`${entry.id} : relation réflexive vers ${rel.cible}`)
      if (!allIds.has(rel.cible)) dangling.add(rel.cible)
    }
  }
  return { problems, dangling }
}

async function main() {
  const { database, warnings } = await loadDatabase()
  for (const warning of warnings) console.warn(`  ⚠ ${warning}`)
  const { problems, dangling } = audit(database)
  for (const problem of problems) console.warn(`  ⚠ ${problem}`)
  if (dangling.size) {
    console.error(`  ⚠ références déportées (lots à venir) : ${[...dangling].sort().join(', ')}`)
  }

  // RAZ autoritaire du coffre : l'archive est un artefact dérivé.
  await rm(VAULT_DIR, { recursive: true, force: true })
  await mkdir(VAULT_DIR, { recursive: true })

  const byCluster = new Map()
  for (const entry of [...database].sort((a, b) => a.id.localeCompare(b.id))) {
    const folder = join(VAULT_DIR, slugify(entry.cluster))
    await mkdir(folder, { recursive: true })
    await writeFile(join(folder, `${entry.id}.md`), markdownOf(entry), 'utf8')
    byCluster.set(slugify(entry.cluster), (byCluster.get(slugify(entry.cluster)) || 0) + 1)
  }

  console.log(`seedVault: ${database.length} notes réécrites → ${VAULT_DIR}/`)
  for (const [dir, count] of [...byCluster.entries()].sort()) {
    console.log(`  · ${dir}/  (${count})`)
  }
  console.log('Prochaine étape : node warframe_lore/ui/timeline/scripts/extractor.js')
}

if (IS_MAIN) {
  main().catch((err) => {
    console.error(`seedVault: ${err && err.stack ? err.stack : err}`)
    process.exit(1)
  })
}

export { markdownOf, relationType, slugify } from './lib/lore.js'