/**
 * extractor.js — pipeline Obsidian → graph.json pour la Timeline (ELK + Vue Flow).
 *
 * Rôle : convertir un coffre Obsidian (Markdown + YAML Frontmatter) en un
 * graphe mono-fichier, trié et idempotent, directement consommé par la UI.
 *
 * Contrat Frontmatter (par note) :
 *   ---
 *   id: lua-prevention-dream        # identifiant stable (cible des relations)
 *   label: "La Prévention du Rêve"  # intitulé affiché (défaut : titre H1, sinon slug)
 *   kind: event                     # entity | era | warframe | character | …
 *   year: "1999"                    # étiquette temporelle (affichage pur)
 *   cluster: "Guerre Ancienne"      # nom de cluster (string) → Compound Node
 *   codex_slug: lua-prevention      # navigation vers la fiche Codex (optionnel)
 *   relations:
 *     - cible: albrecht             # id cible (doit exister dans le coffre)
 *       type: lien_paradoxal        # lien_paradoxal → trait pointillé animé
 *   tags: [era, hex]                # métadonnées descriptives (non-cluster)
 *   ---
 *
 * Résolution de cluster implicite : si `cluster` est absent, le premier
 * segment du chemin relatif (dossier racine) fait office de cluster.
 * Des balises de la forme `cluster:` restent compatibles (normalisées).
 *
 * Sortie graph.json :
 *   { nodes: [{ id, type:'entity'|'cluster', label, year, note, codex_slug,
 *               cluster, parentId, members }],
 *     edges: [{ id, source, target, type
 *               ('lien_chronologique'|'lien_paradoxal'), label }] }
 * Les clusters deviennent des nœuds parents (Compound Nodes) ; chaque entité
 * reçoit `parentId` = id de son cluster. Aucune arête de contenance n'est
 * émise : la hiérarchie est déduite de `parentId` par ELK / Vue Flow.
 *
 * Usage : node scripts/extractor.js [coffreObsidian] [cheminGraphJson]
 * Env   : OBSIDIAN_VAULT, GRAPH_OUT
 * Défauts (projet) : coffre = <racine-du-projet>/data/vault,
 *                     sortie = <racine-du-projet>/data/timeline/graph.json
 *                     (data/timeline est le publicDir Vite → servi/build sous
 *                     /timeline/graph.json sans copie manuelle).
 */
import { mkdir, readdir, readFile, rename, writeFile } from 'node:fs/promises'
import { basename, extname, join, parse, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import matter from 'gray-matter'

import { DATA_DIR, TYPE_PARADOX, TYPE_CHRONO, relationType, slugify } from './lib/lore.js'

/* Point d'entrée exécuté seulement quand le script est lancé directement
 * (`node scripts/extractor.js`) : importable par les tests sans effet de bord. */
const IS_MAIN = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]

/* -------------------------------- CLI (args > env > défauts projet) */
const [vaultArg, outArg] = process.argv.slice(2)
const VAULT = resolve(vaultArg || process.env.OBSIDIAN_VAULT || join(DATA_DIR, 'vault'))
const GRAPH_OUT = resolve(outArg || process.env.GRAPH_OUT || join(DATA_DIR, 'timeline', 'graph.json'))

/* ---------------------------------------------------------------------- normalisation */
/** Explosion : `cluster` string|array, ou balises `cluster:xxx` parmis les tags. */
function extractClusters(meta) {
  const raw = Array.isArray(meta.cluster) ? meta.cluster : [meta.cluster]
  const tagged = (meta.tags || [])
    .filter((t) => /^cluster:/i.test(String(t)))
    .map((t) => String(t).replace(/^cluster:/i, ''))
  return [...tagged, ...raw.filter(Boolean)].map((c) => String(c).trim()).filter(Boolean)
}

/** `relations` accepte des objets { cible, type } ou des chaînes "id-cible". */
function relationEntries(relations) {
  if (!Array.isArray(relations)) return []
  return relations
    .map((r) => {
      if (typeof r === 'string') {
        const target = r.trim()
        return target ? { cible: target, type: TYPE_CHRONO, label: '' } : null
      }
      const raw = typeof r === 'object' && r !== null ? r : {}
      const cible = String(raw.cible || '')
        .split('#')[0] // autorise "id#section" : on garde l'entité, pas la section
        .trim()
      return cible
        ? { cible, type: relationType(raw.type), label: String(raw.label || '') }
        : null
    })
    .filter(Boolean)
}

function firstTitle(rawMarkdown) {
  const match = String(rawMarkdown).match(/^#\s+(.+)$/m)
  return match ? match[1].trim() : ''
}

/* --------------------------------------------------------------------- lecture du coffre */
async function walkFiles(dir, base) {
  const entries = await readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    if (entry.name.startsWith('.')) continue // .obsidian, .trash, …
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...(await walkFiles(full, base)))
    } else if (extname(entry.name).toLowerCase() === '.md') {
      files.push(full)
    }
  }
  return files
}

