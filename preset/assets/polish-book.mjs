// polish-book.mjs — 医学教材 Markdown 成品化后处理（对 MinerU 合并产物做一次"整饰"）。
//
// 目标：让每一本新转换的教材自动达到《儿科学 第10版-p1-200.md》样例的质量：
//   1. 去掉 <!-- 分片 ... --> 标记
//   2. 封面去重 + 版权页合并（去掉封面图片、英文书名页、拼音书名页的重复块）
//   3. 依据 PDF 官方书签插入 `# 第X章　标题` 章标题（原输出缺失）
//   4. 前置页无图注图片引用剔除（编委/主编照片等，文件保留）
//   5. 标题层级规范化：章# / 节## / 一、### / （一）#### / 1.##### / 【】#### / 附## / 思考题##
//   6. 粘连标题拆分（"## 4. 子宫韧带 共有 4 对(图 2-5)。" → 标题 + 正文）
//   7. 目录锚点链接（GitHub 风格 slug，替换原书印刷目录）
//   8. 图片处理：图注分组绑定 figX-Y(-a/-b…) + 二维码/数字资源小图剔除 + 缺失图注占位
//      （规则对齐《儿科学 第10版》样例：带「图X-Y」图注的图归档 figX-Y，多面板图 figX-Y + -a/-b/-c；
//        无图注图与二维码/视频缩略图/章节思维导图/数字人案例/三维模型等 ≈6KB 小图剔除引用+文件）
//   9. 重复"主编/副主编简介"标题去重、人名标题降级、`\- ` 修正
//   10. 未被引用的图片文件清理（哈希原图副本、封面图等残留）
//
// 用法（CLI）:
//   node polish-book.mjs <libraryDir> <book> [bookmarks.json] [pdfPath]
//   例: node polish-book.mjs <libraryDir> "23妇产科学 第10版" <bookmarks.json>
// 也可作为模块调用: import { polishBook } from './polish-book.mjs'
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync, renameSync, unlinkSync } from 'node:fs'
import { join, dirname, basename } from 'node:path'
import { execFileSync } from 'node:child_process'

const RE_CHAPTER = /^第[一二三四五六七八九十百]+章/

