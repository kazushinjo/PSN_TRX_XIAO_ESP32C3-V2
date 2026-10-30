"""回路全体を通した計算（V2）
  受信: アンテナ → BPF → RF 増幅 → 第 1 混合 → 混合後増幅 → ラダー → IF 増幅 → 積検波 → AF → スピーカー
        各段の AC 解析を、混合での周波数の変換も含めてつなぐ（混合器 2 個は利得 0dB の理想的な掛け算器と仮定）
  送信: 局発（CLK0・CLK1）→ 平衡変調器（D4〜D7）→ Q10 → Q8 → PA（Q3）→ LPF → 50Ω を 50.5MHz の過渡解析で通す
        音声は直流（準静的）で与え、出力の 50.5MHz の振幅と位相を求める
"""
import ngs, math, cmath, io, contextlib, re
from gen import *

with contextlib.redirect_stdout(io.StringIO()):
    import rx                       # 受信部の回路（BPF・ラダー・IF 増幅）を読み込む（計算結果の表示は捨てる）
    import af
from tran import tran, lin
from rf import lpf

DIAL = 50.500e6
BFO_USB = 11.9999e6                 # ファームウェアの初期値（BFO_USB_DEFAULT）
LO = DIAL - BFO_USB
S9 = 50e-6                          # 整合時のアンテナ端の電圧（−73dBm）
KT = 1.38e-23 * 290


def db(x):
    return 20 * math.log10(max(abs(x), 1e-30))


def interp(fr, h, x):
    """周波数 fr の複素応答 h を x で直線補間（範囲外は端の値）"""
    if x <= fr[0]: return h[0]
    if x >= fr[-1]: return h[-1]
    lo, hi = 0, len(fr) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if fr[m] <= x: lo = m
        else: hi = m
    t = (x - fr[lo]) / (fr[hi] - fr[lo])
    return h[lo] + (h[hi] - h[lo]) * t


# ================================================================ 受信
def front_end_net(tc3, tc4):
    """アンテナ（50Ω）→ L18（入力同調）→ Q20・Q25（J310 カスコード）→ L19（出力同調）のタップ → C85 → NJM2594 の入力（600Ω）"""
    return rx.front(tc3, tc4)


def if_chain_net():
    """NJM2594 の出力（エミッタフォロワ、50Ω と仮定）→ Q21 → L 整合 → ラダー → Q2 → U5 の入力（600Ω）"""
    xl = lambda ref: 2 * math.pi * rx.IF * val(ref)
    lm = lambda cm, f0: 1 / ((2 * math.pi * f0) ** 2 * cm)
    X = rx.XTAL
    e = [f"VSRC s 0 dc 0 ac 1\nRSRC s {pin('C89','1')} 50", R('R70'), C('C89'), R('R71'), R('R72'),
         BJT('Q21', 'QS'), R('R73'), R('R74'), C('C90'), R('R75'), C('C91'), C('C92'), C('C93'), L('L21', 1.0)]
    for i in range(1, 7):
        a, b = pin(f'Y{i}', '1'), pin(f'Y{i}', '2')
        e.append(f"LY{i} {a} y{i}a {lm(X['Cm'], rx.IF):g}\nCY{i} y{i}a y{i}b {X['Cm']:g}\nRY{i} y{i}b {b} {X['Rs']:g}\nC0Y{i} {a} {b} {X['C0']:g}")
    e += [C(r) for r in ('C94', 'C95', 'C96', 'C97', 'C98')]
    e += [f"MQ2a {pin('Q2','S')} {pin('Q2','G1')} mq 0 DG", f"MQ2b {pin('Q2','D')} {pin('Q2','G2')} mq 0 DG",
          R('R5'), C('C8'), R('R76'), L('L22', xl('L22') / rx.QL_IF), C('C11'), C('C99'),
          f"RDET {pin('C99','2')} 0 {rx.ZIN_DET}", f"VG2 {pin('Q2','G2')} 0 dc 4.0",
          f"V9 {node('+9V')} 0 dc 12"]
    # 水晶の間の点（XF1〜XF5）と L21 の両端は直流的に浮くので、動作点の計算用に 1GΩ でつなぐ（水晶の内部の点には入れない）
    e += [f"RDC{r} {pin(r, '1')} 0 1e9" for r in ('C94', 'C95', 'C96', 'C97', 'C98', 'C93')]
    e.append(f"RDCXF {pin('L21', '2')} 0 1e9")
    return 'ifc\n' + rx.MOD2 + '\n'.join(e) + '\n'


