"""NJM2594V（U1・U2）はんだ付け確認の測定点の図を作る。

使い方（リポジトリのトップで）:
    python3 docs/tools/make_njm2594_points.py
kicad-cli（KiCad 10）と rsvg-convert が要る。出力は manual/images/njm2594-test-points.png。
"""
import os,subprocess,sys,tempfile
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KCLI=os.environ.get('KICAD_CLI','/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
S=tempfile.mkdtemp()
for L in ['F.Cu','F.Silkscreen','Edge.Cuts']:
    subprocess.run([KCLI,'pcb','export','svg','--mode-single','-o',f'{S}/l_{L}.svg','-l',L,
        '--page-size-mode','1','--exclude-drawing-sheet','--black-and-white',
        os.path.join(ROOT,'kicad','PSN_TRX.kicad_pcb')],check=True,capture_output=True)
def body(name):
    s=open(f'{S}/l_{name}.svg').read()
    i=s.index('<desc>'); i=s.index('</desc>',i)+7
    j=s.rindex('</svg>')
    return s[i:j]
cu=body('F.Cu'); silk=body('F.Silkscreen'); edge=body('Edge.Cuts')
layers=(f'<g opacity="0.10">{cu}</g>'
        f'<g opacity="0.55">{silk}</g><g>{edge}</g>')
COL={'1':'#d62728','3':'#2ca02c','5':'#1f77b4','6':'#ff7f0e','7':'#9467bd'}
# (pin, x, y, label, dx, dy)
pts=[
 ('1',111.19,48.38,'U1-1 C11',104,60.5),
 ('3',114.69,51.13,'U1-3 R10',114.5,60.5),
 ('5',103.69,44.88,'U1-5 C9',97,56),
 ('6',107.69,42.38,'U1-6 C13',97,36),
 ('7',117.69,46.38,'U1-7 C10',112,33),
 ('1',130.19,37.88,'U2-1 C27',135,33),
 ('3',129.94,34.38,'U2-3 R27',122,29.6),
 ('5',141.19,45.88,'U2-5 C25',137,54),
 ('6',126.19,46.88,'U2-6 C28',118,56),
 ('7',133.44,65.64,'U2-7 C26',121,63),
]
def marks(pts,fs):
    o=[]
    for p,x,y,t,dx,dy in pts:
        c=COL.get(p,'#000')
        lx,ly=dx,dy
        w=len(t)*fs*0.62
        o.append(f'<rect x="{lx-0.3}" y="{ly-fs*0.95}" width="{w+0.6}" height="{fs*1.25}" rx="0.3" fill="#fff" stroke="{c}" stroke-width="0.15"/>')
        ex=min(max(x,lx),lx+w); ey=ly-fs*0.35 if abs(x-ex)>0.01 else (ly-fs*0.95 if y<ly else ly+fs*0.3)
        o.insert(0,f'<line x1="{x}" y1="{y}" x2="{ex}" y2="{ey}" stroke="{c}" stroke-width="0.22"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="0.85" fill="none" stroke="{c}" stroke-width="0.35"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="0.25" fill="{c}"/>')
        o.append(f'<text x="{lx}" y="{ly}" font-size="{fs}" fill="{c}" font-weight="bold">{t}</text>')
    return '\n'.join(o)
def ic(name,pads,cx,cy,dx,dy):
    o=[]
    xs=[p[1] for p in pads]; ys=[p[2] for p in pads]
    o.append(f'<rect x="{min(xs)-0.7}" y="{min(ys)-0.9}" width="{max(xs)-min(xs)+1.4}" height="{max(ys)-min(ys)+1.8}" fill="none" stroke="#000" stroke-width="0.25" stroke-dasharray="0.6 0.4"/>')
    for n,x,y in pads:
        o.append(f'<text x="{x}" y="{y+0.22}" font-size="0.6" text-anchor="middle" fill="#000" font-weight="bold">{n}</text>')
    o.append(f'<text x="{cx+dx}" y="{cy+dy}" font-size="1.4" font-weight="bold" fill="#000" stroke="#fff" stroke-width="0.4" paint-order="stroke" text-anchor="middle">{name}</text>')
    return '\n'.join(o)
U1=[('1',106.47,51.25),('2',107.11,51.25),('3',107.77,51.25),('4',108.42,51.25),('5',108.42,45.52),('6',107.77,45.52),('7',107.11,45.52),('8',106.47,45.52)]
U2=[('1',130.91,41.02),('2',130.26,41.02),('3',129.62,41.02),('4',128.97,41.02),('5',128.97,46.75),('6',129.62,46.75),('7',130.26,46.75),('8',130.91,46.75)]
FONT='font-family="Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif"'
# main view
vx,vy,vw,vh=96,27,52,41.5
main=f'''<svg x="0" y="14" width="{vw*20}" height="{vh*20}" viewBox="{vx} {vy} {vw} {vh}">
<rect x="{vx}" y="{vy}" width="{vw}" height="{vh}" fill="#fff"/>{layers}
{ic('U1',U1,107.44,48.38,0,5.6)}{ic('U2',U2,129.94,43.88,0,-3.8)}
{marks(pts,1.3)}</svg>'''
# power inset
px,py,pw,ph=176,25,20,11
pp=[('p',187.69,31.64,'U4-1 +5V',189.5,34.5),('g',187.69,30.36,'U4-2 GND',189.5,27.2),('p',183.19,30.39,'C50 +',181,27.2),('g',181.19,30.39,'C50 −',176.5,34.5)]
COL.update({'p':'#d62728','g':'#333'})
inset=f'''<svg x="{vw*20+20}" y="14" width="{pw*20}" height="{ph*20}" viewBox="{px} {py} {pw} {ph}">
<rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="#fff"/>{layers}{marks(pp,1.1)}</svg>'''
W=vw*20+20+pw*20; H=vh*20+14
leg=[('1','1 番 V+ … 5.0V'),('3','3 番 OUTPUT2 … 約 3.3V'),('5','5 番 SIGNAL … 約 2.2V'),('6','6 番 BYPASS … 約 2.2V'),('7','7 番 CARRIER … 約 2.2V')]
lg=[f'<text x="{vw*20+28}" y="{14+ph*20+40}" font-size="17" font-weight="bold">各ピンの測定点（IC 側のパッド）</text>']
for k,(p,t) in enumerate(leg):
    y=14+ph*20+72+k*30
    lg.append(f'<circle cx="{vw*20+38}" cy="{y-6}" r="8" fill="none" stroke="{COL[p]}" stroke-width="3"/><text x="{vw*20+54}" y="{y}" font-size="16" fill="{COL[p]}" font-weight="bold">{t}</text>')
lg.append(f'<text x="{vw*20+28}" y="{14+ph*20+72+5*30+10}" font-size="14" fill="#333">2・8 番は測定不要</text>')
lg.append(f'<text x="{vw*20+28}" y="{14+ph*20+72+5*30+34}" font-size="14" fill="#333">GND 基準で測る</text>')
lg.append(f'<text x="{vw*20+28}" y="{14+ph*20+72+5*30+58}" font-size="14" fill="#333">基板表面（部品面）から見た図</text>')
out=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H+30}" viewBox="0 -30 {W} {H+30}" {FONT}>
<rect x="0" y="-30" width="{W}" height="{H+30}" fill="#fff"/>
<text x="10" y="2" font-size="22" font-weight="bold">NJM2594V（U1・U2）はんだ付け確認の測定点</text>
{main}
<text x="{vw*20+28}" y="2" font-size="16" font-weight="bold">5V を入れる所（U4・C50）</text>
{inset}
<rect x="{vw*20+20}" y="14" width="{pw*20}" height="{ph*20}" fill="none" stroke="#888"/>
{''.join(lg)}
</svg>'''
open(f'{S}/points.svg','w').write(out)
subprocess.run(['rsvg-convert','-z','1.5',f'{S}/points.svg','-o',
    os.path.join(ROOT,'manual','images','njm2594-test-points.png')],check=True)
