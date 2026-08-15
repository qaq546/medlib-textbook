// medlib plugin — Host half. Medical textbook digitalization via MinerU cloud API.
// Plain JS for the dynamic Cordis plugin sandbox. Orchestrates the node bridge.
return {
  inject: ['fs', 'shell'],
  apply(ctx) {
    const fs = ctx.fs
    const shell = ctx.shell

    // ---------- configuration (workspace-local defaults; overridable via medlib_setup) ----------
    const WORKSPACE = 'F:/Develop/DeepSeek-Harness/Agent/Plugins'
    // Sandbox temp dir — writable under ANY workspace-write policy (os.tmpdir()).
    const TMP = 'C:/Users/fu\'bi\'yan/AppData/Local/Temp/dsh-D1L5fg'
    const DEFAULT = {
      bridge: 'F:/Develop/DeepSeek-Harness/Agent/Plugins/medlib-proto/medlib-bridge.mjs',
      workDir: 'F:/Develop/DeepSeek-Harness/Agent/Plugins/medlib-proto/work',
      libraryDir: 'F:/Develop/DeepSeek-Harness/Agent/Plugins/medlib-library',
      configFile: 'F:/Develop/DeepSeek-Harness/Agent/Plugins/medlib-proto/config.json',
    }
    const EXT = /\.(pdf|docx?|pptx?|xlsx?|png|jpe?g|webp|gif|bmp|jp2)$/i
    // workspace-write + explicit root: session workspace for workspace files,
    // user-chosen library dir for library files (dir must pre-exist).
    const sessionPolicy = () => ({ mode: 'workspace-write', workspaceRoot: WORKSPACE })
    const libraryPolicy = (cfg) => ({ mode: 'workspace-write', workspaceRoot: cfg.libraryDir })

    const readJson = async (path, fallback) => {
      try { return JSON.parse(await fs.readText(await fs.resolve(path))) } catch { return fallback }
    }
    const writeJson = async (path, obj, pol) => {
      await fs.writeText(await fs.resolve(path), JSON.stringify(obj, null, 2), undefined, undefined, pol || sessionPolicy())
    }
    const readConfig = async () => ({ ...DEFAULT, ...(await readJson(DEFAULT.configFile, {})) })
    const readToken = async (cfg) => {
      try { return (await fs.readText(await fs.resolve(cfg.libraryDir + '/.medlib-token'))).trim() } catch { return '' }
    }
    const statePath = (cfg) => cfg.libraryDir + '/library.json'
    const readState = async (cfg) => readJson(statePath(cfg), { version: 1, books: {}, tasks: {} })
    const writeState = async (cfg, st) => writeJson(statePath(cfg), st, libraryPolicy(cfg))

    const runBridge = async (cfg, verb, args, { timeoutMs = 120000, token, policy = 'session' } = {}) => {
      const stamp = Date.now() + '-' + Math.floor(Math.random() * 1e6)
      const pol = policy === 'library' ? libraryPolicy(cfg) : sessionPolicy()
      // args go to the sandbox temp dir (writable under any workspace-write policy);
      // the bridge returns its result JSON on stdout — no output file needed.
      const argsPath = TMP + '/medlib-args-' + stamp + '.json'
      await fs.writeText(await fs.resolve(argsPath), JSON.stringify(args), undefined, undefined, pol)
      const env = token ? { MINERU_TOKEN: token } : undefined
      const spec = shell.resolve({
        command: 'node "' + cfg.bridge + '" ' + verb + ' "' + argsPath + '"',
        workdir: cfg.workDir,
        timeoutMs,
        env,
        stdoutMaxBytes: 8 * 1024 * 1024,
        sandboxPolicy: pol,
      })
      const res = await shell.run(spec)
      const text = (res.stdout && res.stdout.text) || ''
      let out = null
      try { out = JSON.parse(text) } catch {}
      if (!out) throw new Error('bridge ' + verb + ' produced no output (exit ' + res.exitCode + ', stderr: ' + String((res.stderr && res.stderr.text) || '').slice(0, 500) + ')')
      return out
    }

    let _tokenCache = ''
    const refreshToken = async (cfg) => { _tokenCache = await readToken(cfg); return _tokenCache }

    const ok = (obj) => Object.assign({ ok: true }, obj)
    const bad = (code, msg) => ({ ok: false, error: { code, msg } })

    // ---------- tool helper ----------
    const makeTool = (name, description, parameters, execute, render) => {
      const tool = harness.defineTool({
        name,
        description,
        parameters,
        output: {
          schema: { type: 'json' },
          render: (args, value) => [{ type: 'text', text: render ? render(args, value) : JSON.stringify(value, null, 2) }],
        },
        execute,
      })
      return harness.registerTool(ctx, tool)
    }

    // ---------- tools ----------

    // medlib_setup: store token (+ optional library dir)
    makeTool(
      'medlib_setup',
      '配置医学教材文库:保存 MinerU API Token(必填)与文库根目录(可选,默认 F:/Develop/DeepSeek-Harness/Agent/Plugins/medlib-library)。Token 获取: https://mineru.net/apiManage/token',
      {
        token: { type: 'string', description: 'MinerU API Token(Bearer 后面的部分)', required: true },
        libraryDir: { type: 'string', description: '文库根目录(可省略,用默认值)' },
      },
      async (args) => {
        const cfg = await readConfig()
        if (args.libraryDir) {
          cfg.libraryDir = String(args.libraryDir).replace(/[\\/]+$/, '')
          await writeJson(DEFAULT.configFile, { bridge: cfg.bridge, workDir: cfg.workDir, libraryDir: cfg.libraryDir })
          await runBridge(cfg, 'mkdir', { path: cfg.libraryDir }, { timeoutMs: 30000, policy: 'library' })
        }
        await runBridge(cfg, 'mkdir', { path: cfg.libraryDir }, { timeoutMs: 30000, policy: 'library' })
        await fs.writeText(await fs.resolve(cfg.libraryDir + '/.medlib-token'), String(args.token).trim(), undefined, undefined, libraryPolicy(cfg))
        await writeJson(statePath(cfg), { version: 1, books: {}, tasks: {} }, libraryPolicy(cfg))
        _tokenCache = String(args.token).trim()
        return ok({ libraryDir: cfg.libraryDir, tokenSaved: true, hint: '现在可以调用 medlib_convert 转换教材了' })
      }
    )

    // medlib_convert: upload + create tasks
    makeTool(
      'medlib_convert',
      '把教材文件(PDF/DOCX/PPTX/XLSX/图片,支持文件夹)通过 MinerU 云端 API 转 Markdown。返回任务列表,然后用 medlib_poll 查进度、medlib_fetch 拉取结果。超过 200 页的 PDF 会自动分片。',
      {
        paths: { type: 'array', items: { type: 'string' }, description: '教材文件或文件夹的路径(可多个)', required: true },
        ocr: { type: 'boolean', description: '扫描版 PDF 需要 OCR 时设为 true(默认 false)' },
        language: { type: 'string', enum: ['ch', 'en'], description: 'OCR 语言,默认 ch' },
        modelVersion: { type: 'string', enum: ['vlm', 'pipeline'], description: '解析模型,默认 vlm' },
        pageChunk: { type: 'integer', description: '超过该页数自动分片,默认 200(云端单文件上限)' },
      },
      async (args) => {
        const cfg = await readConfig()
        const token = await refreshToken(cfg)
        if (!token) return bad('NO_TOKEN', '请先调用 medlib_setup 保存 MinerU API Token')
        const pageChunk = args.pageChunk || 200
        const st = await readState(cfg)

        // 1) collect files
        const files = []
        for (const p of args.paths) {
          const ls = await runBridge(cfg, 'ls', { path: p, depth: 6 }, { timeoutMs: 60000 })
          if (!ls.ok) return bad('LS_FAIL', ls.error ? ls.error.msg : '无法读取路径: ' + p)
          const dirs = ls.files.filter((f) => f.size !== undefined).map((f) => f.path)
          for (const f of dirs) if (EXT.test(f)) files.push(f)
        }
        if (!files.length) return bad('NO_FILES', '没有找到支持的教材文件(pdf/doc/docx/ppt/pptx/xls/xlsx/图片)')

        // 2) plan chunks per file
        const plan = [] // { path, book, dataId, chunks: [{ pageRanges? }] }
        for (const f of files) {
          const book = sanitizeBook(basename(f).replace(extname(f), ''))
          const done = st.books[book] && st.books[book].merged
          if (done) continue
          let chunks = [{}]
          if (/\.pdf$/i.test(f)) {
            const pp = await runBridge(cfg, 'pdf-pages', { path: f }, { timeoutMs: 60000 })
            const pages = pp.estimate || 1
            if (pages > pageChunk) {
              chunks = []
              for (let s = 1; s <= pages; s += pageChunk) chunks.push({ pageRanges: s + '-' + Math.min(s + pageChunk - 1, pages) })
            }
          }
          plan.push({ path: f, book, dataId: book + '-' + chunks.length, chunks })
        }
        if (!plan.length) return ok({ submitted: 0, skipped: files.length, message: '这些文件都已在文库中(已合并),跳过' })

        // 3) request upload urls for every chunk entry (<=40 per call) and PUT.
        //    The service AUTO-submits parse tasks once upload completes.
        const entries = [] // { path, book, dataId, pageRanges, chunkLabel }
        let entryN = 0
        for (const item of plan) {
          for (const chunk of item.chunks) {
            const chunkLabel = chunk.pageRanges ? 'p' + chunk.pageRanges : null
            entries.push({ path: item.path, book: item.book, dataId: 'f' + entryN++, pageRanges: chunk.pageRanges, chunkLabel })
          }
        }
        const tasks = []
        for (let i = 0; i < entries.length; i += 40) {
          const slice = entries.slice(i, i + 40)
          const u = await runBridge(cfg, 'st-upload-urls', {
            token, modelVersion: args.modelVersion || 'vlm',
            enableFormula: true, enableTable: true, language: args.language || 'ch',
            files: slice.map((x) => ({ name: basename(x.path), dataId: x.dataId, pageRanges: x.pageRanges, isOcr: !!args.ocr })),
          }, { timeoutMs: 60000, token })
          if (!u.ok) return bad('UPLOAD_FAIL', u.error ? u.error.msg : '上传地址获取失败')
          for (let j = 0; j < slice.length; j++) {
            const put = await runBridge(cfg, 'st-put', { url: u.urls[j], path: slice[j].path }, { timeoutMs: 15 * 60 * 1000, token })
            if (!put.ok) return bad('PUT_FAIL', slice[j].path + ': ' + (put.error ? put.error.msg : '上传失败'))
          }
          for (const x of slice) {
            const taskId = u.batchId + '#' + x.dataId
            const task = {
              taskId, batchId: u.batchId, dataId: x.dataId, entryIdx: 0, book: x.book, source: x.path,
              pageRange: x.pageRanges || null, chunkLabel: x.chunkLabel,
              state: 'created', errMsg: '', fullZipUrl: '', fetched: false, createdAt: Date.now(),
            }
            st.tasks[taskId] = task
            if (!st.books[x.book]) st.books[x.book] = { sourceFile: x.path, chunks: [], merged: false, mdPath: null }
            st.books[x.book].chunks.push(taskId)
            tasks.push(task)
          }
        }
        await writeState(cfg, st)
        return ok({
          submitted: tasks.length, books: Object.keys(st.books),
          tasks: tasks.map((t) => ({ taskId: t.taskId, book: t.book, pageRange: t.pageRange })),
          next: '调用 medlib_poll 查看进度,完成后 medlib_fetch 拉取',
        })
      }
    )

    // medlib_poll
    makeTool(
      'medlib_poll',
      '查询 MinerU 云端任务进度。不带参数时查询文库中所有未完成任务。',
      {
        taskIds: { type: 'array', items: { type: 'string' }, description: '可选: 只查询这些任务' },
      },
      async (args) => {
        const cfg = await readConfig()
        const token = await refreshToken(cfg)
        if (!token) return bad('NO_TOKEN', '请先调用 medlib_setup 保存 MinerU API Token')
        const st = await readState(cfg)
        const want = new Set(args.taskIds || [])
        const pending = Object.values(st.tasks).filter((t) => !t.fetched && (want.size === 0 || want.has(t.taskId)))
        if (!pending.length) return ok({ done: true, counts: { done: 0, failed: 0, pending: 0 }, message: '没有待查询的任务' })

        const byBatch = {}
        for (const t of pending) (byBatch[t.batchId] = byBatch[t.batchId] || []).push(t)
        const counts = { done: 0, failed: 0, pending: 0 }
        const failed = []
        for (const batchId of Object.keys(byBatch)) {
          const r = await runBridge(cfg, 'st-poll-batch', { token, batchId }, { timeoutMs: 90000, token })
          if (!r.ok) { for (const t of byBatch[batchId]) { t.state = 'poll-error'; counts.pending++ } continue }
          const entries = (r.data && r.data.extract_result) || []
          for (const t of byBatch[batchId]) {
            const e = entries.find((x) => x.data_id === t.dataId) || {}
            const stt = e.state || ''
            if (stt === 'done') { t.state = 'done'; t.fullZipUrl = e.full_zip_url || ''; counts.done++ }
            else if (stt === 'failed' || stt === 'error') { t.state = 'failed'; t.errMsg = e.err_msg || ''; counts.failed++; failed.push({ taskId: t.taskId, book: t.book, errMsg: t.errMsg }) }
            else { t.state = stt || 'running'; counts.pending++ }
          }
        }
        await writeState(cfg, st)
        return ok({ counts, failed, tasks: pending.map((t) => ({ taskId: t.taskId, book: t.book, state: t.state, pageRange: t.pageRange })) })
      }
    )

    // medlib_fetch
    makeTool(
      'medlib_fetch',
      '下载并整理已完成的任务:Markdown 归入 <文库>/<书名>/,图片归入 <文库>/<书名>/images/,多分片自动合并,并重建 _library_index.md。',
      {
        taskIds: { type: 'array', items: { type: 'string' }, description: '可选: 只拉取这些任务' },
      },
      async (args) => {
        const cfg = await readConfig()
        const token = await refreshToken(cfg)
        if (!token) return bad('NO_TOKEN', '请先调用 medlib_setup 保存 MinerU API Token')
        const st = await readState(cfg)
        const want = new Set(args.taskIds || [])
        const ready = Object.values(st.tasks).filter((t) => t.state === 'done' && !t.fetched && (want.size === 0 || want.has(t.taskId)))
        if (!ready.length) return ok({ fetched: 0, message: '没有可拉取的已完成任务(先 medlib_poll)' })

        const fetched = []
        const mergedBooks = []
        for (const t of ready) {
          const dest = cfg.libraryDir + '/.tmp/' + t.taskId
          const fr = await runBridge(cfg, 'st-fetch-one', { token, fullZipUrl: t.fullZipUrl, destDir: dest }, { timeoutMs: 15 * 60 * 1000, token, policy: 'library' })
          if (!fr.ok) { t.state = 'fetch-error'; t.errMsg = fr.error ? fr.error.msg : '下载失败'; await runBridge(cfg, 'rm', { path: dest }, { timeoutMs: 30000, policy: 'library' }); continue }
          const ar = await runBridge(cfg, 'st-arrange', { libraryDir: cfg.libraryDir, book: t.book, chunkLabel: t.chunkLabel, srcDir: dest }, { timeoutMs: 60000, policy: 'library' })
          if (!ar.ok) { t.state = 'arrange-error'; t.errMsg = ar.error ? ar.error.msg : '整理失败'; await runBridge(cfg, 'rm', { path: dest }, { timeoutMs: 30000, policy: 'library' }); continue }
          await runBridge(cfg, 'rm', { path: dest }, { timeoutMs: 30000, policy: 'library' })
          t.fetched = true
          fetched.push({ book: t.book, chunk: t.chunkLabel || 'whole', md: ar.mdDest, images: ar.imageCount })
        }
        // merge fully-fetched books
        const bookTaskCount = {}
        for (const t of Object.values(st.tasks)) { bookTaskCount[t.book] = (bookTaskCount[t.book] || 0) + 1 }
        const fetchedBooks = [...new Set(fetched.map((x) => x.book))]
        for (const b of fetchedBooks) {
          const allDone = Object.values(st.tasks).filter((t) => t.book === b).every((t) => t.fetched || t.state === 'failed')
          if (allDone) {
            const mg = await runBridge(cfg, 'merge-book', { libraryDir: cfg.libraryDir, book: b }, { timeoutMs: 60000, policy: 'library' })
            if (mg.ok && st.books[b]) { st.books[b].merged = true; st.books[b].mdPath = mg.merged; mergedBooks.push({ book: b, mdPath: mg.merged, chunks: mg.chunkFiles }) }
          }
        }
        await writeState(cfg, st)
        // clean scratch/tmp leftovers
        await runBridge(cfg, 'clean', { dir: cfg.libraryDir }, { timeoutMs: 30000, policy: 'library' })
        // rebuild index
        const idx = await buildIndex(cfg)
        return ok({ fetched, merged: mergedBooks, indexUpdated: idx, next: '可用 medlib_search 检索文库' })
      }
    )

    // medlib_search
    makeTool(
      'medlib_search',
      '在已转换的 Markdown 文库中全文检索关键字,返回命中的书名、文件、行号与上下文。',
      {
        query: { type: 'string', description: '检索关键字', required: true },
        book: { type: 'string', description: '可选: 限定某一本书' },
        maxResults: { type: 'integer', description: '最多返回条数,默认 20' },
      },
      async (args) => {
        const cfg = await readConfig()
        const r = await runBridge(cfg, 'search', { libraryDir: cfg.libraryDir, query: args.query, book: args.book, maxResults: args.maxResults || 20 }, { timeoutMs: 90000 })
        if (!r.ok) return bad('SEARCH_FAIL', r.error ? r.error.msg : '检索失败')
        return ok({ query: args.query, total: r.total, hits: r.hits })
      }
    )

    // medlib_index
    makeTool(
      'medlib_index',
      '重建文库索引 _library_index.md(书单 + 各书标题/章节目录),并清理临时文件。',
      {},
      async () => {
        const cfg = await readConfig()
        await runBridge(cfg, 'clean', { dir: cfg.libraryDir }, { timeoutMs: 30000, policy: 'library' })
        const idx = await buildIndex(cfg)
        return ok({ indexUpdated: idx, libraryDir: cfg.libraryDir })
      }
    )

    // medlib_trim: drop tiny images (avatars/logos/icons) from a book's markdown
    makeTool(
      'medlib_trim',
      '清理书籍里被误识别的小图片(头像/logo/图标):删除小于 minBytes 的图片文件及其在 Markdown 中的引用,并重建索引。默认 8KB。',
      {
        book: { type: 'string', description: '可选: 只处理某一本书' },
        minBytes: { type: 'integer', description: '小于该字节数的图片将被删除,默认 8192 (8KB)' },
      },
      async (args) => {
        const cfg = await readConfig()
        const r = await runBridge(cfg, 'trim-images', { libraryDir: cfg.libraryDir, book: args.book, minBytes: args.minBytes || 8192 }, { timeoutMs: 90000, policy: 'library' })
        if (!r.ok) return bad('TRIM_FAIL', r.error ? r.error.msg : '清理失败')
        const idx = await buildIndex(cfg)
        return ok({ report: r.report, indexUpdated: idx })
      }
    )

    // ---------- index builder (plugin-side, pure text) ----------
    const buildIndex = async (cfg) => {
      try {
        const r = await runBridge(cfg, 'scan-md', { libraryDir: cfg.libraryDir }, { timeoutMs: 90000 })
        if (!r.ok) return false
        const books = r.books || []
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
        await fs.writeText(await fs.resolve(cfg.libraryDir + '/_library_index.md'), lines.join('\n'), undefined, undefined, libraryPolicy(cfg))
        return true
      } catch (e) { return false }
    }

    // ---------- small string helpers ----------
    const basename = (p) => { const parts = String(p).replace(/[\\/]+$/, '').split(/[\\/]/); return parts[parts.length - 1] || 'unnamed' }
    const extname = (p) => { const m = /(\.[^.\\/]+)$/.exec(basename(p)); return m ? m[1].toLowerCase() : '' }
    const sanitizeBook = (s) => String(s).replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_').replace(/\s+/g, ' ').trim().slice(0, 120) || 'unnamed'
  },
}
