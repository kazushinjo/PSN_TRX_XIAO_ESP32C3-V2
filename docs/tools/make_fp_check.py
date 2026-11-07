# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 JA6FUF (kazushinjo)
"""間違いやすい部品の部品形（フットプリント）を、寸法入りの図にする（PDF と PNG）。

使い方（リポジトリの一番上で）:
    KiCad 付属の Python で  docs/tools/export_board.py kicad/PSN_TRX.kicad_pcb board.json
    python3 docs/tools/make_fp_check.py board.json docs/PSN_TRX_間違いやすい部品形.pdf [PNG の出力先フォルダ]
図は基板に置いた向きのまま、部品面から見たもの（上が基板の奥）。寸法の単位は mm。
"""
import json, math, sys, os, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Rectangle, Circle, Ellipse, Polygon
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.transforms as mtrans

FW3 = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
FW6 = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
if not os.path.exists(FW3):
    FW3, FW6 = 'C:/Windows/Fonts/YuGothM.ttc', 'C:/Windows/Fonts/YuGothB.ttc'
for f in (FW3, FW6):
    fm.fontManager.addfont(f)
plt.rcParams['font.family'] = fm.FontProperties(fname=FW3).get_name()
BOLD = fm.FontProperties(fname=FW6)
COPPER, FAB, NAVY, RED, DIM = '#d9a066', '#333333', '#1f3a6e', '#c62828', '#00695c'

board = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
PNGDIR = sys.argv[3] if len(sys.argv) > 3 else None
FP = {f['ref']: f for f in board['fps']}
A4 = (11.69, 8.27)
TITLE = 'PSN_TRX_XIAO_ESP32C3-V2　間違いやすい部品の部品形（寸法入り）'
SUB = '基板 V2 Ver 1.3・2026-11-08。部品面から見た図で、向きは基板に置いたとおり（上 = 基板の奥）。寸法は mm。□（四角）パッド = 1 番ピン'


# ---------------------------------------------------------------------------
def pad_of(ref, num):
    if num.startswith('#'):
        return FP[ref]['pads'][int(num[1:])]
    for p in FP[ref]['pads']:
        if p['n'] == num:
            return p
    raise KeyError((ref, num))


def shape(ax, s, dx, dy, col=FAB, lw=0.9):
    t = s['t']
    if t == 'seg':
        ax.plot([s['a'][0] + dx, s['b'][0] + dx], [s['a'][1] + dy, s['b'][1] + dy], color=col, lw=lw)
    elif t == 'poly':
        ax.add_patch(Polygon([(x + dx, y + dy) for x, y in s['p']], closed=True, fill=False, ec=col, lw=lw))
    elif t == 'circ':
        ax.add_patch(Circle((s['c'][0] + dx, s['c'][1] + dy), s['r'], fill=False, ec=col, lw=lw))
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
        pts = [(ux + r * math.cos(a1 + (e1 - a1) * k / 40), uy + r * math.sin(a1 + (e1 - a1) * k / 40)) for k in range(41)]
        ax.plot([x + dx for x, y in pts], [y + dy for x, y in pts], color=col, lw=lw)


def draw_ref(ax, ref, off, labels, fs, shownum=True, tag=False):
    f = FP[ref]
    ox, oy = f['pos']
    dx, dy = off[0] - ox, off[1] - oy
    for s in f['fab']:
        shape(ax, s, dx, dy)
    for p in f['pads']:
        x, y = p['c'][0] + dx, p['c'][1] + dy
        w, h = p['sz']
        tr = mtrans.Affine2D().rotate_deg_around(x, y, -p['ang']) + ax.transData
        ec = RED if p['sh'] == 'rect' else '#7a4a1c'
        lw = 1.4 if p['sh'] == 'rect' else 0.5
        if p['sh'] == 'circle':
            ax.add_patch(Circle((x, y), w / 2, fc=COPPER, ec=ec, lw=lw, zorder=3))
        elif p['sh'] == 'oval':
            ax.add_patch(Ellipse((x, y), w, h, fc=COPPER, ec=ec, lw=lw, transform=tr, zorder=3))
        else:
            ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=COPPER, ec=ec, lw=lw, transform=tr, zorder=3))
        if p['drill'] > 0:
            ax.add_patch(Circle((x, y), p['drill'] / 2, fc='white', ec='none', zorder=4))
        name = labels.get(p['n'], '') if labels else ''
        txt = (p['n'] + (f'\n{name}' if name else '')) if shownum or not name else name
        ax.text(x, y, txt, ha='center', va='center', fontsize=fs, color=NAVY, fontproperties=BOLD, zorder=6,
                bbox=dict(fc='white', ec='none', alpha=0.7, pad=0.1))
    if tag:
        (bx0, by0), (bx1, by1) = f['bbox']
        ax.text((bx0 + bx1) / 2 + dx, by1 + dy + 1.2, f"{ref}  {f['val']}", ha='center', va='top', fontsize=7.5,
                color=RED, fontproperties=BOLD, zorder=9)
    return dx, dy


