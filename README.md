# MedLib Textbook · 医学教材电子化工具集

> 把医学教材(PDF / PPT / Word / 图片)通过 **MinerU 云端 API** 自动转换为结构化 **Markdown 文库**:图片独立归档、表格 / 公式 / 上下标完整保留、超过 200 页的大部头自动分片合并、全文可检索、断点续转;另附一套**校对重构流水线**,可对照原版 PDF 文本层逐字校对、修复 OCR 错字、重建标题层级、将 HTML 表格转为标准 Markdown。

- 零依赖:桥接脚本为单个 Node 文件(无任何 npm 包),脚本语言为 Node ≥ 18
- 云端算力:MinerU `vlm` 解析模型,无需本地 GPU,注册即送**每日 1000 页免费额度**
- 已在真实教材验证:人民卫生出版社《儿科学(第 10 版)》498 页 / 23.9MB 完整转换,自动分 3 片处理并合并,输出 1.9MB Markdown + 248 张图片,全文检索可用

---

## ✨ 功能特性

| 能力 | 说明 |
|---|---|
| 多格式输入 | pdf / docx / pptx / xlsx / 常见图片;扫描版 PDF 可选 OCR(`isOcr`) |
| 自动分片 | 单文件 > 200 页按 200 页一档切分(`1-200`、`201-400`…),拉取后按页序自动合并 |
| 公式 / 表格 | 开启 `enable_formula` / `enable_table`,化学式、表格结构完整保留 |
| 文库规范 | `<文库>/<书名>/<书名>.md` + `<书名>/images/`,相对路径引用,Obsidian / VS Code 直接可用 |
| 断点续转 | 任务状态持久化在 `<文库>/library.json`,中途失败可从 `medlib_poll` 续查 |
| 全文检索 | 按关键字检索命中的书、文件、行号与上下文(精确到行) |
| 图片瘦身 | `trim-images` 清理头像 / logo / 图标等误识别小图(默认 < 8KB)并同步移除引用 |
| 校对重构 | `medfix.py` 对照原版 PDF 文本层逐字校对,修复 OCR 错字 / 断词 / 缺文,重建「章/节/条/项/细分」五级标题,HTML 表格转 GFM,图注标准化,按官方书签重建带锚点与页码的目录 |
| Harness 集成 | 提供 DeepSeek Harness(DSH)动态插件源码与 Agent Preset,7 个 medlib_* 工具开箱即用 |

---

## 📁 目录结构

```
medlib-textbook/
├── bridge/
│   └── medlib-bridge.mjs        # 零依赖 Node 桥接 CLI(核心,可独立使用)
├── plugin/
│   └── plugin-host.js           # DSH 动态插件宿主源码(注册 7 个 medlib_* 工具)
├── preset/                      # DSH Agent Preset(一键挂载)
│   ├── preset.yml
│   ├── agent.cordis.yml
│   ├── skills/med-textbook/SKILL.md
│   └── assets/medlib-bridge.mjs # 随 preset 分发的桥接脚本副本
├── tools/
│   ├── medfix.py                # Markdown 校对重构流水线(需 PyMuPDF)
│   └── gen-pdf.mjs              # 合成 PDF 测试工具(验证分片/合并)
├── docs/
│   └── MINERU_API.md            # MinerU 云端 API 对接要点与踩坑记录
├── config.example.json          # 配置模板(请复制为 config.json 并改为本机路径)
├── LICENSE                      # MIT
└── README.md
```

---

## 🚀 快速开始

### 1. 获取 MinerU API Token

注册 MinerU 开放平台:https://mineru.net/apiManage/token
(注册即送每日 1000 页免费额度,优先级最高;Token 形如 `sk-xxxx`)

### 2. 配置

Token 有两种传入方式(任选其一):

- 环境变量:

  ```bash
  export MINERU_TOKEN="sk-xxxx"
  ```

- Token 文件:在文库根目录放一个 `.medlib-token` 文件(仅一行 Token)。
  DSH 插件中运行 `medlib_setup { token }` 即可自动写入并创建文库目录。

文库根目录(默认 `./library`,可自定义)与 `config.json` 见 [`config.example.json`](config.example.json)。

### 3. 转换一本教材(命令行方式,不依赖 DSH)

