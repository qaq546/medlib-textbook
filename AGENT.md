# AGENT.md — 医学教材电子化项目记忆文件

> 本文件是项目的**记忆中枢**。任何新会话/新工作区处理医学教材电子化时，先读本文件再动手。
> 配套：`preset/skills/med-textbook/SKILL.md`（桥接命令速查）、`QUICKSTART.md`（使用者说明）、`docs/MINERU_API.md`（API 细节）。

## 1. 项目是什么

把医学教材（PDF/PPT/Word/图片）通过 MinerU 云端 API 转成 Markdown 文库，达到《儿科学 第10版-p1-200.md》样例质量（零哈希残留、figX-Y(-a/-b) 图注归档、加粗图注/表题、GitHub slug 目录、五级标题），支持全文检索与按章查阅。

## 2. 关键路径（本机约定）

| 用途 | 路径 |
|---|---|
| 代码仓库（GitHub: medlib-textbook） | `F:\Develop\medlib-textbook` |
| 工作区（plugin 配置副本，无 git，勿误删） | `F:\Develop\DeepSeek-Harness\Agent\Plugins\medlib-proto` |
| Python 运行库（pymupdf，pdf-bookmarks.py 依赖，勿删） | `F:\Develop\DeepSeek-Harness\Agent\Plugins\py-libs` |
| 成品文库（**最终结果放这里**） | `F:\Develop\MedicalTextbooks\md` |
| 过程档案（按科目归档，见 process/README.md） | `F:\Develop\MedicalTextbooks\process\<书名>` |
| MinerU Token（勿外泄、勿提交） | `<文库>\.medlib-token` |
| 机器配置（bridge 路径/文库目录，plugin-host 读取） | `medlib-proto\config.json` |

仓库内布局：`bridge/`（medlib-bridge.mjs 桥接 + polish-book.mjs 整饰 + pdf-bookmarks.py 书签提取）、`plugin/`（plugin-host.js cordis 插件宿主）、`tools/`（finalize2 索引重建 + python 后处理）、`preset/`（DSH 预设：preset.yml + agent.cordis.yml + assets/ + skills/med-textbook/）、`docs/`。

## 3. 标准流程（新教材必走，顺序不可乱）

1. **确认 Token**：读 `<文库>\.medlib-token`；缺失/失效则让用户重新 medlib_setup。
2. **转换**：`ls` 收集文件 → `pdf-pages` 估页数 → >200 页按 200 一档分片（dataId=f0/f1/…）→ `st-upload-urls`（model_version:'vlm', enable_formula:true, enable_table:true, language:'ch'；扫描版 isOcr:true）→ `st-put` 上传。任务记录写 `<文库>\library.json`。
3. **轮询**：`st-poll-batch` 每 5–10 秒一次，直到全部 done。
4. **拉取合并**：`st-fetch-one` 下载解压 → `st-arrange` 归入 `<文库>/<书名>/` → `merge-book` 按页序合并。
5. **整饰（成品化，关键步骤）**：`polish-book.mjs <libraryDir> <book> [bookmarks.json] [pdfPath]`。
   - 书签提取（供插章标题）：`python bridge/pdf-bookmarks.py <pdf> <out.json>`（依赖 pymupdf）。
   - polish 内部图片四段式：**剔二维码/数字资源小图 → 图注分组绑定 figX-Y(-a/-b/-c) → 缺失图注插 `[图X-Y]` 占位 → 清理孤儿图片文件**。幂等：重复运行零变更（图归属用"面板编号延续"内在规则判断，勿依赖可变占位符状态）。
6. **QA 自检（未达标不得交付）**：
   - 0 处 `images/<hash>` 哈希引用残留；md 图引用数 = images/ 实际文件数（无缺失/无孤儿）
   - 无残留 `$`、无 base64 图片
   - `## 思考题` 数量 = 章数；`# 目录` 锚点与正文标题一致（GitHub slug）
   - 标题层级：章 `#` / 节 `##` / 一、`###` / （一）与【】`####` / 1.`#####`
   - 注意：PowerShell 正则计数可能误报（如 `^## 思考题$` 返回 0），用 grep 工具复核
