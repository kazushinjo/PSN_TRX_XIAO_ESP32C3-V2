# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 JA6FUF (kazushinjo)
"""
部品実装図（docs/PSN_TRX_部品実装図.pdf）と、組み立て説明書用の配置図 PNG を作る。

  1) KiCad 付属の Python で基板データを書き出す
       /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
           docs/tools/export_board.py kicad/PSN_TRX.kicad_pcb board.json
  2) matplotlib のある Python で作図する
       python3 docs/tools/make_parts_layout.py board.json docs/tools/parts_notes.json docs/PSN_TRX_部品実装図.pdf [PNG の出力先フォルダ]

parts_notes.json はブロックごとの部品と「種類」「注意」の表（ブロックの順＝組立順の目安）と、ブロックの色。
最後のページは調整箇所（manual/調整手順.md の番号）。
"""
import json, math, sys, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Rectangle, Circle, Ellipse, Polygon, FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.transforms as mtrans

FW3 = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
FW6 = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
if not os.path.exists(FW3):   # Windows: 游ゴシック
    FW3, FW6 = 'C:/Windows/Fonts/YuGothM.ttc', 'C:/Windows/Fonts/YuGothB.ttc'
for f in (FW3, FW6):
    fm.fontManager.addfont(f)
JP = fm.FontProperties(fname=FW3).get_name()
plt.rcParams['font.family'] = JP
BOLD = fm.FontProperties(fname=FW6)

board = json.load(open(sys.argv[1]))
notes = json.load(open(sys.argv[2]))
OUT = sys.argv[3]
PNGDIR = sys.argv[4] if len(sys.argv) > 4 else None

TITLE = 'PSN_TRX_XIAO_ESP32C3-V2　部品実装図'
SUB = '基板 134.1 × 129.7 mm / 4層 / リード部品＋表面実装 2 点（U4・U5 NJM2594V）　V2 Ver 1.0　2026-10-30'
COPPER = '#c8762f'
FAB = '#333333'
FAINT = '#c8c8c8'
NAVY = '#1f2d6b'
NEWCOL = '#7b3fbf'

FP = {f['ref']: f for f in board['fps']}
EDGE = [e for e in board['edge']]
xs = [p[0] for e in EDGE for p in (e.get('p') or [e.get('a'), e.get('b')]) if p]
ys = [p[1] for e in EDGE for p in (e.get('p') or [e.get('a'), e.get('b')]) if p]
BX0, BX1, BY0, BY1 = min(xs), max(xs), min(ys), max(ys)


def draw_shape(ax, s, col, lw, mirror):
    mx = (lambda x: BX0 + BX1 - x) if mirror else (lambda x: x)
    t = s['t']
    if t == 'seg':
        ax.plot([mx(s['a'][0]), mx(s['b'][0])], [s['a'][1], s['b'][1]], color=col, lw=lw, solid_capstyle='round')
    elif t == 'poly':
        pts = [(mx(x), y) for x, y in s['p']]
        ax.add_patch(Polygon(pts, closed=True, fill=bool(s.get('fill')), fc=col if s.get('fill') else 'none', ec=col, lw=lw))
    elif t == 'circ':
        ax.add_patch(Circle((mx(s['c'][0]), s['c'][1]), s['r'], fill=bool(s.get('fill')), fc=col if s.get('fill') else 'none', ec=col, lw=lw))
    elif t == 'arc3':
        (x1, y1), (x2, y2), (x3, y3) = s['a'], s['m'], s['b']
        d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        if abs(d) < 1e-9:
            return
        ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / d
        uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / d
        r = math.hypot(x1 - ux, y1 - uy)
        a1, a2, am = (math.atan2(y - uy, x - ux) for x, y in ((x1, y1), (x3, y3), (x2, y2)))
        # 始点→中点→終点の向きで角度を並べる
        def norm(a, ref):
            while a < ref:
                a += 2 * math.pi
            return a
        e1 = norm(a2, a1); m1 = norm(am, a1)
        if m1 > e1:
            e1 -= 2 * math.pi
        n = 30
        pts = [(ux + r * math.cos(a1 + (e1 - a1) * k / n), uy + r * math.sin(a1 + (e1 - a1) * k / n)) for k in range(n + 1)]
        ax.plot([mx(x) for x, y in pts], [y for x, y in pts], color=col, lw=lw)