// ---------- slug（GitHub 风格锚点） ----------
export function slug(s) {
  // 与 GitHub 相同：去标点（保留 CJK/字母/数字/连字符）、空白→"-"、小写
  return String(s)
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .replace(/[\s\u3000]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

// ---------- 书签提取（python + pymupdf 侧车，失败返回空） ----------
export function extractBookmarks(pdfPath) {
  const selfDir = dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
  const script = join(selfDir, 'pdf-bookmarks.py')
  if (!existsSync(script) || !existsSync(pdfPath)) return null
  const out = join(selfDir, 'work', `.pdf-bookmarks-${Date.now()}.json`)
  try {
    execFileSync('python', [script, pdfPath, out], { stdio: 'ignore', timeout: 120000 })
    if (!existsSync(out)) return null
    const data = JSON.parse(readFileSync(out, 'utf8'))
    unlinkSync(out)
    return data
  } catch { try { unlinkSync(out) } catch {} }
  return null
}

// ---------- 主入口 ----------
export function polishBook({ libraryDir, book, bookmarksPath, pdfPath, dryRun = false }) {
  const bookDir = join(libraryDir, book)
  const mdPath = join(bookDir, `${book}.md`)
  const imagesDir = join(bookDir, 'images')
  if (!existsSync(mdPath)) throw new Error(`missing md: ${mdPath}`)
  let md = readFileSync(mdPath, 'utf8')

  // 0) 书签
  let chapters = []
  let coverEditors = null
  if (bookmarksPath && existsSync(bookmarksPath)) {
    const bm = JSON.parse(readFileSync(bookmarksPath, 'utf8'))
    chapters = (bm.chapters || []).filter((c) => RE_CHAPTER.test(c.title))
    coverEditors = bm.coverEditors || null
  } else if (pdfPath) {
    const bm = extractBookmarks(pdfPath)
    if (bm) {
      chapters = (bm.chapters || []).filter((c) => RE_CHAPTER.test(c.title))
      coverEditors = bm.coverEditors || null
    }
  }
  const report = { book, chaptersFound: chapters.length, steps: {} }

  // 1) 去掉分片标记
  md = md.split('\n').filter((l) => !/^\s*<!--\s*分片/.test(l)).join('\n')

  // 2) 封面去重 + 版权页合并
  md = rebuildFrontMatter(md, book, coverEditors, report)

  // 2b) 前言标题补全（前言正文无标题时，在"副主编简介"之后、目录之前补 `## 前言`）
  md = insertPrefaceHeading(md, report)

  // 3) 插入章标题（基于书签锚句）
  if (chapters.length) md = insertChapterHeadings(md, chapters, report)
  else report.steps.chapters = { skipped: 'no bookmarks' }

  // 4) 前置页无图注图片引用剔除（第一章之前）
  md = removeFrontMatterImages(md, report)

  // 5) 标题层级规范化 + 粘连拆分 + 人名降级 + `\- ` 修正 + 简介标题去重
  md = normalizeHeadings(md, report)

  // 6) 目录锚点链接（替换原书印刷目录）
  md = buildLinkedToc(md, report)

  // 7) 图片处理：图注分组绑定 figX-Y(-a/-b…) + 二维码/小图剔除 + 占位
  md = processImages(md, imagesDir, report)

  // 8) 收尾：折叠多余空行、去行尾空白、确保文件尾换行
  md = md.replace(/[ \t]+$/gm, '').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n'

  report.bytes = Buffer.byteLength(md, 'utf8')
  report.lines = md.split('\n').length
  if (!dryRun) writeFileSync(mdPath, md, 'utf8')
  return report
}

// ---------- 2) 封面去重 + 版权页合并 ----------
function rebuildFrontMatter(md, book, coverEditors, report) {
  const lines = md.split('\n')
  const endIdx = lines.findIndex((l) => /^##\s*编委名单/.test(l))
  if (endIdx < 0) return md
  const head = lines.slice(0, endIdx)
  const rest = lines.slice(endIdx)

  const nonEmpty = head.filter((l) => l.trim())
  const title = nonEmpty[0] ? nonEmpty[0].trim() : book
  // 幂等性: 若封面已被 polish 过(首行已是 "# 书名"), 跳过重建
  if (/^#\s/.test(title)) return md
  const english = nonEmpty[1] ? nonEmpty[1].trim() : ''
  const edition = nonEmpty.find((l) => /^第\s*\d+\s*版/.test(l)) || ''

  // 编者行：优先用 PDF 封面提取的（空格规范），否则回退 md 启发式
  let editors = []
  if (coverEditors && coverEditors.length) {
    const kindLabel = { 主审: '主　审', 主编: '主　编', 副主编: '副主编', 数字主编: '数字主编', 数字副主编: '数字副主编' }
    const seenKeys = new Set()
    for (const e of coverEditors) {
      const key = e.names.replace(/\s+/g, '')
      if (seenKeys.has(key)) continue
      seenKeys.add(key)
      editors.push(`${kindLabel[e.kind] || e.kind}　${e.names.replace(/ +/g, '　')}`)
    }
  } else {
    const editorRe = /^(主\s*审|主\s*编|副\s*主\s*编|数字\s*主\s*编|数字\s*副\s*主\s*编)\s*[|｜:：]/
    const editorMap = new Map()
    for (const l of head) {
      const t = l.trim()
      if (!editorRe.test(t)) continue
      const kind = editorRe.exec(t)[1].replace(/\s+/g, '')
      const names = t.replace(/^.*?[|｜:：]\s*/, '').trim()
      const key = names.replace(/\s+/g, '')
      const cur = editorMap.get(kind)
      if (!cur || countSpaces(names) > countSpaces(cur.names)) editorMap.set(kind, { names, key })
    }
    const kindLabel = { 主审: '主　审', 主编: '主　编', 副主编: '副主编', 数字主编: '数字主编', 数字副主编: '数字副主编' }
    const seenKeys = new Set()
    for (const [kind, v] of editorMap) {
      if (seenKeys.has(v.key)) continue
      seenKeys.add(v.key)
      editors.push(`${kindLabel[kind] || kind}　${v.names.replace(/ +/g, '　')}`)
    }
  }

  const pubIdx = head.findIndex((l) => l.includes('人民卫生出版社'))
  const publisher = pubIdx >= 0 ? head[pubIdx].trim() : '人民卫生出版社'
  const cityIdx = head.findIndex((l) => l.includes('·北京'))
  const city = cityIdx >= 0 ? head[cityIdx].trim() : '·北京·'

  // 版权页正文：从"版权所有/CIP"开始到编委名单前，剔除图片、重复书名标题
  let cpStart = head.findIndex((l) => /版权所有|图书在版编目/.test(l))
  if (cpStart < 0) cpStart = 0
  const cpBody = []
  for (const l of head.slice(cpStart)) {
    const t = l.trim()
    if (!t) { if (cpBody.length) cpBody.push(''); continue }
    if (/^!\[/.test(t)) continue
    if (/^#{1,6}\s*(妇产科学|Obstetrics and Gynecology)\s*$/.test(t)) continue
    if (/^#{1,6}\s*第\s*10\s*版\s*$/.test(t)) continue
    if (/^#{1,6}\s*版权所有/.test(t)) { cpBody.push('## 版权页'); cpBody.push('版权所有，侵权必究！'); continue }
    cpBody.push(t)
  }

  const cover = [
    `# ${title}`, '',
    english, '',
    edition, '',
    ...editors.flatMap((e) => [e, '']),
    publisher, '', city, '',
  ].join('\n')

  const out = cover + '\n' + cpBody.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n\n' + rest.join('\n')
  report.steps.frontMatter = { title, editors: editors.length, hadCoverImage: /^!\[/.test(head.join('\n')) }
  return out
}
const countSpaces = (s) => (s.match(/\s/g) || []).length

// ---------- 2b) 前言标题补全 ----------
// 人卫教材前言的特征结构：…正文段落… → 空行 → 署名行(如 "扎北华 山东大学齐鲁医院") → 日期行 → 目录
// 该函数在"署名行之前、正文段落顶部"补一个 `## 前言` 标题（仅当块内尚无前言标题时）。
function insertPrefaceHeading(md, report) {
  const lines = md.split('\n')
  const tocIdx = lines.findIndex((l) => /^#{1,6}\s*目录\s*$/.test(l.trim()))
  if (tocIdx < 0) return md

  // 找日期行
  let dateIdx = -1
  for (let i = tocIdx - 1; i >= 0; i--) {
    const t = lines[i].trim()
    if (!t) continue
    if (/^#{1,6}\s/.test(t)) break
    if (/^\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日$/.test(t)) { dateIdx = i; break }
  }
  if (dateIdx < 0) return md

  // 从日期行向上，跳过空行，连续收集"署名行"(含单位)
  const sigRe = /^.{1,18}(大学|医院|学院|研究院|医学院)$/
  let sigTop = -1
  for (let i = dateIdx - 1; i >= 0; i--) {
    const t = lines[i].trim()
    if (!t) continue
    if (/^#{1,6}\s/.test(t)) break
    if (sigRe.test(t) && t.length <= 40) { sigTop = i; continue }
    break
  }
  if (sigTop < 0) return md

  // 从署名区顶部再向上，跳过空行，收集连续正文段（遇标题停止）
  let start = sigTop
  for (let i = sigTop - 1; i >= 0; i--) {
    const t = lines[i].trim()
    if (!t) continue
    if (/^#{1,6}\s/.test(t)) break
    start = i
  }
  // 向下跳过"编者简介"段落（以 男，/女，/从事教学/现任/获/担任/曾 等开头的人物简介），
  // 前言正文起点 = 第一个非简介长段落
  const bioOpener = /^(男|女)[，,]\s*\d|^(从|现|获|担|曾|先后|任)\S{1,4}(教学|任|职|教)/ 
  let prefaceStart = start
  for (let i = start; i < sigTop; i++) {
    const t = lines[i].trim()
    if (!t) continue
    if (t.length < 60 || bioOpener.test(t)) { prefaceStart = i + 1; continue }
    prefaceStart = i
    break
  }
  if (prefaceStart >= sigTop) return md
  const first = lines[prefaceStart].trim()
  if (first.length < 30) return md
  const block = lines.slice(prefaceStart, sigTop).filter((l) => l.trim())
  if (block.length < 1) return md
  if (block.some((l) => /^#{1,6}\s*前言/.test(l.trim()))) return md
  // 幂等性: 前言块正上方(跳过空行)已有"前言"标题则跳过
  let above2 = prefaceStart - 1
  while (above2 >= 0 && !lines[above2].trim()) above2--
  if (above2 >= 0 && /^#{1,6}\s*前言/.test(lines[above2].trim())) return md
  lines.splice(prefaceStart, 0, '## 前言', '')
  report.steps.frontMatter = { ...(report.steps.frontMatter || {}), prefaceHeading: 'inserted' }
  return lines.join('\n')
}

// ---------- 3) 插入章标题 ----------
function insertChapterHeadings(md, chapters, report) {
  let lines = md.split('\n')
  const norm = (s) => s.replace(/[\s\u3000]/g, '').replace(/[，。；：、（）(),.;:'"!?]/g, '')
  const inserted = []
  for (const ch of chapters) {
    const anchor = norm(ch.anchor || '').slice(0, 24)
    if (!anchor) continue
    let hit = -1
    for (let i = 0; i < lines.length; i++) {
      if (/^#{1,6}\s/.test(lines[i])) continue
      const t = norm(lines[i])
      if (t && t.startsWith(anchor)) { hit = i; break }
    }
    if (hit < 0) continue
    // 幂等性: 若锚句上方(跳过空行)已有该章标题则跳过
    let above = hit - 1
    while (above >= 0 && !lines[above].trim()) above--
    if (above >= 0 && lines[above].trim() === `# ${ch.title}`) continue
    lines.splice(hit, 0, `# ${ch.title}`, '')
    inserted.push(ch.title)
  }
  report.steps.chapters = { inserted: inserted.length, titles: inserted }
  return lines.join('\n')
}

// ---------- 4) 剔除前置页无图注图片引用 ----------
function removeFrontMatterImages(md, report) {
  const lines = md.split('\n')
  const firstChapter = lines.findIndex((l) => /^#\s*第[一二三四五六七八九十百]+章/.test(l))
  if (firstChapter < 0) return md
  let removed = 0
  for (let i = 0; i < firstChapter; i++) {
    if (!/^!\[[^\]]*\]\(images\//.test(lines[i])) continue
    let hasCaption = false
    for (let j = i + 1; j <= Math.min(i + 3, lines.length - 1); j++) {
      if (/^图\s*\d+\s*[-－]\s*\d+/.test(lines[j].trim())) { hasCaption = true; break }
    }
    if (!hasCaption) { lines[i] = ''; removed++ }
  }
  report.steps.frontImages = { removed }
  return lines.join('\n')
}

// ---------- 5) 标题层级规范化 ----------
function normalizeHeadings(md, report) {
  // `\- ` 修正（MinerU 把列表项转义为 \-）
  md = md.replace(/^\\- /gm, '- ')
  const lines = md.split('\n')
  let glued = 0
  let demoted = 0
  let inIntro = false
  let seenSection = false // 自本章起是否已出现"第X节"（绪论等无节章节的"一、"保持 H2）
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i]
    // 独立成行的"思考题："（MinerU 漏掉标题标记）提升为 H2
    if (/^思考题\s*[：:]?\s*$/.test(l.trim())) { lines[i] = '## 思考题'; continue }
    if (!/^#{1,6}\s/.test(l)) continue
    if (/^#\s*第[一二三四五六七八九十百]+章/.test(l)) { seenSection = false; continue }
    if (/^##\s*第[一二三四五六七八九十百]+节/.test(l)) { seenSection = true }
    if (/^##\s*(主编简介|副主编简介)\s*$/.test(l)) { inIntro = true; continue }
    if (inIntro && /^##\s/.test(l)) {
      if (/^##\s*(前言|序言|编委|版权|目录|获取数字资源|读者信息反馈|第[一二三四五六七八九十百]+章)/.test(l)) inIntro = false
      if (inIntro && /^##\s+[\u3400-\u9fff]{1,4}(\s[\u3400-\u9fff]{1,2})?\s*$/.test(l)) {
        lines[i] = '### ' + l.replace(/^##\s+/, '')
        demoted++
        continue
      }
    }

    // 粘连标题拆分：`## N. 标题 正文。` → `##### N. 标题` + 正文行
    const glue = /^##\s+(\d+[\.、])\s*(\S{2,12}?)\s+(\S.*[。；，]$)/.exec(l)
    if (glue && !/[（(]/.test(glue[2])) {
      lines[i] = `##### ${glue[1]} ${glue[2]}`
      lines.splice(i + 1, 0, glue[3])
      glued++
      continue
    }

    // 节标题 `## 第X节 | Y` / 错误 H1 `# 第X节 | Y` → `## 第X节　Y`
    let m = /^(#{1,6})\s+(第[一二三四五六七八九十百]+节\s*)[|｜]\s*(.+)$/.exec(l)
    if (m) { lines[i] = `## ${m[2].replace(/\s+/g, '　')}${m[3]}`; continue }
    m = /^(#{1,6})\s+(第[一二三四五六七八九十百]+节)\s+(.+)$/.exec(l)
    if (m && m[1] !== '##') { lines[i] = `## ${m[2]}　${m[3]}`; continue }

    // 附：保留 H2（与样例 `## 附：维生素D 中毒` 一致）；【附N】也保留 H2
    if (/^##\s*(附[：:]|【附)/.test(l)) continue

    // 层级：一、→###（无节章节保持 ##）  （一）→####  1.→#####  (N)→#####  【】→####
    if (/^##\s+[一二三四五六七八九十]+、/.test(l)) {
      if (seenSection) lines[i] = '### ' + l.replace(/^##\s+/, '')
      continue
    }
    if (/^##\s+[（(][一二三四五六七八九十]+[）)]/.test(l)) {
      lines[i] = '#### ' + l.replace(/^##\s+/, '').replace(/[（(]/, '（').replace(/[）)]/, '）')
      continue
    }
    if (/^##\s+\d+[\.、]/.test(l)) { lines[i] = '##### ' + l.replace(/^##\s+/, ''); continue }
    if (/^##\s+[（(]\d+[）)]/.test(l)) { lines[i] = '##### ' + l.replace(/^##\s+/, ''); continue }
    if (/^##\s+【/.test(l)) { lines[i] = '#### ' + l.replace(/^##\s+/, ''); continue }
    if (/^##\s*思考题\s*[：:]/.test(l)) { lines[i] = '## 思考题'; continue }
    if (/\s[|｜]\s/.test(l)) lines[i] = l.replace(/\s[|｜]\s/g, '　')
  }
  // 重复的"主编/副主编简介"标题去重（同名标题全书只保留第一个）
  const out = []
  const seenIntro = new Set()
  for (const l of lines) {
    if (/^##\s*(主编简介|副主编简介)\s*$/.test(l)) {
      const k = l.trim()
      if (seenIntro.has(k)) continue
      seenIntro.add(k)
    }
    out.push(l)
  }
  report.steps.headings = { glued, demoted }
  return out.join('\n')
}

// ---------- 6) 目录锚点链接 ----------
function buildLinkedToc(md, report) {
  const lines = md.split('\n')
  const tocIdx = lines.findIndex((l) => /^#{1,6}\s*目录\s*$/.test(l.trim()))
  const firstCh = lines.findIndex((l) => /^#\s*第[一二三四五六七八九十百]+章/.test(l))
  if (tocIdx < 0 || firstCh < 0 || tocIdx > firstCh) return md

  const entries = []
  for (let i = firstCh; i < lines.length; i++) {
    const m = /^(#{1,6})\s+(.+?)\s*$/.exec(lines[i])
    if (!m) continue
    const level = m[1].length
    if (level > 3) continue
    const text = m[2]
    if (/^(思考题|【知识要点】|本章数字资源)/.test(text)) continue
    entries.push({ level, text, anchor: slug(text) })
  }

  const tocLines = ['# 目录', '']
  for (const e of entries) tocLines.push(`${'  '.repeat(e.level - 1)}- [${e.text}](#${e.anchor})`)
  tocLines.push('')

  const head = lines.slice(0, tocIdx).join('\n').replace(/[ \t]+$/gm, '').replace(/\n+$/, '').replace(/\s+$/, '')
  const newLines = head + '\n\n' + tocLines.join('\n') + '\n' + lines.slice(firstCh).join('\n')
  report.steps.toc = { entries: entries.length }
  return newLines
}

// ---------- 7) 图片处理：图注分组绑定 figX-Y(-a/-b…) + 二维码/小图剔除 + 缺失占位 ----------
// 规则（与《儿科学 第10版-p1-200.md》样例一致，见 校对差异清单-第5轮）：
//   - 带「图X-Y」图注的正文图 → 归档 images/figX-Y(.jpg)；多面板图(组内多张) → figX-Y + -a/-b/-c，与 (1)(2)/A/B/C/D 标签交错
//   - 无图注图片（封面/编者照片/logo）→ 剔除引用（文件在 Pass4 清理）
//   - 数字资源小图（二维码/视频缩略图/章节思维导图/数字人案例/三维模型/思考题解题思路/本章目标测试 等 ≈6KB）→ 剔除引用+标签行+文件
// 结构说明：MinerU 常见"图注在图片下方""多面板图拆分""二维码夹在图块中间"等错位，
//   因此采用"先剔二维码 → 再按就近图注归属分组"两段式处理，全部改名走临时名避免碰撞，幂等可重跑。
const JUNK_LABEL_RE = /^(思考题解题思路|本章目标测试|本章思维导图|三维模型|视频|动画|课件|案例分析|数字资源|思维导图|二维码|扫码|人卫APP|本章数字资源|获取数字资源|读者信息反馈|数字人案例\d*|数字人)$/

function processImages(md, imagesDir, report) {
  let lines = md.split('\n')
  const captionRe = /^图\s*(\d+)\s*[-－]\s*(\d+)\s*(.*)$/
  const isCaption = (l) => { const t = l.trim().replace(/^\*\*/, '').replace(/\*\*$/, ''); return captionRe.exec(t) }
  const imgRe = /^!\[[^\]]*\]\((images\/([^)\s]+))\)$/
  const hashRe = /^!\[[^\]]*\]\((images\/([a-f0-9]{16,})\.(\w+))\)$/
  const sigRe = /^[（(][\u3400-\u9fff\s]{2,12}[）)]$/
  const junkLabel = (l) => JUNK_LABEL_RE.test(l.trim())
  const nextNonBlank = (from) => { for (let i = from; i < lines.length; i++) if (lines[i].trim()) return i; return -1 }
  const prevNonBlank = (from) => { for (let i = from; i >= 0; i--) if (lines[i].trim()) return i; return -1 }
  const sizeOf = (name) => { try { return statSync(join(imagesDir, name)).size } catch { return 0 } }

  // 收集图注行与图片行（后续删除一律"置空"保索引稳定）
  const capIdx = []
  const imgIdx = []
  for (let i = 0; i < lines.length; i++) {
    if (isCaption(lines[i])) capIdx.push(i)
    const im = imgRe.exec(lines[i])
    if (im) imgIdx.push({ idx: i, name: im[2], ext: /\.(\w+)$/.exec(im[2])?.[1] || 'jpg' })
  }
  const hasCaptionNear = (idx, radius = 15) => capIdx.some((c) => Math.abs(c - idx) <= radius)
  const nearestCaptions = (idx) => {
    let above = -1, below = -1
    for (const c of capIdx) { if (c < idx) above = c; else if (c > idx) { below = c; break } }
    return { above, below }
  }

  const st = (report.steps.figures = report.steps.figures || {})

  // ---- Pass 1: 剔除二维码 / 数字资源小图 ----
  const junkReasons = {}
  for (const im of imgIdx) {
    if (!hashRe.test(lines[im.idx])) continue // fig* 视为已绑定，不在剔除范围
    const nxt = nextNonBlank(im.idx + 1)
    const prev = prevNonBlank(im.idx - 1)
    const nl = nxt >= 0 ? lines[nxt].trim() : ''
    const pl = prev >= 0 ? lines[prev].trim() : ''
    let reason = null
    if (nxt >= 0 && junkLabel(nl)) reason = 'label:' + nl
    else if (/^#{1,6}\s*思考题/.test(nl)) reason = 'before-思考题'
    else if (prev >= 0 && sigRe.test(pl)) reason = 'after-作者署名'
    else if (!hasCaptionNear(im.idx)) reason = '无图注(±15行)'
    else if (sizeOf(im.name) < 7000) reason = '小图(<7KB)'
    if (!reason) continue
    lines[im.idx] = ''
    // 连锁删除其后的二维码标签行（思考题解题思路 → 本章数字资源 …）
    if (nxt >= 0 && junkLabel(nl)) {
      for (let k = nxt; k < lines.length; k++) {
        const t = lines[k].trim()
        if (!t) continue
        if (junkLabel(t)) { lines[k] = ''; continue }
        break
      }
    }
    junkReasons[reason] = (junkReasons[reason] || 0) + 1
  }
  st.junkRemoved = Object.values(junkReasons).reduce((a, b) => a + b, 0)
  st.junkReasons = junkReasons

  // ---- Pass 1.5: 清理孤立数字资源标签行（本章数字资源 等，均为已删二维码的图注） ----
  let junkLabelsCleaned = 0
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() && junkLabel(lines[i])) { lines[i] = ''; junkLabelsCleaned++ }
  }
  st.junkLabelsCleaned = junkLabelsCleaned

  // ---- Pass 2: 按就近图注归属分组并绑定 figX-Y(-a/-b…) ----
  // 归属规则（优先级）：
  //   1) 图与其下方图注之间存在 `[figX-Y]` 占位符 → 强制归属下方图注（旧逻辑"图注在图片下方"的最强标记）
  //   2) 下方图注更近或等距 → 归下方（MinerU 图注在图片下方为常态）
  //   3) 上方图注更近：仅当本图紧贴上方图注之后、且其面板编号延续上方图组最后一张图的编号
  //      （如 (1)滑脱法 → (2)旋转胎体法）才归上方，否则归下方
  //      （图12-5 的图紧贴图12-4 图注之后但编号从 1 重新开始 → 归下方）
  const numOf = (l) => {
    const t = l.trim()
    let m = /^[（(]?(\d+)[）)]?[.、．]?\s/.exec(t)
    if (m) return { n: parseInt(m[1], 10) }
    m = /^([A-Z])$/.exec(t)
    if (m) return { n: m[1].charCodeAt(0) }
    return null
  }
  const owner = new Map()
  for (const im of imgIdx) {
    if (!lines[im.idx]) continue
    const { above, below } = nearestCaptions(im.idx)
    let own = -1
    if (below >= 0) {
      const bm = isCaption(lines[below])
      if (bm) {
        const keyBelow = `fig${bm[1]}-${bm[2]}`
        for (let j = im.idx + 1; j <= below; j++) {
          if (lines[j].trim() === `[${keyBelow}]`) { own = below; break }
        }
      }
    }
    if (own < 0) {
      if (above < 0) own = below
      else if (below < 0) own = above
      else {
        const da = im.idx - above, db = below - im.idx
        if (db <= da) own = below
        else if (da < db) {
          const nn = nextNonBlank(above + 1)
          let toAbove = false
          if (nn === im.idx) {
            // 本图紧跟上方图注：编号延续检查
            const lb = nextNonBlank(im.idx + 1)
            const cur = lb >= 0 ? numOf(lines[lb]) : null
            let prevImg = -1
            for (let j = above - 1; j >= 0; j--) { if (imgRe.test(lines[j])) { prevImg = j; break } }
            let prev = null
            if (prevImg >= 0) { const pl2 = nextNonBlank(prevImg + 1); prev = pl2 >= 0 ? numOf(lines[pl2]) : null }
            if (cur && prev && cur.n === prev.n + 1) toAbove = true
          }
          own = toAbove ? above : below
        } else own = below
      }
    }
    if (own < 0) continue
    if (!owner.has(own)) owner.set(own, [])
    owner.get(own).push({ ...im })
  }

  const bound = []
  let placeholdersRemoved = 0
  for (const [ci, members] of owner) {
    const m = isCaption(lines[ci])
    if (!m) continue
    const key = `fig${m[1]}-${m[2]}`
    const group = [...members].sort((a, b) => a.idx - b.idx)
    const targets = group.map((g, k) => (k === 0 ? `${key}` : `${key}-${String.fromCharCode(96 + k)}`) + `.${g.ext}`)
    const already = group.every((g, k) => g.name === targets[k])
    if (!already) {
      // 碰撞安全：先全部改名到临时名，再改到目标名（避免 figX-Y.jpg 被另一成员占用）
      const tmps = group.map((g, k) => (g.name !== targets[k] ? `${key}.tmp${k}.${g.ext}` : null))
      group.forEach((g, k) => { if (tmps[k]) { try { renameSync(join(imagesDir, g.name), join(imagesDir, tmps[k])) } catch {} } })
      group.forEach((g, k) => { if (tmps[k]) { try { renameSync(join(imagesDir, tmps[k]), join(imagesDir, targets[k])) } catch {} } })
      group.forEach((g, k) => { lines[g.idx] = `![图${m[1]}-${m[2]}](images/${targets[k]})` })
      bound.push({ key, n: group.length })
    }
    // 移除本图占位符 [figX-Y]（上方或下方 3 行内，兼容早期版本误插到图注下方的情况）
    for (let j = ci - 1; j >= Math.max(0, ci - 3); j--) {
      if (lines[j].trim() === `[${key}]`) { lines[j] = ''; placeholdersRemoved++; break }
    }
    for (let j = ci + 1; j <= Math.min(ci + 3, lines.length - 1); j++) {
      if (lines[j].trim() === `[${key}]`) { lines[j] = ''; placeholdersRemoved++; break }
    }
  }
  st.groupsBound = bound.length
  st.imagesBound = bound.reduce((a, b) => a + b.n, 0)
  st.placeholdersRemoved = placeholdersRemoved

  // ---- Pass 3: 无图图注补占位符 + 图注统一加粗 ----
  const ownedByCaption = new Set(owner.keys())
  const out3 = []
  let placeholdersInserted = 0
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]
    const m = isCaption(raw)
    if (!m) { out3.push(raw); continue }
    const key = `fig${m[1]}-${m[2]}`
    // 无图图注 → 占位符插在图注上方（与旧版一致）；有图图注 → 仅补加粗
    let needsPh = false
    if (!ownedByCaption.has(i)) {
      let hasPh = false
      for (let j = i - 1; j >= Math.max(0, i - 3); j--) {
        const t = lines[j].trim()
        if (!t) continue
        if (t === `[${key}]`) hasPh = true
        break
      }
      if (!hasPh) needsPh = true
    }
    if (needsPh) { out3.push(`[${key}]`); placeholdersInserted++ }
    // 图注加粗（幂等：已加粗则保持原样）
    if (!/^\*\*/.test(raw.trim())) {
      const title = (m[3] || '').trim().replace(/\s+/g, ' ')
      out3.push(`**图${m[1]}-${m[2]}　${title}**`)
    } else {
      out3.push(raw)
    }
  }
  lines = out3
  st.placeholdersInserted = placeholdersInserted

  // ---- Pass 4: 清理未被引用的图片文件（哈希原图副本/封面图/已剔除小图） ----
  const text = lines.join('\n')
  const refSet = new Set()
  for (const mm of text.matchAll(/images\/([^)\s]+)/g)) refSet.add(mm[1])
  let filesDeleted = 0
  let imgFiles = []
  try { imgFiles = readdirSync(imagesDir) } catch {}
  for (const f of imgFiles) {
    if (!/\.(jpg|jpeg|png|webp|gif)$/i.test(f)) continue
    if (refSet.has(f)) continue
    try { unlinkSync(join(imagesDir, f)); filesDeleted++ } catch {}
  }
  st.filesDeleted = filesDeleted

  return lines.join('\n')
}

// ---------- CLI ----------
async function main() {
  const [libraryDir, book, bookmarksPath, pdfPath] = process.argv.slice(2)
  if (!libraryDir || !book) {
    console.error('用法: node polish-book.mjs <libraryDir> <book> [bookmarks.json] [pdfPath]')
    process.exit(2)
  }
  try {
    const r = polishBook({ libraryDir, book, bookmarksPath, pdfPath })
    console.log(JSON.stringify(r, null, 1))
    console.log('POLISH=OK')
  } catch (e) {
    console.error('POLISH_FAIL', e.message)
    process.exit(1)
  }
}
if (process.argv[1] && import.meta.url === new URL('file:///' + process.argv[1].replace(/\\/g, '/')).href) main()
