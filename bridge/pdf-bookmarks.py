# pdf-bookmarks.py — 提取 PDF 官方书签(章/节/附) + 封面编者行，输出 JSON。
# 用法: python pdf-bookmarks.py <input.pdf> <output.json>
# 输出: {
#   pdfPages, tocEntries,
#   chapters: [{title, pdfPage, anchor}],   # 一级书签(章), anchor = 该页正文首行(≥20字符)
#   coverEditors: [{kind, names}]           # 从封面页提取的编者行(空格规范化)
# }
import json, re, sys, unicodedata
import pymupdf

def norm(s):
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s\u3000]+", "", s)

def anchor_for_page(pdf, page_idx):
    try:
        lines = [l.strip() for l in pdf[page_idx].get_text().splitlines()]
    except Exception:
        return ""
    for l in lines:
        if len(l) >= 20:
            return l
    return ""

def extract_cover_editors(pdf, pages=4):
    """从前几页提取 主审/主编/副主编/数字主编/数字副主编 行。"""
    pat = re.compile(r"^(主\s*审|主\s*编|副\s*主\s*编|数\s*字\s*主\s*编|数\s*字\s*副\s*主\s*编)\s*[|｜:：]")
    out = []
    seen = set()
    for p in range(min(pages, pdf.page_count)):
        try:
            for l in pdf[p].get_text().splitlines():
                t = l.strip()
                if not pat.match(t):
                    continue
                m = pat.match(t)
                kind = re.sub(r"\s+", "", m.group(1))
                names = re.sub(r"^.*?[|｜:：]\s*", "", t).strip()
                names = re.sub(r"[\u3000\u2002\u2003 ]+", " ", names).strip()
                key = kind + names.replace(" ", "")
                if key in seen:
                    continue
                seen.add(key)
                out.append({"kind": kind, "names": names})
        except Exception:
            continue
    return out

def main():
    pdf_path, out_path = sys.argv[1], sys.argv[2]
    pdf = pymupdf.open(pdf_path)
    toc = pdf.get_toc()
    chapters = []
    for lvl, title, page in toc:
        if lvl == 1:
            chapters.append({"title": title, "pdfPage": page, "anchor": anchor_for_page(pdf, page - 1)})
    out = {
        "pdfPages": pdf.page_count,
        "tocEntries": len(toc),
        "chapters": chapters,
        "coverEditors": extract_cover_editors(pdf),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