def draw_pad(ax, p, fc, ec, mirror, drill=True):
    x, y = p['c']
    if mirror:
        x = BX0 + BX1 - x
    w, h = p['sz']
    ang = -p['ang'] if not mirror else p['ang']
    tr = mtrans.Affine2D().rotate_deg_around(x, y, ang) + ax.transData
    if p['sh'] == 'circle':
        ax.add_patch(Circle((x, y), w / 2, fc=fc, ec=ec, lw=0.3))
    elif p['sh'] == 'oval':
        ax.add_patch(Ellipse((x, y), w, h, fc=fc, ec=ec, lw=0.3, transform=tr))
    else:
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=fc, ec=ec, lw=0.3, transform=tr))
    if drill and p['drill'] > 0:
        ax.add_patch(Circle((x, y), p['drill'] / 2, fc='white', ec='none'))


def draw_fp(ax, f, mode, mirror=False, label=True, small=False):
    """mode: 'normal' / 'faint' / 'hi'（強調）"""
    col = FAB if mode != 'faint' else FAINT
    lw = 0.5 if mode != 'faint' else 0.4
    for s in f['fab']:
        draw_shape(ax, s, col, lw, mirror)
    for p in f['pads']:
        if mode == 'faint':
            draw_pad(ax, p, 'white', FAINT, mirror)
        else:
            draw_pad(ax, p, COPPER, '#7a4a1c', mirror)
    if label and mode != 'faint':
        (x0, y0), (x1, y1) = f['bbox']
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if mirror:
            cx = BX0 + BX1 - cx
        ref = 'U3 (XIAO)' if f['ref'] == 'U3' else f['ref']
        fs = 4.6 if small else 6.0
        ax.text(cx, cy, ref, ha='center', va='center', fontsize=fs, color=NAVY, fontproperties=BOLD,
                zorder=20, bbox=dict(fc='white', ec='none', alpha=0.65, pad=0.2))
        if not small and f['val'] and not f['ref'].startswith(('H', 'J')):
            ax.text(cx, cy + 1.7, f['val'][:14], ha='center', va='center', fontsize=3.6, color='#555555', zorder=20)


def board_axes(fig, rect, mirror=False):
    ax = fig.add_axes(rect)
    ax.set_xlim(BX0 - 2, BX1 + 2)
    ax.set_ylim(BY1 + 2, BY0 - 2)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.add_patch(Rectangle((BX0, BY0), BX1 - BX0, BY1 - BY0, fill=False, ec='black', lw=1.4, zorder=30))
    # XIAO の USB 向き
    x = FP['U3']
    return ax


def header(fig, sub_title, page, total, side='部品面'):
    fig.text(0.015, 0.965, f'{TITLE}（{side}）', fontsize=13, fontproperties=BOLD, va='top')
    fig.text(0.015, 0.932, SUB, fontsize=7.5, color='#444444', va='top')
    if sub_title:
        fig.text(0.015, 0.905, sub_title, fontsize=11, fontproperties=BOLD, va='top', color=NAVY)
    fig.text(0.985, 0.012, f'{page} / {total}', fontsize=7, ha='right', color='#666666')


def draw_blocks(ax, only=None, alpha=0.45):
    """部品ごとに、外形の範囲をそのブロックの色で塗る（only を指定するとそのブロックだけ濃く）"""
    for f in board['fps']:
        bi = member.get(f['ref'])
        if bi is None:
            continue
        (x0, y0), (x1, y1) = f['bbox']
        a = alpha if (only is None or bi == only) else 0.07
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=blocks[bi]['color'], ec='none', alpha=a, zorder=0))


SHORT_TYPE = {'セラミックコンデンサ': 'セラミックC', '電解コンデンサ': '電解C', 'トランジスタ/FET': 'Tr/FET', 'コイル/トランス': 'コイル',
              'トリマコンデンサ': 'トリマC', '半固定抵抗': '半固定VR', 'IC/レギュレータ': 'IC', 'マイコン(ソケット)': 'マイコン', 'フィルムコンデンサ': 'フィルムC'}


def fit(v, width_pt, fs):
    """列幅（pt）に収まるよう末尾を「…」で切る（全角 1.0、半角 0.55 文字幅で概算）"""
    import unicodedata
    w = lambda c: 1.0 if unicodedata.east_asian_width(c) in 'WF' else 0.55
    if sum(w(c) for c in v) * fs <= width_pt:
        return v
    out = ''
    for c in v:
        if (sum(w(x) for x in out) + w(c) + 1.0) * fs > width_pt:
            return out + '…'
        out += c
    return out


