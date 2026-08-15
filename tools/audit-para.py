# -*- coding: utf-8 -*-
"""audit_para.py — 段落级全文包含审计:每个 md 非空段落(去空白/去表格/去目录行/去标题)
经 Unicode 变体归一后,必须作为子串出现在 PDF 文本层(全部 p001-p220 拼接)中。
未命中的段落即转换/拼接/OCR 疑点。"""
import io, os, re, sys

WORK = r"<输出目录,如 work>"
MD = r"<规范化 md 文件路径>"
PAGES = r"<PDF 逐页 txt 目录(medfix 的 pdfwork/pages)>"

SUBS = dict(zip("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
SUPS = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))
VAR = {
    "⁻": "-", "⁺": "+", "±": "±", "×": "x", "·": "·", "℃": "°C", "℃": "°C",
    "～": "~", "—": "-", "‐": "-", "’": "'", "‘": "'", "“": '"', "”": '"',
    "∶": ":", "：": ":", "％": "%", "½": "1/2", "⅓": "1/3", "¼": "1/4",
    "β": "beta", "α": "alpha", "γ": "gamma", "δ": "delta", "μ": "u", "χ": "chi",
    "≥": ">=", "≤": "<=", "＞": ">", "＜": "<", "→": "->", "↓": "↓", "↑": "↑",
    "①": "1)", "②": "2)", "③": "3)", "④": "4)", "⑤": "5)", "⑥": "6)",
    "⑦": "7)", "⑧": "8)", "⑨": "9)", "⑩": "10)", "⑪": "11)", "⑫": "12)",
    "⑬": "13)", "⑭": "14)", "⑮": "15)", "⑯": "16)", "⑰": "17)", "⑱": "18)",
    "⑲": "19)", "⑳": "20)", "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV",
    "Ⅴ": "V", "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
    "•": "·", "×": "x", "＊": "*",
}

def norm(s):
    out = []
    for ch in s:
        if ch == "*":
            continue  # md 斜体/粗体标记,PDF 侧无
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

def strip_ws(s):
    return re.sub(r"\s+", "", s)

def main():
    with io.open(MD, encoding="utf-8") as f:
        md = f.read()
    # PDF 侧:拼接全部页
    pdf_parts = []
    for p in range(1, 1000):
        fn = os.path.join(PAGES, "p%03d.txt" % p)
        if not os.path.exists(fn):
            continue
        pdf_parts.append(clean_page(io.open(fn, encoding="utf-8").read()))
    pdf_all = strip_ws(norm("\n".join(pdf_parts)))
    print("pdf norm len:", len(pdf_all))

    paras = md.split("\n\n")
    misses = []
    checked = 0
    for para in paras:
        line = para.strip()
        if not line:
            continue
        # 跳过标题/表格/目录列表/围栏块标记
        if re.match(r"^#{1,6}\s", line): continue
        if line.startswith("|"): continue
        if re.match(r"^\s*- \[", line): continue
        if line in ("```", "$$", "---"): continue
        if re.match(r"^(!\[|```)", line): continue
        body = strip_ws(norm(line))
        if len(body) < 8:
            continue
        checked += 1
        if body not in pdf_all:
            misses.append((len(body), line))
    print("checked paragraphs:", checked, " misses:", len(misses))
    misses.sort(key=lambda x: -x[0])
    with io.open(os.path.join(WORK, "audit-misses.txt"), "w", encoding="utf-8") as f:
        for ln, line in misses:
            f.write("=" * 40 + "\n[%d chars]\n%s\n" % (ln, line[:400]))
    print("-> audit-misses.txt")
    for ln, line in misses[:40]:
        print("[%d] %s" % (ln, line[:90].replace("\n", " / ")))

if __name__ == "__main__":
    main()
