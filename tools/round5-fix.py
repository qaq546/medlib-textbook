# -*- coding: utf-8 -*-
"""round5-fix.py — 对"已处理的分片 md"做第 5 轮规则补丁(规则 1-5 / 13-17 / 23):
1) 图片按"图X-Y"图注归档为 images/figX-Y.png(+面板后缀 a/b/c)并回插引用;
   无图注图片(封面/编者照片/logo/二维码/视频缩略图/思维导图/数字人)继续排除;
   缺失文件按规则 4 插占位符 [图X-Y];不做 base64。
2) 目录删除原书页码(…… N),统一 - [标题](#锚点)。
3) 纯文本 $$ 块去包裹(Z 评分等真 LaTeX 块保留)。
4) 修复"根据病变部位分为\\n\\n以下类型。"类断段。
5) 带空格的图注(图 5-5 等)规范加粗。
6) 输出图片分类报告 + 自检(图数=注数、$ 计数、无哈希引用残留、无 base64)。
模板:头部 RAW / SRC_MD / MD / IMG_DIR 等常量按你的分片路径修改;
      SRC_MD 为任意既有底稿,输出写 OUT,再自行拷贝到书目录。
注意:转换出的 fig 图先写工作区 FIG_OUT,再统一拷贝到书目录 images/(沙箱)。
"""
import io, re, os, sys, shutil

PYLIBS = r"<py-libs 目录>"
if PYLIBS not in sys.path:
    sys.path.insert(0, PYLIBS)

WORK = os.path.join(PYLIBS, "work")
RAW = os.path.join(WORK, "<书名>-p1-200-raw.md")
SRC_MD = os.path.join(WORK, "<书名>-p1-200-round4-backfilled.md")  # 纯净第 4 轮底稿
MD = r"<书目录>\<书名>-p1-200.md"  # 书目录交付文件(拷贝目标)
OUT = os.path.join(WORK, "<书名>-p1-200-round5.md")
IMG_DIR = r"<书目录>\images"   # 哈希原图来源
FIG_OUT = os.path.join(WORK, "figs")                                  # 转换产物暂存
REPORT = os.path.join(WORK, "图片分类报告.txt")

CAP_RE = re.compile(r'^图\s*(\d+)-(\d+)[A-Z]?\s*[　 \u3000\u2003\u2002\t ]+(.+)$')
IMG_REF_RE = re.compile(r'images/([0-9a-f]+)\.(?:jpg|jpeg|png)')


def norm_ws(s):
    return re.sub(r'\s+', '', s)


# ---------- 图块解析(raw) ----------

def build_figure_map(raw_lines):
    """返回 figs 列表:每项 {rawline, hashes, kind, cap, capfull, norm}。"""
    figs = []
    n = len(raw_lines)
    i = 0
    while i < n:
        s = raw_lines[i].strip()
        if not s.startswith('!['):
            i += 1
            continue
        # 组:连续图片引用(允许其间空行与面板标签 A/B/C/D)
        hashes = []
        j = i
        while j < n:
            t = raw_lines[j].strip()
            if not t:
                j += 1
                continue
            if re.match(r'^[A-Z]$', t):  # 面板标签,继续找后续图
                j += 1
                continue
            m = IMG_REF_RE.search(t)
            if m:
                hashes.append(m.group(1))
                j += 1
                continue
            break
        # 前瞻:图注 或 类别标记
        kind, cap, capfull = None, None, None
        k, looked = j, 0
        while k < n and looked < 12:
            t = raw_lines[k].strip()
            if not t:
                k += 1
                continue
            if t.startswith('!['):
                break
            looked += 1
            m = CAP_RE.match(t)
            if m:
                kind, cap = 'FIG', '%s-%s' % (m.group(1), m.group(2))
                capfull = t
                break
            if t == '视频':
                kind = 'VIDEO'
                break
            if t in ('本章思维导图', '本章数字资源'):
                kind = 'MINDMAP'
                break
            if t.startswith('数字人'):
                kind = 'NUMHUMAN'
                break
            if t.startswith('#'):
                kind = 'FRONT'
                break
            if re.match(r'^[A-Z]$', t):
                k += 1
                continue
            k += 1
        if kind is None:
            kind = 'FRONT'
        figs.append({'rawline': i + 1, 'hashes': hashes, 'kind': kind,
                     'cap': cap, 'capfull': capfull,
                     'norm': norm_ws(capfull) if capfull else None})
        i = j
    return figs


