"""過渡解析: 大信号の歪み・飽和、PA の高調波、電源投入・送信開始の過渡
（af.py・rf.py の回路をそのまま使い、信号源と解析だけを過渡解析に替える）"""
import ngs, math, re
from gen import *
from af import mic_circuit, out_circuit, rx_circuit
from rf import lpf

# NJM2904（5V 単電源）の出力振幅の制限: 下 0.03V、上 V+ −1.4V（データシートの VOH 下限付近）
OAR = """
.subckt OAR inp inn out
Rin inp inn 1e8
E1 a 0 inp inn 1e5
R1 a b 1k
C1 b 0 26.5u
B2 c 0 V = min(max(V(b), 0.03), 3.6)
R2 c out 50
.ends
"""

def tran(net, tstep, tstop, tstart=0, uic=False):
    net = re.sub(r'\n\.(ac|op)\b.*', '', net)
    out = ngs.run(net + f"\n.options reltol=1e-4 abstol=1e-12 vntol=1e-7\n.tran {tstep:g} {tstop:g} {tstart:g} {tstep:g}{' uic' if uic else ''}\n")
    if 'rror' in out and ('singular' in out.lower() or 'abort' in out.lower()): print(out[-800:])
    return out

def lin(tstep):
    ngs.cmd(f'linearize'); return [x for x in ngs.vec('time')]

def harm(t, v, f0, ncyc, nh=5):
    """最後の ncyc 周期で f0 の 1〜nh 倍の振幅（ピーク値）を DFT で求める"""
    T = ncyc / f0; idx = [i for i, x in enumerate(t) if x >= t[-1] - T]
    t0 = [t[i] for i in idx]; x0 = [v[i] for i in idx]; n = len(x0)
    res = []
    for k in range(1, nh + 1):
        w = 2 * math.pi * k * f0
        re_ = sum(x * math.cos(w * tt) for x, tt in zip(x0, t0)); im = sum(x * math.sin(w * tt) for x, tt in zip(x0, t0))
        res.append(2 * math.hypot(re_, im) / n)
    return res

def thd(h): return 100 * math.sqrt(sum(x * x for x in h[1:])) / h[0]

# ---------------------------------------------------------------- 受信 AF 出力段
def rx_power():
    print('受信 AF 系の最大出力（1 kHz、スピーカー 8Ω、音量 0.9、電源 12V）: 積検波 U5 の出力（DET_EF）の振幅を上げていったときの出力と歪み率')
    row = []
    for ua in [2, 5, 10, 20, 40, 80, 160]:   # mVpk
        net = rx_circuit(0.9).replace(f"VDET {pin('R79','1')} 0 DC 3.3 AC 1", f"VDET {pin('R79','1')} 0 DC 3.3 SIN(3.3 {ua*1e-3} 1k)")
        tran(net, 5e-6, 60e-3, 40e-3); t = lin(5e-6)
        h = harm(t, ngs.vec(pin('J6', '1')), 1e3, 20)
        p = (h[0] / math.sqrt(2)) ** 2 / 8
        row.append((ua, p * 1e3, thd(h)))
    for ua, p, d in row: print(f"  入力 {ua:4} mVpk → 出力 {p:7.2f} mW  歪み率 {d:5.1f} %")
    for lim in (1, 3, 10):
        ok = [p for _, p, d in row if d <= lim]
        print(f"  歪み率 {lim}% 以下の最大出力: {max(ok) if ok else 0:.1f} mW")

# ---------------------------------------------------------------- マイクアンプ
def mic_level():
    print('マイク入力の大きさと飽和（1 kHz、L15 直流抵抗 60Ω、音量つまみ 5kΩ、電源 12V）。'
          'IC2A は NJM2904 の出力範囲 0.03〜3.6V で制限。U3 の ADC（減衰 12dB）は約 0〜2.5V、中点 1.65V')
    for pa in [0.3, 1, 2, 3, 5, 10]:
        ipk = 3.6e-6 * math.sqrt(2) * pa
        net = mic_circuit(60).replace(' OA\n', ' OAR\n').replace('.subckt OA ', OAR + '\n.subckt OA ')
        net = re.sub(r"(IMIC \S+ 0 DC 0.5m) AC \S+", rf"\1 SIN(0 {ipk} 1k)", net)
        tran(net, 5e-6, 0.6, 0.56); t = lin(5e-6)
        vo = ngs.vec(pin('IC2', '1')); va = ngs.vec('n__AF_ADC'); vq = ngs.vec(pin('Q18', 'C'))
        ho, ha = harm(t, vo, 1e3, 20), harm(t, va, 1e3, 20)
        n0 = [i for i, x in enumerate(t) if x >= t[-1] - 20e-3]
        print(f"  {pa:4} Pa（{94+20*math.log10(pa):5.1f} dB SPL）: Q18 コレクタ {min(vq[i] for i in n0):5.2f}〜{max(vq[i] for i in n0):5.2f} V | "
              f"IC2A 出力 {min(vo[i] for i in n0):4.2f}〜{max(vo[i] for i in n0):4.2f} V 歪み {thd(ho):5.1f} % | "
              f"AF_ADC {min(va[i] for i in n0):4.2f}〜{max(va[i] for i in n0):4.2f} V 歪み {thd(ha):5.1f} %")

