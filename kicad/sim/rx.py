"""受信部（V2: 12MHz の SSB シングルスーパー）の計算
  1. 受信の前段（L1 の入力同調 → Q2・Q3 2SK192A-BL カスコード → L2 の出力同調）: 利得・雑音指数・イメージ・半 IF・FM 放送の抑圧、トリマの位置
  2. 12MHz ラダーフィルタ（Y1〜Y6）: 帯域・挿入損失・リップル（水晶の運動定数は仮定）
  3. RF 増幅（Q2・Q3 2SK192A-BL）と混合後増幅（Q5 2SC1815 ＋ L 整合）の利得
  4. IF 増幅（Q6・Q7 2SK192A-BL カスコード）・S メーター増幅（Q8）の利得と、アンテナから積検波・AD8307・スピーカーまでのレベル
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


# 2SK192A-BL（Q2・Q3・Q6・Q7）: Vp −2V・Idss 18mA（dc.py と同じ代表値。Ciss 3.5pF・Crss 0.65pF）
MODRF = """
.model JK192r NJF(VTO=-2 BETA=4.5m LAMBDA=0.01 CGS=2.9p CGD=0.65p RS=5 RD=5)
"""
ZIN_MIX = 600        # NJM2594 の信号入力（約 600Ω と仮定）
TAP19 = 3            # L2 のタップ（+9V 側から数えた巻数。2026-10-31 に 2 → 3）


def front(tc3, tc4, vg2=4.0, tap19=None, c80=None, c82=None):
    """アンテナ（50Ω）→ L1 のタップ（同調 C1・TC1）→ Q2（2SK192A）→ Q3（2SK192A、ゲートは AGC の Q2_G2）
    → L2（同調 C4・TC2、R5 で制動）のタップ → C9 → NJM2594 の入力（600Ω）"""
    e = [tapped('L1', 11, 2), C('C1', c80), f"CTC3 {pin('TC1','1')} 0 {tc3}", f"CD9 {pin('D2','1')} 0 2p",
         f"J20 {pin('Q2','D')} {pin('Q2','G')} {pin('Q2','S')} JK192r", R('R3'), C('C2'),
         f"J25 {pin('Q3','D')} {pin('Q3','G')} {pin('Q3','S')} JK192r", R('R4'), C('C3'),
         tapped('L2', 11, tap19 or TAP19), C('C4', c82), f"CTC4 {pin('TC2','1')} 0 {tc4}", R('R5'), C('C52'), C('C9'),
         f"RMIX {pin('C9','2')} 0 {ZIN_MIX}", f"V9 {node('RX12V')} 0 dc 12", f"VG2 {pin('R4','1')} 0 dc {vg2}",
         f"VS src 0 dc 0 ac 2\nRS src {pin('L1','2')} 50"]
    return 'fe\n' + MODRF + '\n'.join(e) + '\n'


def resp(net, fmin, fmax, pts, out=None):
    ngs.run(net + f".ac lin {pts} {fmin:g} {fmax:g}\n")
    return [x.real for x in ngs.vec('frequency')], ngs.vec(out or pin('C9', '2'))


TMIN, TMAX = 6e-12, 30e-12   # 30pF セラミックトリマの可変範囲（最小 約 6pF）


def tune(**kw):
    """TC1・TC2 を 50.5MHz で混合器の入力が最大になるように合わせる（0.5pF 刻みで全部 → 0.25pF で片側ずつ）"""
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
    ngs.run(net + f".noise v({pin('C9','2')}) VS lin 3 {F0-1e3:g} {F0+1e3:g}\n")
    ngs.cmd('setplot noise1')
    vin = abs(ngs.vec('inoise_spectrum')[1])
    nf = 10 * math.log10((vin / 2) ** 2 / (1.38e-23 * 290 * 50))
    v = abs(resp(net, F0, F0, 1)[1][0])
    return nf, 10 * math.log10((v ** 2 / ZIN_MIX) / (1 / 50))


print('### 受信の前段（L1・L2 T30-6 11T、コア Q 約 120、結合 k 0.9。Q2・Q3 2SK192A-BL カスコード、混合器の入力 600Ω と仮定）')
for t19 in (2, 3):
    a, b = tune(tap19=t19)
    nf, g = nf_gain(front(a, b, tap19=t19))
    print(f'  L2 のタップ {t19}T: TC1 {a*1e12:.2f}pF・TC2 {b*1e12:.2f}pF、電力利得 {g:+.1f}dB、雑音指数 {nf:.2f}dB')
tc3, tc4 = tune()
FE = front(tc3, tc4)
ok = 'トリマの範囲内' if TMIN <= tc3 <= TMAX and TMIN <= tc4 <= TMAX else '範囲外'
print(f'→ タップ {TAP19}T（回路図どおり）で計算: TC1 {tc3*1e12:.2f}pF、TC2 {tc4*1e12:.2f}pF（{ok}）')
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
BPF_GAIN = abs(resp(FE, F0, F0, 1, pin('Q2', 'G'))[1][0])
print(f'  50.5MHz での Q2 のゲート電圧（整合時のアンテナ端 1 に対して）: {BPF_GAIN:.2f} 倍（{db(BPF_GAIN):+.1f} dB）')
for vg2 in (4.0, 2.0, 1.0, 0.0):
    v = abs(resp(front(tc3, tc4, vg2=vg2), F0, F0, 1)[1][0])
    print(f'  AGC（Q3 のゲート {vg2:.1f}V）: 前段の利得 {db(v / ref):+.1f} dB')

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
    for ref in ['C17', 'C18', 'C19', 'C20', 'C21']:
        e.append(C(ref, caps[ref] if caps else None))
    rt = rterm if rterm else val('R16')
    rsrc = rsrc if rsrc else rt          # 入力側は Q5 の L 整合（C16・L4）で出力側と同じ抵抗に合わせる
    e.append(f"RT {pin('R16','1')} 0 {rt:g}")
    e.append(f"VS src 0 dc 0 ac 2\nRS src {pin('Y1','1')} {rsrc:g}")
    net = 'ladder\n' + '\n'.join(e) + f"\n.ac lin 1601 {f0-8e3:g} {f0+8e3:g}\n"
    ngs.run(net)
    fr, hv = [x.real for x in ngs.vec('frequency')], ngs.vec(pin('R16', '1'))
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
print(f"### 12MHz ラダーフィルタ（水晶の運動定数は仮定: Cm 15fF、Rs 25Ω、C0 4pF。入力・出力とも {COMPS['R16']}Ω（出力 R16、入力は L 整合））")
fr, g = ladder()
summary(fr, g, f"今の定数（{'/'.join(COMPS[r] for r in ['C17','C18','C19','C20','C21'])}、R16 {COMPS['R16']}Ω）")
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
print('### 利得（2SK192A-BL: Vp −2V・Idss 18mA、2SC1815: hFE 200 と仮定）')
# RF 増幅: Q2 のゲート → MIX_IN（1. の前段の計算から、ゲートまでの分を除く）
RFA_GAIN = ref / BPF_GAIN
print(f'  RF 増幅（Q2・Q3 2SK192A-BL カスコード、ゲート → L2 のタップ → NJM2594 の入力 600Ω）: 電圧利得 {db(RFA_GAIN):+.1f} dB（50.5MHz）')
ngs.run(FE + ".op\n")
try:
    vs, vd20, vd25 = ngs.vec(pin('Q2', 'S'))[0], ngs.vec(pin('Q2', 'D'))[0], ngs.vec(pin('Q3', 'D'))[0]
    print(f'    動作点: Q2 ソース {vs:.2f}V → ドレイン電流 約 {vs/val("R3")*1e3:.1f}mA、Q2 の Vds {vd20-vs:.2f}V、Q3 の Vds {vd25-vd20:.2f}V')
except KeyError:
    pass

# 混合後増幅: MIX_EF（NJM2594 のエミッタフォロワ出力、出力抵抗 約 50Ω と仮定）→ Q5 → L 整合 → XF_IN（ラダーの入力 = R16 で終端）
e = [f"VSRC s 0 dc 0 ac 1\nRSRC s {pin('C12','1')} 50", R('R10'), C('C12'), R('R11'), R('R12'),
     BJT('Q5', 'QS'), R('R14'), R('R15'), C('C14'), R('R13'), C('C53'), C('C15'), C('C16'), L('L4', 1.0),
     f"RFILT {pin('L4','2')} 0 {val('R16'):g}", f"V9 {node('RX12V')} 0 dc 12"]
ngs.run('ifa\n' + MOD + '\n'.join(e) + f"\n.ac lin 3 {IF-0.5e6} {IF+0.5e6}\n")
vin = ngs.vec(pin('C12', '1'))[1]
vout = ngs.vec(pin('L4', '2'))[1]
pg = (abs(vout) ** 2 / val('R16')) / (abs(vin) ** 2 / 1000)
print(f"  混合後増幅（Q5 ＋ L 整合 → {COMPS['R16']}Ω）: 電圧利得 {db(vout/vin):+.1f} dB、"
      f'電力利得 {10*math.log10(pg):+.1f} dB（NJM2594 の出力 1kΩ 基準）')
IFA_GAIN = abs(vout / vin)
ngs.run('ifadc\n' + MOD + '\n'.join(e) + "\n.op\n")
try:
    ve, vc = ngs.vec(pin('Q5', 'E'))[0], ngs.vec(pin('Q5', 'C'))[0]
    print(f'    動作点: エミッタ {ve:.2f}V（Ic 約 {ve/(val("R14")+val("R15"))*1e3:.1f}mA）、コレクタ {vc:.2f}V')
except KeyError:
    pass

# ---------------------------------------------------------------- 4. IF 増幅・S メーター・レベル配分
# IF 増幅は 2SK192A-BL のカスコード（Q6 下段・Q7 上段、Q7 のゲートに AGC）
MOD2 = MOD + ".model DG NMOS(LEVEL=1 VTO=-1.5 KP=8.9m LAMBDA=0.02 CGSO=0 CGDO=0)\n"
ZIN_DET = 600      # NJM2594 の信号入力（RF 増幅の計算と同じ仮定）
RIN_LOG = 1.1e3    # AD8307 の入力抵抗（データシート 1.1kΩ‖1.4pF）
QL_IF = 60         # L5・L6（4.7µH のマイクロインダクタ）の 12MHz での Q の目安


def ifa(g2=None):
    """Q6 のゲートに 12MHz の小信号 → Q7 のドレイン（L5・C24 の同調）→ C25 → U2（600Ω）、R21 → Q8 → L6・C31 → AD8307"""
    xl = lambda ref: 2 * math.pi * IF * val(ref)
    e = [f"J6 {pin('Q6','D')} {pin('Q6','G')} {pin('Q6','S')} JK192r", f"J7 {pin('Q7','D')} {pin('Q7','G')} {pin('Q7','S')} JK192r",
         R('R18'), C('C23'), R('R16'), L('L5', xl('L5') / QL_IF), C('C24'), C('C25'), f"RDET {pin('C25','2')} 0 {ZIN_DET}",
         R('R21'), C('C29'), R('R22'), R('R23'), BJT('Q8', 'QS'), R('R24'), R('R25'), C('C30'),
         L('L6', xl('L6') / QL_IF), C('C31'), C('C32'), f"RLOG {pin('C32','2')} 0 {RIN_LOG}\nCLOG {pin('C32','2')} 0 1.4p",
         f"V9 {node('RX12V')} 0 dc 12", f"VG2 {pin('Q7','G')} 0 dc {g2 if g2 is not None else 4.0}",
         f"VG {pin('Q6','G')} 0 dc 0 ac 1"]
    return 'ifa2\n' + MOD2 + '\n'.join(e)


print()
print('### IF 増幅（Q6・Q7 2SK192A-BL カスコード: Vp −2V・Idss 18mA）と S メーター増幅（Q8）。'
      f'L5・L6 の Q {QL_IF}、U2 の入力 {ZIN_DET}Ω、AD8307 の入力 1.1kΩ と仮定')
ngs.run(ifa() + f"\n.ac lin 401 {IF-2e6} {IF+2e6}\n")
fq = [x.real for x in ngs.vec('frequency')]
hd, hl = ngs.vec(pin('C25', '2')), ngs.vec(pin('C32', '2'))
pk = fq[max(range(len(fq)), key=lambda i: abs(hd[i]))]
Q2_GAIN, LOG_GAIN = abs(at(fq, hd, IF)), abs(at(fq, hl, IF))
print(f'  Q6 のゲート → U2 の入力: {db(Q2_GAIN):+.1f} dB（12MHz）。L5・C24 の同調 {pk/1e6:.2f}MHz')
pk2 = fq[max(range(len(fq)), key=lambda i: abs(hl[i]))]
print(f'  Q6 のゲート → AD8307 の入力: {db(LOG_GAIN):+.1f} dB（12MHz）。L6・C31 の同調 {pk2/1e6:.2f}MHz')
ngs.run(ifa() + "\n.op\n")
try:
    vs_, ve = ngs.vec(pin('Q6', 'S'))[0], ngs.vec(pin('Q8', 'E'))[0]
    print(f'    動作点（AGC なし・Q7 ゲート 4.0V）: Q6 ソース {vs_:.2f}V（Id 約 {vs_/val("R18")*1e3:.1f}mA）、'
          f'Q8 エミッタ {ve:.2f}V（Ic 約 {ve/(val("R24")+val("R25"))*1e3:.1f}mA）')
except KeyError:
    pass

# レベル配分（AGC なし、水晶フィルタの通過域。NJM2594 の変換利得は 2 個とも 0dB と仮定）
fr, g = ladder()
XF = math.sqrt(max(g))            # 等しい終端なので電圧比 = 電力比の平方根
import af                          # DET_EF → スピーカー（音量 0.9、1kHz）を af.py の回路で計算
ngs.run(af.rx_circuit(0.9)); _f = [x.real for x in ngs.vec('frequency')]
_h = [a / b for a, b in zip(ngs.vec(pin('J6', '1')), ngs.vec(pin('R27', '1')))]
AF_GAIN = abs(at(_f, _h, 1000))
total = BPF_GAIN * RFA_GAIN * IFA_GAIN * XF * Q2_GAIN
print()
print('### レベル配分（AGC なし、NJM2594 の変換利得 0dB と仮定、S9 = −73dBm・50µV/50Ω）')
print(f'  アンテナ端 → U2 の入力（= 積検波の出力）: {db(total):+.1f} dB'
      f'（BPF {db(BPF_GAIN):+.1f}、RF {db(RFA_GAIN):+.1f}、混合後 {db(IFA_GAIN):+.1f}、水晶 {db(XF):+.1f}、IF {db(Q2_GAIN):+.1f}）')
dbm = lambda v: 20 * math.log10(v / math.sqrt(50e-3))   # 50Ω 基準の dBm（AD8307 の規格の表し方）
for name, v in [('S1（0.2µV）', 0.2e-6), ('S5（3.2µV）', 3.2e-6), ('S9（50µV）', 50e-6), ('S9+20dB', 500e-6), ('S9+40dB', 5e-3)]:
    vd = v * total; vl = v * BPF_GAIN * RFA_GAIN * IFA_GAIN * XF * LOG_GAIN
    p = min((vd * AF_GAIN) ** 2 / 8, 0.113)      # tran.py: 出力段の最大 約 113mW（歪み 11%）で頭打ち
    print(f'  {name:12}: 積検波の出力 {vd*1e3:8.3f} mVrms → スピーカー {p*1e3:9.4f} mW（音量 0.9）| '
          f'AD8307 の入力 {dbm(vl):+6.1f} dBm（範囲 −75〜+17）')
print('  ※ スピーカーの出力は出力段の最大（約 113mW）で頭打ちとした。段どうしの負荷を含めた値は full.py（アンテナ → スピーカー）を見る')