# ---------- 图片命名与转换 ----------

def img_dst_name(x, y, idx):
    if idx == 0:
        return 'fig%s-%s.png' % (x, y)
    return 'fig%s-%s-%s.png' % (x, y, chr(ord('a') + idx - 1))


def convert_image(src, dst):
    try:
        import fitz  # vendored PyMuPDF
        pix = fitz.Pixmap(src)
        if pix.n - (pix.alpha or 0) > 3:  # CMYK 等转 RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(dst)
        return True, 'fitz'
    except Exception:
        try:
            shutil.copyfile(src, dst)
            return True, 'copy'
        except Exception:
            return False, 'failed'


def locate_caption(lines, fig):
    """按 raw 图注文本(归一化)在最终文件中定位图注行。返回行号或 None。"""
    key = fig['norm']
    if not key:
        return None
    x, y = fig['cap'].split('-')
    num = '%s-%s' % (x, y)
    for i, l in enumerate(lines):
        s = re.sub(r'^\*{0,2}', '', l.strip())
        s = re.sub(r'\*{0,2}$', '', s)
        if not s.startswith('图'):
            continue
        m = re.match(r'^图\s*' + re.escape(num) + r'[A-Z]?\s*[　 \u3000\u2003\u2002\t ]+', s)
        if not m:
            continue
        n = norm_ws(s)
        if n == key or (num.replace('-', '') in n and key in n):
            return i
    return None


# ---------- 主流程 ----------

