# -*- coding: utf-8 -*-
"""audit_para_lenient.py — 括号归一后的段落包含审计,用于区分"标点型"与"内容型"差异。

用法:python audit-para-lenient.py [--md <md 文件>] [--pages <PDF 逐页 txt 目录>] [--work <输出目录>]
"""
import io, os, re, sys

DEFAULT_MD = r"<规范化 md 文件路径>"
DEFAULT_PAGES = r"<PDF 逐页 txt 目录(medfix 的 pdfwork/pages)>"
DEFAULT_WORK = r"<输出目录,如 work>"

_args = [a for a in sys.argv[1:]]
def _arg(name, default):
    return _args[_args.index(name) + 1] if name in _args else default

WORK = _arg("--work", DEFAULT_WORK)
MD = _arg("--md", DEFAULT_MD)
PAGES = _arg("--pages", DEFAULT_PAGES)

SUBS = dict(zip("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
SUPS = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))
VAR = {
    "⁻": "-", "⁺": "+", "±": "±", "×": "x", "℃": "°C", "～": "~",
    "—": "-", "‐": "-", "’": "'", "‘": "'", "“": '"', "”": '"',
    "∶": ":", "：": ":", "％": "%", "≥": ">=", "≤": "<=", "＞": ">",
    "＜": "<", "→": "->", "（": "(", "）": ")", "·": "·",
    "①": "1)", "②": "2)", "③": "3)", "④": "4)", "⑤": "5)", "⑥": "6)",
    "⑦": "7)", "⑧": "8)", "⑨": "9)", "⑩": "10)", "⑪": "11)", "⑫": "12)",
    "⑬": "13)", "⑭": "14)", "⑮": "15)", "⑯": "16)", "⑰": "17)", "⑱": "18)",
    "⑲": "19)", "⑳": "20)",
}

def norm(s):
    out = []
    for ch in s:
        if ch == "*":
            continue
        if ch in SUBS: out.append(SUBS[ch]); continue
        if ch in SUPS: out.append(SUPS[ch]); continue
        if ch in VAR: out.append(VAR[ch]); continue
        out.append(ch)
    return "".join(out)

def clean_page(t):
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", t)
    t = re.sub(r"本章数字资源\s*\|\s*\d+", "", t)
    out = []
    for ln in t.split("\n"):
        s = ln.strip()
        if re.fullmatch(r"\d+", s):
            continue
        if re.match(r"^第[一二三四五六七八九十]+[章节]\s", s):
            continue
        out.append(ln)
    return "\n".join(out)

def ws(s):
    return re.sub(r"\s+", "", s)

def main():
    pdf_all = ws(norm("\n".join(
        clean_page(io.open(os.path.join(PAGES, "p%03d.txt" % p), encoding="utf-8").read())
        for p in range(1, 1000)
        if os.path.exists(os.path.join(PAGES, "p%03d.txt" % p)))))
    paras = io.open(MD, encoding="utf-8").read().split("\n\n")
    misses = []
    for para in paras:
        line = para.strip()
        if not line: continue
        if re.match(r"^#{1,6}\s", line): continue
        if line.startswith("|"): continue
        if re.match(r"^<(/)?(table|tr|td|th)", line): continue
        if re.match(r"^\s*- \[", line): continue
        if line in ("```", "$$", "---"): continue
        if re.match(r"^(!\[|```)", line): continue
        body = ws(norm(line))
        if len(body) < 8: continue
        if body not in pdf_all:
            misses.append((len(body), line))
    print("lenient misses:", len(misses))
    with io.open(os.path.join(WORK, "audit-misses-lenient.txt"), "w", encoding="utf-8") as f:
        for ln, line in sorted(misses, key=lambda x: -x[0]):
            f.write("=" * 40 + "\n[%d chars]\n%s\n" % (ln, line[:400]))
    for ln, line in sorted(misses, key=lambda x: -x[0])[:60]:
        print("[%d] %s" % (ln, line[:100].replace("\n", " / ")))

if __name__ == "__main__":
    main()
