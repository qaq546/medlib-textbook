# -*- coding: utf-8 -*-
# audit-para-lenient.py — 段落级全文包含审计(宽松模式:半/全角括号归一)
# 用途:同 audit-para.py,但把 （） 与 () 视为等价,用于区分两类未命中:
#       · 标点型差异(换行合并丢标点、括号半全角不一)——宽松模式下消失
#       · 内容型差异(错字 / 拼接 / 符号错乱)——两种模式下都存在,需人工复核
# 建议:先跑 audit-para.py 拿总数,再跑本脚本对比数量,两者差即纯标点问题。
# 模板:把下方 MD / PAGES / WORK 改成你的路径后运行:
#   python audit-para-lenient.py
import io, os, re

WORK = r"<输出目录,如 work>"
MD = r"<规范化 md 文件路径>"
PAGES = r"<PDF 逐页 txt 目录(medfix 的 pdfwork/pages)>"

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

def ws(s):
    return re.sub(r"\s+", "", s)

def main():
    pdf_all = ws(norm("\n".join(
        io.open(os.path.join(PAGES, "p%03d.txt" % p), encoding="utf-8").read()
        for p in range(1, 1000)
        if os.path.exists(os.path.join(PAGES, "p%03d.txt" % p)))))
    paras = io.open(MD, encoding="utf-8").read().split("\n\n")
    misses = []
    for para in paras:
        line = para.strip()
        if not line: continue
        if re.match(r"^#{1,6}\s", line): continue
        if line.startswith("|"): continue
        if re.match(r"^\s*- \[", line): continue
        if line in ("```", "$$", "---"): continue
        body = ws(norm(line))
        if len(body) < 8: continue
        if body not in pdf_all:
            misses.append((len(body), line))
    print("lenient misses:", len(misses))
    with io.open(os.path.join(WORK, "audit-misses-lenient.txt"), "w", encoding="utf-8") as f:
        for ln, line in sorted(misses, key=lambda x: -x[0]):
            f.write("=" * 40 + "\n[%d chars]\n%s\n" % (ln, line[:400]))
    for ln, line in sorted(misses, key=lambda x: -x[0])[:30]:
        print("[%d] %s" % (ln, line[:90].replace("\n", " / ")))

if __name__ == "__main__":
    main()
