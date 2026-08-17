# 医学教材电子化 · 使用说明(QUICKSTART)

> 面向使用者。本 preset 通过 MinerU 云端 API 把医学教材(PDF/PPT/Word/图片)转成 Markdown 文库。
> Agent 干活请读仓库根目录 `AGENT.md`(标准流程)与同目录的 `SKILL.md`(桥接命令速查);本文件讲**你怎么用**。

## 一、最简三步

1. **开新会话,选择「医学教材电子化」preset**
2. **给路径,一句话让 Agent 干活**,例如:
   > 把 `D:\教材\系统解剖学 第9版.pdf` 转成文库,扫描版就开 OCR
3. **遇到沙箱授权提示时点一次"允许"**(文库目录在会话工作区外,首次写入需批准)

之后 Agent 会自动完成:检查 token → 收集文件 → 自动分片(>200 页)→ 上传 → 轮询 → 拉取 → 合并 → **polish 整饰(二维码清理/图注归档)** → 重建索引。转换完成后直接问它"搜一下 xxx"即可。

## 二、常用操作小抄

| 想做什么 | 对 Agent 说 |
|---|---|
| 转换教材 | "把 `<路径>` 转成文库";扫描版加"开 OCR" |
| 查转换进度 | "转换到哪了" / "poll 一下任务" |
| 全文检索 | "在文库搜索 `<关键词>`"(返回书/文件/行号/上下文) |
| 看某本书目录 | "看看 `<书名>` 的章节目录" |
| 图片瘦身 | "清理文库小图片"(自动删头像/logo 类 <8KB 图) |
| 整饰成品质量 | "对 `<书名>` 跑 polish"(二维码/数字资源小图剔除、图注归档 figX-Y、孤儿清理) |
| 校对重构 | "对 `<书名>-pX-Y.md` 做校对重构"(OCR 错字/五级标题/表格转标准 Markdown/重建目录) |
| 换 token / 换文库 | "重新配置 medlib(token/文库目录)" |

## 三、日常须知

- **Token 已存好**:`<文库>/.medlib-token`,新会话无需重复配置;换电脑才需重新 `medlib_setup`
- **免费额度**:1000 页/天(优先),超额报错 `-60018`,次日续转
- **云端限制**:单文件 ≤200MB、≤200 页(自动分片解决)、单批 ≤50 条
- **文库位置**:默认 `F:\Develop\MedicalTextbooks\md`;每本书一个文件夹(`<书名>.md` + `images/`),另有 `_library_index.md` 索引、`library.json` 任务状态;**最终结果都会放进这里**
- **过程档案**:MinerU 返回 json/备份/各轮报告归档在 `F:\Develop\MedicalTextbooks\process\<书名>\`,方便追溯
- **项目记忆**:仓库根目录 `AGENT.md` 是标准流程(新会话/新工作区按它走)
- **图偶尔翻转**:云端偶发,手动旋转后同名覆盖 `images/` 下文件
- **扫描版 PDF**:OCR 选项记得开,语言默认中文

## 四、进阶:不通过 Agent,直接调 CLI

桥接脚本是零依赖 Node 文件,可独立使用:

```bash
node <preset>/assets/medlib-bridge.mjs <verb> <args.json>
# 例:列文件 / 检索
node .../medlib-bridge.mjs ls "D:\教材"
node .../medlib-bridge.mjs search "{\"libraryDir\":\"F:\\Develop\\MedicalTextbooks\\md\",\"query\":\"新生儿黄疸\"}"
```

常用动词:`ls`、`pdf-pages`、`trim-images`、`st-upload-urls`、`st-put`、`st-poll-batch`、`st-fetch-one`、`st-arrange`、`merge-book`、`polish`、`scan-md`、`search`、`clean`、`mkdir`、`rm`。完整说明见开源仓库 README 与 `docs/MINERU_API.md`。

## 五、常见问题

| 现象 | 处理 |
|---|---|
| 新会话没有 `medlib_*` 工具 | 正常——preset 模式是 Agent 按 SKILL.md/AGENT.md 调桥接脚本,不需要工具名;直接说需求即可 |
| 报 `-60018` | 当日 1000 页额度用完,次日再转 |
| 提示 NO_TOKEN | 先运行 `medlib_setup` 重新保存 token |
| 沙箱拒绝写文库 | 在界面批准一次(文库在工作区外) |
| 转换后文字有错 | 用"校对重构"让 Agent 跑 medfix 流程,或手动旋转翻转图 |
