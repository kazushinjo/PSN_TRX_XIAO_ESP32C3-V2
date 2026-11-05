"""直流動作点: 電源 11/12/13.8V × hFE 下限/上限、2SK192A-BL の個体差"""
import ngs
from gen import *

def circuit():
    e = []
    # 受信 IF 増幅: 2SK192A-BL カスコード（Q6 下段・Q7 上段、V2 では 12MHz。R18 は 2SK192A 用の 47Ω）、ゲイン J3（10k と仮定、最大）
    e += [JFET('Q6', 'J2SK192'), JFET('Q7', 'J2SK192'), R('R18'), R('R16'), L('L5', 0.5), R('R17'),
          "RJ4a n_Net__J3_Pin_1_ n__Q2_G2 1m", "RJ4b n__Q2_G2 0 10k",
          BJT('Q21', 'Q2SC1815'), R('R75'), R('R76')]
    # 受信（V2）: RF 増幅 Q2・Q3（2SK192A-BL カスコード、Q3 のゲートは AGC の Q2_G2 から R4）、混合後増幅 Q5、S メーター増幅 Q8
    e += [JFET('Q2', 'J2SK192'), JFET('Q3', 'J2SK192'), f"RL18 {pin('L1','1')} 0 0.3", R('R3'), R('R4'), f"RL19 {pin('L2','1')} {pin('L2','3')} 0.3", R('R5'),
          BJT('Q5', 'Q2SC1815'), R('R11'), R('R12'), R('R14'), R('R15'), R('R13'),
          BJT('Q8', 'Q2SC1815'), R('R22'), R('R23'), R('R24'), R('R25'), L('L6', 0.5)]
    # 受信 AF: Q9（前置増幅）→ Q10 → Q11 → AF 出力 Q13/Q12（入力は積検波 U2 の出力から C39）
    e += [R('R28'), BJT('Q9', 'Q2SC1815'), R('R29'), R('R30'),
          BJT('Q10', 'Q2SC1815'), R('R32'), R('R33'),
          R('R34'), BJT('Q11', 'Q2SC1815'), R('R35'), R('R36'), R('R37'),
          R('R38'), "RJ5a n_Net__J5_Pin_1_ n_Net__J5_Pin_2_ 5k", "RJ5b n_Net__J5_Pin_2_ 0 5k",
          BJT('Q13', 'Q2SC2120'), BJT('Q12', 'Q2SA950'), R('R40'), R('R39'), R('R41'),
          R('R73'), R('R74')]
    # 受信 LO バッファ Q4、送信 Q17・Q18
    e += [JFET('Q4', 'J2SK439'), R('R7'), R('R6'), WIND('L3'),
          JFET('Q17', 'J2SK439'), R('R65'), WIND('L13'), WIND('L12'),
          BJT('Q18', 'Q2SC1815'), R('R66'), R('R67'), R('R68'), WIND('L14')]
    # 送信 AF: マイク Q14、マイクアンプ IC2A、Q15/Q16（U7 の PDM 出力は C72/C70 で直流を切る）
    e += [BJT('Q14', 'Q2SC1815'), R('R45'), R('R46'), R('R44'), R('R42'), R('R43'),
          f"IMIC {pin('J7','2')} 0 DC 0.5m",
          L('L7', 60), R('R47'), R('R48'), R('R49'), R('R50'), R('R51'), OPA('A'),
          BJT('Q15', 'Q2SC1815'), R('R62'), R('R58'), R('R57'),
          BJT('Q16', 'Q2SC1815'), R('R61'), R('R60'), R('R59'),
          L('L10', 20), L('L11', 20), R('R63'), R('R64')]
    # 送信検出 Q22
    e += [BJT('Q22', 'Q2SC1815'), R('R77'), R('R78'), R('R79')]
    return '\n'.join(e)

BODY = circuit()
TR = {'Q7': 'J', 'Q6': 'J', 'Q2': 'J', 'Q3': 'J', 'Q9': 'Q', 'Q5': 'Q', 'Q8': 'Q', 'Q18': 'Q', 'Q10': 'Q', 'Q17': 'J', 'Q4': 'J', 'Q11': 'Q', 'Q13': 'Q',
      'Q12': 'Q', 'Q15': 'Q', 'Q16': 'Q', 'Q21': 'Q', 'Q14': 'Q', 'Q22': 'Q'}

def V(n): return '0' if n=='0' else f'v({n})'