def table(fig, rect, rows, color):
    """rows: [[部品番号, 値, 種類, 注意]]。40 行を超えたら 2 段組み。"""
    cols = ['部品番号', '値/型番', '種類', '注意']
    n = len(rows)
    per = n if n <= 40 else math.ceil(n / 2)
    chunks = [rows[i:i + per] for i in range(0, n, per)]
    x0, y0, w, h = rect
    cw = w / len(chunks)
    for ci, ch in enumerate(chunks):
        ax = fig.add_axes([x0 + ci * cw, y0, cw - 0.005, h])
        ax.axis('off')
        rh = min(0.034 / h, 1.0 / (len(ch) + 1))
        widths = [0.11, 0.23, 0.14, 0.52] if len(chunks) == 1 else [0.17, 0.25, 0.25, 0.33]
        xs = [sum(widths[:i]) for i in range(4)]
        fs = 6.4 if len(chunks) == 1 else 5.4
        ax.add_patch(Rectangle((0, 1 - rh), 1, rh, fc=color, ec='#888888', lw=0.4))
        for i, c in enumerate(cols):
            ax.text(xs[i] + 0.01, 1 - rh / 2, c, fontsize=fs, va='center', color='white', fontproperties=BOLD)
        for r, row in enumerate(ch):
            yy = 1 - rh * (r + 2)
            ax.add_patch(Rectangle((0, yy), 1, rh, fc='#f3f3f3' if r % 2 else 'white', ec='#bbbbbb', lw=0.3))
            for i, v in enumerate(row):
                v = str(v)
                if i == 2:
                    v = SHORT_TYPE.get(v, v)
                f_i = fs if i < 3 else fs - 0.6
                v = fit(v, widths[i] * cw * A4[0] * 72 - 3, f_i)
                ax.text(xs[i] + 0.01, yy + rh / 2, v, fontsize=f_i, va='center',
                        fontproperties=BOLD if i == 0 else None, color=NAVY if i == 0 else 'black', clip_on=True)
        for xv in xs[1:]:
            ax.plot([xv, xv], [1 - rh * (len(ch) + 1), 1], color='#bbbbbb', lw=0.3)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)


blocks = notes['blocks']
member = {r[0]: bi for bi, b in enumerate(blocks) for r in b['rows']}


def shade(col):
    """表の見出し用に色を濃くする"""
    c = matplotlib.colors.to_rgb(col)
    return tuple(x * 0.72 for x in c)


pages_total = 1 + len(blocks) + 1
A4 = (11.69, 8.27)
pdf = PdfPages(OUT, metadata={'Title': 'PSN_TRX_XIAO_ESP32C3-V2 部品実装図 V2 Ver 1.0', 'Author': 'JA6FUF'})
# ---- 1. 全体図
fig = plt.figure(figsize=A4)
header(fig, '全体図', 1, pages_total)
ax = board_axes(fig, [0.03, 0.10, 0.94, 0.78])
draw_blocks(ax)
for f in board['fps']:
    draw_fp(ax, f, 'normal', small=True)