def dim(ax, a, b, off, text=None, fs=7):
    """a, b = (x, y)。a–b の距離を、垂直方向に off ずらした寸法線で描く"""
    (x1, y1), (x2, y2) = a, b
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-6:
        return
    nx, ny = -(y2 - y1) / L, (x2 - x1) / L
    p1 = (x1 + nx * off, y1 + ny * off); p2 = (x2 + nx * off, y2 + ny * off)
    for (px, py), (qx, qy) in (((x1, y1), p1), ((x2, y2), p2)):
        ax.plot([px, qx + nx * 0.4 * math.copysign(1, off)], [py, qy + ny * 0.4 * math.copysign(1, off)], color=DIM, lw=0.4, zorder=7)
    ax.annotate('', xy=p2, xytext=p1, arrowprops=dict(arrowstyle='<->', color=DIM, lw=0.7, shrinkA=0, shrinkB=0), zorder=7)
    mx, my = (p1[0] + p2[0]) / 2 + nx * 0.6 * math.copysign(1, off), (p1[1] + p2[1]) / 2 + ny * 0.6 * math.copysign(1, off)
    ang = math.degrees(math.atan2(-(y2 - y1), x2 - x1))
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    ax.text(mx, my, text or f'{L:.2f}', ha='center', va='center', fontsize=fs, color=DIM, rotation=ang,
            fontproperties=BOLD, zorder=8, bbox=dict(fc='white', ec='none', alpha=0.85, pad=0.1))


