"""受信部（V2: 12MHz の SSB シングルスーパー）の計算
  1. 受信の前段（L18 の入力同調 → Q20・Q25 2SK192A-GR カスコード → L19 の出力同調）: 利得・雑音指数・イメージ・半 IF・FM 放送の抑圧、トリマの位置
  2. 12MHz ラダーフィルタ（Y1〜Y6）: 帯域・挿入損失・リップル（水晶の運動定数は仮定）
  3. RF 増幅（Q20・Q25 2SK192A-GR）と混合後増幅（Q21 2SC1815 ＋ L 整合）の利得
  4. IF 増幅（Q2 3SK59）・S メーター増幅（Q22）の利得と、アンテナから積検波・AD8307・スピーカーまでのレベル
定数は回路図のネットリスト（net.json）から読む。水晶・コア・FET の特性は仮定（下の表）。
"""
import ngs, math, re
from gen import *

F0 = 50.5e6          # 受信帯の中央
IF = 12e6
LO = F0 - IF         # 下側局発 38.5MHz
AL_T30_6 = 3.6e-9    # T-30-6: 36µH/100T
QL_T30 = 120         # 50MHz 付近の無負荷 Q の目安（rf.py と同じ）


def db(x):
    return 20 * math.log10(max(abs(x), 1e-30))


def at(f, h, x):
    i = min(range(len(f)), key=lambda k: abs(f[k] - x))
    return h[i]


# ---------------------------------------------------------------- 1. 受信の前段（入力同調 → カスコード RF 増幅 → 出力同調）
def tapped(ref, n_total, n_tap, k=0.9):
    """タップ付きトロイダル（1=ホット、2=タップ、3=コールド）。巻線を 2 つに分けて結合 k でつなぐ"""
    a, t, c = pin(ref, '1'), pin(ref, '2'), pin(ref, '3')
    l_lo = AL_T30_6 * n_tap ** 2
    l_hi = AL_T30_6 * (n_total - n_tap) ** 2
    l_all = AL_T30_6 * n_total ** 2
    r = 2 * math.pi * F0 * l_all / QL_T30
    if t.startswith('n_unconnected'):
        used[ref] = l_all
        return f"L{ref} {a} m{ref} {l_all:g}\nRL{ref} m{ref} {c} {r:g}"
    used[ref] = l_all
    return (f"L{ref}h {a} {t} {l_hi:g}\nL{ref}c {t} m{ref} {l_lo:g}\nRL{ref} m{ref} {c} {r:g}\n"
            f"K{ref} L{ref}h L{ref}c {k}")


# 2SK192A-GR（Q20・Q25）: Vp −2V・Idss 10mA（dc.py と同じ代表値。Ciss 3.5pF・Crss 0.65pF）
MODRF = """
.model JK192r NJF(VTO=-2 BETA=2.5m LAMBDA=0.01 CGS=2.9p CGD=0.65p RS=5 RD=5)
"""
ZIN_MIX = 600        # NJM2594 の信号入力（約 600Ω と仮定）
TAP19 = 2            # L19 のタップ（+9V 側から数えた巻数）


def front(tc3, tc4, vg2=4.0, tap19=None, c80=None, c82=None):
    """アンテナ（50Ω）→ L18 のタップ（同調 C80・TC3）→ Q20（2SK192A）→ Q25（2SK192A、ゲートは AGC の Q2_G2）
    → L19（同調 C82・TC4、R67 で制動）のタップ → C85 → NJM2594 の入力（600Ω）"""
    e = [tapped('L18', 11, 2), C('C80', c80), f"CTC3 {pin('TC3','1')} 0 {tc3}", f"CD9 {pin('D9','1')} 0 2p",
         f"J20 {pin('Q20','D')} {pin('Q20','G')} {pin('Q20','S')} JK192r", R('R66'), C('C83'),
         f"J25 {pin('Q25','D')} {pin('Q25','G')} {pin('Q25','S')} JK192r", R('R95'), C('C116'),
         tapped('L19', 11, tap19 or TAP19), C('C82', c82), f"CTC4 {pin('TC4','1')} 0 {tc4}", R('R67'), C('C84'), C('C85'),
         f"RMIX {pin('C85','2')} 0 {ZIN_MIX}", f"V9 {node('+9V')} 0 dc 12", f"VG2 {pin('R95','1')} 0 dc {vg2}",
         f"VS src 0 dc 0 ac 2\nRS src {pin('L18','2')} 50"]
    return 'fe\n' + MODRF + '\n'.join(e) + '\n'