# ---------------------------------------------------------------- 変調器ドライブ
def driver_level():
    print('U3 の PDM 出力（平均値）の振幅と変調器入力の歪み（1 kHz、I 側 = Q15、電源 12V）。フルスケール ±1.65V、'
          'FIR の通過域利得 1、出力レベル（out）初期値 10 %')
    print('  FIR 入力のレベル: マイク 1 Pa・mic 0dB で約 −19 dBFS、試験トーン −12 dBFS（ALC で効き始めまで絞られる）、ALC の効き始め −20 dBFS（2026-10-28 から。それまでは −6 dBFS）')
    levels = [(-30, 10), (-23, 10), (-20, 10), (-19, 10), (-12, 10), (-6, 10)]
    for rload in (200, 1000):
        row = []
        for db, pct in levels:
            a = 1.65 * 10 ** (db / 20) * pct / 100
            net = out_circuit(rload).replace(f"VI {pin('R61','2')} 0 DC 1.65 AC 1", f"VI {pin('R61','2')} 0 DC 1.65 SIN(1.65 {a} 1k)")
            tran(net, 5e-6, 0.25, 0.23); t = lin(5e-6)
            h = harm(t, ngs.vec(pin('L11', '1')), 1e3, 20)
            row.append(f"{db:+d}dBFS・{pct}%(±{a*1e3:.0f}mV)→{h[0]*1e3:4.0f}mVpk {thd(h):4.1f}%")
        print(f"  負荷 {rload:4}Ω: " + '  '.join(row))
    print('  （参考）PDM の振幅を大きくした場合')
    for rload in (200, 1000):
        row = []
        for a in [0.2, 0.83, 1.65]:
            net = out_circuit(rload).replace(f"VI {pin('R61','2')} 0 DC 1.65 AC 1", f"VI {pin('R61','2')} 0 DC 1.65 SIN(1.65 {a} 1k)")
            tran(net, 5e-6, 0.25, 0.23); t = lin(5e-6)
            h = harm(t, ngs.vec(pin('L11', '1')), 1e3, 20); hc = harm(t, ngs.vec(pin('Q15', 'C')), 1e3, 20)
            row.append(f"±{a:.2f}V→{h[0]*1e3:5.0f}mVpk {thd(h):4.1f}%(Q15C {thd(hc):4.1f}%)")
        print(f"  負荷 {rload:4}Ω: " + '  '.join(row))

# ---------------------------------------------------------------- PA 大信号
PA_MODEL = ".model RD06 NMOS(LEVEL=1 VTO=3.0 KP=1.2 LAMBDA=0.01 RD=0.25 RS=0.05)"
def pa_point(vgpk, idq, vs=12.0):
    vg0 = 3.0 + math.sqrt(2 * idq / 1.2)
    net = lpf(1.0, 18e-12, 11e-12, 1.0, 6.5e-12)
    net = net.replace('VS src 0 AC 2\n', '').replace(f"RS src {pin('C7','1')} 50\n", '')
    net = net.replace('RRFC rfc 0 0.3', 'RRFC rfc n_sup 0.3')
    net += f"""
{PA_MODEL}
VTX n_sup 0 DC {vs}
VG g 0 DC {vg0} SIN({vg0} {vgpk} 50.5e6)
M3 {pin('C7','1')} g 0 0 RD06 W=1 L=1
"""
    tran(net, 0.05e-9, 3.0e-6, 2.0e-6)
    t = lin(0.05e-9)
    vl = ngs.vec(pin('C1', '1')); vd = ngs.vec(pin('C7', '1')); isup = ngs.vec('i(vtx)')
    hl = harm(t, vl, 50.5e6, 50, 4); hd = harm(t, vd, 50.5e6, 50, 4)
    pout = (hl[0] / math.sqrt(2)) ** 2 / 50
    pin_dc = -vs * sum(isup) / len(isup)
    return pout, [20 * math.log10(max(x, 1e-12) / hl[0]) for x in hl[1:]], [20 * math.log10(max(x, 1e-12) / hd[0]) for x in hd[1:]], max(vd), pin_dc

def pa():
    print('PA 大信号（RD06HVF1 を 2 乗特性の簡易モデル Vth 3.0V で近似、ゲートを 50.5MHz の正弦波で直接駆動、'
          'LPF は L×1.00・Coss 18p・TC1 11p・TC2 6.5p、50Ω 負荷、電源 12V）')
    print('  Idq  | ゲート振幅 | 出力 [W] | 効率 | ドレイン最大 | ドレインの 2/3 倍波 [dBc] | 出力の 2/3/4 倍波 [dBc]')
    for idq in (0.05, 0.2):
        for vg in (0.5, 1.0, 1.5, 2.5):
            po, hl, hd, vmax, pdc = pa_point(vg, idq)
            print(f"  {idq*1e3:3.0f}mA |   {vg:3.1f} V    |  {po:5.2f}  | {100*po/pdc:3.0f}% |   {vmax:5.1f} V   |"
                  f"      {hd[0]:6.1f} / {hd[1]:6.1f}       |  {hl[0]:6.1f} / {hl[1]:6.1f} / {hl[2]:6.1f}")

