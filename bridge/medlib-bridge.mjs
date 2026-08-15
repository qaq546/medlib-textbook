// medlib-bridge.mjs — MinerU cloud API bridge + medical textbook library ops.
// Zero-dependency Node.js. CLI: node medlib-bridge.mjs <verb> <args.json> <out.json>
// Writes a JSON result atomically to out.json. All binary I/O happens here.
import { readFileSync, writeFileSync, renameSync, mkdirSync, readdirSync, statSync, existsSync, copyFileSync, unlinkSync, rmSync } from 'node:fs'
import { dirname, join, basename, extname } from 'node:path'
import { pathToFileURL } from 'node:url'
import { execFileSync } from 'node:child_process'

const API = 'https://mineru.net/api'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export function fail(code, msg, extra = {}) {
  throw Object.assign(new Error(msg), { code, extra })
}

async function req(url, opts = {}, timeoutMs = 60000) {
  const r = await fetch(url, { ...opts, signal: AbortSignal.timeout(timeoutMs) })
  const text = await r.text()
  let body = null
  try { body = text ? JSON.parse(text) : null } catch { body = { raw: text.slice(0, 2000) } }
  return { status: r.status, body }
}

export async function download(url, dest, timeoutMs = 10 * 60 * 1000) {
  const r = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) })
  if (!r.ok) fail('DOWNLOAD_FAIL', `http ${r.status} for ${url}`)
  const buf = Buffer.from(await r.arrayBuffer())
  mkdirSync(dirname(dest), { recursive: true })
  writeFileSync(dest, buf)
  return buf.length
}

const tokenOf = (args) => args.token || process.env.MINERU_TOKEN || ''
const auth = (t) => ({ Authorization: `Bearer ${t}` })

// ---------------- Standard API v4 ----------------
export async function stUploadUrls({ token, files, modelVersion = 'vlm', enableFormula = true, enableTable = true, language = 'ch' }) {
  // files: [{ name, dataId, pageRanges?, isOcr? }] — upload links; the service
  // AUTO-submits parse tasks when upload completes (no extract/task/batch call).
  const { status, body } = await req(`${API}/v4/file-urls/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth(tokenOf({ token })) },
    body: JSON.stringify({
      files: files.map((f) => ({ name: f.name, data_id: f.dataId, ...(f.pageRanges ? { page_ranges: f.pageRanges } : {}), ...(f.isOcr ? { is_ocr: true } : {}) })),
      model_version: modelVersion,
      enable_formula: enableFormula,
      enable_table: enableTable,
      language,
    }),
  })
  if (status !== 200 || !body || body.code !== 0) fail('ST_UPLOAD_URLS_FAIL', (body && (body.msg || body.msgCode)) || `http ${status}`, { status, body })
  return { ...body.data, urls: body.data.file_urls, batchId: body.data.batch_id }
}
export async function stPut(fileUrl, localPath) {
  const buf = readFileSync(localPath)
  const r = await fetch(fileUrl, { method: 'PUT', body: buf, signal: AbortSignal.timeout(15 * 60 * 1000) })
  if (!r.ok) fail('ST_PUT_FAIL', `put ${basename(localPath)} -> http ${r.status}`)
  return buf.length
}
export async function stCreateBatch({ token, modelVersion = 'vlm', files, isOcr = false, enableFormula = true, enableTable = true, language = 'ch' }) {
  const { status, body } = await req(`${API}/v4/extract/task/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth(tokenOf({ token })) },
    body: JSON.stringify({
      files: files.map((f) => ({ url: f.url, data_id: f.dataId, ...(f.pageRanges ? { page_ranges: f.pageRanges } : {}) })),
      model_version: modelVersion, is_ocr: isOcr, enable_formula: enableFormula, enable_table: enableTable, language,
    }),
  })
  if (status !== 200 || !body || body.code !== 0) fail('ST_CREATE_FAIL', (body && (body.msg || body.msgCode)) || `http ${status}`, { status, body })
  return body.data
}
export async function stPollBatch({ token, batchId }) {
  const { status, body } = await req(`${API}/v4/extract-results/batch/${batchId}`, { headers: auth(tokenOf({ token })) })
  if (status !== 200 || !body || body.code !== 0) fail('ST_POLL_FAIL', (body && (body.msg || body.msgCode)) || `http ${status}`, { status, body })
  return body.data
}
export async function stFetchOne({ token, fullZipUrl, destDir }) {
  mkdirSync(destDir, { recursive: true })
  const zipPath = join(destDir, 'result.zip')
  await download(fullZipUrl, zipPath)
  execFileSync('tar', ['-xf', zipPath, '-C', destDir], { stdio: 'inherit' })
  return { zipPath, destDir, files: lsRec(destDir, 3) }
}

