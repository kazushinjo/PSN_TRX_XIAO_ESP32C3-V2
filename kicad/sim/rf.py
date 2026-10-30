"""PA 出力 LPF・PA 入力・RFC1・DC-DC 入力フィルタ・AGC"""
import ngs, math, cmath, itertools, re
from gen import *

F0 = 50.5e6
def at(f, h, x):
    i = min(range(len(f)), key=lambda k: abs(f[k] - x)); return h[i]

AL = {'T-50-10': 3.1e-9, 'T-30-6': 3.6e-9}   # nH/T² 相当（31µH/100T、36µH/100T）
QL = {'T-50-10': 150, 'T-30-6': 120}   # 50MHz（T-50-10）・100MHz（T-30-6）付近の無負荷 Q の目安

def lturns(ref, k=1.0, fq=50.5e6):
    """値 'T-50-10 9T/0.6mm' から L とコアを求める（k はばらつき、損失は周波数 fq での Q から）"""
    m = re.match(r'(T-\d+-\d+)\s+(\d+)T', COMPS[ref])
    core, n = m.group(1), int(m.group(2))
    lv = AL[core] * n * n * k
    return L(ref, 2 * math.pi * fq * lv / QL[core], lv)

def lpf(k, coss, tc1, kt=1.0, tc2=6.5e-12, src=50, fr=50.5e6):
    """Q3 ドレイン（50Ω 源、Coss・RFC1 並列）→ C7 → C6 → L3 → [C4+TC1] → L16 → [C71、トラップ L17+(C72∥TC2)] → L1 → [C1、C2] → 50Ω"""
    used['TC1'] = tc1; used['TC2'] = tc2
    e = [C('C7'), C('C6'), lturns('L3', k), C('C4'), f"CTC1 {pin('TC1','1')} 0 {tc1}",
         lturns('L16', k), C('C71'), lturns('L17', kt, 101e6), C('C72'), f"CTC2 {pin('TC2','1')} 0 {tc2}",
         lturns('L1', k), C('C1'),
         # C2（5p）は TX 検出 D2/D3 へ。検出側を 1k で代用
         C('C2'), f"RDET {pin('C2','2')} 0 1k",
         f"COSS {pin('C7','1')} 0 {coss}",
         f"LRFC {pin('C7','1')} rfc 10u\nRRFC rfc 0 0.3\nCRFC {pin('C7','1')} 0 3p",
         f"RLOAD {pin('C1','1')} 0 50"]
    return f"""lpf
VS src 0 AC 2
RS src {pin('C7','1')} {src}
""" + '\n'.join(e) + f"\n.ac lin 1 {fr} {fr}\n"

def lpf_point(fr, *a, **kw):
    ngs.run(lpf(*a, fr=fr, **kw))
    vin = ngs.vec(pin('C7', '1'))[0]; vo = ngs.vec(pin('C1', '1'))[0]
    zin = 50 * vin / (2 - vin)
    return 20 * math.log10(abs(vo)), -20 * math.log10(max(abs((zin - 50) / (zin + 50)), 1e-6))

def pa_lpf():
    print('PA 出力 LPF（7 素子＋2 倍波トラップ、50Ω 源・50Ω 負荷、出力は整合時 0dB 基準）')
    print('  L1/L3/L16 のばらつき・Coss・トラップ L のばらつきごとに、TC2 を 2 倍波最小、TC1 を反射減衰量最大に合わせた結果')
    print(' L×   Coss | L17×  | TC2[pF] | TC1[pF] | 反射減衰量 | 挿入損失 | 2倍波 | 3倍波 | 4倍波 | TC2 未調整(6.5p)の2倍波')
    for k, coss, kt in itertools.product([0.93, 1.0, 1.07], [18e-12, 25e-12], [0.93, 1.07]):
        tc2 = min([x * 0.25e-12 for x in range(12, 41)], key=lambda c: lpf_point(101e6, k, coss, 15e-12, kt, c)[0])
        tc1 = max([x * 1e-12 for x in range(5, 31)], key=lambda c: lpf_point(50.5e6, k, coss, c, kt, tc2)[1])
        g0, rl = lpf_point(50.5e6, k, coss, tc1, kt, tc2); il = -g0
        h = [lpf_point(50.5e6 * m, k, coss, tc1, kt, tc2)[0] + il for m in (2, 3, 4)]
        hu = lpf_point(101e6, k, coss, tc1, kt, 6.5e-12)[0] + il
        print(f" {k:.2f} {coss*1e12:3.0f}p | {kt:.2f}  |  {tc2*1e12:5.2f}  |  {tc1*1e12:4.0f}   |   {rl:5.1f}    |  {il:5.2f}   | {h[0]:6.1f} | {h[1]:6.1f} | {h[2]:6.1f} | {hu:6.1f}")

