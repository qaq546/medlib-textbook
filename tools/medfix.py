# -*- coding: utf-8 -*-
"""medfix.py — 儿科学 p1-200 分片规范化与重构主脚本(Stage A-E, H-I)。
规则 1-5/16-17/23:图片按图注归档 figX-Y.png 并回插引用;目录不输出原书页码;
纯文本 $$ 块去包裹;图注兼容 '图 X-Y' 空格形态;输出前自检。"""
import io, re, os, json, shutil

WORK = r"F:\Develop\DeepSeek-Harness\Agent\Plugins\py-libs\work"
SRC = os.path.join(WORK, "24儿科学 第10版-p1-200-raw.md")
OUT = os.path.join(WORK, "24儿科学 第10版-p1-200-norm.md")
OUTLINE = r"F:\Develop\DeepSeek-Harness\Agent\Plugins\py-libs\pdfwork\outline.json"
# MinerU 哈希原图目录 / fig 图片输出目录(按书修改)
IMG_SRC = r"F:\Develop\MedicalTextbooks\md\24儿科学 第10版\images"
IMG_DST = IMG_SRC

# ---------- 工具函数 ----------

SUP = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','+':'⁺','-':'⁻','=':'⁼','(':'⁽',')':'⁾','a':'ᵃ','b':'ᵇ','c':'ᶜ','d':'ᵈ','e':'ᵉ','f':'ᶠ','g':'ᵍ','h':'ʰ','i':'ⁱ','j':'ʲ','k':'ᵏ','l':'ˡ','m':'ᵐ','n':'ⁿ','o':'ᵒ','p':'ᵖ','r':'ʳ','s':'ˢ','t':'ᵗ','u':'ᵘ','v':'ᵛ','w':'ʷ','x':'ˣ','y':'ʸ'}
SUB = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉','+':'₊','-':'₋','(':'₍',')':'₎','a':'ₐ','e':'ₑ','i':'ᵢ','o':'ₒ','r':'ᵣ','u':'ᵤ','v':'ᵥ','x':'ₓ'}

def sup_unicode(s):
    out = []
    for ch in s:
        out.append(SUP.get(ch, ch))
    return ''.join(out)

def sub_unicode(s):
    out = []
    for ch in s:
        out.append(SUB.get(ch, ch))
    return ''.join(out)

def convert_sup_sub(text):
    """把 <sup>...</sup> / <sub>...</sub> 转为 Unicode 上/下标。"""
    def _sup(m):
        return sup_unicode(m.group(1))
    def _sub(m):
        return sub_unicode(m.group(1))
    text = re.sub(r'<sup>\s*([^<]*?)\s*</sup>', _sup, text)
    text = re.sub(r'<sub>\s*([^<]*?)\s*</sub>', _sub, text)
    return text

MATH_KEEP = re.compile(r'\\bar\s*\{\s*x\s*\}\s*\\pm\s*s')