def resp(net, fmin, fmax, pts, out=None):
    ngs.run(net + f".ac lin {pts} {fmin:g} {fmax:g}\n")
    return [x.real for x in ngs.vec('frequency')], ngs.vec(out or pin('C85', '2'))


TMIN, TMAX = 6e-12, 30e-12   # 30pF セラミックトリマの可変範囲（最小 約 6pF）


def tune(**kw):
    """TC3・TC4 を 50.5MHz で混合器の入力が最大になるように合わせる（0.5pF 刻みで全部 → 0.25pF で片側ずつ）"""
    one = lambda a, b: abs(resp(front(a, b, **kw), F0, F0, 1)[1][0])
    best = max(((one(a, b), a, b) for a in [x * 1e-12 for x in range(2, 31)] for b in [x * 1e-12 for x in range(2, 31)]))
    v, a, b = best
    for _ in range(2):
        for which in (0, 1):
            for c in [((a if which == 0 else b) + d * 0.25e-12) for d in range(-4, 5)]:
                if c < 0.25e-12: continue
                ta, tb = (c, b) if which == 0 else (a, c)
                vv = one(ta, tb)
                if vv > v: v, a, b = vv, ta, tb
    return a, b


def nf_gain(net):
    """前段の雑音指数（50Ω 源）と電力利得（有能電力 → 600Ω）"""
    ngs.run(net + f".noise v({pin('C85','2')}) VS lin 3 {F0-1e3:g} {F0+1e3:g}\n")
    ngs.cmd('setplot noise1')
    vin = abs(ngs.vec('inoise_spectrum')[1])
    nf = 10 * math.log10((vin / 2) ** 2 / (1.38e-23 * 290 * 50))
    v = abs(resp(net, F0, F0, 1)[1][0])
    return nf, 10 * math.log10((v ** 2 / ZIN_MIX) / (1 / 50))


print('### 受信の前段（L18・L19 T30-6 11T、コア Q 約 120、結合 k 0.9。Q20・Q25 2SK192A-GR カスコード、混合器の入力 600Ω と仮定）')
for t19 in (2, 3):
    a, b = tune(tap19=t19)
    nf, g = nf_gain(front(a, b, tap19=t19))
    print(f'  L19 のタップ {t19}T: TC3 {a*1e12:.2f}pF・TC4 {b*1e12:.2f}pF、電力利得 {g:+.1f}dB、雑音指数 {nf:.2f}dB')
tc3, tc4 = tune()
FE = front(tc3, tc4)
ok = 'トリマの範囲内' if TMIN <= tc3 <= TMAX and TMIN <= tc4 <= TMAX else '範囲外'
print(f'→ タップ {TAP19}T（回路図どおり）で計算: TC3 {tc3*1e12:.2f}pF、TC4 {tc4*1e12:.2f}pF（{ok}）')
f, h = resp(FE, 10e6, 120e6, 2000)
ref = abs(resp(FE, F0, F0, 1)[1][0])
for name, x in [('50.0MHz', 50e6), ('51.0MHz', 51e6), ('イメージ 26.5MHz（LO 38.5 − 12）', LO - IF),
                ('27MHz 帯（CB・小電力）', 27.1e6), ('半 IF 44.5MHz（LO + 6）', LO + IF / 2),
                ('局発 38.5MHz の漏れ', LO), ('12MHz の素通り', IF), ('FM 放送 76MHz', 76e6), ('FM 放送 90MHz', 90e6),
                ('3LO − IF 103.5MHz', 3 * LO - IF)]:
    v = abs(resp(FE, x, x, 1)[1][0])
    print(f'  {name}: {db(v / ref):+.1f} dB')
bw = [x for x, y in zip(f, h) if abs(y) >= ref / math.sqrt(2)]
print(f'  −3dB 帯域: {bw[0]/1e6:.2f}〜{bw[-1]/1e6:.2f}MHz')
BPF_GAIN = abs(resp(FE, F0, F0, 1, pin('Q20', 'G'))[1][0])
print(f'  50.5MHz での Q20 のゲート電圧（整合時のアンテナ端 1 に対して）: {BPF_GAIN:.2f} 倍（{db(BPF_GAIN):+.1f} dB）')
for vg2 in (4.0, 2.0, 1.0, 0.0):
    v = abs(resp(front(tc3, tc4, vg2=vg2), F0, F0, 1)[1][0])
    print(f'  AGC（Q25 のゲート {vg2:.1f}V）: 前段の利得 {db(v / ref):+.1f} dB')