def panel(fig, rect, title, items, dims=(), notes=(), table=None, fs=6.5, margin=3.0, shownum=True):
    """items: [(ref, (x, y), {pad: 名前})]。dims: [(ref, padA, ref, padB, off) または ('xy', (x,y), (x,y), off, text)]"""
    x0, y0, w, h = rect
    full = w > 0.6
    ax = fig.add_axes([x0, y0 + h * 0.40, w * (0.50 if full else 0.52), h * 0.52])
    tx = fig.add_axes([x0 + w * (0.52 if full else 0.54), y0 + h * 0.40, w * (0.48 if full else 0.46), h * 0.52]); tx.axis('off')
    nx = fig.add_axes([x0, y0, w, h * 0.33]); nx.axis('off')
    fig.text(x0, y0 + h * 0.955, title, fontsize=11, fontproperties=BOLD, color=NAVY, va='center')
    xs, ys = [], []
    offs = {}
    for ref, at, lab in items:
        dx, dy = draw_ref(ax, ref, at, lab, fs, shownum, tag=len(items) > 1)
        offs[ref] = (dx, dy)
        f = FP[ref]
        (bx0, by0), (bx1, by1) = f['bbox']
        xs += [bx0 + dx, bx1 + dx]; ys += [by0 + dy, by1 + dy + (3.0 if len(items) > 1 else 0)]
    for d in dims:
        if d[0] == 'xy':
            dim(ax, d[1], d[2], d[3], d[4])
        else:
            r1, n1, r2, n2, off = d[:5]
            p1, p2 = pad_of(r1, n1), pad_of(r2, n2)
            a = (p1['c'][0] + offs[r1][0], p1['c'][1] + offs[r1][1])
            b = (p2['c'][0] + offs[r2][0], p2['c'][1] + offs[r2][1])
            dim(ax, a, b, off, d[5] if len(d) > 5 else None)
    cx0, cx1, cy0, cy1 = min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin
    span = max(cx1 - cx0, (cy1 - cy0) * 1.25)
    mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
    ax.set_xlim(mx - span / 2, mx + span / 2)
    ax.set_ylim(my + span / 2.5, my - span / 2.5)
    ax.set_aspect('equal', adjustable='datalim')
    ax.grid(True, which='major', color='#e3e3e3', lw=0.4)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=5, colors='#888888', length=2)
    for s in ax.spines.values():
        s.set_color('#bbbbbb')
    ax.set_xticklabels([]); ax.set_yticklabels([])
    # 部品形の寸法（ランド・穴）
    lines = []
    for ref, _, _ in items:
        f = FP[ref]
        ds = sorted({p['drill'] for p in f['pads'] if p['drill'] > 0})
        sz = sorted({tuple(round(v, 2) for v in p['sz']) for p in f['pads']})
        szs = '・'.join(f'{a:g}×{b:g}' if a != b else f'φ{a:g}' for a, b in sz)
        (bx0, by0), (bx1, by1) = f['bbox']
        lines.append(f"{ref}（{f['val']}）: 穴 {'・'.join(f'φ{d:g}' for d in ds) or 'なし（表面実装）'}、ランド {szs}、外形の枠 {bx1-bx0:.1f}×{by1-by0:.1f}")
    if table is None:
        rows = [['部品', 'パッド', 'ピン', 'つながる信号（ネット・相手のピン）']]
        for ref, _, lab in items:
            for p in sorted(FP[ref]['pads'], key=lambda q: (len(q['n']), q['n'])):
                if not p['n']:
                    continue
                rows.append([ref, p['n'], (lab or {}).get(p['n'], '').replace('\n', ' '), sig(ref, p)])
        table = rows[:25]
    if table:
        RH = min(0.075, 1.0 / len(table))
        tb = tx.table(cellText=table[1:], colLabels=table[0], loc='upper left', cellLoc='left', colLoc='left',
                      bbox=[0, 1 - RH * len(table), 1, RH * len(table)],
                      colWidths=colw(table))
        fsz = 6.3 if len(table) < 12 else 5.4
        tb.auto_set_font_size(False); tb.set_fontsize(fsz)
        for (r, c), cell in tb.get_celld().items():
            cell.set_edgecolor('#cccccc'); cell.set_linewidth(0.4)
            cell.PAD = 0.03
            if r == 0:
                cell.set_facecolor('#e8eef7'); cell.get_text().set_fontproperties(BOLD); cell.get_text().set_fontsize(fsz)
    width = 150 if full else 74
    txt = [lines_ for lines_ in lines]
    body = []
    for ln in txt:
        body += wrap(ln, width + 8)
    body.append('')
    for n in notes:
        ws = wrap('・' + n, width)
        body += [ws[0]] + ['　' + x for x in ws[1:]]
    nx.text(0, 1, '\n'.join(body), fontsize=6.8, va='top', ha='left', transform=nx.transAxes, linespacing=1.45)


NETS = {}
for _f in board['fps']:
    for _p in _f['pads']:
        if _p.get('net'):
            NETS.setdefault(_p['net'], []).append((_f['ref'], _p['n'], _p.get('fn', '')))


def sig(ref, p):
    """つながる信号: 名前のあるネットはその名前、自動名のネットはつながる先の部品とピン"""
    n = p.get('net', '')
    if not n:
        return '（なし）'
    if n.startswith('unconnected'):
        return '（未接続）'
    if not n.startswith('Net-('):
        return n.lstrip('/')
    others = []
    for r, q, fn in NETS.get(n, []):
        if r == ref and q == p['n']:
            continue
        fn = re.sub(r'_\d+$', '', fn.split('/')[0]) if fn else ''
        others.append(f'{r}.{q}' + (f'({fn})' if fn and not fn.startswith('Pin') and fn != q else ''))
    t = '・'.join(others[:3]) + ('…' if len(others) > 3 else '')
    return '→ ' + t


def colw(table):
    def wd(t):
        return sum(1 if ord(c) < 0x2E80 else 2 for c in str(t))
    n = len(table[0])
    # 最後の列（信号）以外は文字が切れないよう少し余裕を持たせる
    m = [max(4, max(wd(r[i]) for r in table)) + (5 if i < n - 1 else 0) for i in range(n)]
    return [x / sum(m) for x in m]


def wrap(t, n):
    out, line, wid = [], '', 0
    for ch in t:
        cw = 1 if ord(ch) < 0x2E80 else 2
        if wid + cw > n:
            out.append(line); line, wid = '', 0
        line += ch; wid += cw
    if line:
        out.append(line)
    return out


pages = []


def page(func):
    pages.append(func)
    return func


def header(fig, n, total):
    fig.text(0.02, 0.975, TITLE, fontsize=13, fontproperties=BOLD, va='top')
    fig.text(0.02, 0.945, SUB, fontsize=7.5, color='#444444', va='top')
    fig.text(0.98, 0.015, f'{n} / {total}', fontsize=7, ha='right', color='#666666')