def convert_math(text):
    r"""把 $...$ 与 $$...$$ 公式转为 Unicode 纯文本;保留 $\bar{x} \pm s$。"""
    def _clean(s):
        if MATH_KEEP.search(s):
            return '$' + s + '$'
        # 1) 去掉 \mathrm / \text* 命令(任意花括号形态)
        s = re.sub(r'\\mathrm\s*', '', s)
        s = re.sub(r'\\text[a-z]*\s*', '', s)
        # 2) 去掉 \left \right;处理 \overline;处理 ( ) _ {\circ} 残渣
        s = s.replace('\\left', '').replace('\\right', '')
        s = re.sub(r'\\overline\s*(\{\s*)+([^{}]+?)(\s*\})+', lambda mm: mm.group(2) + '\u0304', s)
        s = re.sub(r'\)\s*_\s*\{\s*\\circ\s*\}', ')', s)
        # 3) P_{10^\circ} -> P₁₀ (百分位数,° 为 OCR 伪影)
        s = re.sub(r'_\s*\{\s*(\d[\d\s]*?)\s*\^\s*\{\s*\\circ\s*\}\s*\}', lambda mm: sub_unicode(mm.group(1).replace(' ', '')), s)
        # 4) _ { 数字 } / _{数字} -> 下标
        s = re.sub(r'_\s*\{\s*([0-9][0-9\s]*?)\s*\}', lambda mm: sub_unicode(mm.group(1).replace(' ', '')), s)
        # 字母下标(如 _ { o } 垃圾) 丢弃
        s = re.sub(r'_\s*\{\s*[a-zA-Z]\s*(?:_\s*\{\s*[a-zA-Z]\s*\}\s*)?\}', '', s)
        # 5) ^ { 内容 } -> 上标(其中 \circ -> °)
        def _sup(m):
            c = m.group(1).replace(' ', '').replace('\\circ', '°')
            return sup_unicode(c)
        s = re.sub(r'\^\s*\{\s*([^{}]*?)\s*\}', _sup, s)
        # 6) 剥离简单花括号(由内向外)
        for _ in range(20):
            s2 = re.sub(r'\{\s*([^{}]{1,80}?)\s*\}', lambda mm: mm.group(1), s)
            if s2 == s:
                break
            s = s2
        # 7) 无花括号下标/上标
        s = re.sub(r'_\s*(\d+)', lambda mm: sub_unicode(mm.group(1)), s)
        s = re.sub(r'\^\s*([+\-]?\d+|[+\-]+)', lambda mm: sup_unicode(mm.group(1)), s)
        # 8) 数字/小数点/逗号 粘连
        s = re.sub(r'(?<=\d)\s*,\s*(?=\d)', ',', s)
        s = re.sub(r'(?<=\d)\s*\.\s*(?=\d)', '.', s)
        s = re.sub(r'(?<=\d)\s+(?=\d)', '', s)
        # 9) 运算符与符号
        s = s.replace('\\pm', '±').replace('\\geqslant', '≥').replace('\\leqslant', '≤')
        s = s.replace('\\sim', '～').replace('\\downarrow', '↓').replace('\\uparrow', '↑')
        s = s.replace('\\times', '×').replace('\\div', '÷')
        s = s.replace('\\circ', '°').replace('\\%', '%')
        s = re.sub(r'\\\s*([<>()])', r'\1', s)
        # 10) 分隔: 非数字间逗号->顿号, 非数字小数点->顿号
        s = re.sub(r'(?<!\d),(?!\d)', '、', s)
        s = re.sub(r'(?<!\d)\.(?!\d)', '、', s)
        # 11) 去空白
        s = re.sub(r'\s+', '', s)
        # 12) OCR 化学式修正(去空白后)
        s = re.sub(r'PaC\s*0', 'PaCO', s)
        s = re.sub(r'TcS0', 'TcSO', s)
        s = re.sub(r'\(\s*0\s*H\s*\)', '(OH)', s)
        # 13) 清理孤立下划线/^ 与尾部标点
        s = re.sub(r'[_^]\s*', '', s)
        s = re.sub(r'[.,，。;；、]+$', '', s)
        return s
    def _disp(m):
        return '$$\n' + _clean(m.group(1)) + '\n$$'
    text = re.sub(r'\$\$\n(.*?)\n\$\$', _disp, text, flags=re.S)
    def _one(m):
        return _clean(m.group(1))
    out = []
    pos = 0
    for m in re.finditer(r'\$([^$\n]+)\$', text):
        out.append(text[pos:m.start()])
        out.append(_one(m))
        pos = m.end()
    out.append(text[pos:])
    return ''.join(out)

# ---------- 通用 LaTeX 垃圾清理(全文,保护 $ 公式) ----------

GREEK = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'varepsilon': 'ε', 'zeta': 'ζ',
    'eta': 'η', 'theta': 'θ', 'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ',
    'nu': 'ν', 'xi': 'ξ', 'pi': 'π', 'tau': 'τ', 'upsilon': 'υ', 'phi': 'φ',
    'chi': 'χ', 'psi': 'ψ', 'omega': 'ω', 'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ',
    'Lambda': 'Λ', 'Xi': 'Ξ', 'Pi': 'Π', 'Sigma': 'Σ', 'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω',
}
FONT_CMDS = r'(?:mathrm|mathbf|mathbb|textrm|mathit|boldsymbol|boldsymbol|bm|bf|rm|it|tt|sc|operatorname|text[a-z]*|mbox|hbox)'
KEEP_CMDS = r'(?:bar|pm|sim|circ|times|div|leq|geq|leqslant|geqslant|downarrow|uparrow|overline|left|right)'

