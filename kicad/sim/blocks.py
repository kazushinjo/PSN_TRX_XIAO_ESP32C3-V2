"""ブロックごとの確認（2026-11-05、V2 Ver 1.1）。ほかのスクリプトで見ていない点を計算する。
  1. 7T50 コイル（L3 第 1 局発、L12〜L14 送信）がコアの調整範囲で目的の周波数に合うか
  2. 第 1 局発バッファ（Q4）: CLK0 → RF PSN の LPF → Q4 → L3 → R8・R9 → U1 のキャリア入力のレベル
  3. BFO: CLK2 → R19・R20 → U2 のキャリア入力のレベル
  4. IF 増幅（L5・C24）と S メーター増幅（L6・C31）の同調と、12MHz に合わせる C
  5. 送信表示: アンテナ側の RF → C103 → D8・D9 → Q20 → LED（J9）が点く出力
  6. 送受切替: PTT → Q1 → K1 のコイル
"""
import math, cmath
import ngs
from gen import *

F_LO, F_TX, IF = 38.5e6, 50.5e6, 12e6
# FCZ 07S50（FCZ 研究所の 07S コイルデータシート、第 6 表）: L1-3 6 回 0.68µH（コアで 0.51〜0.80µH）、L4-6 2 回、Qo 100
L7_NOM, L7_MIN, L7_MAX, N7_TURNS, QO7 = 0.68e-6, 0.51e-6, 0.80e-6, (6, 2), 100
STRAY = 3e-12          # 配線・FET/トランジスタの出力容量などの浮遊容量（仮定）
V_CLK = 4 / math.pi * 1.65   # Si5351 の 3.3Vp-p 矩形波の基本波の振幅（ピーク）
R_CLK = 30             # Si5351 の出力抵抗（仮定、full.py と同じ）
Z_CARR = 1e3           # NJM2594 のキャリア入力の入力抵抗（仮定）
MOD = """
.model J2SK439 NJF(VTO=-1.5 BETA=4.44m LAMBDA=0.01 CGS=5p CGD=1p)
.model JK192r NJF(VTO=-2 BETA=4.5m LAMBDA=0.01 CGS=2.9p CGD=0.65p RS=5 RD=5)
.model QS NPN(IS=2e-14 BF=200 VAF=100 BR=3 RB=50 RC=1 CJE=10p CJC=3.5p TF=0.5n)
.model D1N60 D(IS=1u N=1.1 RS=5 CJO=1p)
.model DLED D(IS=1e-18 N=2 RS=10)
"""


def f_res(l, c): return 1 / (2 * math.pi * math.sqrt(l * c))
def l_for(f, c): return 1 / ((2 * math.pi * f) ** 2 * c)
def db(x): return 20 * math.log10(max(abs(x), 1e-30))


def coil7(ref, lp, f0):
    """7T50: 一次 SA−SB（CT は使わない／GND のときは二分割）、二次 AA−AB（2/6 巻）、結合 0.85、Q 100"""
    sa, sb, ct, aa, ab = (pin(ref, p) for p in ('SA', 'SB', 'CT', 'AA', 'AB'))
    ls = lp * (N7_TURNS[1] / N7_TURNS[0]) ** 2; w = 2 * math.pi * f0
    return (f"L{ref}p {sa} m{ref} {lp:g}\nR{ref}p m{ref} {sb} {w*lp/QO7:g}\n"
            f"L{ref}s {aa} s{ref} {ls:g}\nR{ref}s s{ref} {ab} {w*ls/QO7:g}\nK{ref} L{ref}p L{ref}s 0.85")


def ac_peak(net, out, f0, f1, n=401):
    ngs.run(net + f"\n.ac lin {n} {f0:g} {f1:g}\n")
    fr = [x.real for x in ngs.vec('frequency')]; h = ngs.vec(out)
    i = max(range(len(fr)), key=lambda k: abs(h[k]))
    return fr, h, fr[i]


def at(fr, h, f):
    i = min(range(len(fr)), key=lambda k: abs(fr[k] - f)); return h[i]


print('## ブロックごとの確認（blocks.py）')
# ---------------------------------------------------------------- 1. 7T50 コイルの同調範囲
print('### 7T50 コイル（FCZ 07S50: 0.68µH、コアで 0.51〜0.80µH）の同調。浮遊容量は 3pF と仮定')
for ref, cref, f in [('L3', 'C8', F_LO), ('L12', 'C84', F_TX), ('L13', 'C86', F_TX), ('L14', 'C90', F_TX)]:
    c = val(cref) + STRAY; need = l_for(f, c)
    lo, hi = f_res(L7_MAX, c), f_res(L7_MIN, c)
    ok = L7_MIN <= need <= L7_MAX
    margin = min(need - L7_MIN, L7_MAX - need) / L7_NOM * 100
    print(f'  {ref}（{cref} {val(cref)*1e12:.0f}p）: {f/1e6:.1f}MHz に必要な L {need*1e6:.3f}µH → '
          f'{"範囲内" if ok else "範囲外"}（コアの端まで {margin:+.0f}%）。コアで合う範囲 {lo/1e6:.1f}〜{hi/1e6:.1f}MHz')

