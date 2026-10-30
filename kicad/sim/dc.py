"""直流動作点: 電源 11/12/13.8V × hFE 下限/上限、J310 の個体差"""
import ngs
from gen import *

def circuit():
    e = []
    # 受信 IF 増幅: J310 カスコード（Q5 下段・Q4 上段、V2 では 12MHz）、ゲイン J4（10k と仮定、最大）
    e += [JFET('Q5', 'JJ310'), JFET('Q4', 'JJ310'), R('R5'), R('R76'), L('L22', 0.5), R('R4'),
          "RJ4a n_Net__J4_Pin_1_ n__Q2_G2 1m", "RJ4b n__Q2_G2 0 10k",
          BJT('Q17', 'Q2SC1815'), R('R42'), R('R44')]
    # 受信（V2）: RF 増幅 Q20・Q25（J310 カスコード、Q25 のゲートは AGC の Q2_G2 から R95）、混合後増幅 Q21、S メーター増幅 Q22
    e += [JFET('Q20', 'JJ310'), JFET('Q25', 'JJ310'), f"RL18 {pin('L18','1')} 0 0.3", R('R66'), R('R95'), f"RL19 {pin('L19','1')} {pin('L19','3')} 0.3", R('R67'),
          BJT('Q21', 'Q2SC1815'), R('R71'), R('R72'), R('R73'), R('R74'), R('R75'),
          BJT('Q22', 'Q2SC1815'), R('R82'), R('R83'), R('R84'), R('R85'), L('L23', 0.5)]
    # 受信 AF: Q23（前置増幅）→ Q9 → Q12 → AF 出力 Q13/Q14（入力は積検波 U5 の出力から C22）
    e += [R('R96'), BJT('Q23', 'Q2SC1815'), R('R97'), R('R98'),
          BJT('Q9', 'Q2SC1815'), R('R15'), R('R17'),
          R('R18'), BJT('Q12', 'Q2SC1815'), R('R20'), R('R21'), R('R23'),
          R('R24'), "RJ5a n_Net__J5_Pin_1_ n_Net__J5_Pin_2_ 5k", "RJ5b n_Net__J5_Pin_2_ 0 5k",
          BJT('Q13', 'Q2SC2120'), BJT('Q14', 'Q2SA950'), R('R25'), R('R26'), R('R27'),
          R('R38'), R('R39')]
    # 受信 LO バッファ Q11、送信 Q10・Q8
    e += [JFET('Q11', 'J2SK439'), R('R19'), R('R22'), WIND('L9'),
          JFET('Q10', 'J2SK439'), R('R16'), WIND('L7'), WIND('L8'),
          BJT('Q8', 'Q2SC1815'), R('R13'), R('R14'), R('R11'), WIND('L6')]
    # 送信 AF: マイク Q18、マイクアンプ IC2A、Q15/Q16（U3 の PDM 出力は C48/C49 で直流を切る）
    e += [BJT('Q18', 'Q2SC1815'), R('R46'), R('R47'), R('R49'), R('R51'), R('R52'),
          f"IMIC {pin('J10','2')} 0 DC 0.5m",
          L('L15', 60), R('R58'), R('R41'), R('R43'), R('R40'), R('R36'), OPA('A'),
          BJT('Q15', 'Q2SC1815'), R('R28'), R('R29'), R('R30'),
          BJT('Q16', 'Q2SC1815'), R('R31'), R('R32'), R('R33'),
          L('L11', 20), L('L10', 20), R('R34'), R('R35')]
    # 送信検出 Q19
    e += [BJT('Q19', 'Q2SC1815'), R('R45'), R('R48'), R('R50')]
    return '\n'.join(e)

BODY = circuit()
TR = {'Q4': 'J', 'Q5': 'J', 'Q20': 'J', 'Q25': 'J', 'Q23': 'Q', 'Q21': 'Q', 'Q22': 'Q', 'Q8': 'Q', 'Q9': 'Q', 'Q10': 'J', 'Q11': 'J', 'Q12': 'Q', 'Q13': 'Q',
      'Q14': 'Q', 'Q15': 'Q', 'Q16': 'Q', 'Q17': 'Q', 'Q18': 'Q', 'Q19': 'Q'}

def V(n): return '0' if n=='0' else f'v({n})'