def clean_latex_junk(text):
    # 只保护需要保留的 $\bar{x} \pm s$ 公式,其余公式也允许清理
    spans = []

    def _protect(m):
        s = m.group(0)
        if MATH_KEEP.search(s):
            spans.append(s)
            return '\x00S%d\x00' % (len(spans) - 1)
        return s

    text = re.sub(r'\$\$[^$]*\$\$|\$[^$\n]*\$', _protect, text, flags=re.S)
    # 特殊合并命令(OCR 粘连)
    text = re.sub(r'\\Deltac\b', '', text)
    text = re.sub(r'\\Delta\s*c\b', '', text)
    text = re.sub(r'\\bf\\nabla\\cdot\\bfq₁\\cdot\\bf\\nabla', 'α₁-', text)
    # 数学符号(convert_math 会在 $ 内再做一次,这里覆盖 $ 外)
    for k, v in [('leqslant', '≤'), ('geqslant', '≥'), ('times', '×'), ('div', '÷'),
                 ('pm', '±'), ('sim', '～'), ('circ', '°'), ('downarrow', '↓'),
                 ('uparrow', '↑'), ('lvert', '|'), ('rvert', '|')]:
        text = re.sub(r'\\' + k + r'\b', v, text)
    # 希腊字母(无条件替换,覆盖 \mug \gammac \beta₂ 等 OCR 粘连)
    for k, v in GREEK.items():
        text = re.sub(r'\\' + k, v, text)
    # 字体命令
    text = re.sub(r'\\' + FONT_CMDS + r'\s*', '', text)
    # \left \right
    text = re.sub(r'\\left\s*', '', text)
    text = re.sub(r'\\right\s*', '', text)
    # 简单符号
    text = text.replace(r'\,', '').replace(r'\!', '').replace(r'\;', '').replace(r'\,', '')
    text = re.sub(r'\\\*\s*', '*', text)
    text = re.sub(r'\\、', '、', text)
    text = re.sub(r'\\~', '～', text)
    text = re.sub(r'\\cdot\s*', '·', text)
    text = re.sub(r'\\cdoth\b', '·h', text)
    text = re.sub(r'\\substack\s*', '', text)
    text = re.sub(r'\\big[lr]?\s*', '', text)
    text = re.sub(r'\\begin\{[a-zA-Z*]*\}\s*', '', text)
    text = re.sub(r'\\end\{[a-zA-Z*]*\}\s*', '', text)
    # OCR 垃圾命令
    for junk in ['DF', 'odot', 'varsigma', 'setminus', 'nabla', 'ell', 'pH', 'rho', 'sigma',
                 'mathbb']:
        text = re.sub(r'\\' + junk + r'\b', '', text)
    text = re.sub(r'\\mathbb\s*\{\s*K\s*\}', '', text)
    text = re.sub(r'\\log\b', 'kg', text)
    text = re.sub(r'\\k(?=[a-z])', 'k', text)
    # 残留未知命令(保留合法数学命令)
    text = re.sub(r'\\(?!(?:' + KEEP_CMDS + r')\b)[a-zA-Z]{1,8}\s*', '', text)
    # 孤立的反斜杠
    text = re.sub(r'\\\s*(?=[^\\\s])', '', text)
    # 恢复 $ 公式
    text = re.sub(r'\x00S(\d+)\x00', lambda m: spans[int(m.group(1))], text)
    return text

# ---------- HTML 表格 -> GFM ----------

def parse_table(html):
    """解析 <table>..</table> 为 (header_rows, data_rows, col_count)。"""
    rows_html = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S)
    grid = []          # 每行: list of [text, rowspan, colspan] 按出现顺序
    for rh in rows_html:
        cells = []
        for cm in re.finditer(r'<t[dh]((?:\s[^>]*)?)>(.*?)</t[dh]>', rh, re.S):
            attrs, content = cm.group(1), cm.group(2)
            rs = int(re.search(r'rowspan\s*=\s*"?(\d+)"?', attrs).group(1)) if re.search(r'rowspan\s*=\s*"?(\d+)"?', attrs) else 1
            cs = int(re.search(r'colspan\s*=\s*"?(\d+)"?', attrs).group(1)) if re.search(r'colspan\s*=\s*"?(\d+)"?', attrs) else 1
            content = re.sub(r'<[^>]+>', '', content)          # 去内部标签
            content = convert_sup_sub(content)
            content = convert_math(content)
            content = content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&nbsp;', ' ')
            content = content.replace(';', '；').replace('\n', ' ').strip()
            content = re.sub(r'(?<!\d),', '，', content)
            content = re.sub(r'(?<=[\u4e00-\u9fff]):', '：', content)
            cells.append([content, rs, cs])
        grid.append(cells)
    return grid

def expand_grid(grid):
    """展开 rowspan/colspan 为矩形 grid。"""
    out = []
    active_spans = {}   # col -> 剩余行数 (来自上方 rowspan)
    for row in grid:
        cols = []
        col = 0
        # 先处理上方 rowspan 占位
        new_active = {}
        for c, remain in active_spans.items():
            if remain > 1:
                new_active[c] = remain - 1
        for c, remain in active_spans.items():
            while col < c:
                cols.append('')
                col += 1
            if remain == 1:
                cols.append('')
                col += 1
        for cell in row:
            text, rs, cs = cell
            while col in new_active:
                cols.append('')
                col += 1
            cols.append(text)
            col += 1
            for _ in range(cs - 1):
                cols.append('')
                col += 1
            if rs > 1:
                for k in range(1, rs):
                    new_active[col - 1] = rs - k  # 占位列 col-1,剩余 rs-1 行
        active_spans = new_active
        out.append(cols)
    width = max((len(r) for r in out), default=0)
    out = [r + [''] * (width - len(r)) for r in out]
    return out, width

def render_gfm(grid, width):
    lines = []
    lines.append('| ' + ' | '.join(grid[0]) + ' |')
    lines.append('|' + '---|' * width)
    for r in grid[1:]:
        lines.append('| ' + ' | '.join(r) + ' |')
    return '\n'.join(lines)

def convert_tables(text):
    def _one(m):
        grid = parse_table(m.group(1))
        if not grid:
            return ''
        exp, width = expand_grid(grid)
        if width == 0:
            return ''
        return render_gfm(exp, width)
    # 处理 <table> 跨行
    out = []
    pos = 0
    for m in re.finditer(r'<table>(.*?)</table>', text, re.S):
        out.append(text[pos:m.start()])
        out.append(_one(m))
        pos = m.end()
    out.append(text[pos:])
    return ''.join(out)