def ac(net, out, f0, f1, n, src='VS'):
    ngs.run(net + f".ac lin {n} {f0:g} {f1:g}\n")
    return [x.real for x in ngs.vec('frequency')], ngs.vec(out)


def receiver():
    print('### 受信: アンテナからスピーカーまで（混合器の変換利得 0dB・BFO %.4f MHz（USB）・局発 %.4f MHz・音量 0.9）' % (BFO_USB / 1e6, LO / 1e6))
    tc3, tc4 = rx.tune()
    fe = front_end_net(tc3, tc4)
    # 前段（BPF＋RF 増幅）: 50MHz 付近と、妨害の周波数
    f_rf, h_rf = ac(fe, pin('C85', '2'), 49.5e6, 51.5e6, 401)
    spots = {}
    for name, f in (('26.5MHz', 26.4989e6), ('12MHz', 12.0015e6), ('44.5MHz', 44.5e6), ('76MHz', 76e6)):
        ngs.run(fe + f".ac lin 1 {f:g} {f:g}\n"); spots[name] = ngs.vec(pin('C85', '2'))[0]
    # IF 段（12MHz ±20kHz）
    ifn = if_chain_net()
    f_if, h_if = ac(ifn, pin('C99', '2'), rx.IF - 20e3, rx.IF + 20e3, 4001)
    # AF 段
    ngs.run(af.rx_circuit(0.9)); f_af = [x.real for x in ngs.vec('frequency')]
    h_af = [a / b for a, b in zip(ngs.vec(pin('J6', '1')), ngs.vec(pin('R79', '1')))]

    def total(f_rf_in, h_rf_val=None):
        """アンテナの周波数 f_rf_in の信号（整合時 1V）がスピーカーに出す電圧"""
        hr = h_rf_val if h_rf_val is not None else interp(f_rf, h_rf, f_rf_in)
        f_i = abs(f_rf_in - LO)
        hi = interp(f_if, h_if, f_i)
        fa = abs(f_i - BFO_USB)
        if fa < 20 or fa > 20e3: return 0j, fa
        return hr * hi * interp(f_af, h_af, fa), fa

    # 1. 音声の帯域（USB の希望信号）
    print('  希望の側帯波（USB）: S9 の信号の音声周波数ごとのスピーカー出力（8Ω）')
    row = []; best = 0
    pts = [100, 200, 300, 400, 600, 1000, 1500, 2000, 2500, 2800, 3000, 3500]
    vals = {}
    for fa in pts:
        v, _ = total(DIAL + fa)
        vals[fa] = abs(v) * S9 / 2 * 2      # VS ac 2 で整合時 1V
    ref = max(vals.values())
    print('   ' + '  '.join(f"{fa}Hz {20*math.log10(max(vals[fa],1e-30)/ref):+.1f}dB" for fa in pts))
    pk = max(vals, key=vals.get)
    p9 = vals[1000] ** 2 / 8
    print(f'   S9・1kHz でスピーカー {p9*1e3:.2f}mW 相当（{db(vals[1000]):+.1f}dBV、小信号の線形計算で出力段の飽和を含まない値）。いちばん大きいのは {pk}Hz')
    print(f'   ※ 実際の出力は出力段の最大 約 113mW（tran.py、歪み 11%）で頭打ちになる → S9 では {min(p9, 0.113)*1e3:.0f}mW。'
          '帯域・選択度・イメージなどの比は線形の値のまま使える')
    # −6dB の帯域
    fine = [x * 10 for x in range(5, 400)]
    lv = [abs(total(DIAL + fa)[0]) for fa in fine]
    m = max(lv); ok = [fa for fa, v in zip(fine, lv) if v >= m / 2]
    print(f'   音声の −6dB 帯域: {ok[0]}〜{ok[-1]}Hz')
    # 2. 選択度（希望 1kHz を基準に、同じ大きさの妨害がスピーカーにどれだけ出るか）
    want = abs(total(DIAL + 1000)[0])
    print('  選択度（希望信号 USB 1kHz と同じ大きさの妨害波を入れたときのスピーカー出力の比）')
    for name, f in (('逆側帯波（LSB 1kHz、受信周波数 −1kHz）', DIAL - 1000), ('逆側帯波（LSB 2kHz）', DIAL - 2000),
                    ('隣接（+3.5kHz）', DIAL + 3500), ('隣接（+5kHz）', DIAL + 5000), ('隣接（−3kHz）', DIAL - 3000),
                    ('隣接（−5kHz）', DIAL - 5000), ('隣接（+10kHz）', DIAL + 10e3)):
        v, fa = total(f)
        print(f'   {name}: {db(v / want):+.1f}dB（音声 {fa:.0f}Hz）')
    # イメージ: 受信周波数 = LO − (BFO + 1kHz)
    img = LO - (BFO_USB + 1000)
    v, fa = total(img, spots['26.5MHz'] if abs(img - 26.4989e6) < 1e3 else None)
    print(f'   イメージ（{img/1e6:.4f}MHz）: {db(v / want):+.1f}dB（前段の同調回路と RF 増幅の差。混合器の偶数次などは含まない）')
    hr0 = abs(interp(f_rf, h_rf, DIAL))
    print(f'   12MHz の素通り（前段で {db(spots["12MHz"] / hr0):+.1f}dB。NJM2594 の信号の漏れ −30dB と仮定すると合計 {db(spots["12MHz"] / hr0) - 30:+.0f}dB）')
    print(f'   半 IF（44.5MHz）: 前段で {db(spots["44.5MHz"] / hr0):+.1f}dB（混合器の 2 次ひずみの分はさらに低い）')
    # 3. 感度（前段の雑音指数と最小検出信号）
    ngs.run(fe + f".noise v({pin('C85','2')}) VS lin 3 {DIAL-1e3:g} {DIAL+1e3:g}\n")
    ngs.cmd('setplot noise1')
    try:
        inn = ngs.vec('inoise_spectrum')
        vin = abs(inn[1])                         # V/√Hz（信号源 VS の位置、RS 50Ω の雑音を含む）
        f_fe = (vin / 2) ** 2 / (KT * 50)          # VS ac 2 は開放電圧なので整合時の端子では 1/2
        nf_fe = 10 * math.log10(f_fe)
    except KeyError:
        nf_fe = float('nan')
    # 前段の電力利得（50Ω の有能電力 → 混合器の入力 600Ω）
    g_fe = (abs(hr0) ** 2 / 600) / (1 ** 2 / 50)
    for nf_mix in (10, 15):
        f_tot = 10 ** (nf_fe / 10) + (10 ** (nf_mix / 10) - 1) / g_fe
        nf = 10 * math.log10(f_tot)
        mds = -174 + nf + 10 * math.log10(2400)
        uv = math.sqrt(10 ** (mds / 10) * 1e-3 * 50) * 1e6
        print(f'  感度: 前段（入力同調＋Q20・Q25）の雑音指数 {nf_fe:.1f}dB、電力利得 {10*math.log10(g_fe):+.1f}dB。混合器の雑音指数を {nf_mix}dB とすると'
              f' 全体 {nf:.1f}dB、最小検出信号（帯域 2.4kHz）{mds:.0f}dBm（{uv:.2f}µV）≒ S{max(0, 9 + round((20*math.log10(uv/50))/6))}')
    return h_rf