# ---------------------------------------------------------------- 電源投入・送信開始
def power_on():
    print('電源投入（+9V が 1ms で 0→12V）時のスピーカー（8Ω）のポップ音: 音量 0.5、電源 12V')
    net = rx_circuit(0.5).replace('V9 n__9V 0 DC 12', 'V9 n__9V 0 PWL(0 0 1m 12)')
    tran(net, 10e-6, 1.0, 0, uic=True); t = ngs.vec('time'); v = ngs.vec(pin('J6', '1'))
    k = max(range(len(v)), key=lambda i: abs(v[i]))
    print(f"  スピーカー端の最大 {v[k]:+.2f} V（{t[k]*1e3:.0f} ms）、瞬間電力 {v[k]**2/8*1e3:.0f} mW。"
          f"0.1V 以下に戻るまで {next((t[i] for i in range(len(v)-1, -1, -1) if abs(v[i]) > 0.1), 0)*1e3:.0f} ms")

def tx_start():
    print('送信開始（リレーで TX12V が 0→12V、10µs）: 変調器入力の過渡（I 側）。'
          'U3 は同時に PDM の平均を 64ms かけて中点 1.65V へ上げる（I は AGC のデューティ 0.6V から、Q は 0V から）。入力は 0.45 秒無音にする（MUTE_N）')
    for rload in (200, 1000):
        net = out_circuit(rload).replace('VTX n__TX12V 0 DC 12', 'VTX n__TX12V 0 PWL(0 0 10u 12)')
        net = net.replace(f"VI {pin('R61','2')} 0 DC 1.65 AC 1", f"VI {pin('R61','2')} 0 PWL(0 0.6 64m 1.65)")
        net = net.replace(f"VQ {pin('R63','2')} 0 DC 1.65 AC 1", f"VQ {pin('R63','2')} 0 PWL(0 0 64m 1.65)")
        tran(net, 10e-6, 0.6, 0); t = ngs.vec('time')
        for nm, nd, q in (('I', pin('L11', '1'), 'Q15'), ('Q', pin('L10', '1'), 'Q16')):
            v = ngs.vec(nd); vc = ngs.vec(pin(q, 'C'))
            k = max(range(len(v)), key=lambda i: abs(v[i]))
            st = next((t[i] for i in range(len(v) - 1, -1, -1) if abs(v[i]) > 0.01), 0)
            print(f"  負荷 {rload:4}Ω {nm}: 変調器入力の最大 {v[k]*1e3:+6.0f} mV（{t[k]*1e3:5.1f} ms）、±10mV 以内になるまで {st*1e3:4.0f} ms、"
                  f"{q} コレクタ {vc[-1]:.2f} V（定常）")
    print('送信開始時のマイク系: AF_ADC（U3 の A2）の過渡（マイク無音、L15 60Ω）')
    net = mic_circuit(60).replace(' OA\n', ' OAR\n').replace('.subckt OA ', OAR + '\n.subckt OA ')
    net = net.replace('VTX n__TX12V 0 DC 12', 'VTX n__TX12V 0 PWL(0 0 10u 12)')
    net = re.sub(r"IMIC (\S+) 0 DC 0.5m AC \S+", r"IMIC \1 0 PWL(0 0 10u 0.5m)", net)
    net = net.replace('V5 n__5V 0 DC 5', 'V5 n__5V 0 DC 5')
    tran(net, 20e-6, 1.5, 0, uic=False)
    t = ngs.vec('time'); va = ngs.vec('n__AF_ADC'); vo = ngs.vec(pin('IC2', '1'))
    k = max(range(len(va)), key=lambda i: abs(va[i] - va[-1]))
    st = next((t[i] for i in range(len(va) - 1, -1, -1) if abs(va[i] - va[-1]) > 0.01), 0)
    print(f"  AF_ADC の最大のずれ {va[k]-va[-1]:+.2f} V（{t[k]*1e3:.0f} ms、{va[k]:.2f} V）、±10mV 以内になるまで {st*1e3:.0f} ms、"
          f"IC2A 出力 {min(vo):.2f}〜{max(vo):.2f} V")

if __name__ == '__main__':
    import sys
    parts = sys.argv[1:] or ['rx', 'mic', 'drv', 'pa', 'on', 'tx']
    fn = dict(rx=rx_power, mic=mic_level, drv=driver_level, pa=pa, on=power_on, tx=tx_start)
    for p in parts: fn[p]()
