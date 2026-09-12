/**
 * split-seed.js — scinde un fichier de seed "patch" en lots thématiques.
 *
 * Lit data/seed/patch-factions-warframes.json (Lots 2 + 3 mélangés + rattrapages),
 * redistribue chaque entrée vers son fichier de lot, puis supprime le patch.
 *
 *   lot2-factions.json   leaders de factions (Corpus · Grineer · Sentients)
 *   lot3-warframes.json  cluster "warframes"
 *   lot1-foundations.json / lot4-hex-1999.json  pour les rattrapages
 *
 * L'id est la source de vérité (cible stable des relations) : un cluster seul
 * ne différencie pas protoframe_minerva (1999) des rattrapages du Lot 1.
 * Chaque destination est triée par id (déterminisme) ; toute entité sans
 * destination ni cluster "warframes" fait échouer le script (périmètre sûr).
 *
 * Usage (racine du projet) :
 *   node warframe_lore/ui/timeline/scripts/split-seed.js
 */
import { readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { SEED_DIR } from './lib/lore.js'

const IS_MAIN = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]
const SOURCE = 'patch-factions-warframes.json'
const LOT3 = 'lot3-warframes.json'
const WARFRAMES_CLUSTER = 'warframes'

/** Destination par id (les rattrapages dépaysés du patch retrouvent leur lot). */
export const TARGET_OF = {
  // Lot 2 — Leaders de factions (les 7 présents dans le patch)
  parvos_granum: 'lot2-factions.json',
  alad_v: 'lot2-factions.json',
  reines_jumelles: 'lot2-factions.json',
  tyl_regor: 'lot2-factions.json',
  hunhow: 'lot2-factions.json',
  erra: 'lot2-factions.json',
  natah: 'lot2-factions.json',
  // Rattrapages Lot 1
  zariman: 'lot1-foundations.json',
  otak: 'lot1-foundations.json',
  tuvul: 'lot1-foundations.json',
  avantus: 'lot1-foundations.json',
  // Rattrapage Lot 4
  protoframe_minerva: 'lot4-hex-1999.json',
}

async function readJson(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'))
  } catch (err) {
    if (err.code === 'ENOENT') return []
    throw err
  }
}

async function writeJson(path, entries) {
  await writeFile(path, JSON.stringify(entries, null, 2) + '\n', 'utf8')
}

/** Fusionne des entrées dans un lot cible : dédoublonnage d'ids + tri stable. */
async function mergeInto(targetFile, additions) {
  const path = join(SEED_DIR, targetFile)
  const all = [...(await readJson(path)), ...additions]
  const seen = new Set()
  for (const entry of all) {
    if (seen.has(entry.id)) throw new Error(`id dupliqué après fusion dans ${targetFile} : ${entry.id}`)
    seen.add(entry.id)
  }
  await writeJson(path, all.sort((a, b) => a.id.localeCompare(b.id)))
  console.log(`${targetFile}: +${additions.length} entrées (${all.length} au total)`)
}

async function main() {
  const sourcePath = join(SEED_DIR, SOURCE)
  const source = await readJson(sourcePath)
  if (!source.length) throw new Error(`${SOURCE} : fichier vide ou introuvable`)

  const buckets = new Map()
  for (const entry of source) {
    const id = String(entry.id)
    const target = TARGET_OF[id] ?? (entry.cluster === WARFRAMES_CLUSTER ? LOT3 : null)
    if (!target) {
      throw new Error(`${SOURCE} : entrée ${id || '<sans id>'} sans destination (cluster ${entry.cluster})`)
    }
    if (!buckets.has(target)) buckets.set(target, [])
    buckets.get(target).push(entry)
  }

  for (const [target, entries] of buckets) {
    await mergeInto(target, entries)
  }

  await rm(sourcePath)
  console.log(`${SOURCE}: supprimé — ${source.length} entrées redistribuées, 0 perdue`)
}

if (IS_MAIN) {
  main().catch((err) => {
    console.error(`split-seed: ${err && err.stack ? err.stack : err}`)
    process.exit(1)
  })
}