# ---------- 图片回插(规则 1-5):按图注命名 figX-Y.png 并插入引用 ----------

def build_fig_map(lines):
    """从分片原始行构建 图注 -> [哈希] 映射(带图注的图片块;面板图多图一注)。"""
    fig_map = {}
    n = len(lines)
    i = 0
    while i < n:
        if not lines[i].strip().startswith('!['):
            i += 1
            continue
        hashes = []
        j = i
        while j < n:
            t = lines[j].strip()
            if not t:
                j += 1
                continue
            if re.match(r'^[A-Z]$', t):   # 面板标签,继续找后续图
                j += 1
                continue
            m = re.search(r'images/([0-9a-f]+)\.(?:jpg|jpeg|png)', t)
            if m:
                hashes.append(m.group(1))
                j += 1
                continue
            break
        cap = None
        k, looked = j, 0
        while k < n and looked < 12:
            t = lines[k].strip()
            if not t:
                k += 1
                continue
            if t.startswith('!['):
                break
            looked += 1
            m = re.match(r'^图\s*(\d+-\d+[A-Z]?)\s*[　 \u3000\u2003\u2002\t ]+', t)
            if m:
                cap = m.group(1)
                break
            if re.match(r'^[A-Z]$', t):
                k += 1
                continue
            break
        if cap and hashes:
            fig_map[cap] = hashes
        i = j
    return fig_map

def fig_dst_name(cap, idx):
    if idx == 0:
        return 'fig%s.png' % cap
    return 'fig%s-%s.png' % (cap, chr(ord('a') + idx - 1))

def convert_to_png(src, dst):
    """fitz 转 PNG;失败则复制字节。"""
    try:
        import fitz
        pix = fitz.Pixmap(src)
        if pix.n - (pix.alpha or 0) > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(dst)
        return True
    except Exception:
        try:
            shutil.copyfile(src, dst)
            return True
        except Exception:
            return False

def insert_figures(text, fig_map):
    """在文本中:图片引用插到图注行上方(命名 figX-Y.png),图注统一加粗;
    无对应图注的图片引用不处理(调用方已丢弃)。"""
    lines = text.split('\n')
    cap_idx = {}
    for cap in fig_map:
        for i, l in enumerate(lines):
            s = re.sub(r'\*{0,2}$', '', re.sub(r'^\*{0,2}', '', l.strip()))
            if re.match(r'^图\s*' + re.escape(cap) + r'[A-Z]?\s*[　 \u3000\u2003\u2002\t ]+', s):
                cap_idx[cap] = i
                break
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
        blocks[cap] = (top, ci, labels, annots)
    consumed = set()
    for top, ci, labels, annots in blocks.values():
        consumed.update(range(top, ci))
    rev = {ci: cap for cap, ci in cap_idx.items()}
    out = []
    i, n = 0, len(lines)
    while i < n:
        if i in rev:
            cap = rev[i]
            top, ci, labels, annots = blocks[cap]
            block = []
            for idx, h in enumerate(fig_map[cap]):
                name = fig_dst_name(cap, idx)
                src = os.path.join(IMG_SRC, h + '.jpg')
                if not os.path.exists(src):
                    alt = os.path.join(IMG_SRC, h + '.png')
                    if os.path.exists(alt):
                        src = alt
                dst = os.path.join(IMG_DST, name)
                ok = os.path.exists(dst) or convert_to_png(src, dst)
                if ok:
                    block.append('![图%s](images/%s)' % (cap, name))
                else:
                    block.append('[图%s]' % cap)   # 规则 4 占位符
                if idx < len(labels):
                    block.append(labels[idx])
                block.append('')
            for a in annots:
                block.append(a)
                block.append('')
            raw_l = lines[i].strip()
            core = raw_l[2:-2] if raw_l.startswith('**') and raw_l.endswith('**') else raw_l
            core = re.sub(r'^图\s*(\d+-\d+[A-Z]?)\s*[　 \u3000\u2003\u2002\t ]+',
                          lambda m: '图%s　' % m.group(1), core)
            block.append('**%s**' % core)
            out.extend(block)
            i += 1
            continue
        if i in consumed:
            i += 1
            continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out)

# ---------- 锚点 ----------

def make_anchor(title):
    t = title.strip()
    # GitHub-slugger 风格: 去标点(保留中文/字母数字/_/-), 空格->'-'
    t = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', t)
    t = t.replace('\u3000', '-').replace(' ', '-')
    t = re.sub(r'-+', '-', t).strip('-')
    return t.lower()

# ---------- 目录重建 ----------

def norm_key(t):
    t = t.lower()
    t = re.sub(r'[\s\u3000，。、；：？！（）()【】《》""''「」·…—\-—.,/\\|]+', '', t)
    return t

