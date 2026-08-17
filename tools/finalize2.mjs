// finalize2.mjs — 重建 _library_index.md（含 polish 后的章节标题）
import { writeFileSync } from 'node:fs'
import { scanMd } from '../bridge/medlib-bridge.mjs'

// 用法: node finalize2.mjs [libraryDir]  或  MEDLIB_LIB=<libraryDir> node finalize2.mjs
const LIB = process.env.MEDLIB_LIB || process.argv[2]
if (!LIB) { console.error('FINALIZE2_ERR: need libraryDir (argv[2] or MEDLIB_LIB)'); process.exit(1) }
const books = scanMd({ libraryDir: LIB })
const lines = []
lines.push('# 医学教材 Markdown 文库')
lines.push('')
lines.push('> 由 MinerU 云端解析生成 · ' + new Date().toISOString().slice(0, 10))
lines.push('')
lines.push('| 书名 | 大小 | 章节数 |')
lines.push('| --- | --- | --- |')
for (const b of books) lines.push('| ' + b.book + ' | ' + Math.round(b.size / 1024) + ' KB | ' + b.headings.length + ' |')
lines.push('')
for (const b of books) {
  lines.push('## ' + b.book)
  lines.push('')
  lines.push('`' + b.md + '`')
  lines.push('')
  for (const h of b.headings.slice(0, 200)) lines.push(h)
  lines.push('')
}
writeFileSync(LIB + '/_library_index.md', lines.join('\n'))
console.log('INDEX_REBUILT books:', books.length)
for (const b of books) console.log(' -', b.book, Math.round(b.size / 1024) + 'KB', b.headings.length, 'headings')
console.log('FINALIZE2=OK')