# ---------------------------------------------------------------- 2. 第 1 局発バッファ
print('### 第 1 局発バッファ（受信、CLK0 38.5MHz → C74 → L8・C76・C77 → VR3（中点）→ C5 → Q4 → L3 → R8・R9 → C10 → U1）')
print(f'  Si5351 の出力は基本波 {V_CLK:.2f}Vpk・出力抵抗 {R_CLK}Ω、U1 のキャリア入力 {Z_CARR:.0f}Ω と仮定。L3 はコアで 38.5MHz に合わせる')


def lo_net(lp):
    e = [f"VCK s 0 dc 0 ac {V_CLK}\nRCK s {pin('C74','2')} {R_CLK}", C('C74'), C('C76'), L('L8', 0.3), C('C77'),
         POT('VR3', 0.5), R('R63'), C('C80'), f"RMODL {pin('C80','2')} 0 200",
         C('C5'), R('R6'), JFET('Q4', 'J2SK439'), R('R7'), C('C6'), C('C8'), f"CST {pin('L3','SA')} {pin('L3','SB')} {STRAY:g}",
         coil7('L3', lp, F_LO), R('R8'), R('R9'), C('C10'), f"RCAR {pin('C10','2')} 0 {Z_CARR:g}",
         f"V9 {node('RX12V')} 0 dc 12"]
    return 'lo\n' + MOD + '\n'.join(e)


best = None
for k in range(51):
    lp = L7_MIN + (L7_MAX - L7_MIN) * k / 50
    fr, h, pk = ac_peak(lo_net(lp), pin('C10', '2'), 30e6, 47e6, 171)
    if best is None or abs(pk - F_LO) < abs(best[1] - F_LO): best = (lp, pk, abs(at(fr, h, F_LO)))
lp, pk, vc = best
ngs.run(lo_net(lp) + "\n.op\n")
vs, vd = ngs.vec(pin('Q4', 'S'))[0], ngs.vec(pin('Q4', 'D'))[0]
fr, h, _ = ac_peak(lo_net(lp), pin('Q4', 'G'), 30e6, 47e6, 171)
vg = abs(at(fr, h, F_LO))
print(f'  L3 を {lp*1e6:.3f}µH に合わせると同調 {pk/1e6:.2f}MHz: Q4 のゲート {vg/math.sqrt(2)*1e3:.0f}mVrms → '
      f'U1 のキャリア入力 {vc/math.sqrt(2)*1e3:.0f}mVrms（{20*math.log10(vc/math.sqrt(2)/1e-3):.0f}dBmV）')
print(f'    動作点: Q4 ソース {vs:.2f}V（Id 約 {vs/val("R7")*1e3:.1f}mA）、ドレイン {vd:.2f}V')
for f in (38.0e6, 39.0e6):
    print(f'    {f/1e6:.1f}MHz（受信 50.0／51.0MHz）: {db(at(*ac_peak(lo_net(lp), pin("C10","2"), 30e6, 47e6, 171)[:2], f)/vc):+.1f}dB（38.5MHz 比）')

# ---------------------------------------------------------------- 3. BFO
print('### BFO（CLK2 12MHz → R19・R20 → C26 → U2 のキャリア入力）')
e = [f"VCK s 0 dc 0 ac {V_CLK}\nRCK s {pin('R19','1')} {R_CLK}", R('R19'), R('R20'), C('C26'), f"RCAR {pin('C26','2')} 0 {Z_CARR:g}"]
fr, h, _ = ac_peak('bfo\n' + '\n'.join(e), pin('C26', '2'), 11e6, 13e6, 21)
v = abs(at(fr, h, IF))
print(f'  U2 のキャリア入力 {v/math.sqrt(2)*1e3:.0f}mVrms（基本波。矩形波の高調波はそのまま入る）')

# ---------------------------------------------------------------- 4. IF 増幅・S メーターの同調
print('### IF 増幅（Q6・Q7 → L5・C24）と S メーター増幅（Q8 → L6・C31）の同調（L5・L6 は AL0410-4R7K、Q 60 と仮定）')
QL = 60


def ifa_net(c24=None, c31=None, vg2=4.0):
    xl = lambda ref: 2 * math.pi * IF * val(ref)
    e = [f"J6 {pin('Q6','D')} {pin('Q6','G')} {pin('Q6','S')} JK192r", f"J7 {pin('Q7','D')} {pin('Q7','G')} {pin('Q7','S')} JK192r",
         R('R18'), C('C23'), R('R16'), L('L5', xl('L5') / QL), C('C24', c24), C('C25'), f"RDET {pin('C25','2')} 0 600",
         R('R21'), C('C29'), R('R22'), R('R23'), BJT('Q8', 'QS'), R('R24'), R('R25'), C('C30'),
         L('L6', xl('L6') / QL), C('C31', c31), C('C32'), f"RLOG {pin('C32','2')} 0 1.1k\nCLOG {pin('C32','2')} 0 1.4p",
         f"V9 {node('RX12V')} 0 dc 12", f"VG2 {pin('Q7','G')} 0 dc {vg2}", f"VG {pin('Q6','G')} 0 dc 0 ac 1"]
    return 'ifa\n' + MOD + '\n'.join(e)


