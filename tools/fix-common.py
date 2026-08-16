# -*- coding: utf-8 -*-
"""fix-common.py — 通用字符规范层(对所有教材生效,无需 PDF 文本层)。

在 fix-tables(书特定表格修复)之后运行,自动修复跨书通用的字符错误:

  1) 化学离子上下标:Na+→Na⁺, K+→K⁺, Cl-→Cl⁻, NH4+→NH₄⁺, HCO3-→HCO₃⁻,
     Ca2+→Ca²⁺, Mg2+→Mg²⁺, Fe2+→Fe²⁺, Fe3+→Fe³⁺, OH-→OH⁻, NO3-→NO₃⁻,
     SO42-→SO₄²⁻, CO32-→CO₃²⁻, PO43-→PO₄³⁻(含空格变体)
  2) 数字比值冒号:1:3→1∶3、1：3→1∶3(仅数字比值,排除时间 10:30、URL)
  3) 离子间比值:Na⁺:Cl⁻→Na⁺∶Cl⁻(上/下标符号之间的冒号)
  4) 乘号:数字间的 x/X → ×(如 2x3→2×3)
  5) [可选 --bold-titles] 表题加粗:独占行 "表 6-6 标题" → "**表6-6　标题**"

安全规则:
  - 离子名必须成词(前/后不能是字母数字),避免误伤 pH、NaCl 等
  - 比值仅限数字两侧,排除时间格式(10:30)与 URL
  - 所有替换逐条计数;--dry-run 只报告不改写

用法:python fix-common.py [--md <md 文件>] [--bold-titles] [--dry-run]
"""
import io, re, sys

DEFAULT_MD = r"<md 文件路径>"

_args = [a for a in sys.argv[1:]]
MD = _args[_args.index("--md") + 1] if "--md" in _args else DEFAULT_MD
DO_BOLD = "--bold-titles" in _args
DRY = "--dry-run" in _args

# ---- 1. 化学离子上下标(白名单;前缀/后缀均须非字母数字) ----
IONS = [
    # (正则片段, 替换)
    (r"Na\+", "Na⁺"),
    (r"K\+", "K⁺"),
    (r"Cl-", "Cl⁻"),
    (r"NH4\+", "NH₄⁺"),
    (r"HCO3-", "HCO₃⁻"),
    (r"Ca2\+", "Ca²⁺"),
    (r"Mg2\+", "Mg²⁺"),
    (r"H\+", "H⁺"),
    (r"OH-", "OH⁻"),
    (r"Fe2\+", "Fe²⁺"),
    (r"Fe3\+", "Fe³⁺"),
    (r"Zn2\+", "Zn²⁺"),
    (r"Cu2\+", "Cu²⁺"),
    (r"NO3-", "NO₃⁻"),
    (r"SO4\s*2-", "SO₄²⁻"),
    (r"CO3\s*2-", "CO₃²⁻"),
    (r"PO4\s*3-", "PO₄³⁻"),
]
ION_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:%s)(?![A-Za-z0-9])" % "|".join(p for p, _ in IONS)
)

# ---- 2. 数字比值冒号(排除时间格式 时:分/分:秒) ----
RATIO_RE = re.compile(r"(?<!\d)(\d{1,4})\s*[:：]\s*(\d{1,4})(?!\d)")
# 时间格式 "10:30" / "1:05"(分钟 00-59 且前段 ≤ 2 位)不当作比值
TIME_RE = re.compile(r"(?<!\d)\d{1,2}\s*[:：]\s*[0-5]\d(?!\d)")

# ---- 3. 离子间比值(上/下标符号之间的冒号) ----
ION_RATIO_RE = re.compile(r"(?<=[⁺⁻₊₋])\s*[:：]\s*(?=[⁺⁻₊₋])")

# ---- 4. 乘号(数字之间) ----
MUL_RE = re.compile(r"(?<=\d)\s*[xX]\s*(?=\d)")

# ---- 5. 表题加粗(可选;独占行,已加粗或引用不处理) ----
BOLD_RE = re.compile(r"^表 ?(\d+)-(\d+)[ \u2003\u3000]+(\S.*)$", re.MULTILINE)

def _ratio_repl(m):
    return "%s∶%s" % (m.group(1), m.group(2))

REPLACERS = [
    ("离子上下标", ION_RE, lambda m: _ion_repl(m)),
    ("比值冒号", RATIO_RE, _ratio_repl),
    ("离子间比值", ION_RATIO_RE, lambda m: "∶"),
    ("乘号", MUL_RE, lambda m: "×"),
]

def _ion_repl(m):
    s = m.group(0)
    for pat, rep in IONS:
        if re.fullmatch(r"(?<![A-Za-z0-9])(?:%s)(?![A-Za-z0-9])" % pat, s):
            return rep
    return s

def bold_repl(m):
    return "**表%s-%s　%s**" % (m.group(1), m.group(2), m.group(3))

def main():
    with io.open(MD, "r", encoding="utf-8") as f:
        text = f.read()
    total = 0
    detail = []
    # 时间格式位置集合(比值冒号需跳过)
    time_spans = set()
    for m in TIME_RE.finditer(text):
        time_spans.add((m.start(), m.end()))
    for name, rx, repl in REPLACERS:
        n = 0
        def _sub(mm, rx=rx, repl=repl, name=name):
            nonlocal n
            if name == "比值冒号":
                # 与任何时间格式位置重叠则跳过
                for (s, e) in time_spans:
                    if mm.start() < e and mm.end() > s:
                        return mm.group(0)
            n += 1
            return repl(mm)
        text = rx.sub(_sub, text)
        if n:
            detail.append("%s: %d 处" % (name, n))
            total += n
    if DO_BOLD:
        n = 0
        def _bold(mm):
            nonlocal n
            n += 1
            return bold_repl(mm)
        text = BOLD_RE.sub(_bold, text)
        if n:
            detail.append("表题加粗: %d 处" % n)
            total += n
    if DRY:
        print("=== dry-run: 将修复 %d 处(未写回)===" % total)
        for d in detail:
            print("  ", d)
    else:
        with io.open(MD, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("=== 完成,共 %d 处修复 ===" % total)
        for d in detail:
            print("  ", d)

if __name__ == "__main__":
    main()