// ---------------- PDF page estimate (heuristic, no libs) ----------------
export function pdfPages(path) {
  const buf = readFileSync(path)
  let text = ''
  try { text = buf.toString('latin1') } catch { text = '' }
  let count = 0
  const re = /\/Type\s*\/Page[^s]/g
  let m
  while ((m = re.exec(text)) !== null) count++
  const cm = /\/Count\s+(\d+)/.exec(text)
  const countVal = cm ? parseInt(cm[1], 10) : 0
  return { estimate: Math.max(count, countVal), pageObjs: count, countField: countVal }
}

// ---------------- Library ops ----------------
const BOOK_SAFE = /[<>:"/\\|?*\u0000-\u001f]/g
export const sanitize = (s) => s.replace(BOOK_SAFE, '_').replace(/\s+/g, ' ').trim().slice(0, 120) || 'unnamed'

export function lsRec(root, depth = 4, prefix = '') {
  if (depth < 0) return []
  let out = []
  let st = null
  try { st = statSync(root) } catch { return out }
  if (st.isFile()) return [{ path: root, rel: basename(root), size: st.size }]
  let entries = []
  try { entries = readdirSync(root, { withFileTypes: true }) } catch { return out }
  for (const e of entries) {
    const p = join(root, e.name)
    const rel = prefix ? `${prefix}/${e.name}` : e.name
    if (e.isDirectory()) out = out.concat(lsRec(p, depth - 1, rel))
    else { try { out.push({ path: p, rel, size: statSync(p).size }) } catch {} }
  }
  return out
}

// Arrange one extracted task output into the book folder.
export function stArrange({ libraryDir, book, chunkLabel, srcDir }) {
  const bookDir = join(libraryDir, book)
  const imagesDir = join(bookDir, 'images')
  mkdirSync(imagesDir, { recursive: true })
  const files = lsRec(srcDir, 5)
  const mds = files.filter((f) => /\.md$/i.test(f.rel)).sort((a, b) => b.size - a.size)
  if (!mds.length) fail('NO_MD', 'extracted zip contains no markdown', { files: files.map((f) => f.rel) })
  const mdSrc = mds[0].path
  const mdName = chunkLabel ? `${book}-${chunkLabel}.md` : `${book}.md`
  const mdDest = join(bookDir, mdName)
  let mdText = readFileSync(mdSrc, 'utf8')

  // move every raster image under srcDir into imagesDir (flatten, dedupe by name)
  const imgExt = /\.(png|jpe?g|webp|gif|bmp|jp2|svg)$/i
  const moved = new Map() // originalName -> finalName
  let collisions = 0
  for (const f of files.filter((x) => imgExt.test(x.rel))) {
    let name = basename(f.path)
    let final = join(imagesDir, name)
    let i = 1
    while (existsSync(final)) { final = join(imagesDir, `${i}-${name}`); i++; collisions++ }
    copyFileSync(f.path, final)
    moved.set(name, basename(final))
  }
  // rewrite md image refs to images/<finalName>
  mdText = mdText.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (whole, alt, src) => {
    const bare = src.replace(/^\.?\//, '')
    const name = basename(bare.split(/[?#]/)[0])
    const finalName = moved.get(name) || name
    return `![${alt}](images/${finalName})`
  })
  writeFileSync(mdDest, mdText)
  return { mdDest, mdName, imageCount: moved.size, collisions, files: files.map((f) => f.rel) }
}

// Concatenate chunk mds (<book>-p<start>-<end>.md) into one <book>.md.
export function mergeBook({ libraryDir, book }) {
  const bookDir = join(libraryDir, book)
  if (!existsSync(bookDir)) fail('NO_BOOK_DIR', `book dir missing: ${bookDir}`)
  const chunkRe = new RegExp(`^${escapeRe(book)}-p(\\d+)-\\d+\\.md$`)
  const chunks = readdirSync(bookDir).filter((n) => chunkRe.test(n)).map((n) => ({ n, start: parseInt(chunkRe.exec(n)[1], 10) })).sort((a, b) => a.start - b.start)
  if (!chunks.length) fail('NO_CHUNKS', 'no chunk files to merge')
  const parts = []
  for (const c of chunks) {
    const txt = readFileSync(join(bookDir, c.n), 'utf8')
    parts.push(`<!-- 分片 ${c.n} 开始 -->\n\n${txt}\n\n<!-- 分片 ${c.n} 结束 -->`)
  }
  const merged = join(bookDir, `${book}.md`)
  writeFileSync(merged, parts.join('\n'))
  for (const c of chunks) unlinkSync(join(bookDir, c.n))
  return { merged, chunkFiles: chunks.length, bytes: statSync(merged).size }
}
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// Scan md corpus for headings (index source) or search hits.
export function scanMd({ libraryDir, book }) {
  const books = existsSync(libraryDir) ? readdirSync(libraryDir, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name) : []
  const out = []
  for (const b of books) {
    if (book && b !== book) continue
    const mdPath = join(libraryDir, b, `${b}.md`)
    if (existsSync(mdPath)) {
      const headings = readFileSync(mdPath, 'utf8').split('\n').filter((l) => /^#{1,4}\s/.test(l)).slice(0, 500)
      out.push({ book: b, md: mdPath, headings, size: statSync(mdPath).size })
    }
  }
  return out
}
export function search({ libraryDir, query, book, maxResults = 20 }) {
  const q = String(query || '').toLowerCase()
  if (!q) return { hits: [] }
  const books = existsSync(libraryDir) ? readdirSync(libraryDir, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name) : []
  const hits = []
  for (const b of books) {
    if (book && b !== book) continue
    const mdPath = join(libraryDir, b, `${b}.md`)
    if (!existsSync(mdPath)) continue
    const lines = readFileSync(mdPath, 'utf8').split('\n')
    let count = 0
    for (let i = 0; i < lines.length && count < 5; i++) {
      if (lines[i].toLowerCase().includes(q)) {
        count++
        hits.push({ book: b, file: mdPath, line: i + 1, text: lines[i].slice(0, 300) })
      }
    }
  }
  hits.sort((a, b) => b.line - a.line) // rough recency; fine for v1
  return { hits: hits.slice(0, maxResults), total: hits.length }
}

// ---------------- Agent API (dev / smoke; no token) ----------------
export async function agentParse({ fileName, language = 'ch', enableTable = true, isOcr = false, enableFormula = true }) {
  const { status, body } = await req(`${API}/v1/agent/parse/file`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_name: fileName, language, enable_table: enableTable, is_ocr: isOcr, enable_formula: enableFormula }),
  })
  if (status !== 200 || !body || body.code !== 0) fail('AGENT_PARSE_FAIL', (body && (body.msg || body.msgCode)) || `http ${status}`, { status, body })
  return body.data
}
export async function agentPoll(taskId) { return req(`${API}/v1/agent/parse/${taskId}`) }

// ---------------- CLI dispatch ----------------
const verbs = {
  'pdf-pages': (a) => ({ ok: true, ...pdfPages(a.path) }),
  'mkdir': (a) => { mkdirSync(a.path, { recursive: true }); return { ok: true, path: a.path } },
  'rm': (a) => { rmSync(a.path, { recursive: true, force: true }); return { ok: true, path: a.path } },
  'trim-images': (a) => {
    // drop image references (and files) smaller than minBytes — avatars/logos/icons.
    const { libraryDir, book, minBytes = 8192 } = a
    const books = existsSync(libraryDir) ? readdirSync(libraryDir, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name) : []
    const report = []
    for (const b of books) {
      if (book && b !== book) continue
      const mdPath = join(libraryDir, b, `${b}.md`)
      if (!existsSync(mdPath)) continue
      let md = readFileSync(mdPath, 'utf8')
      const removed = []
      md = md.replace(/!\[[^\]]*\]\((images\/[^)\s]+)\)/g, (whole, rel) => {
        const p = join(libraryDir, b, rel)
        let size = 0
        try { size = statSync(p).size } catch { return whole }
        if (size < minBytes) { removed.push({ rel, size }); try { unlinkSync(p) } catch {}; return '' }
        return whole
      })
      md = md.replace(/\n[ \t]*\n[ \t]*\n/g, '\n\n')
      writeFileSync(mdPath, md)
      if (removed.length) report.push({ book: b, removed })
    }
    return { ok: true, report }
  },
  'clean': (a) => {
    // remove .medlib-* scratch/out leftovers and the .tmp dir inside `dir`
    // (never the token file, and never this invocation's own output file)
    let removed = []
    const selfOut = a.__outPath ? basename(a.__outPath) : ''
    try {
      for (const e of readdirSync(a.dir, { withFileTypes: true })) {
        const name = e.name
        if (name === '.medlib-token') continue
        if ((name.startsWith('.medlib-') || name === '.tmp') && name !== selfOut) {
          rmSync(join(a.dir, name), { recursive: true, force: true })
          removed.push(name)
        }
      }
    } catch {}
    return { ok: true, removed }
  },
  'st-upload-urls': async (a) => ({ ok: true, ...(await stUploadUrls(a)) }),
  'st-put': async (a) => ({ ok: true, bytes: await stPut(a.url, a.path) }),
  'st-create-batch': async (a) => ({ ok: true, data: await stCreateBatch(a) }),
  'st-poll-batch': async (a) => ({ ok: true, data: await stPollBatch(a) }),
  'st-fetch-one': async (a) => ({ ok: true, ...(await stFetchOne(a)) }),
  'st-arrange': (a) => ({ ok: true, ...stArrange(a) }),
  'merge-book': (a) => ({ ok: true, ...mergeBook(a) }),
  'scan-md': (a) => ({ ok: true, books: scanMd(a) }),
  'search': (a) => ({ ok: true, ...search(a) }),
  'ls': (a) => ({ ok: true, files: lsRec(a.path, a.depth || 4) }),
  'agent-parse': async (a) => ({ ok: true, ...(await agentParse(a)) }),
  'agent-poll': async (a) => ({ ok: true, ...(await agentPoll(a.taskId)) }),
}

async function main() {
  const [verb, argsPath] = process.argv.slice(2)
  let args = {}
  if (argsPath) { try { args = JSON.parse(readFileSync(argsPath, 'utf8')); unlinkSync(argsPath) } catch { args = { path: argsPath } } }
  const send = (obj) => { process.stdout.write(JSON.stringify(obj)) }
  try {
    const fn = verbs[verb]
    if (!fn) throw new Error(`unknown verb ${verb}`)
    send(await fn(args))
  } catch (e) {
    send({ ok: false, error: { code: e.code || 'BRIDGE_ERROR', msg: e.message, extra: e.extra } })
    process.exit(1)
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main()