# ---------------------------------------------------------------- 2. ラダーフィルタ
XTAL = dict(Cm=15e-15, Rs=25, C0=4e-12)   # 12MHz HC-49/US の運動定数の仮定（実物を測って置き換える）


def ladder(cm=XTAL['Cm'], rs=XTAL['Rs'], c0=XTAL['C0'], rterm=None, rsrc=None, caps=None, spread=None, f0=IF):
    lm = 1 / ((2 * math.pi * f0) ** 2 * cm)
    e = []
    for i in range(1, 7):
        a, b = pin(f'Y{i}', '1'), pin(f'Y{i}', '2')
        d = (spread[i - 1] if spread else 0)
        fi = f0 + d
        lmi = 1 / ((2 * math.pi * fi) ** 2 * cm)
        e.append(f"LY{i} {a} y{i}a {lmi:g}\nCY{i} y{i}a y{i}b {cm:g}\nRY{i} y{i}b {b} {rs:g}\nC0Y{i} {a} {b} {c0:g}")
    for ref in ['C94', 'C95', 'C96', 'C97', 'C98']:
        e.append(C(ref, caps[ref] if caps else None))
    rt = rterm if rterm else val('R76')
    rsrc = rsrc if rsrc else rt          # 入力側は Q21 の L 整合（C93・L21）で出力側と同じ抵抗に合わせる
    e.append(f"RT {pin('R76','1')} 0 {rt:g}")
    e.append(f"VS src 0 dc 0 ac 2\nRS src {pin('Y1','1')} {rsrc:g}")
    net = 'ladder\n' + '\n'.join(e) + f"\n.ac lin 1601 {f0-8e3:g} {f0+8e3:g}\n"
    ngs.run(net)
    fr, hv = [x.real for x in ngs.vec('frequency')], ngs.vec(pin('R76', '1'))
    # 電力利得（源の有能電力に対する負荷の電力）
    g = [abs(v) ** 2 / rt / (1 / rsrc) for v in hv]
    return fr, g


def summary(fr, g, label):
    gmax = max(g)
    pk = fr[g.index(gmax)]
    def edge(level_db):
        thr = gmax * 10 ** (level_db / 10)
        idx = [i for i, x in enumerate(g) if x >= thr]
        return fr[idx[0]], fr[idx[-1]]
    a3, b3 = edge(-3); a6, b6 = edge(-6); a60, b60 = edge(-60)
    inside = [10 * math.log10(x / gmax) for x, f in zip(g, fr) if a3 <= f <= b3]
    print(f'  {label}: 損失 {-10*math.log10(gmax):.1f} dB、−3dB 幅 {(b3-a3):.0f}Hz、−6dB 幅 {(b6-a6):.0f}Hz、'
          f'−60dB 幅 {(b60-a60):.0f}Hz、通過域のリップル {-min(inside):.1f} dB、中心 {(a6+b6)/2-IF:+.0f}Hz（12MHz から）')


print()
print(f"### 12MHz ラダーフィルタ（水晶の運動定数は仮定: Cm 15fF、Rs 25Ω、C0 4pF。入力・出力とも {COMPS['R76']}Ω（出力 R76、入力は L 整合））")
fr, g = ladder()
summary(fr, g, f"今の定数（{'/'.join(COMPS[r] for r in ['C94','C95','C96','C97','C98'])}、R76 {COMPS['R76']}Ω）")
for rt in (220, 470):
    fr, g = ladder(rterm=rt)
    summary(fr, g, f'終端 {rt}Ω なら')
for cm in (10e-15, 20e-15):
    fr, g = ladder(cm=cm)
    summary(fr, g, f'Cm {cm*1e15:.0f}fF の水晶なら')
fr, g = ladder(spread=[0, 60, -60, 40, -40, 0])
summary(fr, g, '水晶の直列共振が ±60Hz ばらついたとき')

