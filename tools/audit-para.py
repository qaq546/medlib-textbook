# -*- coding: utf-8 -*-
# audit-para.py — 段落级全文包含审计(严格模式:保留半/全角标点差异)
# 用途:把规范化 md 的每个正文段落与 PDF 文本层(全部页拼接)做归一化子串比对,
#       未命中的段落即转换 / 拼接 / OCR 疑点。能捕获旧字符级 diff(diff_pdf.py)漏掉的:
#       · 行拼接丢标点(，。；、)   · 跨章节拼接   · 无中文的公式错乱   · 前置页错误。
# 模板:把下方 MD / PAGES / WORK 改成你的路径后运行:
#   python audit-para.py
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
    "＜": "<", "→": "->", "·": "·",
    "①": "1)", "②": "2)", "③": "3)", "④": "4)", "⑤": "5)", "⑥": "6)",
    "⑦": "7)", "⑧": "8)", "⑨": "9)", "⑩": "10)", "⑪": "11)", "⑫": "12)",
    "⑬": "13)", "⑭": "14)", "⑮": "15)", "⑯": "16)", "⑰": "17)", "⑱": "18)",
    "⑲": "19)", "⑳": "20)",
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

def ws(s):
    return re.sub(r"\s+", "", s)

def main():
    pdf_all = ws(norm("\n".join(
        io.open(os.path.join(PAGES, "p%03d.txt" % p), encoding="utf-8").read()
        for p in range(1, 1000)
        if os.path.exists(os.path.join(PAGES, "p%03d.txt" % p)))))
    paras = io.open(MD, encoding="utf-8").read().split("\n\n")
    misses = []
    checked = 0
    for para in paras:
        line = para.strip()
        if not line: continue
        if re.match(r"^#{1,6}\s", line): continue      # 标题
        if line.startswith("|"): continue               # 表格
        if re.match(r"^\s*- \[", line): continue        # 目录列表
        if line in ("```", "$$", "---"): continue       # 围栏块
        body = ws(norm(line))
        if len(body) < 8: continue
        checked += 1
        if body not in pdf_all:
            misses.append((len(body), line))
    print("checked paragraphs:", checked, " misses:", len(misses))
    with io.open(os.path.join(WORK, "audit-misses.txt"), "w", encoding="utf-8") as f:
        for ln, line in sorted(misses, key=lambda x: -x[0]):
            f.write("=" * 40 + "\n[%d chars]\n%s\n" % (ln, line[:400]))
    for ln, line in sorted(misses, key=lambda x: -x[0])[:30]:
        print("[%d] %s" % (ln, line[:90].replace("\n", " / ")))

if __name__ == "__main__":
    main()
