// gen-pdf.mjs — create a simple N-page ASCII PDF (for chunking tests).
// Usage: node gen-pdf.mjs <pages> <outPath>
import { writeFileSync } from 'node:fs'
const n = Math.max(1, parseInt(process.argv[2] || '3', 10))
const out = process.argv[3] || 'gen.pdf'

let pdf = '%PDF-1.4\n'
const offsets = [0]
const addObj = (body) => { offsets.push(pdf.length); pdf += `${offsets.length - 1} 0 obj\n${body}\nendobj\n` }

addObj('<< /Type /Catalog /Pages 2 0 R >>')
addObj('<< /Type /Pages /Kids [' + Array.from({ length: n }, (_, i) => `${3 + i} 0 R`).join(' ') + '] /Count ' + n + ' >>')
for (let i = 0; i < n; i++) addObj(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents ${3 + n + i} 0 R /Resources << /Font << /F1 ${3 + 2 * n} 0 R >> >> >>`)
for (let i = 0; i < n; i++) {
  const s = `BT /F1 24 Tf 72 720 Td (Synthetic page ${i + 1} of ${n}) Tj ET`
  addObj(`<< /Length ${s.length} >>\nstream\n${s}\nendstream`)
}
addObj('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')

const xrefPos = pdf.length
let xref = 'xref\n0 ' + offsets.length + '\n0000000000 65535 f \n'
for (let i = 1; i < offsets.length; i++) xref += String(offsets[i]).padStart(10, '0') + ' 00000 n \n'
pdf += xref
pdf += `trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xrefPos}\n%%EOF\n`

writeFileSync(out, Buffer.from(pdf, 'latin1'))
console.log('wrote', out, 'pages:', n, 'bytes:', pdf.length)