# ---------------------------------------------------------------- 3. 利得
MOD = """
.model QS NPN(IS=2e-14 BF=200 VAF=100 BR=3 RB=50 RC=1 CJE=10p CJC=3.5p TF=0.5n)
""" + MODRF
print()
print('### 利得（2SK192A-GR: Vp −2V・Idss 10mA、2SC1815: hFE 200 と仮定）')
# RF 増幅: Q20 のゲート → MIX_IN（1. の前段の計算から、ゲートまでの分を除く）
RFA_GAIN = ref / BPF_GAIN
print(f'  RF 増幅（Q20・Q25 2SK192A-GR カスコード、ゲート → L19 のタップ → NJM2594 の入力 600Ω）: 電圧利得 {db(RFA_GAIN):+.1f} dB（50.5MHz）')
ngs.run(FE + ".op\n")
try:
    vs, vd20, vd25 = ngs.vec(pin('Q20', 'S'))[0], ngs.vec(pin('Q20', 'D'))[0], ngs.vec(pin('Q25', 'D'))[0]
    print(f'    動作点: Q20 ソース {vs:.2f}V → ドレイン電流 約 {vs/val("R66")*1e3:.1f}mA、Q20 の Vds {vd20-vs:.2f}V、Q25 の Vds {vd25-vd20:.2f}V')
except KeyError:
    pass

# 混合後増幅: MIX_EF（NJM2594 のエミッタフォロワ出力、出力抵抗 約 50Ω と仮定）→ Q21 → L 整合 → XF_IN（ラダーの入力 = R76 で終端）
e = [f"VSRC s 0 dc 0 ac 1\nRSRC s {pin('C89','1')} 50", R('R70'), C('C89'), R('R71'), R('R72'),
     BJT('Q21', 'QS'), R('R73'), R('R74'), C('C90'), R('R75'), C('C91'), C('C92'), C('C93'), L('L21', 1.0),
     f"RFILT {pin('L21','2')} 0 {val('R76'):g}", f"V9 {node('+9V')} 0 dc 12"]
ngs.run('ifa\n' + MOD + '\n'.join(e) + f"\n.ac lin 3 {IF-0.5e6} {IF+0.5e6}\n")
vin = ngs.vec(pin('C89', '1'))[1]
vout = ngs.vec(pin('L21', '2'))[1]
pg = (abs(vout) ** 2 / val('R76')) / (abs(vin) ** 2 / 1000)
print(f"  混合後増幅（Q21 ＋ L 整合 → {COMPS['R76']}Ω）: 電圧利得 {db(vout/vin):+.1f} dB、"
      f'電力利得 {10*math.log10(pg):+.1f} dB（NJM2594 の出力 1kΩ 基準）')
IFA_GAIN = abs(vout / vin)
ngs.run('ifadc\n' + MOD + '\n'.join(e) + "\n.op\n")
try:
    ve, vc = ngs.vec(pin('Q21', 'E'))[0], ngs.vec(pin('Q21', 'C'))[0]
    print(f'    動作点: エミッタ {ve:.2f}V（Ic 約 {ve/(val("R73")+val("R74"))*1e3:.1f}mA）、コレクタ {vc:.2f}V')
except KeyError:
    pass

# ---------------------------------------------------------------- 4. IF 増幅・S メーター・レベル配分
# 3SK59 はデュアルゲート MOSFET。下側（G1）と上側（G2）の 2 個の NMOS の直列で近似（Idss 約 10mA、Vp −1.5V と仮定）
MOD2 = MOD + ".model DG NMOS(LEVEL=1 VTO=-1.5 KP=8.9m LAMBDA=0.02 CGSO=0 CGDO=0)\n"
ZIN_DET = 600      # NJM2594 の信号入力（RF 増幅の計算と同じ仮定）
RIN_LOG = 1.1e3    # AD8307 の入力抵抗（データシート 1.1kΩ‖1.4pF）
QL_IF = 60         # L22・L23（4.7µH のマイクロインダクタ）の 12MHz での Q の目安


def ifa(g2=None):
    """Q2_G1 に 12MHz の小信号 → Q2_D（L22・C11 の同調）→ C99 → U5（600Ω）、R81 → Q22 → L23・C108 → AD8307"""
    xl = lambda ref: 2 * math.pi * IF * val(ref)
    e = [f"MQ2a {pin('Q2','S')} {pin('Q2','G1')} mq 0 DG", f"MQ2b {pin('Q2','D')} {pin('Q2','G2')} mq 0 DG",
         R('R5'), C('C8'), R('R76'), L('L22', xl('L22') / QL_IF), C('C11'), C('C99'), f"RDET {pin('C99','2')} 0 {ZIN_DET}",
         R('R81'), C('C106'), R('R82'), R('R83'), BJT('Q22', 'QS'), R('R84'), R('R85'), C('C107'),
         L('L23', xl('L23') / QL_IF), C('C108'), C('C110'), f"RLOG {pin('C110','2')} 0 {RIN_LOG}\nCLOG {pin('C110','2')} 0 1.4p",
         f"V9 {node('+9V')} 0 dc 12", f"VG2 {pin('Q2','G2')} 0 dc {g2 if g2 is not None else 4.0}",
         f"VG {pin('Q2','G1')} 0 dc 0 ac 1"]
    return 'ifa2\n' + MOD2 + '\n'.join(e)


