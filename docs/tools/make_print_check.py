# -*- coding: utf-8 -*-
"""原寸確認図（docs/PSN_TRX_原寸確認図.pdf）を作る。

A4 縦に基板を 1:1 で描く（部品の外形・パッド・穴・部品番号、100mm の目盛り）。
100%（実際のサイズ）で印刷し、実物の部品を紙の上に置いて足の位置・外形の当たりを確かめる。

使い方（リポジトリの一番上で）:
    KiCad 付属の Python で  docs/tools/export_board.py kicad/PSN_TRX.kicad_pcb board.json
    python3 docs/tools/make_print_check.py board.json docs/PSN_TRX_原寸確認図.pdf
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
plt.rcParams['font.family'] = fm.FontProperties(fname=FW3).get_name()
BOLD = fm.FontProperties(fname=FW6)

board = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
VER = 'V2 Ver 1.3　2026-11-08'
MM = 1 / 25.4
PW, PH = 210.0, 297.0            # A4 縦 [mm]

xs = [x for e in board['edge'] for x, y in (e['p'] if e['t'] == 'poly' else [e['a'], e['b']])]
ys = [y for e in board['edge'] for x, y in (e['p'] if e['t'] == 'poly' else [e['a'], e['b']])]
BX0, BX1, BY0, BY1 = min(xs), max(xs), min(ys), max(ys)
BW, BH = BX1 - BX0, BY1 - BY0
LM, TM = (PW - BW) / 2, 30.0     # 左右中央、上 30mm


def shape(ax, s, col, lw):
    t = s['t']
    if t == 'seg':
        ax.plot([s['a'][0], s['b'][0]], [s['a'][1], s['b'][1]], color=col, lw=lw, solid_capstyle='round')
    elif t == 'poly':
        ax.add_patch(Polygon(s['p'], closed=True, fill=False, ec=col, lw=lw))
    elif t == 'circ':
        ax.add_patch(Circle(s['c'], s['r'], fill=False, ec=col, lw=lw))
    elif t == 'arc3':
        (x1, y1), (x2, y2), (x3, y3) = s['a'], s['m'], s['b']
        d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        if abs(d) < 1e-9:
            return
        ux = ((x1*x1 + y1*y1) * (y2 - y3) + (x2*x2 + y2*y2) * (y3 - y1) + (x3*x3 + y3*y3) * (y1 - y2)) / d
        uy = ((x1*x1 + y1*y1) * (x3 - x2) + (x2*x2 + y2*y2) * (x1 - x3) + (x3*x3 + y3*y3) * (x2 - x1)) / d
        r = math.hypot(x1 - ux, y1 - uy)
        a1, a2, am = (math.atan2(y - uy, x - ux) for x, y in ((x1, y1), (x3, y3), (x2, y2)))
        def norm(a, ref):
            while a < ref:
                a += 2 * math.pi
            return a
        e1 = norm(a2, a1); m1 = norm(am, a1)
        if m1 > e1:
            e1 -= 2 * math.pi
        pts = [(ux + r * math.cos(a1 + (e1 - a1) * k / 30), uy + r * math.sin(a1 + (e1 - a1) * k / 30)) for k in range(31)]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=lw)


def pad(ax, p):
    x, y = p['c']; w, h = p['sz']
    tr = mtrans.Affine2D().rotate_deg_around(x, y, -p['ang']) + ax.transData
    kw = dict(fc='#d9d9d9', ec='black', lw=0.25)
    if p['sh'] == 'circle':
        ax.add_patch(Circle((x, y), w / 2, **kw))
    elif p['sh'] == 'oval':
        r = min(w, h) / 2
        ax.add_patch(FancyBboxPatch((x - w / 2 + r, y - h / 2 + r), w - 2 * r, h - 2 * r, boxstyle=f'round,pad={r}', transform=tr, **kw))
    else:
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, transform=tr, **kw))
    if p['drill'] > 0:
        ax.add_patch(Circle((x, y), p['drill'] / 2, fc='white', ec='black', lw=0.15))


fig = plt.figure(figsize=(PW * MM, PH * MM))
ax = fig.add_axes([LM / PW, (PH - TM - BH) / PH, BW / PW, BH / PH])
ax.set_xlim(BX0, BX1); ax.set_ylim(BY1, BY0); ax.axis('off')
for e in board['edge']:
    shape(ax, e, 'black', 0.6)
for f in board['fps']:
    for s in f['fab']:
        shape(ax, s, '#555555', 0.3)
    for p in f['pads']:
        pad(ax, p)
    (x0, y0), (x1, y1) = f['bbox']
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, 'U7 (XIAO)' if f['ref'] == 'U7' else f['ref'], ha='center', va='center',
            fontsize=3.4, color='#1f2d6b', fontproperties=BOLD, zorder=20, bbox=dict(fc='white', ec='none', alpha=0.6, pad=0.1))

# 目盛り（紙の座標 mm で描く）
ov = fig.add_axes([0, 0, 1, 1]); ov.set_xlim(0, PW); ov.set_ylim(PH, 0); ov.axis('off'); ov.patch.set_alpha(0)
yb = TM + BH + 8
ov.plot([LM, LM + 100], [yb, yb], color='black', lw=0.8)
for k in range(0, 101, 10):
    ov.plot([LM + k, LM + k], [yb, yb - (2.5 if k % 50 == 0 else 1.5)], color='black', lw=0.5)
ov.text(LM + 50, yb + 4, '100 mm（印刷後に定規で確かめる）', ha='center', fontsize=7)
xr = LM + BW + 6
ov.plot([xr, xr], [TM, TM + 100], color='black', lw=0.8)
for k in range(0, 101, 10):
    ov.plot([xr, xr - (2.5 if k % 50 == 0 else 1.5)], [TM + k, TM + k], color='black', lw=0.5)
ov.text(xr + 2, TM + 50, '100 mm', rotation=90, va='center', fontsize=7)
ov.text(LM, 12, 'PSN_TRX_XIAO_ESP32C3-V2　原寸確認図（部品面から見た図、1:1）', fontsize=11, fontproperties=BOLD)
ov.text(LM, 18, f'基板 {BW:.1f} × {BH:.1f} mm　{VER}。必ず「実際のサイズ（100%）」で印刷する（「用紙に合わせる」は使わない）。', fontsize=7)
ov.text(LM, 22.5, '印刷したら、上の基板の幅と下・右の 100mm の目盛りを定規で測り、ずれが 0.5mm 以内であることを確かめてから使う。', fontsize=7)
notes = [
    '実物の部品を紙の上に置き、足が穴（白い丸）に合うか、外形が隣の部品や外枠に当たらないかを確かめる。特に次の部品:',
    '□ U7 XIAO ESP32C3（ピッチ 2.54・列の間隔 15.24、USB は右辺側）　□ U6 Si5351 モジュール（7.62）　□ J4 AE-ADS1015（10 ピン）',
    '□ K1 G5V-2（穴 φ1.0）　□ U8 R-78E5.0（3 ピン、四角が Vin）　□ TC1〜TC4 TMCV01（足の間隔 6.3）',
    '□ HS1 放熱器 17PB046（脚 2 本 30mm、Q19 側のつば 7mm が L15・L16 に当たらない）と Q19 RD06HVF1',
    '□ L3・L12〜L14 FCZ コイル（足 5 本＋ケースの爪 2 本）　□ VR3〜VR6 GF063P・VR7 3266W　□ 電解コンデンサ（ピッチ 2.0／2.5）',
    '□ C8・C17・C19・C21・C66〜C69・C76〜C79（5mm ピッチ品を 2.5mm の穴へ寄せる）　□ L15 47nH（縦置き 2.54）　□ RFC1（横置き 15.24）',
]
for i, t in enumerate(notes):
    ov.text(LM, yb + 14 + i * 5.2, t, fontsize=6.6)
with PdfPages(OUT, metadata={'Title': 'PSN_TRX_XIAO_ESP32C3-V2 原寸確認図', 'Author': 'JA6FUF'}) as pdf:
    pdf.savefig(fig)
print('saved', OUT, f'{BW:.2f} x {BH:.2f} mm')