```bash
# ① 列出待转换文件
node bridge/medlib-bridge.mjs ls "/path/to/教材.pdf"

# ② 申请上传链接(>200 页会自动给出分片参数,见下方工作流)
#    实际使用建议直接走「转换工作流」一节中的五步,或使用 DSH 插件的 medlib_convert
```

> 桥接 CLI 的完整用法见下文「📖 命令行用法」与「🔄 转换工作流」。

### 4. 转换一本教材(DSH 方式)

1. 复制 `preset/` 到 `$HOME/.dsh/.agent-presets/med-textbook/`(Windows:`C:\Users\<你>\.dsh\.agent-presets\med-textbook\`)
2. 重启 DSH,新建会话并选择 **「医学教材电子化」** preset
3. 会话内直接调用 `medlib_setup` → `medlib_convert` → `medlib_poll` → `medlib_fetch`,或让 Agent 按 `SKILL.md` 的工作流执行

> 动态插件 `plugin/plugin-host.js` 供自建 DSH 插件使用;其中的工作区 / 临时目录 / 桥接路径为作者本机值,按需改为你自己的路径(见文件头部 `WORKSPACE`、`TMP`、`DEFAULT` 常量)。

---

## 📖 命令行用法(bridge)

调用约定:每个动词接收一个 UTF-8 JSON 参数文件,结果以 JSON 打印到 stdout,无任何第三方依赖:

```bash
node bridge/medlib-bridge.mjs <verb> <args.json>
# 便捷形式:ls / pdf-pages 可直接传裸路径
node bridge/medlib-bridge.mjs ls "/path/to/file-or-dir"
```

| 动词 | 作用 | 关键参数 |
|---|---|---|
| `ls` | 列出文件或目录内容 | `path` |
| `mkdir` / `rm` | 建目录 / 递归删除 | `path` |
| `clean` | 清理 `.tmp` 与 `.medlib-*` 残留(绝不删 `.medlib-token`) | `dir` |
| `pdf-pages` | 启发式估算 PDF 页数(用于分片决策) | `path` |
| `trim-images` | 删除小于阈值的图片及其 md 引用 | `libraryDir, book?, minBytes?`(默认 8192) |
| `st-upload-urls` | 申请 MinerU 批量上传链接 | `token, files[{name, dataId, pageRanges?, isOcr?}], model_version?, enable_formula?, enable_table?, language?` |
| `st-put` | PUT 上传文件到 OSS 链接 | `url, path` |
| `st-poll-batch` | 轮询解析结果 | `token, batchId` |
| `st-fetch-one` | 下载结果 zip 并解压 | `token, fullZipUrl, destDir` |
| `st-arrange` | 把 MinerU 产物整理进文库 | `libraryDir, book, chunkLabel, srcDir` |
| `merge-book` | 合并一本书的全部分片 md | `libraryDir, book` |
| `scan-md` | 扫描文库生成书单与标题层级 | `libraryDir, book?` |
| `search` | 全文检索 | `libraryDir, query, book?, maxResults?` |

---

## 🔄 转换工作流(转换 → 轮询 → 拉取)

MinerU 标准 API v4 的完整流程(与插件 `medlib_convert / poll / fetch` 等价):

1. **收集与分片**:`ls` 收集输入文件;PDF 用 `pdf-pages` 估页数;>200 页生成 `pageRanges: ["1-200","201-400",…]`,每片一个独立 `dataId`(仅 ASCII,如 `f0/f1`);≤200 页用单条且不带 `pageRanges`
2. **申请链接**:`st-upload-urls` → 返回 `{ batchId, urls }`;`data_id` 用于后续结果匹配
3. **上传**:`st-put {url, path}` —— **PUT 不要带 Content-Type 头**(带了会 403 `SignatureDoesNotMatch`);上传完成后**系统自动创建解析任务**,不要再调 `extract/task/batch`(多调一次会报"failed to read file")
4. **记录任务**:taskId = `batchId#dataId`,写入 `<文库>/library.json`(断点续转的依据)
5. **轮询**:`st-poll-batch {token, batchId}` → 按 `data_id` 匹配结果;`state` 为 `pending / running / done / failed`;`done` 时取 `full_zip_url`,间隔 5–10 秒直至全部完成
6. **拉取整理**:`st-fetch-one` 下载 zip 并 `tar` 解压 → `st-arrange` 把 md 归入 `<文库>/<书名>/<书名>[-pX-Y].md`、图片归入 `images/` 并重写相对引用 → 全部片拉完后 `merge-book` 按页码顺序合并 → `clean` 清理临时目录 → `scan-md` + 重建 `_library_index.md`

---

## 🧹 校对重构流水线(tools/medfix.py)

MinerU 输出通常存在系统性问题:标题全部是 `##`、部分表格是 HTML、公式带 LaTeX 垃圾命令、OCR 单字错、英文断词、图片链接冗长。`medfix.py` 针对单个分片做全自动修复:

- **文字校对**:逐章与 PDF 文本层做 SequenceMatcher 差异比对,输出候选错误清单并修复(错字、断词、缺文补回、`PaC0₂→PaCO₂` 等数字字母混淆)
- **医学符号**:540 处 `$...$` 公式 → Unicode(`HCO₃⁻`、`PaCO₂`、`Na⁺`、`1,25-(OH)₂D₃`、`P₅₀`…);34 处 HTML 上/下标 → Unicode;清理 `\bf \mathbf \mathbb \substack` 等残渣命令;保留标准写法 `$\bar{x} \pm s$`
- **标题层级**:按「`#` 章 / `##` 节 / `###` 一、 / `####`（一）与【】 / `#####` 1.」五级重排(缺失章标题自动补入)
- **表格**:HTML `<table>`(含 rowspan/colspan)→ 标准 GFM 表格;表内半角标点转全角
- **图片**:删除 `![](images/…)` 链接,仅保留加粗图注 `**图X-X　名称**`;表题同步加粗
- **目录**:用 PDF 官方书签重建 `# 目录`(锚点 + 原版页码;印刷页码 = PDF 页码 − 前置偏移,需按书校准)
- **冗余清理**:分片注释、页脚残留、连续空行、尾随空格、被分页切断的续句合并

依赖与使用:

```bash
pip install pymupdf            # 提取 PDF 文本层做对照
python tools/medfix.py         # 头部 SRC/OUT/OUTLINE 等常量按你的文件路径修改
```

> 该脚本以《儿科学》p1-200 分片为实例编写,路径常量在文件头部,替换后即可用于任意教材分片。

---

## ⚠️ 已知限制与 FAQ

- **云端限制**:单文件 ≤ 200MB;单文件 ≤ 200 页(本项目自动分片解决);单批 ≤ 50 条;免费额度 1000 页/天,错误码 `-60018` 表示当日额度用尽,次日可续
- **扫描版 PDF**:解析质量依赖 OCR,转换参数加 `isOcr: true`(语言默认 `ch`)
- **图片偶发方向翻转**:MinerU 云端偶发问题,可人工旋转后同名覆盖 `images/` 下文件
- **断点续转**:重新 `medlib_setup` 会重置 `library.json` 任务记录(磁盘上的书不受影响);续转同一批任务建议直接改状态文件或重新 convert 同名文件
- **沙箱/权限**:DSH 中文库目录若在会话工作区之外,首次写入需在界面批准一次沙箱升级
- **安全**:Token 只经参数或 `MINERU_TOKEN` 环境变量传递,不要写入日志或提交到仓库(仓库 `.gitignore` 已忽略 `.medlib-token`、`config.json`)

---

## 📚 文库布局参考

```
<文库根目录>/
├── _library_index.md      # 书单 + 每书标题/章节目录(自动重建)
├── library.json           # 转换任务状态(断点续转)
├── .medlib-token          # MinerU Token(不入库)
├── <书名A>/
│   ├── <书名A>.md         # 合并后的全书 Markdown
│   ├── <书名A>-p1-200.md  # 分片(合并后可删)
│   └── images/            # 书中图片,md 内相对引用
└── <书名B>/…
```

---

## 📄 License

MIT License — 见 [LICENSE](LICENSE)。

> 版权提示:本仓库开源的是**工具与脚本**;通过本工具转换产生的 Markdown 内容版权归原书权利人所有,请仅转换你拥有版权或有授权使用的教材,勿将转换产物对外公开分发。