L = [0.03, 0.03, 0.46, 0.88]
R = [0.52, 0.03, 0.46, 0.88]


@page
def p_xiao(fig):
    lab = {'1': 'D0', '2': 'D1', '3': 'D2\nA2', '4': 'D3', '5': 'D4\nSDA', '6': 'D5\nSCL', '7': 'D6\nTX',
           '8': '5V', '9': 'GND', '10': '3V3', '11': 'D10', '12': 'D9', '13': 'D8', '14': 'D7\nRX'}
    panel(fig, L, 'U7  XIAO ESP32C3（ソケット）', [('U7', (0, 0), lab)],
          dims=[('U7', '1', 'U7', '2', 2.5), ('U7', '1', 'U7', '7', -3.0), ('U7', '1', 'U7', '8', 3.0)],
          notes=['列の間隔は 15.24mm（Seeed 公式。前の部品形は 11.43mm で誤り）。',
                 '部品面を上にして差し、USB 端子は基板の右辺（外側）に向ける。',
                 '1 番（D0）の列が基板の奥側、D0 は USB 側の端。ピンの名前は XIAO の裏の印字と同じ。',
                 'XIAO はふちが端子の基板なので、ピンヘッダ（0.64mm 角、1×7 を 2 本）をはんだ付けして差す。基板側はピンソケットでもよい。穴は 0.64mm 角の足が入る φ1.0（V2 Ver 1.3 で φ0.9 から変更）。',
                 'XIAO の外形は 21 × 17.5mm（実測）。',
                 'D0・D9 は起動設定ピン。PTT やつまみを押したまま電源を入れない。'])
    lab6 = {'1': 'VDDO', '2': 'SCL', '3': 'SDA', '4': 'GND', '5': 'CLK0', '6': 'CLK1', '7': 'CLK2', '8': 'VDD'}
    panel(fig, R, 'U6  Si5351 モジュール（秋月 AE-Si5351A-B）', [('U6', (0, 0), lab6)],
          dims=[('U6', '1', 'U6', '2', -2.0), ('U6', '1', 'U6', '8', -2.2), ('U6', '1', 'U6', '4', -3.6)],
          notes=['秋月の資料の端子番号: 1 VDDO・2 SCL・3 SDA・4 GND・5 CLK0・6 CLK1・7 CLK2・8 VDD（上から見て左上が 1、反時計回り）。',
                 'モジュールは 10 × 10mm、ピッチ 2.54mm、列の間隔 7.62mm（秋月の資料の寸法図と一致）。',
                 'DIP-8 のソケットに差す。前の部品形は鏡写しだった（2026-11-05 に修正）。',
                 'モジュールに I2C のプルアップ抵抗も電源のレギュレータも付いていない（秋月の資料の回路図）。VDD は 2.5〜3.3V、VDDO は 1.8〜3.3V なので、U9（LP2950-3.3）の 3.3V で動かす。'])


@page
def p_ads_dcdc(fig):
    lab = {'1': 'VIN\n3V3', '2': 'GND', '3': 'SCL', '4': 'SDA', '5': 'ADR\nGND', '6': 'ALT', '7': 'A0', '8': 'A1', '9': 'A2', '10': 'A3'}
    panel(fig, L, 'J4  ADS1015 モジュール（秋月 AE-ADS1015）', [('J4', (0, 0), lab)],
          dims=[('J4', '1', 'J4', '2', 2.0), ('J4', '1', 'J4', '10', -2.4)],
          notes=['秋月の資料のピン順: VIN・GND・SCL・SDA・ADR・ALT・A0・A1・A2・A3（1 番が VIN）。',
                 'ADR = GND で I2C アドレス 0x48（モジュールの中でもプルダウン済み）。ALT はモジュールの中でプルアップ済みで未接続でよい。A0 = AD8307（U3）の出力。電源は 2〜5V（ここでは XIAO の 3V3）。',
                 '【要対応】SDA・SCL のプルアップ抵抗（10kΩ、モジュールの R3・R4）は出荷時は未接続（秋月の資料）。I2C の線にほかのプルアップがないので、モジュール裏のはんだジャンパを短絡して SDA・SCL をプルアップする。'])
    lab8 = {'3': 'VIN', '2': 'GND', '1': 'VOUT'}
    panel(fig, R, 'U8  5V DC-DC（RECOM R-78E5.0-1.0）', [('U8', (0, 0), lab8)],
          dims=[('U8', '3', 'U8', '2', 2.5), ('U8', '3', 'U8', '1', -3.0)],
          notes=['部品形のパッド番号は 78L05 のシンボルに合わせて入れ替えてある: 四角パッド（パッド 3）= モジュールの 1 番（Vin）、パッド 2 = GND、パッド 1 = モジュールの 3 番（Vout）。',
                 'モジュールの印字の 1 番ピンを四角パッドに合わせる。逆に差すと壊れる。',
                 'R-78E は SIP-3、ピッチ 2.54mm、外形 11.6 × 8.5 × 10.4mm（RECOM の資料: 1 +Vin・2 GND・3 +Vout、入力 8〜28V）。'])


