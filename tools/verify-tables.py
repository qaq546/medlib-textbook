# -*- coding: utf-8 -*-
"""verify-tables.py — 表格结构校验引擎(模板版)。

通用校验(对所有书有效):
  1) HTML 表格 rowspan/colspan 感知的列宽一致性
  2) GFM 表格列数一致性(表头 vs 数据行)
【本书校验区】:残留模式 / 表7-2 圈号 / 表4-9 内容抽查等按目标书填写
(参考 specs/README.md 与 specs/_template.py)。

用法:python verify-tables.py [--md <md 文件>]
"""
import io, re, sys

DEFAULT_MD = r"<md 文件路径>"

_args = [a for a in sys.argv[1:]]
MD = _args[_args.index("--md") + 1] if "--md" in _args else DEFAULT_MD

with io.open(MD, "r", encoding="utf-8") as f:
    text = f.read()
lines = text.split("\n")
errors = []

# ---- 1. HTML 表格结构(rowspan 感知) ----
tables = []
cur = None
for i, l in enumerate(lines):
    if l.strip() == "<table>":
        cur = {"start": i + 1, "rows": []}
    elif l.strip() == "</table>":
        tables.append(cur)
        cur = None
    elif cur is not None and "<tr" in l:
        cur["rows"].append((i + 1, l))

def parse_cells(html):
    out = []
    for attr in re.findall(r"<t[dh]([^>]*)>", html):
        cm = re.search(r'colspan="(\d+)"', attr)
        rm = re.search(r'rowspan="(\d+)"', attr)
        out.append((int(cm.group(1)) if cm else 1, int(rm.group(1)) if rm else 1))
    return out

for t in tables:
    rows = t["rows"]
    if not rows:
        errors.append("行 %d: 空表格" % t["start"])
        continue
    ref = sum(c for c, _ in parse_cells(rows[0][1]))
    pending = {}  # col -> 尚需覆盖的行数(不含当前行)
    for (ln, r) in rows:
        cells = parse_cells(r)
        col = 0
        newp = {}
        for (cw, rw) in cells:
            while col in pending or col in newp:
                col += 1
            for c in range(col, col + cw):
                if rw > 1:
                    newp[c] = rw - 1
            col += cw
        width = col
        for c in pending:
            if c >= width:
                width = c + 1
        if width != ref:
            errors.append("行 %d: 列宽 %d != 表宽 %d" % (ln, width, ref))
        # 旧的跨行占位递减;新占位接管(同列以新为准)
        pending = {c: r - 1 for c, r in pending.items() if r > 1}
        pending.update(newp)

print("HTML 表格数: %d, 列宽检查完成" % len(tables))

# ---- 2. GFM 表列数一致性 ----
seps = [i for i, l in enumerate(lines) if re.match(r"^\s*\|[\s\-|:]+\|\s*$", l)]
for s in seps:
    hdr = lines[s - 1]
    hc = len(hdr.strip().strip("|").split("|"))
    for j in range(s + 1, len(lines)):
        if not lines[j].startswith("|"):
            break
        c = len(lines[j].strip().strip("|").split("|"))
        if c != hc:
            errors.append("行 %d: GFM 列数 %d != 表头 %d" % (j + 1, c, hc))

# ================= 本书校验区 =================
# 按目标书填写(示例见 specs/_template.py):
#   1) 残留模式:对已知 OCR/转换错误的模式做全文件扫描
#   2) 表内内容抽查:某表必须包含的片段
#   3) 表题加粗检查:期望的加粗表题清单
# 示例(占位,非真实书数据):
# for pat in [r"10\.9%氯化钠", r"MYS M1"]:
#     for i, l in enumerate(lines):
#         if re.search(pat, l):
#             errors.append("残留 %r: 行 %d: %s" % (pat, i + 1, l.strip()[:70]))

print()
if errors:
    print("=== %d 处问题 ===" % len(errors))
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("=== 全部通过 ===")
