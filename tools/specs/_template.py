# -*- coding: utf-8 -*-
"""_template.py — fix-tables.py / verify-tables.py 数据区填写模板(示例,非真实书数据)。

复制本文件到 specs/<书名>.py 并把常量复制进对应脚本的数据区即可。
真实数据请对照目标书 PDF 文本层逐格核对后填写。"""

# ---- fix-tables.py 数据区示例 ----

# 1) 合并单元格表:表题 -> HTML <table>(表题用与目标一致的空格码位)
TABLE_EXAMPLE = """<table>
<tr><th rowspan="2">第一列</th><th colspan="2">合并大列</th></tr>
<tr><th>子列1</th><th>子列2</th></tr>
<tr><td>a</td><td>1</td><td>2</td></tr>
</table>"""

# 用法(在 fix-tables.py 数据区):
#   replace_table("**表X-X　示例表**", TABLE_EXAMPLE)

# 2) 内容修正:整行替换 / 子串替换
#   replace_line("| 旧整行 |", "| 新整行 |")
#   replace_sub("旧子串", "新子串", 1)

# 3) 表题加粗(非粗体 U+2003 -> 加粗 U+3000):
#   replace_line("表 X-X\u2003 标题", "**表X-X　标题**")

# 4) 圈号恢复循环(示例结构,需按书配置分类头与最大编号):
#   cat_headers = ["| 1. 分类一 |"]
#   maxns = {1: 3}
#   # ... 参照 fix-tables.py 私有版中 "表7-2 圈号恢复" 段落

# ---- verify-tables.py 数据区示例 ----

# 残留模式(全文件扫描):
#   for pat in [r"10\\.9%氯化钠"]:
#       for i, l in enumerate(lines):
#           if re.search(pat, l):
#               errors.append("残留 %r: 行 %d" % (pat, i + 1))

# 必含片段抽查:
#   for pat in ["colspan=\"5\"", "Na⁺:Cl⁻"]:
#       if pat not in text:
#           errors.append("缺 %r" % pat)

# 表题加粗检查:
#   for t in ["**表X-X　标题**"]:
#       if t not in text:
#           errors.append("表题未加粗: %s" % t)
