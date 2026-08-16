# -*- coding: utf-8 -*-
# backfill-punct.py — 按 PDF 文本层回填 md 中"行拼接丢失/错误的标点"(安全模式)
# 用途:medfix 校对后的二次精修。行拼接(换行合并)会系统性丢失 ，。；、 等标点,
#       本脚本把每个未通过 audit-para 的段落与 PDF 文本层对齐,仅当差异**全部是标点**时
#       才自动回填,并用"修复结果必须仍包含于 PDF 文本层"做最终验证,否则整段跳过。
# 安全规则:
#   1) 差异块中出现任何非标点字符(错字/漏字/符号)→ 整段跳过,列入人工复核清单;
#   2) 页眉/页码/控制字符从 PDF 侧清理(消除跨页假阳性);
#   3) 触碰对齐窗口边界的块视为相邻段落文字,忽略;
#   4) 非标点的"纯插入"块(图注/页码等外来文字)忽略,交给包含验证兜底。
# 用法:
#   python backfill-punct.py [--md <md 文件>] [--pages <PDF 逐页 txt 目录>] [--work <输出目录>]
import io, os, re, difflib, sys

DEFAULT_MD = r"<规范化 md 文件路径>"
DEFAULT_PAGES = r"<PDF 逐页 txt 目录(medfix 的 pdfwork/pages)>"
DEFAULT_WORK = r"<输出目录,如 work>"

_args = [a for a in sys.argv[1:]]
def _arg(name, default):
    return _args[_args.index(name) + 1] if name in _args else default

WORK = _arg("--work", DEFAULT_WORK)
SRC = _arg("--md", DEFAULT_MD)
OUT = os.path.join(WORK, os.path.basename(SRC).replace(".md", "-backfilled.md"))
PAGES = _arg("--pages", DEFAULT_PAGES)

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
ALLOWED = set("，。、；：？！（）《》〈〉「」『』【】…—–·・∶,,.;:?!()'\"")

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

def norm_with_map(s):
    """返回 (归一化字符串, 输出字符位置->原始字符索引 映射)。"""
    out, idx = [], []
    for i, ch in enumerate(s):
        if ch == "*":
            continue
        if ch in SUBS: reps = SUBS[ch]
        elif ch in SUPS: reps = SUPS[ch]
        elif ch in VAR: reps = VAR[ch]
        else: reps = ch
        reps_list = list(reps)
        out.extend(reps_list)
        idx.extend([i] * len(reps_list))
    return "".join(out), idx

def ws(s):
    return re.sub(r"\s+", "", s)

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

def is_punct_only(s):
    return all(c in ALLOWED for c in s)

def find_window(pdf_all, md_s):
    """返回 (win_s, win_e) 或 None:先取中部锚点,再就近验证段落首尾 10 字,得到精确窗口。"""
    L = len(md_s)
    if L < 12:
        return None
    first10, last10 = md_s[:10], md_s[-10:]
    for size in (60, 40, 30, 20, 15, 12):
        mid = L // 2
        for off in range(-3, 4):
            s0 = max(0, min(mid + off, L - size))
            chunk = md_s[s0:s0 + size]
            i = pdf_all.find(chunk)
            if i < 0:
                continue
            lo, hi = max(0, i - 3 * L), i + 3 * L
            i1 = pdf_all.find(first10, lo, hi)
            i2 = pdf_all.find(last10, lo, hi)
            if i1 >= 0 and i2 >= 0 and i2 > i1:
                return max(0, i1 - 40), min(len(pdf_all), i2 + 40)
    return None