@page
def p_ic(fig):
    lab = {'1': 'V+', '2': 'OUT1', '3': 'OUT2', '4': 'GND', '5': 'SIG', '6': 'BYP', '7': 'CARR', '8': 'NC'}
    panel(fig, L, 'U1・U2  NJM2594V（SSOP-8、表面実装）', [('U1', (0, 0), lab)],
          dims=[('U1', '1', 'U1', '2', 1.2), ('U1', '1', 'U1', '8', -1.6), ('U1', '1', 'U1', '4', 2.2)], fs=5.5, margin=1.5,
          notes=['ピン: 1 V+・2 OUT1（未使用）・3 OUT2（エミッタフォロワ）・4 GND・5 信号入力・6 BYP・7 キャリア入力・8 NC（データシートで照合）。',
                 'ピッチ 0.65mm。1 番ピンの印（くぼみ・線）を四角パッドに合わせる。',
                 '全部品の中で最初に付ける。ブリッジしたらフラックスと吸取線で取る。',
                 'U2 も同じ向き・同じ部品形（実装図で 1 番の位置を確かめる）。'])
    l3 = {'1': 'INM', '2': 'COM', '3': 'OFS', '4': 'OUT', '5': 'INT', '6': 'ENB', '7': 'VPS', '8': 'INP'}
    l5 = {'1': 'A出力', '2': 'A−', '3': 'A+', '4': 'GND', '5': 'B+', '6': 'B−', '7': 'B出力', '8': 'V+'}
    panel(fig, R, 'U3 AD8307・U5 NJM2904（DIP-8）', [('U3', (0, 0), l3), ('U5', (0, 15), l5)],
          dims=[('U3', '1', 'U3', '2', 2.0), ('U3', '1', 'U3', '8', -2.0)], fs=5.5,
          notes=['どちらも DIP-8（ピッチ 2.54mm・列の間隔 7.62mm）。ソケットに差す。',
                 '切り欠き（1 番ピン）を四角パッドの側に合わせる。U3・U5 とも 1 番は図の右上（基板の奥・右）。',
                 '上の図が U3（AD8307）、下の図が U5（NJM2904）。U6（Si5351 モジュール）も同じ DIP-8 の部品形。'])


@page
def p_to92(fig):
    E = lambda a, b, c: {'1': a, '2': b, '3': c}
    items = [('Q5', (0, 0), E('E', 'C', 'B')), ('Q1', (11, 0), E('E', 'C', 'B')), ('Q12', (22, 0), E('E', 'C', 'B')), ('Q13', (33, 0), E('E', 'C', 'B')),
             ('Q2', (0, 13), E('D', 'S', 'G')), ('Q4', (11, 13), E('G', 'S', 'D')), ('U4', (22, 13), E('VO', 'GND', 'VI')), ('U9', (33, 13), E('VO', 'GND', 'VI'))]
    panel(fig, [0.03, 0.03, 0.94, 0.88], 'TO-92 の部品（ピンの並びが部品ごとに違う）', items,
          dims=[('Q5', '1', 'Q5', '2', 2.0), ('Q5', '1', 'Q5', '3', -2.4)], fs=6,
          shownum=False, table=[['部品番号', '部品', 'パッド 1・2・3', '注意'],
                 ['Q5・Q8〜Q11・Q14〜Q16・Q18・Q20〜Q22', '2SC1815', 'E・C・B', 'NPN'],
                 ['Q1', '2SA1015', 'E・C・B', 'PNP（2SC1815 と取り違えない）'],
                 ['Q12', '2SA950', 'E・C・B', 'PNP'],
                 ['Q13', '2SC2120', 'E・C・B', 'NPN'],
                 ['Q2・Q3・Q6・Q7', '2SK192A-BL', 'D・S・G', 'BL ランクを 4 個'],
                 ['Q4・Q17', '2SK439', 'G・S・D', '2SK192A と逆の並び'],
                 ['U4', '78L05', 'VO・GND・VI', '受信中だけの 5V'],
                 ['U9', 'LP2950-3.3', 'VO・GND・VI', 'Si5351 の 3.3V']],
          notes=['どの部品も、シルクの外形の平らな側に部品の平らな面（型番の印字面）を合わせて差すと、上の表の並びになる。',
                 'FET の並びはメーカーの資料で確認: 2SK192A（東芝）1 ドレイン・2 ソース・3 ゲート、2SK439（ルネサス、SPAK）1 ゲート・2 ソース・3 ドレイン。IDSS は 2SK192A の BL ランクが 12〜24mA、2SK439 が 4〜12mA（D・E・F の 3 区分）。',
                 'パッドの間隔は 1.27mm（TO-92 のまっすぐな足のまま差せる）、穴 φ0.75。',
                 '上の段の左から Q5（2SC1815 の代表）・Q1・Q12・Q13、下の段の左から Q2（2SK192A の代表）・Q4・U4・U9。向きは基板に置いたとおりなので、部品ごとに平らな側の向きが違う。'])


