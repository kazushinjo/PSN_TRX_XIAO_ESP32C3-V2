"""送信 AF 系（マイク→U3 の ADC、U3 の PDM 出力→変調器入力）と受信 AF 系（積検波 U5 の出力→スピーカー）
（Ver 2.0: I/Q の 90° 移相は U3 のファームウェアで行うので、ここではアナログ部分だけを計算する）"""
import ngs, math, cmath, itertools
from gen import *

HDR = """.options rshunt=1e9
.param hfe1815=300 hfe1923=100 hfe2120=180 vp310=-4 b310=2.5m
"""

def mic_circuit(rl15, vol=5e3, vs=12, imic=1.0):
    """マイク → Q18 → L15 LPF（R58 で終端）→ C60 → IC2A（非反転、約 21 倍）→ C73・R59 → AF_ADC（U3 の A2）
    AF_ADC には R38/R39 のバイアスがつながる（V2 で受信音の R37・C50 は外した）"""
    e = [BJT('Q18', 'Q2SC1815'), R('R46'), R('R47'), R('R49'), R('R51'), R('R52'), C('C67'), C('C68'),
         C('C66'), C('C65'), L('L15', rl15), C('C63'), C('C62'), R('R58'), C('C60'), R('R41'), R('R43'),
         OPA('A'), R('R40'), C('C54'), R('R36'), C('C73'), R('R59'),
         R('R38'), R('R39')]
    return f"""mic
{HDR}{MODELS}
{OPAMP}
VTX n__TX12V 0 DC {vs}
V5 n__5V 0 DC 5
V33 n__XIAO_3V3 0 DC 3.3
IMIC {pin('J10','2')} 0 DC 0.5m AC {imic}
""" + '\n'.join(e) + "\n.ac dec 40 50 20k\n"

def out_circuit(rload, vs=12, dI=1.0, dQ=1.0):
    """U3 の PDM 出力（D10=I、D8=Q、平均 1.65V）→ 2 段 RC → C49/C48 → Q15/Q16 → L11/L10 → 変調器
    dI・dQ は RC の定数の倍率（部品のばらつきの確認用）"""
    e = [f"VI {pin('R61','2')} 0 DC 1.65 AC 1", f"VQ {pin('R63','2')} 0 DC 1.65 AC 1",
         R('R61', 3.3e3*dI), C('C75', 3.3e-9*dI), R('R62', 3.3e3*dI), C('C76', 3.3e-9*dI), C('C49'),
         R('R63', 3.3e3*dQ), C('C77', 3.3e-9*dQ), R('R64', 3.3e3*dQ), C('C78', 3.3e-9*dQ), C('C48'),
         BJT('Q16', 'Q2SC1815'), R('R31'), R('R32'), R('R33'), C('C43'), C('C35'), L('L10', 20),
         BJT('Q15', 'Q2SC1815'), R('R28'), R('R29'), R('R30'), C('C44'), C('C38'), L('L11', 20),
         C('C39'), R('R34'), C('C40'), R('R35'),
         f"RLI {pin('L11','1')} 0 {rload}", f"RLQ {pin('L10','1')} 0 {rload}"]
    return f"""out
{HDR}{MODELS}
VTX n__TX12V 0 DC {vs}
""" + '\n'.join(e) + "\n.ac dec 60 50 400k\n"

def at(freqs, h, f):
    i = min(range(len(freqs)), key=lambda k: abs(freqs[k] - f)); return h[i]

def sup(pe, ae):
    """位相誤差 pe[deg]・振幅差 ae[dB] を含めた逆側帯波抑圧 [dB]"""
    k = 10 ** (ae / 20); th = math.radians(pe)
    return 10 * math.log10((1 + 2*k*math.cos(th) + k*k) / (1 - 2*k*math.cos(th) + k*k))