async function parseNote(filePath, vault) {
  const raw = await readFile(filePath, 'utf8')
  const { data, content } = matter(raw)
  const rel = relative(vault, filePath)
  const fileSlug = slugify(parse(basename(filePath)).name)

  const id = String(data.id || fileSlug).trim() || fileSlug
  // Cluster implicite : le dossier racine du fichier (premier segment du
  // chemin relatif), sinon un cluster "Racine" pour les notes à plat.
  const relSegments = rel.split(/[\\/]/)
  const rootFolder = relSegments.length > 1 ? relSegments[0] : null
  const cluster = extractClusters(data)[0] || rootFolder || 'Racine'
  const label = String(data.label || firstTitle(content) || id).trim()

  return {
    id,
    label,
    kind: String(data.kind || 'entity').trim() || 'entity',
    year: String(data.year || '').trim(),
    note: String(data.note || '').trim(),
    codex_slug: String(data.codex_slug || id).trim() || null,
    cluster,
    relations: relationEntries(data.relations),
    source: rel,
  }
}

/* --------------------------------------------------------------------- construction */
function buildGraph(notes) {
  const byId = new Map(notes.map((n) => [n.id, n]))

  // Le fichier classé par slug garantit un output déterministe (reproducible build).
  notes.sort((a, b) => a.id.localeCompare(b.id))

  // Cluster : id stable, label propre, rangée temporelle dérivée des membres
  // (range 1990–1999, mais un an unique n'apparaît pas s'il reprend le nom).
  const clusterNames = [...new Set(notes.map((n) => n.cluster))].sort()
  const clusterNodes = clusterNames.map((name, index) => {
    const members = notes.filter((n) => n.cluster === name)
    const years = members
      .map((n) => parseInt(String(n.year).replace(/[^\d]/g, ''), 10))
      .filter((y) => Number.isFinite(y))
    const displayName = name.replace(/^cluster:\s*/i, '').replace(/^\p{L}/u, (c) => c.toUpperCase())
    const span = years.length ? `${Math.min(...years)}–${Math.max(...years)}` : ''
    const range = years.length > 1 && span !== displayName ? span : ''
    return {
      id: `cluster:${slugify(name)}`,
      label: [displayName, range].filter(Boolean).join(' · '),
      type: 'cluster',
      index,
      members: members.map((n) => n.id),
    }
  })

  // Relations validées (cible existante, pas de boucle, dédoublonnées).
  const seen = new Set()
  const edges = []
  for (const note of notes) {
    for (const rel of note.relations) {
      if (!byId.has(rel.cible)) continue
      if (rel.cible === note.id) continue // relation réflexive : sans objet pour ELK
      const key = `${note.id}\u0000${rel.cible}\u0000${rel.type}`
      if (seen.has(key)) continue
      seen.add(key)
      edges.push({
        id: `edge:${slugify(note.id)}-${slugify(rel.cible)}-${slugify(rel.type)}`,
        source: note.id,
        target: rel.cible,
        type: rel.type,
        label: rel.label,
      })
    }
  }
  edges.sort((a, b) => a.id.localeCompare(b.id))

  const clusterById = new Map(clusterNodes.map((c) => [c.id, c]))
  const nodes = notes.map((n) => {
    const clusterId = `cluster:${slugify(n.cluster)}`
    const parent = clusterById.get(clusterId)
    const parentId = parent || clusterNodes.length > 1 ? clusterId : null
    return {
      id: n.id,
      type: 'entity',
      label: n.label,
      year: n.year,
      note: n.note,
      codex_slug: n.codex_slug,
      cluster: n.cluster,
      parentId: parent ? clusterId : null,
    }
  })
  const clusterFull = clusterNodes.map((c) => ({ id: c.id, type: 'cluster', label: c.label, index: c.index }))

  return { nodes: [...clusterFull, ...nodes].sort((a, b) => a.id.localeCompare(b.id)), edges }
}

/* ----------------------------------------------------------------------- écriture idempotente */
async function writeAtomic(filePath, graph) {
  await mkdir(parse(filePath).dir, { recursive: true })
  const tmp = `${filePath}.tmp`
  await writeFile(tmp, JSON.stringify(graph, null, 2), 'utf8')
  await rename(tmp, filePath)
}

/* ------------------------------------------------------------------------- point d'entrée */
async function main() {
  if (!(await readdir(VAULT).catch(() => null))) {
    console.error(`extractor: coffre introuvable : ${VAULT}`)
    process.exit(1)
  }
  const files = await walkFiles(VAULT, VAULT)
  const notes = []
  for (const file of files) {
    try {
      notes.push(await parseNote(file, VAULT))
    } catch (err) {
      console.warn(`extractor: note ignorée ${file} : ${err.message}`)
    }
  }
  if (!notes.length) {
    console.error('extractor: aucune note Markdown trouvée dans le coffre.')
    process.exit(1)
  }
  const graph = buildGraph(notes)
  await writeAtomic(GRAPH_OUT, graph)
  console.error(
    `extractor: ${notes.length} notes → ` +
      `${graph.nodes.length} nœuds (${graph.nodes.filter((n) => n.type === 'cluster').length} clusters) + ` +
      `${graph.edges.length} relations → ${GRAPH_OUT}`,
  )
}

if (IS_MAIN) {
  main().catch((err) => {
    console.error(`extractor: ${err && err.stack ? err.stack : err}`)
    process.exit(1)
  })
}

export { parseNote, buildGraph, relationType, slugify }