@page
def p_pa_relay(fig):
    panel(fig, L, 'Q19  RD06HVF1（TO-220）と放熱器 HS1', [('Q19', (0, 0), {'1': 'G', '2': 'S\n(タブ)', '3': 'D'})],
          dims=[('Q19', '1', 'Q19', '2', 2.4), ('Q19', '1', 'Q19', '3', -2.8)], fs=6,
          notes=['ピン 1 = G（四角パッド）・2 = S（タブと共通）・3 = D。ピッチ 2.54mm、穴 φ1.1。',
                 'タブ（図の上側の細長い枠）を放熱器 HS1 側に向ける。HS1 の脚ピン 2 本の穴（φ1.6、ピッチ 30.0mm）は Q19 の奥側にある。先に HS1 をタブに M3 ねじで固定し、足と放熱器の脚ピン 2 本（ピッチ 30mm、基板の穴 φ1.6）を同時に差す。',
                 '放熱器は秋月 17PB046（46.2 × 17 × 25mm、11.9℃/W）。断面は取付面からフィン側 10mm、Q19 側に両端のつば（厚さ約 1.3mm、長さ 7mm）。Q19 はつばの間に入る（GEC の資料）。'])
    lk = {'1': 'コイル\n(GND)', '16': 'コイル\n(Q1)', '4': 'COM1\nANT', '6': 'NC1\n受信', '8': 'NO1\n送信',
          '13': 'COM2\n+12V', '11': 'NC2\nRX12V', '9': 'NO2\nTX12V'}
    panel(fig, R, 'K1  リレー G5V-2 DC12', [('K1', (0, 0), lk)],
          dims=[('K1', '1', 'K1', '4', 3.0), ('K1', '4', 'K1', '6', 3.0), ('K1', '1', 'K1', '16', -3.0)], fs=5.5,
          notes=['DC12V のコイル品を使う（DC5V 品では焼ける）。コイルは 288Ω・41.7mA（約 0.5W、オムロンの資料）で、Q1（2SA1015）が流す。極性はない。',
                 'オムロンの資料（裏から見た図）: 1・16 = コイル、4・13 = COM、6・11 = NC（受信側）、8・9 = NO（送信側）。穴の間隔 7.62・5.08・5.08mm、列の間隔 7.62mm で部品形と一致。',
                 '穴はオムロンの推奨どおり φ1.0、ランド φ1.8（V2 Ver 1.3 で KiCad 標準の φ0.7 から変更。部品形は PSN_TRX:Relay_DPDT_Omron_G5V-2_D1.0mm）。',
                 'ピンの並びで向きは一つに決まる（逆には入らない）。コイルの 1 番が四角パッド。',
                 'D1（1N4001）はコイルの逆起電力の吸収。'])


