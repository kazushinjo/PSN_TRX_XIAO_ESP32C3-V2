"""NJM2594V はんだ付け確認（U4・K1 も付けて 12V で確かめる方法）の測定点の図を作る。

使い方（リポジトリのトップで）:
    python3 docs/tools/make_njm2594_12v_points.py
kicad-cli（KiCad 10）と rsvg-convert が要る。出力は manual/images/njm2594-test-12v-points.png。
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KCLI = os.environ.get('KICAD_CLI', '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
S = tempfile.mkdtemp()
for L in ['F.Cu', 'F.Silkscreen', 'Edge.Cuts']:
    subprocess.run([KCLI, 'pcb', 'export', 'svg', '--mode-single', '-o', f'{S}/l_{L}.svg', '-l', L,
                    '--page-size-mode', '1', '--exclude-drawing-sheet', '--black-and-white',
                    os.path.join(ROOT, 'kicad', 'PSN_TRX.kicad_pcb')], check=True, capture_output=True)


def body(name):
    s = open(f'{S}/l_{name}.svg').read()
    i = s.index('</desc>') + 7
    return s[i:s.rindex('</svg>')]


LAYERS = (f'<g opacity="0.10">{body("F.Cu")}</g>'
          f'<g opacity="0.55">{body("F.Silkscreen")}</g><g>{body("Edge.Cuts")}</g>')

RED, BLK, GRN, BLU, PUR, ORG = '#d62728', '#333333', '#2ca02c', '#1f77b4', '#9467bd', '#ff7f0e'


def marks(pts, fs):
    o = []
    for c, x, y, t, lx, ly in pts:
        w = sum(1.0 if ord(ch) > 0x2000 else 0.62 for ch in t) * fs
        o.append(f'<rect x="{lx-0.3}" y="{ly-fs*0.95}" width="{w+0.6}" height="{fs*1.25}" rx="0.3" '
                 f'fill="#fff" stroke="{c}" stroke-width="{fs*0.12}"/>')
        ex = min(max(x, lx), lx + w)
        ey = ly - fs * 0.35 if abs(x - ex) > 0.01 else (ly - fs * 0.95 if y < ly else ly + fs * 0.3)
        o.insert(0, f'<line x1="{x}" y1="{y}" x2="{ex}" y2="{ey}" stroke="{c}" stroke-width="{fs*0.17}"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="{fs*0.65}" fill="none" stroke="{c}" stroke-width="{fs*0.27}"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="{fs*0.2}" fill="{c}"/>')
        o.append(f'<text x="{lx}" y="{ly}" font-size="{fs}" fill="{c}" font-weight="bold">{t}</text>')
    return '\n'.join(o)


def box(x0, y0, x1, y1, t, c, fs, tx=None, ty=None):
    tx = x0 if tx is None else tx
    ty = y0 - fs * 0.3 if ty is None else ty
    return (f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="none" stroke="{c}" '
            f'stroke-width="{fs*0.18}" stroke-dasharray="{fs*0.6} {fs*0.4}"/>'
            f'<text x="{tx}" y="{ty}" font-size="{fs}" font-weight="bold" fill="{c}" stroke="#fff" '
            f'stroke-width="{fs*0.25}" paint-order="stroke">{t}</text>')


# 全体図（基板 81.45〜215.55 × 25.1〜154.9）
ov = (80, 20, 137, 137)
ov_marks = [
    (RED, 198.0, 151.69, 'J2 +12V', 178, 145),
    (BLK, 203.08, 151.69, 'J2 GND', 202, 139.5),
    (RED, 187.69, 29.09, 'U4-3 入力', 160, 37),
    (RED, 187.69, 31.64, 'U4-1 出力', 160, 43),
    (RED, 177.4, 51.93, 'C55 +', 165, 58),
]
ov_body = (box(95.5, 57.5, 106, 80, 'K1', BLU, 3.2, 95.5, 56) +
           box(105.5, 44.5, 109.5, 52.2, 'U1', BLK, 3.2, 110, 54) +
           box(128, 40, 132, 47.8, 'U2', BLK, 3.2, 133, 45) +
           box(179.5, 27.5, 189.5, 33.5, 'U4・C50', BLK, 3.2, 165, 25.5) +
           box(84, 50, 112, 81, '右の拡大図', PUR, 2.6, 84, 86) +
           marks(ov_marks, 3.2))

# K1 まわりの拡大図
kz = (83, 50, 30, 32)
k_marks = [
    (RED, 104.38, 67.49, 'K1-13 +12V（共通）', 106.5, 64.5),
    (GRN, 104.38, 72.57, 'K1-11 RX12V（受信）', 106.5, 71.7),
    (ORG, 104.38, 77.65, 'K1-9 TX12V（送信）', 106.5, 79.3),
    (BLU, 92.63, 64.94, 'J1-1 ANT', 84, 59.5),
    (GRN, 88.44, 65.14, 'D2 帯側（受信入力）', 83.6, 53.5),
    (ORG, 88.19, 68.64, 'L19-1（送信 LPF）', 84, 81),
    (PUR, 108.19, 68.12, 'D1 帯側（コイル）', 106.5, 57.5),
]
kz_body = marks(k_marks, 1.25)

SC1, SC2 = 6.0, 22.0
W1, H1 = ov[2] * SC1, ov[3] * SC1
W2, H2 = kz[2] * SC2 + 260, kz[3] * SC2
FONT = 'font-family="Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif"'
W, H = W1 + 20 + W2, max(H1, H2) + 50
legend = [
    (GRN, '受信: K1-13 と 11、J1 と D2 がつながる'),
    (ORG, '送信（D1 帯側に +12V）: K1-13 と 9、J1 と L19 がつながる'),
]
lg = ''.join(f'<text x="{W1+20}" y="{H2+80+k*26}" font-size="17" font-weight="bold" fill="{c}">{t}</text>'
             for k, (c, t) in enumerate(legend))
out = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H+60}" viewBox="0 -10 {W} {H+60}" {FONT}>
<rect x="0" y="-10" width="{W}" height="{H+60}" fill="#fff"/>
<text x="10" y="22" font-size="22" font-weight="bold">U4・K1 も付けて 12V で確かめる方法の測定点</text>
<svg x="0" y="40" width="{W1}" height="{H1}" viewBox="{ov[0]} {ov[1]} {ov[2]} {ov[3]}">
<rect x="{ov[0]}" y="{ov[1]}" width="{ov[2]}" height="{ov[3]}" fill="#fff"/>{LAYERS}{ov_body}</svg>
<svg x="{W1+20}" y="40" width="{W2}" height="{H2}" viewBox="{kz[0]} {kz[1]} {kz[2]+260/SC2} {kz[3]}">
<rect x="{kz[0]}" y="{kz[1]}" width="{kz[2]+260/SC2}" height="{kz[3]}" fill="#fff"/>
<svg x="{kz[0]}" y="{kz[1]}" width="{kz[2]}" height="{kz[3]}" viewBox="{kz[0]} {kz[1]} {kz[2]} {kz[3]}">{LAYERS}</svg>
<rect x="{kz[0]}" y="{kz[1]}" width="{kz[2]}" height="{kz[3]}" fill="none" stroke="{PUR}" stroke-width="0.2"/>
{kz_body}</svg>
{lg}
<text x="{W1+20}" y="{H2+80+2*26+6}" font-size="14" fill="#333">基板表面（部品面）から見た図</text>
</svg>'''
open(f'{S}/points12.svg', 'w').write(out)
subprocess.run(['rsvg-convert', '-z', '1.3', f'{S}/points12.svg', '-o',
                os.path.join(ROOT, 'manual', 'images', 'njm2594-test-12v-points.png')], check=True)
