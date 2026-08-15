# MinerU 云端 API 对接要点

本文档记录 MinerU 标准 API v4 对接中验证过的关键行为与踩坑记录,供二次开发参考。
官方文档:https://mineru.net/apiManage/docs

## 端点

| 用途 | 端点 |
|---|---|
| 批量申请上传链接 | `POST /api/v4/file-urls/batch` |
| 查询解析结果 | `GET /api/v4/extract-results/batch/{batch_id}` |
| Token 管理 | https://mineru.net/apiManage/token |

## 请求体结构(实测有效的形态)

```json
{
  "enable_formula": true,
  "enable_table": true,
  "language": "ch",
  "model_version": "vlm",
  "files": [
    {
      "name": "demo.pdf",
      "data_id": "f0",
      "page_ranges": "1-200",
      "is_ocr": false
    }
  ]
}
```

- 顶层 `model_version / enable_formula / enable_table / language` 为批级参数
- 每个文件的 `is_ocr / page_ranges / data_id` 必须放在 `files[]` 元素**内部**(放在顶层会不生效)
- `data_id` 仅允许 `[A-Za-z0-9_.-]`,≤ 128 字符,用于结果匹配
- `page_ranges` 格式:`"1-200"` 或 `"2,4-6"`;单文件页数上限 200

## 关键行为(已实测验证)

1. **上传后系统自动创建解析任务**:`PUT` 文件到签名的 OSS URL 后,不要调用任何 `extract/task/batch` 之类的"提交任务"接口 —— 多调一次会导致任务报 `failed to read file`。直接轮询上传批次即可。
2. **PUT 上传不要带 `Content-Type` 头**:加了 Content-Type 会返回 403 `SignatureDoesNotMatch`(签名仅对裸文件计算)。
3. **结果按 `data_id` 匹配**:轮询 `extract-results/batch/{batch_id}` 返回 `data.extract_result[]`,每项含 `data_id` 与 `state`(`pending / running / done / failed`);`done` 时取 `full_zip_url` 下载解析产物 zip。
4. **限制**:单文件 ≤ 200MB;单文件 ≤ 200 页(分片解决);单批 ≤ 50 个文件;免费额度 1000 页/天;错误码 `-60018` = 当日免费额度用尽。
5. **产物 zip 结构**:`full_zip_url` 下载后为 zip,内含 `*.md` 与 `images/` 目录;md 内图片为相对路径引用,整理时把图片归入文库 `images/` 并保持相对引用即可在 Obsidian / VS Code 中直接打开。
6. **分片合并**:同一文件的多个分片(如 `p1-200` / `p201-400`)各自生成独立 md;按页码顺序拼接并去重即可得到全书 md(本项目 `merge-book` 实现)。

## 已知偶发问题

- 个别图片方向翻转(云端 OCR 偶发):人工旋转后同名覆盖 `images/` 下文件即可
- 表格偶尔输出为 HTML `<table>`(非 GFM):本项目的 `medfix.py` 校对流水线会自动转换
- 公式偶尔带 LaTeX 垃圾命令(`\bf`、`\mathbf`、`\substack` 等):`medfix.py` 会自动清理并转 Unicode
