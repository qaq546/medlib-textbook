# 书籍规格(specs)说明

`fix-tables.py` 与 `verify-tables.py` 的【本书数据区】需要按目标书的 **PDF 文本层**
逐表核对后填写。同一本书用相同 MinerU 模型版本重新转换时输出是确定性的,因此
这些修复可以**直接重跑并复用**;换书时只需重写数据区。

## 流程

1. 转换:`medlib_convert` → 得到分片 md 与 PDF 逐页文本(`pdfwork/pages/p001.txt`…)
2. 校对:对照 PDF 文本层,把表格内容逐格核对(合并单元格结构、圈号、上下标)
3. 填数据:在 `fix-tables.py` 数据区用 `replace_table` / `replace_line` /
   `replace_lines` / `replace_sub` 表达修复;在 `verify-tables.py` 数据区写
   残留模式与内容抽查
4. 跑流水线:`python postprocess.py --md <md> --pages <pages> [--work <work>]`
5. 校验:verify 全部通过、audit misses 数量不回升即为合格

## 引擎函数

| 函数 | 用途 | 匹配方式 |
|---|---|---|
| `replace_table(title, html)` | 合并单元格表:把表题后的 GFM 块替换为 HTML `<table>` | 表题前缀唯一匹配 |
| `replace_lines(olds, news)` | 整块行替换(如整表内容修正) | 逐行 strip 精确匹配 |
| `replace_line(old, new)` | 单行替换 | 整行 strip 精确匹配 |
| `replace_sub(old, new, count)` | 子串替换(如整行内的长片段) | 全文件计数断言 |

## 常见陷阱

- **表题空格码位**:非加粗表题的数字后是 U+2003(EM SPACE),加粗表题统一用
  U+3000(IDEOGRAPHIC SPACE)。定位表题时务必用与目标一致的空格码位。
- **圈号**:`①`~`⑳` = U+2460~U+2473。行首 `| 1. xxx |` 是分类头(不要圈号化),
  正文 `；1xxx` / `| 1 xxx |` 才是需恢复圈号处。
- **上下标**:离子一律用 Unicode 上下标(`Na⁺`、`HCO₃⁻`、`NH₄⁺`、`25-(OH)D₃`),
  禁止 `Na+/Cl-` 写法。
- **比值用 ∶**(U+2236),不用半角 `:`;范围用 `～`;大于/小于用 `＞/＜`(全角)。
- **断言即保护**:`replace_*` 的 `assert count==1` 保证内容定位唯一;若 MinerU
  版本变化导致输出不同,断言会失败并提示,而不是静默改错。

## 校验要点(verify-tables.py)

- HTML 表:rowspan/colspan 感知的列宽一致性(引擎已内置)
- GFM 表:每张表数据行列数 == 表头列数(引擎已内置)
- 数据区补充:残留错误模式(如 `10.9%氯化钠`)、必含片段抽查、表题加粗清单