# ================================================================ 送信
LP7, N7, K7, QL7 = 0.50e-6, 2 / 7, 0.85, 70     # 7T50: 一次 約 0.5µH（15pF＋浮遊で 50.5MHz）、二次リンク 2/7 巻と仮定


def coil7(ref, ct_used):
    """7T50（SA−[CT]−SB 一次、AA−AB 二次リンク）を結合インダクタで表す"""
    sa, sb, ct, aa, ab = (pin(ref, p) for p in ('SA', 'SB', 'CT', 'AA', 'AB'))
    w = 2 * math.pi * 50.5e6
    out = []
    if ct_used:
        lh = LP7 / 4 / (1 + 0.98) * 2          # 2 つの半分（結合 0.98）で全体が LP7
        out += [f"L{ref}a {sa} m{ref}a {lh:g}", f"R{ref}a m{ref}a {ct} {w*lh/QL7:g}",
                f"L{ref}b {ct} m{ref}b {lh:g}", f"R{ref}b m{ref}b {sb} {w*lh/QL7:g}"]
        prim = [f"L{ref}a", f"L{ref}b"]
        out.append(f"K{ref}ab L{ref}a L{ref}b 0.98")
    else:
        out += [f"L{ref}p {sa} m{ref}p {LP7:g}", f"R{ref}p m{ref}p {sb} {w*LP7/QL7:g}"]
        prim = [f"L{ref}p"]
    ls = LP7 * N7 ** 2
    out += [f"L{ref}s {aa} m{ref}s {ls:g}", f"R{ref}s m{ref}s {ab} {w*ls/QL7:g}"]
    for i, p in enumerate(prim): out.append(f"K{ref}{i}s {p} L{ref}s {K7}")
    return '\n'.join(out)