@page
def p_coil(fig):
    l = {'1': 'SA', '2': 'CT', '3': 'SB', '4': 'AA', '5': 'AB'}
    panel(fig, L, 'L3・L12〜L14  FCZ コイル 7T50（07S50）', [('L3', (0, 0), l)],
          dims=[('L3', '1', 'L3', '2', 2.4), ('L3', '1', 'L3', '3', 3.6), ('L3', '4', 'L3', '5', -2.4)], fs=6,
          notes=['FCZ 研究所の寸法表（07S）: 外形 A 7.2mm 角、ピン間隔 B 4.5mm、ケースの爪の幅 C 1.0mm、ピン径 D 0.7mm。1–3 が同調巻線（2 = センタータップ）、4–5 がリンク巻線。',
                 'ケースの爪（2 か所、辺の中央）は長穴 1.4 × 0.7mm に差してはんだ付けする（GND。V2 Ver 1.3 で追加、それまでは穴がなく浮いた）。',
                 '5 本足の並びで向きは一つに決まる。',
                 'L3 は第 1 局発（38.5MHz、C8 27p）、L12〜L14 は送信（50.5MHz、15p）。L12 だけ CT を GND に使う。'])
    l1 = {'1': 'Q2 G', '2': 'タップ', '3': 'GND'}
    l2 = {'1': 'Q3 D', '2': 'タップ', '3': 'RX12V'}
    panel(fig, R, 'L1・L2  受信の同調コイル（T30-6、自分で巻く）', [('L1', (0, 0), l1), ('L2', (12, 0), l2)],
          dims=[('L1', '1', 'L1', '2', 2.0), ('L1', '1', 'L1', '3', -2.4)], fs=5.5,
          notes=['T30-6（黄、外径 7.8mm）に 0.4mm 線を 11 回。',
                 'L1（左）: GND 側（3 番）の端から 2 回目でタップ。L2（右）: RX12V 側（3 番）の端から 3 回目でタップ。',
                 'タップは真ん中の穴（2 番）。巻き始め・巻き終わりを 1 番・3 番に取り違えると利得が大きく変わる。'])


@page
def p_diode_cap(fig):
    items = [('D1', (0, 0), {'1': 'K', '2': 'A'}), ('D2', (0, 10), {'1': 'K', '2': 'A'}), ('D10', (10, 10), {'1': 'K', '2': 'A'})]
    panel(fig, L, 'ダイオード（D1・D2〜D9・D10）', items,
          dims=[('D1', '1', 'D1', '2', 2.0), ('D2', '1', 'D2', '2', 2.0), ('D10', '1', 'D10', '2', 2.0)], fs=6,
          notes=['四角パッドがカソード（K、帯の側）。',
                 'D1（1N4001／1N4007）: 横置き 10.16mm。',
                 'D2〜D9（1N4148・1N60、DO-35）: 縦置き 2.54mm。本体を A（丸パッド）の上に立て、K の足を折り返す（CathodeUp）。図は D2。',
                 'D10（1N5819、DO-41）: 縦置き 5.08mm。本体を K（四角パッド、XIAO 側）の上に立て、A の足を折り返す（AnodeUp）。D2 と逆なので注意。'])
    items = [('C96', (0, 0), {'1': '＋', '2': '−'}), ('C57', (12, 0), {'1': '＋', '2': '−'})]
    panel(fig, R, '電解コンデンサ（20 個）', items,
          dims=[('C96', '1', 'C96', '2', 4.0), ('C57', '1', 'C57', '2', 3.5)], fs=6,
          notes=['四角パッドが＋。足の長い方を四角パッドに。',
                 'C47・C48・C96（100µF）は φ6.3・ピッチ 2.5mm の部品形だが、秋月の 25PX100MEFC5X11 は φ5・ピッチ 2.0mm。足を 0.25mm ずつ広げて差す（φ5 なので外形は収まる）。',
                 'ほかの 10µF・47µF・1µF は φ5・ピッチ 2.0mm で部品形と同じ。',
                 'C59（0.01µF セラミック）・C60（0.068µF フィルム）は電解と同じ大きさの 2mm ピッチの穴に付ける無極性品（V2 Ver 1.3 から極性マークなし）。'])


