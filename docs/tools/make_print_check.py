# -*- coding: utf-8 -*-
"""原寸確認図（docs/PSN_TRX_原寸確認図.pdf）を作る。

A4 縦に基板を 1:1 で描く（1 ページ目: 部品の外形・パッド・穴・部品番号、100mm の目盛り。
2 ページ目: 主な部品のピン名・コネクタの信号名）。
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
VER = 'V2 Ver 1.4　2026-11-11'
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
    '□ C8・C17・C19・C21・C66〜C69・C76〜C79（5mm ピッチ品を 2.5mm の穴へ寄せる）　□ L15 270nH（縦置き 2.54）　□ RFC1（横置き 15.24）',
]
for i, t in enumerate(notes):
    ov.text(LM, yb + 14 + i * 5.2, t, fontsize=6.6)
# ---- 2 ページ目: 主な部品のピン名・信号名
KEY = ['U7', 'U6', 'J4', 'K1', 'U8', 'U3', 'U5', 'U4', 'U9', 'Q19'] + [f'J{i}' for i in range(1, 13)]
LABEL = {'U7': {'1': 'D0', '2': 'D1', '3': 'D2/A2', '4': 'D3', '5': 'D4/SDA', '6': 'D5/SCL', '7': 'D6/TX',
                '8': '5V', '9': 'GND', '10': '3V3', '11': 'D10', '12': 'D9', '13': 'D8', '14': 'D7/RX'},
         'K1': {'1': 'コイル', '16': 'コイル', '4': 'COM1(ANT)', '6': 'NC1(受信)', '8': 'NO1(送信)',
                '13': 'COM2(+12V)', '11': 'NC2(RX12V)', '9': 'NO2(TX12V)'},
         'U8': {'3': 'VIN(1)', '2': 'GND', '1': 'VOUT(3)'},
         'J1': {'1': 'ANT 芯線', '2': 'GND 編組'}, 'J2': {'1': '+12V', '2': 'GND'},
         'J3': {'1': 'VR1 上(R17)', '2': 'VR1 中(AGC)', '3': 'GND'}, 'J5': {'1': 'VR2 上(AF)', '2': 'VR2 中', '3': 'GND'},
         'J6': {'1': 'SP+', '2': 'GND'}, 'J7': {'1': '+5V', '2': 'MIC', '3': 'PTT', '4': 'GND'},
         'J8': {'1': 'SDA', '2': 'SCL', '3': 'GND'}, 'J9': {'1': 'LED K(Q20)', '2': 'LED A(R72)'},
         'J10': {'1': 'ENC A(D3)', '2': 'ENC B(D1)', '3': 'SW(D9)', '4': 'GND'},
         'J11': {'1': 'GND', '2': 'TX(D6)→LCD RX', '3': 'RX(D7)←LCD TX', '4': '+5V'},
         'J12': {'1': 'LED A(R80)', '2': 'GND'}}


def netname(n):
    if not n or n.startswith('unconnected'):
        return '－'
    n = n.lstrip('/')
    return n[5:-1] if n.startswith('Net-(') else n


def pinlabel(f, p):
    if f['ref'] in LABEL:
        return LABEL[f['ref']].get(p['n'], p['n'])
    if f['ref'].startswith('J'):
        return netname(p.get('net', ''))
    fn = (p.get('fn') or '').split('_')[0]
    return fn if fn and fn != p['n'] else netname(p.get('net', ''))


fig2 = plt.figure(figsize=(PW * MM, PH * MM))
ax = fig2.add_axes([LM / PW, (PH - TM - BH) / PH, BW / PW, BH / PH])
ax.set_xlim(BX0, BX1); ax.set_ylim(BY1, BY0); ax.axis('off')
for e in board['edge']:
    shape(ax, e, 'black', 0.6)
for f in board['fps']:
    key = f['ref'] in KEY
    for s in f['fab']:
        shape(ax, s, '#333333' if key else '#cccccc', 0.35 if key else 0.25)
    for p in f['pads']:
        if key:
            pad(ax, p)
        else:
            x, y = p['c']
            ax.add_patch(Circle((x, y), max(p['sz']) / 2, fc='none', ec='#cccccc', lw=0.2))
    if not key:
        continue
    (x0, y0), (x1, y1) = f['bbox']; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ax.text(cx, cy, 'U7 (XIAO)' if f['ref'] == 'U7' else f['ref'], ha='center', va='center', fontsize=4.5,
            color='#b00020', fontproperties=BOLD, zorder=21, bbox=dict(fc='white', ec='none', alpha=0.7, pad=0.1))
    pxs = [p['c'][0] for p in f['pads']]; pys = [p['c'][1] for p in f['pads']]
    col = len(f['pads']) > 1 and max(pxs) - min(pxs) < 0.5      # 縦 1 列 → 右に横書き
    row = len(f['pads']) > 1 and max(pys) - min(pys) < 0.5      # 横 1 列 → 上に縦書き
    for p in f['pads']:
        x, y = p['c']; dx, dy = x - cx, y - cy; r = max(p['sz']) / 2 + 0.25
        t = pinlabel(f, p)
        if col: dx, dy = 1, 0
        if row: dx, dy = 0, -1
        if abs(dx) >= abs(dy):
            ax.text(x + (r if dx >= 0 else -r), y, t, ha='left' if dx >= 0 else 'right', va='center',
                    fontsize=2.4, color='#1f2d6b', zorder=22)
        else:
            ax.text(x, y + (r if dy >= 0 else -r), t, ha='center', va='top' if dy >= 0 else 'bottom', rotation=90,
                    fontsize=2.4, color='#1f2d6b', zorder=22)
ov = fig2.add_axes([0, 0, 1, 1]); ov.set_xlim(0, PW); ov.set_ylim(PH, 0); ov.axis('off'); ov.patch.set_alpha(0)
ov.plot([LM, LM + 100], [yb, yb], color='black', lw=0.8)
for k in range(0, 101, 10):
    ov.plot([LM + k, LM + k], [yb, yb - (2.5 if k % 50 == 0 else 1.5)], color='black', lw=0.5)
ov.text(LM + 50, yb + 4, '100 mm', ha='center', fontsize=7)
ov.text(LM, 12, 'PSN_TRX_XIAO_ESP32C3-V2　原寸確認図（2）主な部品のピン名・信号名（部品面から見た図、1:1）', fontsize=10, fontproperties=BOLD)
ov.text(LM, 18, f'{VER}。1 ページ目と同じく 100% で印刷する。赤字の部品のパッドの横にピン名（IC・モジュール）または信号名（コネクタ）を書いた。', fontsize=7)
ov.text(LM, 22.5, '□ のパッドが 1 番ピン。実物を当てたとき、1 番ピンの向きと信号の並びが合っているかを確かめる。', fontsize=7)
notes2 = [
    'U7 XIAO: 上の列が右から D0〜D6、下の列が右から 5V・GND・3V3・D10・D9・D8・D7（USB は右辺側、部品面を上）。',
    'U6 Si5351 モジュール: 1 VDDO・2 SCL・3 SDA・4 GND・5〜7 CLK0〜2・8 VDD（秋月の資料の上面図を 180° 回した向き）。',
    'J4 AE-ADS1015: VIN・GND・SCL・SDA・ADR・ALT・A0〜A3（□ が VIN）。U8 R-78E: □ がモジュールの 1 番（VIN）。',
    'K1 G5V-2: コイル 1・16、COM 4・13、NC 6・11（受信側）、NO 8・9（送信側）。Q19 RD06HVF1: □ = G、中 = S（タブ）、右 = D。',
    'コネクタは信号名: J1 アンテナ（芯線・編組）、J2 電源（+12V・GND）、J7 マイク（+5V・MIC・PTT・GND）、J11 表示器（GND・TX・RX・+5V）など。',
]
for i, t in enumerate(notes2):
    ov.text(LM, yb + 14 + i * 5.2, t, fontsize=6.6)
with PdfPages(OUT, metadata={'Title': 'PSN_TRX_XIAO_ESP32C3-V2 原寸確認図', 'Author': 'JA6FUF'}) as pdf:
    pdf.savefig(fig)
    pdf.savefig(fig2)
print('saved', OUT, f'{BW:.2f} x {BH:.2f} mm')