def main():
    with io.open(RAW, encoding='utf-8') as f:
        raw_lines = f.read().split('\n')
    figs = build_figure_map(raw_lines)
    figmap = {}
    for fg in figs:
        if fg['kind'] == 'FIG':
            assert fg['cap'] not in figmap, 'dup caption %s' % fg['cap']
            figmap[fg['cap']] = fg

    # ---- 1. 转图(写到工作区 FIG_OUT) ----
    if not os.path.isdir(FIG_OUT):
        os.makedirs(FIG_OUT)
    conv = {}          # cap -> {name: (ok, how)}
    placeholder = {}   # cap -> True 若至少一张缺失
    for cap, fg in figmap.items():
        x, y = cap.split('-')
        conv[cap] = {}
        for idx, h in enumerate(fg['hashes']):
            src = os.path.join(IMG_DIR, h + '.jpg')
            if not os.path.exists(src):
                alt = os.path.join(IMG_DIR, h + '.png')
                if os.path.exists(alt):
                    src = alt
                else:
                    placeholder[cap] = True
                    conv[cap][img_dst_name(x, y, idx)] = (False, 'missing')
                    continue
            dst = os.path.join(FIG_OUT, img_dst_name(x, y, idx))
            ok, how = convert_image(src, dst)
            conv[cap][img_dst_name(x, y, idx)] = (ok, how)

    # ---- 2. 读第 4 轮底稿并定位图注(按 raw 图注文本) ----
    with io.open(SRC_MD, encoding='utf-8') as f:
        lines = f.read().split('\n')
    cap_idx = {}
    for cap, fg in figmap.items():
        idx = locate_caption(lines, fg)
        if idx is not None:
            cap_idx[cap] = idx
    missing_caps = [c for c in figmap if c not in cap_idx]
    if missing_caps:
        print('!! 未在最终文件中找到图注:', missing_caps)

    # ---- 3. 图注块顶扫描(吸收面板标签 A/B/C/D 与图内标注行) ----
    blocks = {}
    for cap, ci in cap_idx.items():
        labels, annots, top = [], [], ci
        j = ci - 1
        while j >= 0:
            s = lines[j].strip()
            if s == '':
                j -= 1
                continue
            if re.match(r'^[A-Z]$', s):
                labels.insert(0, s)
                top = j
                j -= 1
                continue
            if (len(s) <= 60 and not re.search(r'[。；：、，,]$', s)
                    and not s.startswith(('#', '|', '-', '!', '（', '('))
                    and not s.startswith('**图') and not re.match(r'^图\s*\d', s)):
                annots.insert(0, s)
                top = j
                j -= 1
                continue
            break
        blocks[cap] = {'top': top, 'ci': ci, 'labels': labels, 'annots': annots}
    consumed = set()
    for b in blocks.values():
        for k in range(b['top'], b['ci']):
            consumed.add(k)
    rev_cap = {v: k for k, v in cap_idx.items()}

    # ---- 4. 逐行重建 ----
    new_lines = []
    i, n = 0, len(lines)
    while i < n:
        if i in rev_cap:
            cap = rev_cap[i]
            b = blocks[cap]
            fg = figmap[cap]
            x, y = cap.split('-')
            nimg = len(fg['hashes'])
            refs = []
            for idx in range(nimg):
                name = img_dst_name(x, y, idx)
                if conv[cap].get(name, (False, 'missing'))[0]:
                    refs.append('![图%s](images/%s)' % (cap, name))
                else:
                    refs.append('[图%s]' % cap)  # 规则 4 占位符
            block = []
            for idx, ref in enumerate(refs):
                block.append(ref)
                if idx < len(b['labels']):
                    block.append(b['labels'][idx])
                block.append('')
            for a in b['annots']:
                block.append(a)
                block.append('')
            raw_l = lines[i].strip()
            core = raw_l[2:-2] if raw_l.startswith('**') and raw_l.endswith('**') else raw_l
            core = re.sub(r'^图\s*(\d+-\d+[A-Z]?)\s*[　 \u3000\u2003\u2002\t ]+',
                          lambda m: '图%s　' % m.group(1), core)
            block.append('**%s**' % core)
            new_lines.extend(block)
            i += 1
            continue
        if i in consumed:
            i += 1
            continue
        new_lines.append(lines[i])
        i += 1
    text = '\n'.join(new_lines)

    # ---- 5. 目录去页码 ----
    tl = text.split('\n')
    toc_start = next((k for k, l in enumerate(tl) if l.strip() == '# 目录'), None)
    toc_end = next((k for k, l in enumerate(tl) if l.startswith('# 第一章')), None)
    toc_fixed = 0
    if toc_start is not None and toc_end is not None:
        for k in range(toc_start, toc_end):
            new = re.sub(r'\s*……\s*\d+\s*$', '', tl[k])
            if new != tl[k]:
                toc_fixed += 1
            tl[k] = new
        text = '\n'.join(tl)

    # ---- 6. 纯文本 $$ 块去包裹 ----
    def _unwrap(m):
        inner = m.group(1)
        return inner if '\\' not in inner else m.group(0)
    text = re.sub(r'\$\$\n(.*?)\n\$\$', _unwrap, text, flags=re.S)

    # ---- 7. 断段修复(分为/包括/如下 结尾 + 短续句) ----
    tl = text.split('\n')
    merged = []
    i, n = 0, len(tl)
    while i < n:
        l = tl[i]
        if re.search(r'(分为|包括|如下)$', l.strip()):
            j = i + 1
            while j < n and tl[j].strip() == '':
                j += 1
            if j < n and tl[j].strip() and not tl[j].strip().startswith(
                    ('#', '|', '-', '**', '!', '（', '(', '①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩')) \
                    and not re.match(r'^\d+[\.、]', tl[j].strip()) \
                    and not re.match(r'^[一二三四五六七八九十]+、', tl[j].strip()):
                merged.append(l + tl[j].strip())
                i = j + 1
                continue
        merged.append(l)
        i += 1
    text = '\n'.join(merged)

    # ---- 7.5 针对性符号修正(规则 11:CD4⁺ 保留下标/上标) ----
    if 'CD4+' in text:
        text = text.replace('CD4+', 'CD4⁺')
        print('fix: CD4+ -> CD4⁺')

    # ---- 8. 空白清理 ----
    lines2 = [l.rstrip() for l in text.split('\n')]
    out = []
    blank = 0
    for l in lines2:
        if l == '':
            blank += 1
            if blank <= 1:
                out.append('')
        else:
            blank = 0
            out.append(l)
    while out and out[0] == '':
        out.pop(0)
    while out and out[-1] == '':
        out.pop()

    # ---- 9. 自检 ----
    final_text = '\n'.join(out)
    fig_refs = re.findall(r'!\[图\d+-\d+[A-Z]?-?[a-z]*\]\(images/fig', final_text)
    ph_refs = re.findall(r'(?<!\!)\[图\d+-\d+[A-Z]?\]', final_text)
    dollars = re.findall(r'\$+', final_text)
    hash_left = re.findall(r'images/[0-9a-f]{20,}\.', final_text)
    b64 = re.findall(r'data:image|base64', final_text)
    captions_final = set(re.findall(r'\*\*图(\d+-\d+[A-Z]?)[　 ]', final_text))
    n_fig_files = len([fn for fn in os.listdir(FIG_OUT) if re.match(r'^fig\d+-\d+', fn)])
    print('== 自检 ==')
    print('插入图片引用数:', len(fig_refs))
    print('fig 文件数(暂存):', n_fig_files)
    print('图注(加粗)数:', len(captions_final), '| 与 raw 图注一致:',
          captions_final == set(figmap.keys()))
    print('占位符(缺失图片):', len(ph_refs))
    print('$ 记号:', dollars)
    print('残留哈希引用:', len(hash_left), ' base64:', len(b64))
    print('目录去页码行数:', toc_fixed)

    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(final_text + '\n')
    print('written:', OUT, 'lines:', len(out))

    # ---- 10. 分类报告 ----
    rep = []
    rep.append('图片分类报告(p1-200) — 共 %d 组图片引用' % len(figs))
    rep.append('图注数=%d, 插入图片数=%d, 排除组数=%d' % (
        len(figmap), sum(len(fg['hashes']) for fg in figs if fg['kind'] == 'FIG'),
        sum(1 for fg in figs if fg['kind'] != 'FIG')))
    rep.append('')
    for fg in figs:
        cap = fg['cap'] or '-'
        if fg['kind'] == 'FIG':
            x, y = cap.split('-')
            names = [img_dst_name(x, y, idx) for idx in range(len(fg['hashes']))]
            desc = []
            for nm in names:
                st = conv[cap].get(nm, (False, 'missing'))
                desc.append('%s(%s)' % (nm, 'ok' if st[0] else st[1]))
            decision = '插入 ' + ', '.join(desc)
        else:
            reason = {'VIDEO': '视频缩略图/二维码', 'MINDMAP': '章节思维导图',
                      'NUMHUMAN': '数字人案例图', 'FRONT': '前置页(封面/编者照片/logo)'}[fg['kind']]
            decision = '排除 - ' + reason
        sizes = []
        for h in fg['hashes']:
            p = os.path.join(IMG_DIR, h + '.jpg')
            sizes.append(os.path.getsize(p) if os.path.exists(p) else -1)
        rep.append('L%-5d kind=%-8s 图注=%-6s 张数=%d 大小=%s  => %s' % (
            fg['rawline'], fg['kind'], cap, len(fg['hashes']), sizes, decision))
    with io.open(REPORT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(rep) + '\n')
    print('report:', REPORT)


if __name__ == '__main__':
    main()