def run(vs, lo, fet):
    h = dict(hfe1815=200 if lo else 400, hfe1923=40 if lo else 240, hfe2120=120 if lo else 240)
    vp, idss = fet
    params = '\n'.join(f".param {k}={v}" for k, v in h.items()) + f"\n.param vpfet={vp} bfet={idss/vp**2}"
    net = f"""dc
{params}
{MODELS}
{OPAMP}
V9 n_RX12V 0 DC {vs}
VTX n__TX12V 0 DC {vs}
V5 n__5V 0 DC 5
V33 n__XIAO_3V3 0 DC 3.3
VAGC n__AGC_PWM 0 DC 0
{circuit()}
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
        if q == 'Q21':  # @q[ic] が不正確なので R17 と J3 の電流差から求める
            ic = (vs - ngs.vec(pin('R17', '1'))[0]) / 20e3 - ngs.vec('n__Q2_G2')[0] / 10e3; p = ic * vc
        r[q] = (ic, vc, p)
    v = lambda n: ngs.vec(n)[0]
    r['R27W'] = (v('n_RX12V') - v(pin('Q12', 'E'))) ** 2 / 100
    r['MIC'] = v(pin('J7', '2'))
    r['IC2A_out'] = v(pin('U5', '1'))
    r['Q21_B'] = v(pin('Q21','B')); r['C104'] = v('n_Net__C104_Pad1_')
    r['TX_SENSE'] = v('n__TX_SENSE'); r['Q2_G2'] = v('n__Q2_G2')
    return r

if __name__ == '__main__':
    import itertools, json
    res = {}
    for vs, lo in itertools.product([11, 12, 13.8], [True, False]):
        res[(vs, lo)] = run(vs, lo, (-2, 0.018))
    keys = list(TR)
    print('Ic/Id [mA] (Vc/Vd [V]) Pd[mW]  hFE下限/上限 × 11/12/13.8V の範囲')
    for q in keys:
        ics = [res[k][q][0] * 1e3 for k in res]; vcs = [res[k][q][1] for k in res]; ps = [res[k][q][2] * 1e3 for k in res]
        print(f"{q:4} {COMPS[q]:9} Ic {min(ics):6.2f}〜{max(ics):6.2f} mA  Vc {min(vcs):5.2f}〜{max(vcs):5.2f} V  Pd 最大 {max(ps):6.1f} mW")
    for k in ['R27W', 'MIC', 'IC2A_out', 'TX_SENSE', 'Q2_G2', 'Q21_B', 'C104']:
        xs = [res[x][k] for x in res]; print(f"{k:9} {min(xs):.3f}〜{max(xs):.3f}")
    for vs in [11, 12, 13.8]:
        print('MIC', vs, round(res[(vs, True)]['MIC'], 2), round(res[(vs, False)]['MIC'], 2))
    import gen
    print('2SK192A-BL 個体差（12V、VGS(off) −1.2〜−3V・IDSS 12〜24mA）と、ソース抵抗 R3（RF 増幅 Q2）・R18（IF 増幅 Q6）:')
    FETS = [(-1.2, 0.012), (-2, 0.018), (-3, 0.024), (-1.2, 0.024), (-3, 0.012)]
    for rs in ['47', '68', '100', '150']:
        gen.OVERRIDE.update({'R3': rs, 'R18': rs})
        rows = [run(12, False, f) for f in FETS]
        q2 = [r['Q2'][0] * 1e3 for r in rows]; q6 = [r['Q6'][0] * 1e3 for r in rows]
        p2 = max(r['Q2'][2] for r in rows) * 1e3; p3 = max(r['Q3'][2] for r in rows) * 1e3
        p6 = max(r['Q6'][2] for r in rows) * 1e3; p7 = max(r['Q7'][2] for r in rows) * 1e3
        vd3 = [r['Q3'][1] for r in rows]; vd7 = [r['Q7'][1] for r in rows]
        print(f"  R3=R18={rs:>3}Ω: RF Id {min(q2):5.1f}〜{max(q2):5.1f} mA（Q3 Vd {min(vd3):.2f}〜{max(vd3):.2f} V、Pd 最大 Q2 {p2:.0f}・Q3 {p3:.0f} mW）"
              f" | IF Id {min(q6):5.1f}〜{max(q6):5.1f} mA（Q7 Vd {min(vd7):.2f}〜{max(vd7):.2f} V、Pd 最大 Q6 {p6:.0f}・Q7 {p7:.0f} mW）")
    gen.OVERRIDE.clear()
    print('定数:', ' '.join(f"{k}={v}" for k, v in sorted(used.items())))