def if_point(c24=None, c31=None):
    ngs.run(ifa_net(c24, c31) + f"\n.ac lin 801 {6e6:g} {16e6:g}\n")
    fr = [x.real for x in ngs.vec('frequency')]
    hd, hl = ngs.vec(pin('C25', '2')), ngs.vec(pin('C32', '2'))
    pd = fr[max(range(len(fr)), key=lambda k: abs(hd[k]))]; pl = fr[max(range(len(fr)), key=lambda k: abs(hl[k]))]
    return pd, abs(at(fr, hd, IF)), pl, abs(at(fr, hl, IF))


pd, gd, pl, gl = if_point()
print(f'  今の定数（C24 {val("C24")*1e12:.0f}p・C31 {val("C31")*1e12:.0f}p）: L5 の同調 {pd/1e6:.2f}MHz → U2 の入力 {db(gd):+.1f}dB、'
      f'L6 の同調 {pl/1e6:.2f}MHz → AD8307 の入力 {db(gl):+.1f}dB（12MHz、Q6 のゲート基準）')
for c in (39e-12, 47e-12, 56e-12):
    p, g, _, _ = if_point(c24=c)
    print(f'    C24 を {c*1e12:.0f}p にすると: 同調 {p/1e6:.2f}MHz、U2 の入力 {db(g):+.1f}dB')
for c in (10e-12, 15e-12, 18e-12, 22e-12):
    _, _, p, g = if_point(c31=c)
    print(f'    C31 を {c*1e12:.0f}p にすると: 同調 {p/1e6:.2f}MHz、AD8307 の入力 {db(g):+.1f}dB')
ref = None
row = []
for vg2 in (4.0, 2.0, 1.0, 0.5, 0.0):
    ngs.run(ifa_net(vg2=vg2) + f"\n.ac lin 101 {11e6:g} {13e6:g}\n")
    fr = [x.real for x in ngs.vec('frequency')]; g = abs(at(fr, ngs.vec(pin('C25', '2')), IF)); ref = ref or g
    row.append(f"{vg2:.1f}V {db(g/ref):+.1f}dB")
print('  IF 増幅の AGC（Q7 のゲート電圧 → U2 の入力、4.0V 基準）: ' + '、'.join(row))
lmin, lmax = 4.7e-6 * 0.9, 4.7e-6 * 1.1
print(f'  L5・L6 は ±10%（{lmin*1e6:.2f}〜{lmax*1e6:.2f}µH）で同調が約 ±5% 動く（12MHz で ±0.6MHz）。Q 60 の帯域は約 0.2MHz なので、'
      'ばらつきの大きいときは C の差し替えで合わせる（調整 5）')

# ---------------------------------------------------------------- 5. 送信表示
print('### 送信表示（アンテナ側 C102 の RF → C103 5p → D8・D9 の倍電圧検波 → R71 → Q20 → LED、J9）')


def txd_net(vpk):
    e = [f"VRF {pin('C103','1')} 0 SIN(0 {vpk:g} {F_TX:g})", C('C103'),
         f"D8 {pin('D8','A')} {pin('D8','K')} D1N60", f"D9 {pin('D9','A')} {pin('D9','K')} D1N60", R('R71'),
         BJT('Q20', 'QS'), f"DLED {pin('J9','2')} {pin('J9','1')} DLED", R('R72'), f"VTX {node('/TX12V')} 0 dc 12"]
    return 'txd\n' + MOD + '\n'.join(e) + "\n.tran 2n 4u 3u\n"


for pw in (0.0001, 0.0003, 0.001, 0.003, 0.01, 0.1, 1.0, 2.0):
    vpk = math.sqrt(2 * 50 * pw)
    ngs.run(txd_net(vpk))
    vb = ngs.vec(pin('Q20', 'B')); vc = ngs.vec(pin('Q20', 'C'))
    ib = sum(vb) / len(vb); il = (12 - 2.0 - sum(vc) / len(vc)) / val('R72')
    print(f'  出力 {pw*1e3:7.1f}mW（{vpk:5.2f}Vpk）: Q20 のベース {ib:.2f}V → LED 電流 約 {max(il,0)*1e3:.1f}mA')

# ---------------------------------------------------------------- 6. 送受切替
print('### 送受切替（PTT → R1 → Q1（2SA1015）→ K1 のコイル、G5V-2 DC12 のコイル 12V・約 41.7mA と仮定）')
vs = 12.0; ib = (vs - 0.75) / val('R1') - 0.75 / val('R2'); ic = vs / 288
print(f'  PTT を GND に落としたとき: Q1 のベース電流 約 {ib*1e3:.2f}mA、コイル電流 {ic*1e3:.1f}mA → 必要な hFE {ic/ib:.0f}（2SA1015-GR は 200〜400 で十分に飽和）')
print(f'  PTT を開放したとき: R2（{val("R2")/1e3:.0f}kΩ）でベースがエミッタと同電位 → Q1 はオフ。D1（1N4001）がコイルの逆起電力を吸収')
