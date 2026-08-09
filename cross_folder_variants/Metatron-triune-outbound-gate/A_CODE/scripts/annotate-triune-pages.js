const fs = require('fs')
const path = require('path')

// Usage: node annotate-triune-pages.js
// Reads frontend/src/triune_pages_map.js and inserts `export const triuneRoles = [...]`
// at top of matching page files under frontend/src/pages if not already present.

const repoRoot = path.join(__dirname, '..')
const mapPath = path.join(repoRoot, 'frontend', 'src', 'triune_pages_map.js')
if (!fs.existsSync(mapPath)) {
  console.error('triune_pages_map.js not found')
  process.exit(1)
}

const map = require(mapPath)

const pagesDir = path.join(repoRoot, 'frontend', 'src', 'pages')

function tryFiles(baseName) {
  const exts = ['.jsx', '.tsx', '.js', '.jsx.jsx']
  for (const e of exts) {
    const p = path.join(pagesDir, baseName + e)
    if (fs.existsSync(p)) return p
  }
  return null
}

Object.keys(map).forEach((pageKey) => {
  if (pageKey === 'Default') return
  // pageKey like WorldViewPage or GraphWorld
  let base = pageKey
  if (base.endsWith('Page')) base = base.replace(/Page$/, '')
  const candidates = [pageKey, base]
  for (const c of candidates) {
    const file = tryFiles(c)
    if (!file) continue
    const src = fs.readFileSync(file, 'utf8')
    if (src.includes('export const triuneRoles')) {
      console.log(`Already annotated: ${file}`)
      break
    }
    const roles = JSON.stringify(map[pageKey])
    const inject = `export const triuneRoles = ${roles}\n\n`;
    fs.writeFileSync(file, inject + src, 'utf8')
    console.log(`Annotated ${file} with triuneRoles=${roles}`)
    break
  }
})

console.log('Done')