def tx():
    pts = [300, 500, 1000, 2000, 2700, 4000, 10000]
    print('マイク → IC2A → AF_ADC（U3 の A2）の 1kHz 基準の振幅 [dB]、1 Pa（エレクトレット −42 dBV/Pa ≒ 3.6 µA）での電圧')
    for rl15 in (30, 90):
        ngs.run(mic_circuit(rl15, imic=3.6e-6)); f = [x.real for x in ngs.vec('frequency')]
        h = ngs.vec('n__AF_ADC'); o = ngs.vec(pin('IC2', '1')); ref = abs(at(f, h, 1000))
        print(f"  RL15 {rl15:3}Ω: " + ' '.join(f"{p}Hz {20*math.log10(abs(at(f,h,p))/ref):+.1f}" for p in pts)
              + f" | 1 kHz・1 Pa で IC2A 出力 {abs(at(f,o,1000))*1e3:.0f} mVrms、AF_ADC {ref*1e3:.0f} mVrms")
    print('U3 の PDM 出力 → 変調器入力（I=L11 側、Q=L10 側）の 1kHz 基準の振幅 [dB]、PDM・PWM の周波数での減衰')
    for rload in (200, 1000):
        ngs.run(out_circuit(rload)); f = [x.real for x in ngs.vec('frequency')]
        hi = ngs.vec(pin('L11', '1')); hq = ngs.vec(pin('L10', '1')); ref = abs(at(f, hi, 1000))
        pe = max(abs(abs(math.degrees(cmath.phase(hi[k] / hq[k]))) - 0) for k, fr in enumerate(f) if 300 <= fr <= 2700)
        ae = max(abs(20*math.log10(abs(hi[k]) / abs(hq[k]))) for k, fr in enumerate(f) if 300 <= fr <= 2700)
        print(f"  負荷 {rload:4}Ω: " + ' '.join(f"{p}Hz {20*math.log10(abs(at(f,hi,p))/ref):+.1f}" for p in pts)
              + f" | 78kHz {20*math.log10(abs(at(f,hi,78125))/ref):+.1f} 156kHz {20*math.log10(abs(at(f,hi,156250))/ref):+.1f}"
              + f" | I/Q の差 位相 {pe:.2f}° 振幅 {ae:.2f}dB")
    # RC の定数が I と Q で 3% ずれた場合（R±1%・C±2% の最悪程度）。ファームウェアの I/Q 補正前
    ngs.run(out_circuit(500, dI=1.03, dQ=0.97)); f = [x.real for x in ngs.vec('frequency')]
    hi = ngs.vec(pin('L11', '1')); hq = ngs.vec(pin('L10', '1'))
    pe = max(abs(math.degrees(cmath.phase(hi[k] / hq[k]))) for k, fr in enumerate(f) if 300 <= fr <= 2700)
    ae = max(abs(20*math.log10(abs(hi[k]) / abs(hq[k]))) for k, fr in enumerate(f) if 300 <= fr <= 2700)
    print(f"  RC が I +3%・Q −3% ずれた場合（補正なし）: 位相差 最大 {pe:.2f}° 振幅差 最大 {ae:.2f}dB → 抑圧の上限 {sup(pe, ae):.1f}dB")
    # ファームウェアの I/Q 補正（遅延差と利得差）を当てはめた後
    pts = [(fr, hi[k] / hq[k]) for k, fr in enumerate(f) if 300 <= fr <= 2700]
    tau = -sum(fr * cmath.phase(r) for fr, r in pts) / sum(fr * fr for fr, _ in pts) / (2 * math.pi)
    g = math.exp(sum(math.log(abs(r)) for _, r in pts) / len(pts))
    cor = min(sup(abs(math.degrees(cmath.phase(r / (g * cmath.exp(-2j * math.pi * fr * tau))))),
                  abs(20 * math.log10(abs(r / (g * cmath.exp(-2j * math.pi * fr * tau)))))) for fr, r in pts)
    print(f"  同上、ファームウェアで遅延差 {tau*1e6:.2f}µs・利得差 {20*math.log10(g):.2f}dB を補正した後: 抑圧 最悪 {cor:.1f}dB")

def rx_circuit(vol, vs=12):
    e = [R('R79'), C('C117'), R('R96'), BJT('Q23', 'Q2SC1815'), R('R97'), R('R98'), R('R80'), C('C103'),
         C('C22'), BJT('Q9', 'Q2SC1815'), R('R15'), R('R17'), C('C26'), C('C28'),
         R('R18'), C('C32'), BJT('Q12', 'Q2SC1815'), R('R20'), R('R21'), C('C34'), R('R23'),
         C('C37'), R('R24'), f"RJ5a n_Net__J5_Pin_1_ n_Net__J5_Pin_2_ {10e3*(1-vol)+1e-3}", f"RJ5b n_Net__J5_Pin_2_ 0 {10e3*vol+1e-3}",
         C('C41'), C('C42'), BJT('Q13', 'Q2SC2120'), BJT('Q14', 'Q2SA950'), R('R25'), R('R26'), R('R27'), C('C45'),
         C('C46'), f"RSP {pin('J6', '1')} 0 8", C('C27'), C('C47')]
    return f"""rx
.param hfe1815=300 hfe1923=100 hfe2120=180 vp310=-4 b310=2.5m
{MODELS}
V9 n__9V 0 DC {vs}
V33 n__XIAO_3V3 0 DC 3.3
VDET {pin('R79','1')} 0 DC 3.3 AC 1
""" + '\n'.join(e) + "\n.ac dec 40 50 20k\n"

def rx():
    pts = [300, 1000, 2700, 4000, 10000]
    print('受信 AF 系: 積検波 U5 の出力（DET_EF）→ Q23（前置増幅）→ スピーカー（8Ω）の 1kHz 基準 [dB]、音量つまみ 10kΩ の位置別')
    for vol in [0.2, 0.5, 0.9]:
        ngs.run(rx_circuit(vol)); f = [x.real for x in ngs.vec('frequency')]
        h = [a / b for a, b in zip(ngs.vec(pin('J6', '1')), ngs.vec(pin('R79', '1')))]
        ref = abs(at(f, h, 1000))
        print(f"  音量 {vol:.1f}: " + ' '.join(f"{p}Hz {20*math.log10(abs(at(f,h,p))/ref):+.1f}" for p in pts) + f"  (1kHz 利得 {20*math.log10(ref):.1f} dB)")

if __name__ == '__main__':
    tx(); rx()
    print('定数:', ' '.join(f"{k}={v}" for k, v in sorted(used.items())))