def main():
    md = io.open(SRC, encoding="utf-8").read()
    pdf_all = ws(norm("\n".join(
        clean_page(io.open(os.path.join(PAGES, "p%03d.txt" % p), encoding="utf-8").read())
        for p in range(1, 1000)
        if os.path.exists(os.path.join(PAGES, "p%03d.txt" % p)))))

    paras = md.split("\n\n")
    fixed, skipped, fixed_detail = [], [], []
    out_paras = []
    cnt = {"pass": 0, "anchor-none": 0, "non-punct": 0, "no-edits": 0, "verify-fail": 0, "fixed": 0}
    for para in paras:
        line = para.strip()
        if not line:
            out_paras.append(para)
            continue
        if re.match(r"^#{1,6}\s", line):
            out_paras.append(para); continue
        if re.match(r"^(!\[|```)", line):
            out_paras.append(para); continue
        if line.startswith("|"):
            out_paras.append(para); continue
        if re.match(r"^\s*- \[", line):
            out_paras.append(para); continue
        if line in ("```", "$$", "---"):
            out_paras.append(para); continue
        body = ws(line)
        if len(body) < 8:
            out_paras.append(para); continue
        # 归一化(保留原始行位置映射):normed 含空白,md_s 去空白,posmap 指回原始行
        normed, nidx = norm_with_map(line)
        md_chars, posmap = [], []
        for p, ch in enumerate(normed):
            if ch.isspace():
                continue
            md_chars.append(ch)
            posmap.append(nidx[p])
        md_s = "".join(md_chars)
        if md_s in pdf_all:
            cnt["pass"] += 1
            out_paras.append(para); continue
        # 定位 PDF 窗口
        win = find_window(pdf_all, md_s)
        if win is None:
            cnt["anchor-none"] += 1
            skipped.append((len(body), "anchor-not-found", line))
            out_paras.append(para); continue
        win_s, win_e = win
        pdf_win = pdf_all[win_s:win_e]
        # 对齐
        sm = difflib.SequenceMatcher(None, md_s, pdf_win, autojunk=False)
        ops = sm.get_opcodes()
        edits = []          # (orig_start, orig_end, repl)
        ok = True
        reason = ""
        for tag, i1, i2, j1, j2 in ops:
            if tag == "equal":
                continue
            # 触碰窗口边界的块是相邻段落文字,非本段差异,丢弃
            if j1 == 0 or j2 == len(pdf_win):
                continue
            b = md_s[i1:i2] if i1 < i2 else ""
            a = pdf_win[j1:j2] if j1 < j2 else ""
            if tag == "insert" and not b and not is_punct_only(a):
                # 纯插入且非标点:页眉/页码/图注等外来文本,忽略,由最终包含验证兜底
                continue
            if not is_punct_only(a) or not is_punct_only(b):
                ok = False
                reason = "non-punct diff: pdf=%r md=%r" % (a[:20], b[:20])
                break
            if i1 == i2:
                # 插入
                pos = posmap[i1] if i1 < len(posmap) else len(line)
                edits.append((pos, pos, a))
            elif j1 == j2:
                # 删除
                s0 = posmap[i1]; s1 = posmap[i2 - 1] + 1
                edits.append((s0, s1, ""))
            else:
                s0 = posmap[i1]; s1 = posmap[i2 - 1] + 1
                edits.append((s0, s1, a))
        if not ok:
            cnt["non-punct"] += 1
            skipped.append((len(body), reason, line))
            out_paras.append(para); continue
        if not edits:
            cnt["no-edits"] += 1
            skipped.append((len(body), "no-edits", line))
            out_paras.append(para); continue
        # 应用编辑(倒序)到原始行(保留空白)
        chars = list(line)
        for s0, s1, repl in sorted(edits, key=lambda e: -e[0]):
            chars[s0:s1] = list(repl)
        new_body = "".join(chars)
        new_norm = ws(norm_with_map(new_body)[0])
        if new_norm not in pdf_all:
            cnt["verify-fail"] += 1
            skipped.append((len(body), "verify-fail", line))
            out_paras.append(para); continue
        cnt["fixed"] += 1
        fixed.append(len(body))
        fixed_detail.append((line, new_body))
        out_paras.append(new_body)

    new_md = "\n\n".join(out_paras)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(new_md)
    with io.open(os.path.join(WORK, "backfill-report.txt"), "w", encoding="utf-8") as f:
        f.write("FIXED: %d paragraphs\n\n" % len(fixed))
        for old, new in fixed_detail:
            f.write("=" * 30 + "\nOLD: %s\nNEW: %s\n" % (old[:200], new[:200]))
        f.write("\n\nSKIPPED: %d paragraphs\n\n" % len(skipped))
        for ln, reason, line in skipped:
            f.write("[%d] %s\n%s\n" % (ln, reason, line[:150]))
    print("fixed:", len(fixed), " skipped:", len(skipped))
    print("branch counts:", cnt)
    print("->", OUT)
    print("-> backfill-report.txt")

if __name__ == "__main__":
    main()