fig.text(0.03, 0.082, '□（四角）パッド = 1 番ピン / 電解コンデンサの＋ / ダイオードの K（カソード）。H1〜H4 = M3 取付穴（GND）。', fontsize=7, va='center')
fig.text(0.03, 0.064, '部品はすべて部品面。表面実装は U4・U5（NJM2594V）だけで、最初に付ける。', fontsize=7, va='center')
fig.text(0.03, 0.046, 'Q2（3SK59）と Q4+Q5（2SK192A-GR カスコード）はどちらか一方だけ付ける。', fontsize=7, va='center')
fig.text(0.03, 0.028, 'ブロック別の詳細と部品表は次ページ以降（組立順の目安: 1→%d）。調整箇所は最終ページ。' % len(blocks), fontsize=7, va='center')
lx = 0.555
for i, b in enumerate(blocks):
    yy = 0.082 - (i % 4) * 0.018; xx = lx + (i // 4) * 0.108
    fig.patches.append(Rectangle((xx, yy - 0.006), 0.015, 0.012, transform=fig.transFigure, fc=b['color'], ec='#888888', lw=0.4, alpha=0.8))
    fig.text(xx + 0.02, yy, b['short'], fontsize=6.2, va='center')
pdf.savefig(fig);
if PNGDIR:
    fig.savefig(os.path.join(PNGDIR, 'layout_overview.png'), dpi=200)
plt.close(fig)

# ---- ブロック別
for bi, b in enumerate(blocks):
    fig = plt.figure(figsize=A4)
    header(fig, f"{bi + 1}. {b['name']}（{len(b['rows'])}点）", bi + 2, pages_total)
    nm = len(b.get('memo', []))
    ax = board_axes(fig, [0.01, 0.04, 0.60, 0.82 - nm * 0.022])
    draw_blocks(ax, only=bi, alpha=0.6)
    refs = set(r[0] for r in b['rows'])
    for f in board['fps']:
        draw_fp(ax, f, 'normal' if f['ref'] in refs else 'faint')
    tcol = shade(b['color'])
    table(fig, [0.625, 0.06, 0.365, 0.82], b['rows'], tcol)
    if b.get('memo'):
        for k, line in enumerate(b['memo']):
            fig.text(0.015, 0.875 - k * 0.018, line, fontsize=7, va='top', color='#333333')
    pdf.savefig(fig); plt.close(fig)

# ---- 調整箇所（manual/調整手順.md の番号）
ADJ = notes.get('adjust', [])
fig = plt.figure(figsize=A4)
header(fig, "調整箇所（丸数字は manual/調整手順.md の手順の番号）", pages_total, pages_total)
ax = board_axes(fig, [0.01, 0.06, 0.60, 0.80])
adj_refs = {r for a in ADJ for r in a['refs']}
for f in board['fps']:
    draw_fp(ax, f, 'normal' if f['ref'] in adj_refs else 'faint', label=f['ref'] in adj_refs)
for a in ADJ:
    for r in a['refs']:
        (x0, y0), (x1, y1) = FP[r]['bbox']
        ax.add_patch(Rectangle((x0 - 0.6, y0 - 0.6), x1 - x0 + 1.2, y1 - y0 + 1.2, fill=False, ec='#d62728', lw=1.1, zorder=26))
        ax.text(x0 - 0.8, y0 - 0.8, str(a['no']), ha='right', va='bottom', fontsize=7.5, color='white', zorder=27,
                fontproperties=BOLD, bbox=dict(boxstyle='circle,pad=0.18', fc='#d62728', ec='none'))
rows = [[str(a['no']), a['what'], a.get('parts') or '・'.join(a['refs']), a['how']] for a in ADJ]
axr = fig.add_axes([0.625, 0.06, 0.365, 0.82]); axr.axis('off'); axr.set_xlim(0, 1); axr.set_ylim(0, 1)
rh = min(0.06, 1.0 / (len(rows) + 1)); widths = [0.06, 0.30, 0.20, 0.44]; xs = [sum(widths[:i]) for i in range(4)]
axr.add_patch(Rectangle((0, 1 - rh), 1, rh, fc='#d62728', ec='#888888', lw=0.4))
for i, c in enumerate(['No', '調整', '部品', '合わせ方']):
    axr.text(xs[i] + 0.01, 1 - rh / 2, c, fontsize=6.4, va='center', color='white', fontproperties=BOLD)
for k, row in enumerate(rows):
    yy = 1 - rh * (k + 2)
    axr.add_patch(Rectangle((0, yy), 1, rh, fc='#f3f3f3' if k % 2 else 'white', ec='#bbbbbb', lw=0.3))
    for i, v in enumerate(row):
        v = fit(v, widths[i] * 0.365 * A4[0] * 72 - 3, 6.0 if i < 3 else 5.6)
        axr.text(xs[i] + 0.01, yy + rh / 2, v, fontsize=6.0 if i < 3 else 5.6, va='center',
                 fontproperties=BOLD if i == 0 else None, color='#d62728' if i == 0 else 'black')
fig.text(0.015, 0.875, '赤枠 = 調整する部品（半固定抵抗・トリマ・コア付きコイル）と、測る・値を選ぶ部品。番号順に調整する', fontsize=7, va='top')
pdf.savefig(fig); plt.close(fig)
pdf.close()
print('pages', pages_total, OUT)

# ---- 組み立て説明書用の PNG（全体図・左半分・右半分）
if PNGDIR:
    W_MM, H_MM = (BX1 - BX0) + 4, (BY1 - BY0) + 4
    fig = plt.figure(figsize=(W_MM / 25.4 * 1.6, H_MM / 25.4 * 1.6))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(BX0 - 2, BX1 + 2); ax.set_ylim(BY1 + 2, BY0 - 2); ax.set_aspect('equal'); ax.axis('off')
    ax.add_patch(Rectangle((BX0, BY0), BX1 - BX0, BY1 - BY0, fill=False, ec='black', lw=1.2, zorder=30))
    draw_blocks(ax, alpha=0.4)
    for f in board['fps']:
        draw_fp(ax, f, 'normal')
    full = os.path.join(PNGDIR, 'layout_full.png')
    DPI = 330
    fig.savefig(full, dpi=DPI); plt.close(fig)
    from PIL import Image
    im = Image.open(full); px = im.size[0] / W_MM
    def crop(x0, x1, name):
        a = int((x0 - (BX0 - 2)) * px); b = int((x1 - (BX0 - 2)) * px)
        im.crop((a, 0, b, im.size[1])).save(os.path.join(PNGDIR, name))
    mid = (BX0 + BX1) / 2
    crop(BX0 - 2, mid + 4, 'layout_left.png')
    crop(mid - 4, BX1 + 2, 'layout_right.png')
    print('png', im.size)