PA_MODEL = ".model RD06 NMOS(LEVEL=1 VTO=3.0 KP=1.2 LAMBDA=0.01 RD=0.25 RS=0.05)"


def tx_net(vi, vq, vr3=0.5, vr4=0.5, d4is=1.0, idq=0.1, vs=12.0, vr6=0.5, vr7=0.5):
    """局発（矩形波 3.3V、CLK1 は 90° 遅れ）→ LPF → VR6/VR7 → 変調器 → Q10 → Q8 → Q3 → LPF → 50Ω。
    vi・vq は変調器への音声（直流、L11・L10 の音声側）"""
    T = 1 / 50.5e6
    e = [f"VCK0 ck0 0 PULSE(0 3.3 0 0.4n 0.4n {T/2-0.4e-9:g} {T:g})\nRCK0 ck0 {pin('C58','2')} 30",
         f"VCK1 ck1 0 PULSE(0 3.3 {T/4:g} 0.4n 0.4n {T/2-0.4e-9:g} {T:g})\nRCK1 ck1 {pin('C59','2')} 30",
         C('C58'), C('C56'), L('L13', 0.3), C('C51'), POT('VR6', vr6),
         C('C59'), C('C57'), L('L14', 0.3), C('C53'), POT('VR7', vr7),
         R('R34'), R('R35'), C('C39'), C('C40'),
         f"CQ11 {pin('C36','2')} 0 5p",
         POT('VR3', vr3), POT('VR4', vr4), C('C31'),
         f"D4 {pin('D4','A')} {pin('D4','K')} DS{'X' if d4is != 1 else ''}", f"D5 {pin('D5','A')} {pin('D5','K')} DS",
         f"D6 {pin('D6','A')} {pin('D6','K')} DS", f"D7 {pin('D7','A')} {pin('D7','K')} DS",
         L('L11', 20), L('L10', 20), C('C38'), C('C35'),
         f"VI ai 0 dc {vi}\nRI ai {pin('C38','1')} 1k", f"VQ aq 0 dc {vq}\nRQ aq {pin('C35','1')} 1k",
         coil7('L8', True),
         JFET('Q10', 'J2SK439'), R('R16'), C('C25'), coil7('L7', False), C('C24'),
         C('C21'), BJT('Q8', 'Q2SC1815'), R('R13'), R('R14'), R('R11'), C('C19'),
         coil7('L6', False), C('C18'), C('C17'), C('C23'),
         C('C15'), L('L5', 0.2), C('C14'), R('R7'), R('R6'),
         f"CGS3 {pin('Q3','G')} 0 25p\nCGD3 {pin('Q3','G')} {pin('Q3','D')} 1.3p",
         f"M3 {pin('Q3','D')} {pin('Q3','G')} 0 0 RD06 W=1 L=1",
         f"VTX {node('Net-(L6-SB)')} 0 dc {vs}"]
    # VR2: ゲート電圧が Idq になる位置
    vg = 3.0 + math.sqrt(2 * idq / 1.2)
    r23 = vg * (330 + 500) / vs                      # ワイパー〜GND の抵抗
    e.append(POT('VR2', 1 - r23 / 500))
    net = lpf(1.0, 18e-12, 11e-12, 1.0, 6.5e-12)     # PA ドレイン → LPF → 50Ω（rf.py と同じ）
    net = net.replace('VS src 0 AC 2\n', '').replace(f"RS src {pin('C7','1')} 50\n", '')
    net = net.replace('RRFC rfc 0 0.3', f"RRFC rfc {node('Net-(L6-SB)')} 0.3")
    net = re.sub(r'\n\.ac .*', '', net)
    models = MODELS.replace('{hfe1815}', '250').replace('{hfe1923}', '100').replace('{hfe2120}', '180')
    return (net + '\n' + models + '\n' + PA_MODEL +
            f"\n.model DS D(IS=1u N=1.1 RS=5 CJO=1p)\n.model DSX D(IS={d4is}u N=1.1 RS=5 CJO=1p)\n" + '\n'.join(e) + '\n')