def pa_input():
    """L6 リンク（50Ω と仮定）→ C15 → L5 → ゲート（C14、R7→VR2 ワイパー、Ciss/Crss/gm）"""
    print('PA 入力: 50Ω 源から見た不整合損失（VR2 は Idq に合わせた位置を 0.3〜0.7 で振る）')
    for gm, pos, vs in itertools.product([0.3, 1.0], [0.3, 0.7], [12]):
        net = f"""pain
VS src 0 AC 2
RS src {pin('C15','1')} 50
{C('C15')}
{L('L5', 0.05)}
{C('C14')}
{R('R7')}
{POT('VR2', pos)}
{R('R6')}
VTX n__TX12V 0 DC {vs}
CGS {pin('L5','2')} 0 23.7p
CGD {pin('L5','2')} d 1.3p
GM d 0 {pin('L5','2')} 0 {gm}
RD d 0 25
CDS d 0 18p
.ac lin 1 {F0} {F0}
"""
        ngs.run(net)
        vin = ngs.vec(pin('C15', '1'))[0]; zin = 50 * vin / (2 - vin); g = abs((zin - 50) / (zin + 50))
        print(f"  gm {gm} S, VR2 {pos}: Zin {zin.real:6.1f}{zin.imag:+7.1f}j Ω  不整合損失 {-10*math.log10(1-g*g):4.1f} dB")
    vmax = {v: v * 500 / (val('R6') + 500) for v in (11, 12, 13.8)}
    print('  ゲート電圧の上限（VR2 最大）:', ', '.join(f"{v}V→{x:.2f}V" for v, x in vmax.items()))

def rfc():
    f = 51e6; l = 10e-6; c = 1 / ((2 * math.pi * 29e6) ** 2 * l)
    z = 1 / (1 / (1j * 2 * math.pi * f * l) + 1j * 2 * math.pi * f * c)
    print(f"RFC1 10µH（自己共振 29MHz、分布容量 {c*1e12:.1f}pF）: 51MHz で {z.imag:+.0f}j Ω（{abs(z):.0f}Ω、容量性）")

def dcdc():
    print('DC-DC 入力フィルタ L12/C52: R-78E の入力側から見たインピーダンス')
    for rsrc, esr in [(0.05, 0.3), (0.1, 0.1), (0.2, 0.5)]:
        net = f"""dcdc
VS src 0 DC 12
RSRC src n__PWR_IN {rsrc}
{L('L12', 0.05)}
CC52 {pin('C52','1')} cesr {val('C52'):g}
RESR cesr 0 {esr}
IT 0 n__DCDC_IN DC 0 AC 1
.ac dec 100 1k 100k
"""
        ngs.run(net); f = [x.real for x in ngs.vec('frequency')]; z = [abs(x) for x in ngs.vec('n__DCDC_IN')]
        k = max(range(len(z)), key=lambda i: z[i])
        print(f"  電源抵抗 {rsrc}Ω・C52 ESR {esr}Ω: ピーク {z[k]:.2f}Ω @ {f[k]/1e3:.1f}kHz")
    for pload in [1.5, 2.5]:
        print(f"  R-78E の負性入力抵抗（入力電力 {pload}W、12V）: {-(12**2)/pload:.0f}Ω")

def agc():
    print('AGC（Q17）: AGC_PWM の平均電圧（12 ビット PWM のデューティ）→ Q2_G2 [V]（J4 は 10kΩ・最大と仮定）')
    for hfe in (200, 400):
      row = []
      for vpwm in [0, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 1.13]:
        net = f""".param hfe1815={hfe} hfe1923=100 hfe2120=180 vp310=-4 b310=2.5m
agc
{MODELS}
V9 n__9V 0 DC 12
VAGC n__AGC_PWM 0 DC {vpwm}
{R('R4')}
RJ4a n_Net__J4_Pin_1_ n__Q2_G2 1m
RJ4b n__Q2_G2 0 10k
{BJT('Q17','Q2SC1815')}
{R('R42')}
{R('R44')}
.op
"""
        ngs.run('agc\n' + net.replace('agc\n', ''))
        row.append(f"{vpwm:.2f}V({round(vpwm/3.3*4096)})→{ngs.vec('n__Q2_G2')[0]:.2f}")
      print(f"  hFE {hfe}: " + ' '.join(row))

if __name__ == '__main__':
    pa_lpf(); pa_input(); rfc(); dcdc(); agc()
    print('定数:', ' '.join(f"{k}={v}" for k, v in sorted(used.items())))