def build_toc(outline_path, raw_lines, body_lines):
    """从 PDF 书签重建 # 目录(锚点取正文实际标题,保证链接有效)。"""
    with io.open(outline_path, encoding='utf-8') as f:
        toc = json.load(f)
    # 正文标题 map: 归一化标题 -> 实际标题
    body_map = {}
    for l in body_lines:
        m = re.match(r'^(#{1,6})\s+(.*)$', l)
        if m:
            key = norm_key(m.group(2))
            if key and key not in body_map:
                body_map[key] = m.group(2)
    def printed(pdf_pg):
        if pdf_pg >= 28:
            return pdf_pg - 27
        return None
    out = ['# 目录', '']
    for lvl, title, pg in toc:
        if lvl > 3:
            continue
        if title.strip() == '目录':
            continue
        if title.strip() == '封底页':
            continue
        t = title.strip().replace('\x00', '').replace('\u200b', '')
        # 清理 outline 里的 OCR 小问题
        t = t.replace('附表1 -1', '附表1-1').replace('附表1 -2', '附表1-2')
        t = re.sub(r'\s+', ' ', t)
        t = t.replace('（x ±s）', '（x̄±s）').replace('（x̄ ± s）', '（x̄±s）')
        t = t.replace('3 ～＜ 7 岁', '3～＜7岁')
        t = t.replace('3 ～ < 7 岁', '3～＜7岁')
        t = t.replace(' ', '\u3000')
        key = norm_key(t)
        disp = body_map.get(key, t)
        # 正文标题可能还带 MinerU 的 | 伪影与半角空格,统一清理
        disp = disp.replace('|', '\u3000').replace('｜', '\u3000')
        disp = re.sub(r'(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])', '', disp)
        p = printed(pg)
        indent = '  ' * (lvl - 1)
        link = '[%s](#%s)' % (disp, make_anchor(disp))
        out.append('%s- %s' % (indent, link))   # 规则 16/17:不输出原书页码
    # 附加:原书目录里的特殊条目(数字创新)
    out.append('')
    out.append('【数字创新：虚拟仿真数字人】')
    for i, l in enumerate(raw_lines):
        ls = l.strip()
        if ls.startswith('数字人案例'):
            out.append('- ' + re.sub(r'\s*……\s*\d+\s*$', '', re.sub(r'\s+', ' ', ls)))
    out.append('')
    return out

# ---------- 主流程 ----------