def phasor(t, v, f0, ncyc):
    T = ncyc / f0; idx = [i for i, x in enumerate(t) if x >= t[-1] - T]
    re_ = sum(v[i] * math.cos(2 * math.pi * f0 * t[i]) for i in idx); im = sum(v[i] * math.sin(2 * math.pi * f0 * t[i]) for i in idx)
    return 2 * complex(re_, -im) / len(idx)


def tx_point(**kw):
    tran(tx_net(**kw), 0.1e-9, 12e-6, 10e-6)
    t = lin(0.1e-9)
    vo = ngs.vec(pin('C1', '1'))
    p = phasor(t, vo, 50.5e6, 80)
    h2 = abs(phasor(t, vo, 101e6, 80))
    return p, (abs(p) / math.sqrt(2)) ** 2 / 50, h2


def transmitter():
    print()
    print('### 送信: 局発・変調器から PA・LPF・50Ω まで（50.5MHz の過渡解析、音声は直流で与える準静的な計算）')
    print('  7T50（L6〜L8）は一次 0.5µH・二次リンク 2/7 巻・結合 0.85・Q 70 と仮定（実物の値で変わる）。PA は 2 乗特性の簡易モデル、Idq 100mA')
    p0, w0, _ = tx_point(vi=0, vq=0)
    print(f'  音声なし（VR3・VR4 は中点、ダイオードがそろっている）: キャリアの漏れ {w0*1e3:.3f}mW（{10*math.log10(max(w0,1e-15)/1e-3):.0f}dBm）')
    # VR3・VR4 を回して漏れを最小にする（粗く探してから細かく）
    best = (w0, 0.5, 0.5)
    for step in (0.1, 0.03, 0.01):
        b3, b4 = best[1], best[2]
        for d3 in (-2, -1, 0, 1, 2):
            for d4 in (-2, -1, 0, 1, 2):
                a3, a4 = b3 + d3 * step, b4 + d4 * step
                if not (0.05 < a3 < 0.95 and 0.05 < a4 < 0.95): continue
                w = tx_point(vi=0, vq=0, vr3=a3, vr4=a4)[1]
                if w < best[0]: best = (w, a3, a4)
    print(f'  VR3 {best[1]:.2f}・VR4 {best[2]:.2f} に合わせると: キャリアの漏れ {best[0]*1e3:.4f}mW（{10*math.log10(max(best[0],1e-15)/1e-3):.0f}dBm）')
    p1, w1, _ = tx_point(vi=0, vq=0, d4is=1.3)
    print(f'  D4 の IS が 30% 大きいとき: キャリアの漏れ {w1*1e3:.3f}mW（{10*math.log10(max(w1,1e-15)/1e-3):.0f}dBm）→ VR3 で打ち消す')
    print('  I 側だけに音声（直流）を入れたときの出力（50Ω）と 2 倍波')
    for a in (0.02, 0.05, 0.1, 0.2, 0.4, 0.8):
        p, w, h2 = tx_point(vi=a, vq=0)
        print(f'    音声 {a*1e3:4.0f}mV: 出力 {w:6.3f}W（{10*math.log10(w/1e-3):5.1f}dBm）、2 倍波 {db(h2/abs(p)):+.0f}dBc')
    pi, wi, _ = tx_point(vi=0.1, vq=0)
    pq, wq, _ = tx_point(vi=0, vq=0.1)
    ph = math.degrees(cmath.phase(pq / pi)); am = db(abs(pq) / abs(pi))
    # 位相差の 90° からのずれと振幅差による逆側帯波の抑圧
    pe = abs(abs(ph) - 90); k = 10 ** (am / 20); th = math.radians(pe)
    sup = 10 * math.log10((1 + 2 * k * math.cos(th) + k * k) / (1 - 2 * k * math.cos(th) + k * k))
    print(f'  I と Q の出力の位相差 {ph:+.1f}°・振幅差 {am:+.2f}dB（音声 100mV、VR6・VR7 は中点）→ RF 側だけで決まる逆側帯波の抑圧 {sup:.0f}dB')

    def supp(pe, am):
        k = 10 ** (am / 20); th = math.radians(pe)
        return 10 * math.log10((1 + 2 * k * math.cos(th) + k * k) / (1 - 2 * k * math.cos(th) + k * k))
    # VR6 を 0.9 にして、VR7 で位相差を 90° に合わせる（振幅の差はファームウェアの iqa で補正）
    best = None
    for v7 in [0.5 + 0.05 * i for i in range(9)]:
        a_ = tx_point(vi=0.1, vq=0, vr6=0.9, vr7=v7)[0]; b_ = tx_point(vi=0, vq=0.1, vr6=0.9, vr7=v7)[0]
        p_ = math.degrees(cmath.phase(b_ / a_)); m_ = db(abs(b_) / abs(a_))
        if best is None or abs(abs(p_) - 90) < abs(abs(best[1]) - 90): best = (v7, p_, m_)
    v7, p_, m_ = best
    print(f'  VR6 0.9・VR7 {v7:.2f} に合わせると: 位相差 {p_:+.1f}°・振幅差 {m_:+.2f}dB → 振幅を iqa で補正して抑圧 {supp(abs(abs(p_) - 90), 0):.0f}dB'
          f'（ファームウェアの iqd・iqa は音声側の遅延と利得の補正なので、RF 側の一定の位相ずれは VR6・VR7 で合わせる）')


if __name__ == '__main__':
    import sys
    parts = sys.argv[1:] or ['rx', 'tx']
    if 'rx' in parts: receiver()
    if 'tx' in parts: transmitter()