@page
def p_trim(fig):
    items = [('VR7', (0, 0), {'1': 'R70', '2': 'ワイパ', '3': 'GND'}), ('VR3', (12, 0), {'1': '1', '2': '2', '3': '3'}), ('TC1', (24, 0), {'2': 'GND'})]
    panel(fig, [0.03, 0.03, 0.94, 0.88], '半固定抵抗・トリマ（VR7 3266W・VR3〜VR6 GF063P・TC1〜TC4 TMCV01）', items,
          dims=[('VR7', '1', 'VR7', '3', -2.6), ('VR7', '1', 'VR7', '2', 2.4), ('VR3', '1', 'VR3', '3', -2.6), ('VR3', '1', 'VR3', '2', 2.4), ('TC1', '1', 'TC1', '2', 3.0)], fs=6,
          notes=['VR7（Bourns 3266W、Idq 調整）: 足は三角の並び（1・3 番の間 5.08mm、2 番がずれた位置）で、向きは一つに決まる。最初はゲート電圧最小（GND 側いっぱい）にしておく。秋月の 3296W は大きくて入らない。',
                 'VR3〜VR6（TOCOS GF063P、6mm 角）: 足は 2.5mm の三角の並び。VR3・VR4 は 500Ω、VR5・VR6 は 1kΩ（取り違えない）。',
                 'TC1〜TC3（TMCV01 30pF、緑）・TC4（10pF、白）: 6mm 角・2 本足。足の間隔 6.3mm（Topmay の取付穴図: 1 番〜回転子中心 3.0mm、中心〜2 番 3.3mm）、穴は長穴 1.0 × 1.3mm（V2 Ver 1.3 で 5.0mm・φ1.2 から修正）。TC4 だけ値が違う。',
                 '図は左から VR7・VR3・TC1（向きは基板に置いたとおり）。'])


@page
def p_misc(fig):
    items = [('J2', (0, 0), {'1': '+12V', '2': 'GND'}), ('Y1', (14, 0), {'1': '1', '2': '2'}), ('L20', (26, 0), {'1': '1', '2': '2'})]
    panel(fig, L, '電源入力 J2・水晶 Y1〜Y6・縦置きインダクタ', items,
          dims=[('J2', '1', 'J2', '2', -3.0), ('Y1', '1', 'Y1', '2', 3.0), ('L20', '1', 'L20', '2', -3.0)], fs=6,
          notes=['J2: 電線のじか付け（穴 φ1.1、AWG20 = 0.5sq。電流は送信時でも 1A 弱）。四角パッドが +12V。基板の左辺の前寄り（ケースの電源スイッチ・DC ジャックの側）。J1（アンテナ）も同じ穴 φ1.1 の同軸じか付け（2.54mm ピッチ、1 = 芯線、2 = 編組）。',
                 'Y1〜Y6: 部品形は HC-49/U だが、買う品（HUSG-12.000-20）は背の低い HC-49/S。足の間隔は同じ 4.88mm。',
                 'L4〜L11・L20（AL0510／AL0410）は縦置き 2.54mm。本体を片方の穴の上に立て、もう一方の足を折り返す。L4 は 8.2µH、L5・L6 は 4.7µH（色帯で見分ける）。'])
    items = [('RFC1', (0, 0), {'1': 'TX12V', '2': 'Q19 D'}), ('L15', (0, 9), {'1': '1', '2': '2'}), ('C8', (22, 0), {'1': '1', '2': '2'})]
    panel(fig, R, '横置きのコイル・足を寄せるコンデンサ', items,
          dims=[('RFC1', '1', 'RFC1', '2', 2.6), ('L15', '1', 'L15', '2', 2.6), ('C8', '1', 'C8', '2', 2.0)], fs=6,
          notes=['RFC1（10µH、AL0510 長さ 14mm）: 横置き 15.24mm。スピーカーのマグネットの下なので寝かせて付ける。',
                 'L15（47nH）: 縦置き 2.54mm（本体を 1 番の上に立てる。放熱器のつばの内側。V2 Ver 1.3 で横置き 12.7mm から変更）。',
                 'C8（27p）・C17・C21（82p）・C19（120p）・C66〜C69（3300p）・C76〜C79（47p）は、2.54mm ピッチ品がないので 5mm ピッチ品（RDE、幅 4mm・厚み 2.5mm）の足を寄せて 2.5mm の穴に差す。図は C8（部品形の外形 3.0 × 1.6mm より実物が大きいので、隣の部品に当たらないよう少し浮かせる）。'])


if __name__ == '__main__':
    total = len(pages)
    with PdfPages(OUT, metadata={'Title': 'PSN_TRX_XIAO_ESP32C3-V2 間違いやすい部品の部品形', 'Author': 'JA6FUF'}) as pdf:
        for i, fn in enumerate(pages, 1):
            fig = plt.figure(figsize=A4)
            header(fig, i, total)
            fn(fig)
            pdf.savefig(fig)
            if PNGDIR:
                os.makedirs(PNGDIR, exist_ok=True)
                fig.savefig(os.path.join(PNGDIR, f'fp_check_{i:02d}.png'), dpi=130)
            plt.close(fig)
    print('pages', total, OUT)