def main():
    with io.open(SRC, encoding='utf-8') as f:
        lines = f.read().split('\n')

    # Stage 0: 去掉 \r、分片注释
    lines = [l.rstrip('\r') for l in lines]
    lines = [l for l in lines if not re.match(r'^\s*<!--\s*分片', l)]

    # ---- Stage H(前): 目录区替换 ----
    # 找 目录 起始行 和 第一章绪论行,替换中间区域
    toc_start = next((i for i, l in enumerate(lines) if l.strip() == '## 目录' or l.strip() == '# 目录'), None)
    ch1_intro = next(i for i, l in enumerate(lines) if l.startswith('儿科学是临床医学范畴中的二级学科'))
    if toc_start is not None:
        new_toc = build_toc(OUTLINE, lines, lines[ch1_intro:])
        lines = lines[:toc_start] + new_toc + lines[ch1_intro:]

    # ---- Stage B: 封面重复块删除 ----
    # 找第一个 '# 儿科学'
    idx_cover = next(i for i, l in enumerate(lines) if l.strip() == '# 儿科学')
    # 删除其前面的重复 OCR 封面块(## 儿科学 ... 副主编|...)
    del_start = None
    for i in range(idx_cover):
        if lines[i].strip() == '## 儿科学':
            del_start = i
            break
    if del_start is not None:
        del lines[del_start:idx_cover]
        # 重新计算 idx_cover
        idx_cover = next(i for i, l in enumerate(lines) if l.strip() == '# 儿科学')

    # 封面区文本修正 (到 '·北　京·' 之后)
    def fix_cover(l):
        l = re.sub(r'^##\s*Pediatrics\s*$', 'Pediatrics', l)
        l = re.sub(r'第\s*\u3000*\s*版\s*10', '第10版', l)
        l = l.replace('主 审 | 王卫平', '主　审　王卫平')
        l = l.replace('主 编 | 黄国英', '主　编　黄国英')
        l = re.sub(r'^副\s*\u3000*\s*主\s*\u3000*\s*编\s*\|?\s*', '副主编　', l)
        l = l.replace('数 字 主 审 | 王卫平', '数字主审　王卫平')
        l = l.replace('数 字 主 编 | 黄国英', '数字主编　黄国英')
        l = l.replace('数字副主编 | 杜立中', '数字副主编　杜立中')
        l = re.sub(r'^主\s+审\s*\|?\s*', '主　审　', l)
        l = re.sub(r'^主\s+编\s*\|?\s*', '主　编　', l)
        l = re.sub(r'^主\s*编\s*：', '主　编：', l)
        l = re.sub(r'^数\s*字\s*主\s*审\s*\|?\s*', '数字主审　', l)
        l = re.sub(r'^数\s*字\s*主\s*编\s*\|?\s*', '数字主编　', l)
        l = re.sub(r'^副\s*主\s*编\s*：', '副主编：', l)
        l = re.sub(r'^数字副主编\s*：', '数字副主编：', l)
        l = re.sub(r'E\s*[-\u2002\u2003]?\s*mail\s*：?\s*pmph\s*@\s*pmph\.com', 'E-mail：pmph@pmph.com', l)
        l = re.sub(r'E\s*[-\u2002\u2003]?\s*mail\s*：?\s*WQ\s*@\s*pmph\.com', 'E-mail：WQ@pmph.com', l)
        l = re.sub(r'E\s*[-\u2002\u2003]?\s*mail\s*：?\s*zhiliang\s*@\s*pmph\.com', 'E-mail：zhiliang@pmph.com', l)
        l = re.sub(r'E\s*[-\u2002\u2003]?\s*mail\s*：?\s*zengzhi\s*@\s*pmph\.com', 'E-mail：zengzhi@pmph.com', l)
        l = re.sub(r'^本\s*：\s*850', '开　本：850', l)
        l = re.sub(r'人卫智网\s*\u3000*\s*www\.ipmph\.com', '人卫智网　www.ipmph.com　', l)
        l = re.sub(r'人卫官网\s*\u3000*\s*www\.pmph\.com', '人卫官网　www.pmph.com　', l)
        l = l.replace('## 儿　科　学', '')
        l = l.replace('## 版权所有，侵权必究！', '## 版权页\n\n版权所有，侵权必究！')
        return l
    lines = [fix_cover(l) for l in lines]

    # 版权页"印 刷:" 等字段归一(全角空格)
    lines = [re.sub(r'^(印\s*刷|经\s*销|地\s*址|邮\s*编|字\s*数|版\s*次|印\s*次|标\s*准\s*书\s*号|定\s*价)\s*：', lambda m: m.group(1).replace(' ', '　') + '　：', l) for l in lines]

    # 编委区: 归一化
    lines = [re.sub(r'^##\s*编\s*\u3000*\s*委\s*（', '## 编委（', l) for l in lines]
    lines = [l.replace('数字编委', '## 数字编委') if l.strip() == '数字编委' else l for l in lines]
    lines = [re.sub(r'^##\s*(孙\s*锟|李\s*秋)\s*$', lambda m: '### ' + m.group(1).replace(' ', '　'), l) for l in lines]
    lines = [re.sub(r'^##\s*(王卫平|黄国英|罗小平|杜立中|母得志|钱素云)\s*$', lambda m: '### ' + m.group(1), l) for l in lines]

    # ---- Stage C: 正文结构 ----
    chapters = [
        ('儿科学是临床医学范畴中的二级学科', '第一章　绪论'),
        ('人的生长发育是指从受精卵到成人的成熟过程', '第二章　生长发育'),
        ('儿童保健同属儿科学与预防医学的分支', '第三章　儿童保健'),
        ('与成人不同，儿童各器官系统的结构与功能', '第四章　儿科疾病诊治原则'),
        ('充足的营养是小儿维持生命和身心健康', '第五章　营养和营养障碍疾病'),
        ('新生儿期属于儿科的特殊阶段', '第六章　新生儿与新生儿疾病'),
        ('免疫系统参与绝大多数儿科疾病', '第七章　免疫性疾病'),
        ('风湿性疾病既往曾称为结缔组织疾病', '第八章　风湿性疾病'),
        ('感染性疾病是由各种病原体感染引起', '第九章　感染性疾病'),
    ]
    inserts = []
    for phrase, title in chapters:
        for i, l in enumerate(lines):
            if l.startswith(phrase):
                inserts.append((i, title))
                break
    for i, title in sorted(inserts, reverse=True):
        lines[i:i] = ['# ' + title, '']

    # 正文标题层级
    def fix_heading(l):
        # 标题内汉字间的半角空格(如 概 述)先行去除;全角空格保留
        if l.startswith('#'):
            l = re.sub(r'(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])', '', l)
        m = re.match(r'^#\s+(第[一二三四五六七八九十百]+节)\s*[|｜]?\s*(.*)$', l)
        if m:
            return '## %s　%s' % (m.group(1), m.group(2))
        m = re.match(r'^##\s+(第[一二三四五六七八九十百]+节)\s*[|｜]\s*(.*)$', l)
        if m:
            return '## %s　%s' % (m.group(1), m.group(2))
        m = re.match(r'^##\s+([一二三四五六七八九十]+)、(.*)$', l)
        if m:
            return '### %s、%s' % (m.group(1), m.group(2))
        m = re.match(r'^##\s+（([一二三四五六七八九十]+)）(.*)$', l)
        if m:
            return '#### （%s）%s' % (m.group(1), m.group(2))
        # ## 数字条目 -> 五级标题(内容过长则拆行)
        m = re.match(r'^##\s+(\d+)[\.、]\s*(.*)$', l)
        if m:
            return '##### %s. %s' % (m.group(1), m.group(2))
        # ## 【...】 -> 四级标题
        m = re.match(r'^##\s+(【[^】]+】.*)$', l)
        if m:
            return '#### %s' % m.group(1)
        return l
    lines = [fix_heading(l) for l in lines]

    # ## 数字条目: 拆分过长内容行(五级标题 + 正文)
    new_lines = []
    for i, l in enumerate(lines):
        m = re.match(r'^#####\s+\d+[\.、](.*)$', l)
        if m:
            rest = m.group(1)
            sp = re.search(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff（(])', rest)
            if sp:
                head = '##### %s' % rest[:sp.start()]
                body = rest[sp.end():]
                new_lines.append(head)
                new_lines.append('')
                new_lines.append(body)
                continue
        new_lines.append(l)
    lines = new_lines

    # ---- Stage D/E: 图片/视频/图注/表格/公式 ----
    fig_map = build_fig_map(lines)   # 图片:图注 -> 哈希(供 insert_figures 回插)
    new_lines = []
    for l in lines:
        ls = l.strip()
        if ls.startswith('![') and 'images/' in l:
            continue
        if ls == '视频':
            continue
        if ls == '本章数字资源':
            continue
        m = re.match(r'^图\s*(\d+-\d+[A-Z]?)\s*[　 \u3000\u2003\u2002\t ]+(.*)$', ls)
        if m and len(m.group(2)) > 0 and not l.startswith('**'):
            new_lines.append('**图%s　%s**' % (m.group(1), m.group(2).strip()))
            continue
        m = re.match(r'^(表\d+-\d+[A-Z]?)\s*\u3000*\s*(.*)$', ls)
        if m and len(m.group(2)) > 0 and not l.startswith('**'):
            new_lines.append('**%s　%s**' % (m.group(1), m.group(2).strip()))
            continue
        if ls == '本章思维导图':
            continue
        new_lines.append(l)
    text = '\n'.join(new_lines)
    text = convert_tables(text)
    text = clean_latex_junk(text)
    text = convert_math(text)
    text = convert_sup_sub(text)
    # 图片回插(规则 1-5):figX-Y.png + 引用 + 图注加粗
    text = insert_figures(text, fig_map)
    # 纯文本 $$ 块去包裹(内容无任何 LaTeX 命令时;Z 评分等真 LaTeX 保留)
    text = re.sub(r'\$\$\n(.*?)\n\$\$',
                  lambda m: m.group(1) if '\\' not in m.group(1) else m.group(0),
                  text, flags=re.S)

    # ---- 针对性行修复(对照 PDF 原文核实) ----
    targeted = [
        # 公式类
        ('PaO₂PH 降低', 'PaO₂、pH 降低'),
        ('并不困难， ·pH 的变化', '并不困难，pH 的变化'),
        ('metabolicrate', 'metabolic rate'),
        ('Cl⁻、HCO⁻ 和蛋白', 'Cl⁻、HCO₃⁻ 和蛋白'),
        ('身高(K)(m)]', '身高（长）（m）］'),
        ('(mmol)=|-BE|×0.3× 体重 (kg) ）', '（mmol）=|-BE|×0.3×体重（kg）'),
        ('(mlΛ)=|-BE|×0.5× 体重 (kg) ）', '（ml）=|-BE|×0.5×体重（kg）'),
        ('RDR (⁰/₀)=(A₅-A₀)/A₅×100⁰/₀', 'RDR（%）=（A₅-A₀）/A₅×100%'),
        ('口服 5h 后（A）血浆视黄醇浓度', '口服5h后（A₅）血浆视黄醇浓度'),
        ('[llrlr 体重 (~kg~)-30]', '［体重（kg）-30］'),
        ('·q₁· 抗胰蛋白酶', 'α₁-抗胰蛋白酶'),
        ('PaCO₂、HCO₃ 变化与 pH', 'PaCO₂、HCO₃⁻ 变化与 pH'),
        # 中文 OCR 错字(逐条对照 PDF 文本层核实)
        ('研穷', '研究'),
        ('迄令为止', '迄今为止'),
        ('今人瞩目', '令人瞩目'),
        ('影响令后一生', '影响今后一生'),
        ('预防于预', '预防干预'),
        ('机休新陈代谢', '机体新陈代谢'),
        ('伴随症状及透因', '伴随症状及诱因'),
        ('第几助间', '第几肋间'),
        ('许多优占能保持', '许多优点，能保持'),
        ('临床特占为口渴', '临床特点为口渴'),
        ('必需氨基酸句括', '必需氨基酸包括'),
        ('固体食物包括角类', '固体食物包括鱼类'),
        ('腹部膨降下垂', '腹部膨隆下垂'),
        ('皮肤表皮角化层蒲', '皮肤表皮角化层薄'),
        ('使肺手细血管', '使肺毛细血管'),
        ('皮肤黏膜瘀占瘀斑', '皮肤黏膜瘀点、瘀斑'),
        ('以余黄色葡萄球菌', '以金黄色葡萄球菌'),
        ('或附着占炎', '或附着点炎'),
        ('间歇性数且或数年后', '间歇性数月或数年后'),
        ('宽松目少接缝', '宽松且少接缝'),
        ('河豚、角苦胆', '河豚、鱼苦胆'),
        # 英文/缩写 OCR 错误
        ('Kernigsign', 'Kernig sign'),
        ('（WH0)', '（WHO）'),
        ('中JMCI战略', '中IMCI战略'),
        ('growth retardationrestriction', 'growth restriction'),
        ('disseminatedintravascular coagulation', 'disseminated intravascular coagulation'),
        ('congenitaadrenal', 'congenital adrenal'),
        ('protein complementaryaction', 'protein complementary action'),
        ('secretorimmunoglobulin A', 'secretory immunoglobulin A'),
        ('parenteralnutrition', 'parenteral nutrition'),
        ('acrodermatitienteropathica', 'acrodermatitis enteropathica'),
        ('肺泡上皮细胞钠离子通道（epitheliasodium channel', '肺泡上皮细胞钠离子通道（epithelial sodium channel'),
        ('humanparvovirus B19', 'human parvovirus B19'),
        ('human immunodeficiencyvirus', 'human immunodeficiency virus'),
        ('juvenilechronic arthritis', 'juvenile chronic arthritis'),
        ('lunghypoplasia', 'lung hypoplasia'),
        ('mononuclearcell', 'mononuclear cell'),
        ('phosphatidylcholin', 'phosphatidylcholine'),
        ('pulmonarysurfactant', 'pulmonary surfactant'),
        ('researchlaboratories', 'research laboratories'),
        ('transcutaneousoxygen saturation', 'transcutaneous oxygen saturation'),
        ('weightedimaging', 'weighted imaging'),
        ('herpessimplex virus', 'herpes simplex virus'),
        ('经皮氧分压（TcPO）', '经皮氧分压（TcPO₂）'),
        ('经皮二氧化碳分压（TcPCO）', '经皮二氧化碳分压（TcPCO₂）'),
        ('表明血清中存在游离的A', '表明血清中存在游离的ABO或Rh血型抗体，并可能与红细胞结合引起溶血。此项试验有助于估计是否继续溶血、'),
        ('Sustainable Development Goals，SGs）', 'Sustainable Development Goals，SDGs）'),
        ('World HealthOrganization', 'World Health Organization'),
        ('peakheight velocity', 'peak height velocity'),
        ('~', '～'),
    ]
    for old, new in targeted:
        text = text.replace(old, new)

    # ---- 术语定义斜体:（English term，ABBR）→（*English term*，ABBR）----
    _def_pat = re.compile(r'（([A-Za-z]+(?: [A-Za-z]+)+)[，,]\s*([A-Za-z][A-Za-z0-9/]*?)）')
    def _def_rep(m):
        return '（*%s*，%s）' % (m.group(1), m.group(2))
    tmp = text.split('\n')
    for i, l in enumerate(tmp):
        if re.match(r'^\|[\s:|-]+\|$', l):
            continue
        tmp[i] = _def_pat.sub(_def_rep, l)
    text = '\n'.join(tmp)

    # ---- 合并被分页/图片切断的续句 ----
    tmp = text.split('\n')
    merged = []
    i = 0
    n = len(tmp)
    while i < n:
        l = tmp[i]
        if re.search(r'[，、；：,;:]\s*$', l) or re.search(r'(分为|包括|如下)$', l.strip()):
            j = i + 1
            while j < n and tmp[j] == '':
                j += 1
            if j < n and tmp[j] and not tmp[j].startswith(('|', '#', '**', '!', '- ', '（', '①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩')) \
                    and not re.match(r'^\d+[\.、]', tmp[j]) and not re.match(r'^[一二三四五六七八九十]+、', tmp[j]):
                merged.append(l + tmp[j].lstrip())
                i = j + 1
                continue
        merged.append(l)
        i += 1
    text = '\n'.join(merged)

    lines = text.split('\n')

    # ---- 空白清理 ----
    lines = [l.rstrip() for l in lines]
    # 合并连续空行
    out = []
    blank = 0
    for l in lines:
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

    # ---- 自检(规则 23):图引用/图注/残留 $/哈希引用/base64 ----
    ft = '\n'.join(out)
    print('[自检] 图引用=%d 图注=%d $=%d 哈希残留=%d base64=%d' % (
        len(re.findall(r'!\[图\d+-\d+[A-Z]?-?[a-z]*\]\(images/fig', ft)),
        len(set(re.findall(r'\*\*图(\d+-\d+[A-Z]?)[　 ]', ft))),
        len(re.findall(r'\$', ft)),
        len(re.findall(r'images/[0-9a-f]{20,}\.', ft)),
        len(re.findall(r'data:image|base64', ft))))

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    print('written', OUT, 'lines:', len(out))

if __name__ == '__main__':
    main()