def run(vs, lo, j310):
    h = dict(hfe1815=200 if lo else 400, hfe1923=40 if lo else 240, hfe2120=120 if lo else 240)
    vp, idss = j310
    params = '\n'.join(f".param {k}={v}" for k, v in h.items()) + f"\n.param vp310={vp} b310={idss/vp**2}"
    net = f"""dc
{params}
{MODELS}
{OPAMP}
V9 n__9V 0 DC {vs}
VTX n__TX12V 0 DC {vs}
V5 n__5V 0 DC 5
V33 n__XIAO_3V3 0 DC 3.3
VAGC n__AGC_PWM 0 DC 0
{BODY}
.op
"""
    out = ngs.run(net)
    if 'rror' in out and 'singular' in out.lower(): print(out)
    r = {}
    for q, t in TR.items():
        n = 'q' + q.lower() if t == 'Q' else 'j' + q.lower()
        # 電流は @device[ic] / [id]
        if t == 'Q':
            ngs.cmd(f'let tmp_ic=@{n}[ic]'); ngs.cmd(f'let tmp_p=@{n}[ic]*({V(pin(q,"C"))}-{V(pin(q,"E"))})')
        else:
            ngs.cmd(f'let tmp_ic=@{n}[id]'); ngs.cmd(f'let tmp_p=@{n}[id]*({V(pin(q,"D"))}-{V(pin(q,"S"))})')
        ic = ngs.vec('tmp_ic')[0]; p = ngs.vec('tmp_p')[0]
        vc = ngs.vec(pin(q, 'C' if t == 'Q' else 'D'))[0] if pin(q, 'C' if t == 'Q' else 'D') != '0' else 0
        if q == 'Q17':  # @q[ic] が不正確なので R4 と J4 の電流差から求める
            ic = (vs - ngs.vec(pin('R4', '1'))[0]) / 20e3 - ngs.vec('n__Q2_G2')[0] / 10e3; p = ic * vc
        r[q] = (ic, vc, p)
    v = lambda n: ngs.vec(n)[0]
    r['R27W'] = (v('n__9V') - v(pin('Q14', 'E'))) ** 2 / 100
    r['MIC'] = v(pin('J10', '2'))
    r['IC2A_out'] = v(pin('IC2', '1'))
    r['Q17_B'] = v(pin('Q17','B')); r['C61'] = v('n_Net__C61_Pad1_')
    r['TX_SENSE'] = v('n__TX_SENSE'); r['Q2_G2'] = v('n__Q2_G2')
    return r

if __name__ == '__main__':
    import itertools, json
    res = {}
    for vs, lo in itertools.product([11, 12, 13.8], [True, False]):
        res[(vs, lo)] = run(vs, lo, (-4, 0.040))
    keys = list(TR)
    print('Ic/Id [mA] (Vc/Vd [V]) Pd[mW]  hFE下限/上限 × 11/12/13.8V の範囲')
    for q in keys:
        ics = [res[k][q][0] * 1e3 for k in res]; vcs = [res[k][q][1] for k in res]; ps = [res[k][q][2] * 1e3 for k in res]
        print(f"{q:4} {COMPS[q]:9} Ic {min(ics):6.2f}〜{max(ics):6.2f} mA  Vc {min(vcs):5.2f}〜{max(vcs):5.2f} V  Pd 最大 {max(ps):6.1f} mW")
    for k in ['R27W', 'MIC', 'IC2A_out', 'TX_SENSE', 'Q2_G2', 'Q17_B', 'C61']:
        xs = [res[x][k] for x in res]; print(f"{k:9} {min(xs):.3f}〜{max(xs):.3f}")
    for vs in [11, 12, 13.8]:
        print('MIC', vs, round(res[(vs, True)]['MIC'], 2), round(res[(vs, False)]['MIC'], 2))
    print('J310 個体差（12V）:')
    for vp, idss in [(-2, 0.024), (-4, 0.040), (-6.5, 0.060), (-2, 0.060), (-6.5, 0.024)]:
        r = run(12, False, (vp, idss)); print(f"  Vp {vp} Idss {idss*1e3:.0f}mA → Id {r['Q5'][0]*1e3:.1f} mA, Q4 Vd {r['Q4'][1]:.2f} V, Q5 Vds {r['Q5'][1]-0:.2f}")
    print('定数:', ' '.join(f"{k}={v}" for k, v in sorted(used.items())))