7. **部署与索引**：`MEDLIB_LIB=<libraryDir> node tools/finalize2.mjs` 重建 `_library_index.md`；更新 `<文库>\library.json` 的 polished 元数据（figures/qrRemoved/groupsBound/filesCleaned 等）。
8. **归档过程产物**：把 MinerU json（content_list/model/layout）、书签 json、转换脚本、修复前备份、各轮 md/报告/校对清单移到 `process\<书名>\`（结构见 process/README.md）。
9. **代码同步**：改过的 bridge/plugin/tools 文件同步进仓库并 git commit；提交前检查无本地路径泄漏（grep `F:\\Develop` / `F:/Develop`），机器配置用 env/argv 参数化，不得硬编码。

## 4. 后处理规则（对齐儿科学样例，polish-book.mjs 已实现）

1. **图片**：只归档带「图X-Y」图注的图 → `images/figX-Y(-a/-b/-c)`；多面板图 base + a/b/c 后缀与 A./B. 标签交错（模板见 24儿科学-p1-200 L2734）；图注加粗在图片下方；缺失文件插 `[图X-Y]` 占位符；封面/编者照片/logo/**二维码/视频缩略图/章节思维导图/数字人案例**等无图注图剔除引用+文件；**禁止 base64**。
2. **符号**：T₁/T₂、HCO₃⁻、PaCO₂、PaO₂、CD4⁺、P₃/P₅₀/P₉₇ 等上下标 Unicode 保留。
3. **段落**：段中不插换行；空行只在段落间/标题前后/列表项间；修复「分为\n以下类型」类断段。
4. **目录**：删原书页码，统一 `- [标题](#锚点)`（GitHub slug，锚点与正文一致）。
5. **表格**：简单表 Markdown；合并单元格复杂表 HTML（rowspan/colspan）；表题加粗在表格上方。
6. **公式**：行内医学符号 Unicode；真数学结构保留 `$$...$$`（如 Z 评分）；纯文本 `$$` 去包裹；输出自检无残留 `$`。
7. **术语/层级**：英文术语首现 `（*English term*，ABBR）` 斜体；标题层级见流程第 6 步。
8. **输出自检**：图引用数 = 图注数；无残留 `$`、无 base64、无 `images/<hash>` 引用残留。

## 5. 新会话怎么用（两种方式）

- **方式 A（preset 模式）**：新建会话时选择「医学教材电子化」preset（已安装到 `~/.dsh/.agent-presets/med-textbook/`），agent 自动带 skill、按本流程走。注意：preset 是否生效看**会话 header 的 `agentPreset` 字段**（`~/.dsh/sessions/.../session.jsonl.zstd` 首行），不是看 GUI 下拉框；若改了 `agent.cordis.yml` 需**重启 DSH** 才会重新挂载。
- **方式 B（工作区模式，用户主推）**：把本 AGENT.md 复制到新工作区，连同要解析的教材一起放入；agent 读本文件按流程执行。
- 两种方式下：文库在会话工作区外，首次写入需用户批准一次（沙箱升级）；preset/skill 只含流程知识，机器路径以 `medlib-proto\config.json` 为准。

## 6. 已完成的教材

| 教材 | 状态 | 成品 |
|---|---|---|
| 24儿科学 第10版 | 模板质量（p1-200 已 polish；全本 `24儿科学 第10版.md` 未 polish，可选补跑） | `md/24儿科学 第10版/` |
| 23妇产科学 第10版 | 已 polish：142 二维码剔除、96 图绑定（35 组）、220 fig 文件、0 哈希残留、fig12-13 真缺图占位、34 思考题、449 目录、1.81MB | `md/23妇产科学 第10版/` |

## 7. 常见坑

- MinerU 限制：单文件 ≤200 页/≤200MB、单批 ≤50 条、免费 1000 页/天（-60018 = 额度用尽，次日续转）。
- 图注在图片下方、多面板图拆分、`(1)(2)`/`A/B/C` 标签夹在图文之间、二维码夹在图块中间——都是 MinerU 常态，polish 已处理。
- polish 幂等性依赖稳定输入；人为改过 md 后再跑 polish 需重新核对报告数字。
- 图片当前为 `.jpg`（儿科学样例为 `.png`）；如需统一格式可后处理转换（可选，未做）。
- git 提交到公共仓库前，必须清掉所有 `F:\Develop` 本地路径（已发生过一次泄漏，靠 grep 拦截）。
- DSH 技能目录为空/只有无关 skill 时：先确认 preset 的 `agent.cordis.yml` 里 `skill-filesystem` 行带 `customSkillDirs` 指向 preset 自带的 `skills/` 目录（对照 shipped `cordis` preset 的写法），缺了它预设捆绑的 skill 永远不会被扫描；其次确认会话 header 的 `agentPreset` 字段确实是本 preset（GUI 下拉 ≠ 已生效）。改完需重启 DSH。
- DSH 会把 `~/.agents/skills`（默认 agentsHome）里的 skill 也扫进目录——那里可能出现与 DSH 无关的历史 skill（如给 Claude Code 装的），属正常，不代表本 preset 有问题。
