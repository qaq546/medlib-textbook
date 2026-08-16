# -*- coding: utf-8 -*-
"""fix-tables.py — 复杂表格专项修复引擎(模板版)。

功能:合并单元格转 HTML、圈号修正、列对齐、上下标、表题加粗。
引擎函数保留在下方;【本书数据区】需要按目标书的 PDF 文本层逐表核对后填写
(参考 specs/README.md 与 specs/_template.py)。

用法:python fix-tables.py [--md <md 文件>]
"""
import io, re, sys

DEFAULT_MD = r"<md 文件路径>"

_args = [a for a in sys.argv[1:]]
MD = _args[_args.index("--md") + 1] if "--md" in _args else DEFAULT_MD

with io.open(MD, "r", encoding="utf-8") as f:
    lines = f.read().split("\n")

log = []
skipped = []

def collect_gfm_block(idx):
    """从 title 行之后收集 GFM 表格块(连续 | 行),返回 (start, end)。
    表题后允许紧跟至多 1 个非空非 | 说明行(如 "单位：%"),随后必须是连续 | 块;
    找不到返回 (None, None)。"""
    i = idx + 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    # 允许 1 行说明(不以 | 开头,且下一行是 | 开头)
    if i < len(lines) and not lines[i].startswith("|") and lines[i].strip() != "":
        nxt = i + 1
        while nxt < len(lines) and lines[nxt].strip() == "":
            nxt += 1
        if nxt < len(lines) and lines[nxt].startswith("|"):
            i = nxt
        else:
            return None, None
    if i >= len(lines) or not lines[i].startswith("|"):
        return None, None
    start = i
    while i < len(lines) and lines[i].startswith("|"):
        i += 1
    return start, i

def replace_table(title, html):
    hits = [i for i, l in enumerate(lines) if l.strip().startswith(title)]
    if len(hits) != 1:
        skipped.append("表 %r: 表题命中 %d 处(可能已应用或版本变化),跳过" % (title, len(hits)))
        return
    start, end = collect_gfm_block(hits[0])
    if start is None:
        skipped.append("表 %r: 表题后无 GFM 块(可能已转 HTML),跳过" % title)
        return
    old_rows = end - start
    lines[start:end] = html.split("\n")
    log.append("表 %s: GFM %d 行 -> HTML %d 行" % (title, old_rows, len(html.split("\n"))))

def replace_lines(olds, news):
    """行块替换(逐行 strip 匹配,容忍尾部空格)。"""
    olds = [l.strip() for l in olds]
    news = [l.strip() for l in news]
    i = 0
    found = None
    while i <= len(lines) - len(olds):
        if [lines[i + k].strip() for k in range(len(olds))] == olds:
            found = i
            break
        i += 1
    if found is None:
        skipped.append("行块未命中: %s" % olds[0][:40])
        return
    lines[found:found + len(olds)] = news
    log.append("行块: %s" % olds[0][:50])

def replace_line(old, new, count=1):
    """单行替换(逐行 strip 匹配)。"""
    old = old.strip()
    new = new.strip()
    hits = [i for i, l in enumerate(lines) if l.strip() == old]
    if len(hits) != count:
        skipped.append("单行 %r 命中 %d != %d,跳过" % (old[:40], len(hits), count))
        return
    lines[hits[0]] = new
    log.append("单行: %s" % old[:50])

def replace_sub(old, new, count=1):
    """子串替换(全文件计数)。"""
    joined = "\n".join(lines)
    n = joined.count(old)
    if n != count:
        skipped.append("子串 %r 计数 %d != %d,跳过" % (old[:40], n, count))
        return
    joined = joined.replace(old, new)
    lines[:] = joined.split("\n")
    log.append("子串: %s" % old[:50])

def circled(n):
    return chr(0x2460 + n - 1)

# ================= 本书数据区 =================
# 按目标书填写,三部分:
#   1) replace_table(title, html)        合并单元格表:把表题后的 GFM 块替换为 HTML <table>
#                                        注意表题空格码位:非粗体用 U+2003,加粗后统一 U+3000
#   2) replace_lines / replace_line / replace_sub
#                                        内容修正(列对齐、上下标 Na⁺/HCO₃⁻、∶、＜＞、圈号等)
#   3) 表题加粗 + 圈号恢复循环(可参考 specs/_template.py 中的示例)
# 示例(占位,非真实书数据):
# replace_line("| 旧内容 |", "| 新内容 |")
# replace_table("**表X-X　示例表**", """<table>
# <tr><th rowspan="2">列A</th><th colspan="2">列B</th></tr>
# <tr><th>B1</th><th>B2</th></tr>
# <tr><td>a</td><td>b</td><td>c</td></tr>
# </table>""")

# ================= 写出 =================
with io.open(MD, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines))

print("=== 完成,共 %d 处替换 ===" % len(log))
for l in log:
    print(l)
if skipped:
    print("--- 跳过 %d 处(已应用或未命中,未修改) ---" % len(skipped))
    for s in skipped:
        print("SKIP:", s)