print()
print('### IF 増幅（Q2 3SK59 を NMOS 2 個で近似: Idss 約 10mA・Vp −1.5V）と S メーター増幅（Q22）。'
      f'L22・L23 の Q {QL_IF}、U5 の入力 {ZIN_DET}Ω、AD8307 の入力 1.1kΩ と仮定')
ngs.run(ifa() + f"\n.ac lin 401 {IF-2e6} {IF+2e6}\n")
fq = [x.real for x in ngs.vec('frequency')]
hd, hl = ngs.vec(pin('C99', '2')), ngs.vec(pin('C110', '2'))
pk = fq[max(range(len(fq)), key=lambda i: abs(hd[i]))]
Q2_GAIN, LOG_GAIN = abs(at(fq, hd, IF)), abs(at(fq, hl, IF))
print(f'  Q2_G1 → U5 の入力: {db(Q2_GAIN):+.1f} dB（12MHz）。L22・C11 の同調 {pk/1e6:.2f}MHz')
pk2 = fq[max(range(len(fq)), key=lambda i: abs(hl[i]))]
print(f'  Q2_G1 → AD8307 の入力: {db(LOG_GAIN):+.1f} dB（12MHz）。L23・C108 の同調 {pk2/1e6:.2f}MHz')
ngs.run(ifa() + "\n.op\n")
try:
    vs_, ve = ngs.vec(pin('Q2', 'S'))[0], ngs.vec(pin('Q22', 'E'))[0]
    print(f'    動作点（AGC なし・G2 4.0V）: Q2 ソース {vs_:.2f}V（Id 約 {vs_/val("R5")*1e3:.1f}mA）、'
          f'Q22 エミッタ {ve:.2f}V（Ic 約 {ve/(val("R84")+val("R85"))*1e3:.1f}mA）')
except KeyError:
    pass

# レベル配分（AGC なし、水晶フィルタの通過域。NJM2594 の変換利得は 2 個とも 0dB と仮定）
fr, g = ladder()
XF = math.sqrt(max(g))            # 等しい終端なので電圧比 = 電力比の平方根
import af                          # DET_EF → スピーカー（音量 0.9、1kHz）を af.py の回路で計算
ngs.run(af.rx_circuit(0.9)); _f = [x.real for x in ngs.vec('frequency')]
_h = [a / b for a, b in zip(ngs.vec(pin('J6', '1')), ngs.vec(pin('R79', '1')))]
AF_GAIN = abs(at(_f, _h, 1000))
total = BPF_GAIN * RFA_GAIN * IFA_GAIN * XF * Q2_GAIN
print()
print('### レベル配分（AGC なし、NJM2594 の変換利得 0dB と仮定、S9 = −73dBm・50µV/50Ω）')
print(f'  アンテナ端 → U5 の入力（= 積検波の出力）: {db(total):+.1f} dB'
      f'（BPF {db(BPF_GAIN):+.1f}、RF {db(RFA_GAIN):+.1f}、混合後 {db(IFA_GAIN):+.1f}、水晶 {db(XF):+.1f}、IF {db(Q2_GAIN):+.1f}）')
dbm = lambda v: 20 * math.log10(v / math.sqrt(50e-3))   # 50Ω 基準の dBm（AD8307 の規格の表し方）
for name, v in [('S1（0.2µV）', 0.2e-6), ('S5（3.2µV）', 3.2e-6), ('S9（50µV）', 50e-6), ('S9+20dB', 500e-6), ('S9+40dB', 5e-3)]:
    vd = v * total; vl = v * BPF_GAIN * RFA_GAIN * IFA_GAIN * XF * LOG_GAIN
    p = min((vd * AF_GAIN) ** 2 / 8, 0.113)      # tran.py: 出力段の最大 約 113mW（歪み 11%）で頭打ち
    print(f'  {name:12}: 積検波の出力 {vd*1e3:8.3f} mVrms → スピーカー {p*1e3:9.4f} mW（音量 0.9）| '
          f'AD8307 の入力 {dbm(vl):+6.1f} dBm（範囲 −75〜+17）')
print('  ※ スピーカーの出力は出力段の最大（約 113mW）で頭打ちとした。段どうしの負荷を含めた値は full.py（アンテナ → スピーカー）を見る')
