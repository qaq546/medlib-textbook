# 医学教材电子化(Medlib)

> 日常使用说明见 QUICKSTART.md(新会话怎么用、常用操作小抄)。

把医学教材(PDF/PPT/Word/图片)通过 MinerU 云端 API 转成 Markdown 文库,支持全文检索与按章查阅。

## 资源与约定
- 桥接脚本:`<preset 目录>/assets/medlib-bridge.mjs`(零依赖 Node 脚本;调 MinerU API 并做文库整理)
- 文库根目录:`F:\Develop\MedicalTextbooks\md`(默认;每本书一个子目录)
- Token 文件:`<文库>\.medlib-token`(MinerU API Token,获取: https://mineru.net/apiManage/token ;注册即送每日 1000 页免费额度)
- 状态文件:`<文库>\library.json`;索引:`<文库>\_library_index.md`
- 文库布局:`<文库>/<书名>/<书名>.md` + `<书名>/images/`

## 调用桥接
每次操作用 pwsh 执行:
```
node "<preset>/assets/medlib-bridge.mjs" <verb> <args.json>
```
args.json 为 UTF-8 JSON;结果以 JSON 打印到 stdout。`pdf-pages` 与 `ls` 可直接传裸路径(<args.json> 位置放路径,解析失败时视为 path 参数)。

## 转换工作流(转换 → 轮询 → 拉取)
### 1) 转换(等价 medlib_convert)
1. 收集文件:`ls {path}` → files[].path;过滤扩展名 pdf/doc/docx/ppt/pptx/xls/xlsx/png/jpg/jpeg/webp/gif/bmp/jp2
2. 分片:PDF 用 `pdf-pages` 估页数;>200 页按 200 一档生成 pageRanges("1-200","201-400",…);≤200 页用单条(不带 pageRanges);每片是一个独立 dataId
3. 申请上传链接:`st-upload-urls {token, files:[{name, dataId, pageRanges?, isOcr?}], model_version:'vlm', enable_formula:true, enable_table:true, language:'ch'}` → {batchId, urls}(dataId 用 ASCII,如 f0/f1;同一文件多片 = 多条同名 entry,每片一个 url)
4. 上传:`st-put {url, path}`(PUT 不加 Content-Type;系统会自动为每个上传创建解析任务)
5. 本地记录:taskId = batchId#dataId;把任务写进 `<文库>/library.json`(books/tasks 结构)
### 2) 轮询(等价 medlib_poll)
`st-poll-batch {token, batchId}` → data.extract_result[] 按 data_id 匹配;state: pending/running/done/failed;done 时取 full_zip_url。间隔 5-10 秒,直到全部完成。
### 3) 拉取整理(等价 medlib_fetch)
1. `st-fetch-one {token, fullZipUrl, destDir}` → 下载 zip 并用 tar 解压到 destDir
2. `st-arrange {libraryDir, book, chunkLabel, srcDir}` → md 归入 `<文库>/<book>/<book>[-pX-Y].md`,图片归入 `images/`(相对路径引用,Obsidian/VS Code 可直接打开)
3. 一本书所有分片拉完后 `merge-book {libraryDir, book}` → 按页码顺序合并为 `<book>.md`
4. 清理 `.tmp` 临时目录;`scan-md` 后重建 `_library_index.md`

## 检索与维护
- `search {libraryDir, query, book?, maxResults?}` → 命中 {book, file, line, text}
- `scan-md {libraryDir, book?}` → 书单 + 标题层级(索引数据源)
- `trim-images {libraryDir, book?, minBytes?}` → 删除小于阈值的图片(头像/logo/图标)及其 md 引用,默认 8KB
- `clean {dir}` → 清理 `.tmp` 与 `.medlib-*` 残留(不删 `.medlib-token`)
- `rm {path}` → 递归删除

## 注意事项
- Token 经 args.token 或环境变量 MINERU_TOKEN 传入;绝不写入日志或聊天
- 限制:单文件 ≤200MB、单文件 ≤200 页(分片解决)、单批 ≤50 条、免费 1000 页/天(错误 -60018 表示额度用尽,次日续转)
- 扫描版 PDF 加 `isOcr:true`;语言默认 ch
- 图偶尔方向翻转是云端偶发,可人工旋转后同名覆盖 images/ 下文件
- 沙箱:文库目录在会话工作区外时,首次写入需要用户批准一次(sandbox 升级)
