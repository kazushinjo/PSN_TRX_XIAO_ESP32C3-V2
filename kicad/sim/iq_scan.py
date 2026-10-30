"""送信 AF の I/Q 位相差を周波数スキャンしてグラフにする（Ver 2.0）

  U3 の複素 FIR（tx_dsp.cpp と同じ作り方・同じ int16 量子化）× PDM 出力〜変調器入力のアナログ部（ngspice）で、
  I と Q の位相差が 90° からどれだけずれるか、振幅差、そこから決まる逆側帯波の抑圧を 100〜4000 Hz で求める。
  RC のばらつき（I +3%・Q −3%）と、ファームウェアの iqd・iqa で補正した後も並べる。

  使い方: kicad/sim で  <numpy と matplotlib の入った python3> iq_scan.py  → iq_scan.png と数値の要約
"""
import math, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import ngs
from gen import pin
from af import out_circuit

FS, NTAP, F_CENTER, F_CUT, BETA = 16000, 127, 1600.0, 1400.0, 7.5   # tx_dsp.cpp と同じ
F = np.linspace(100, 3200, 621)   # 3.3 kHz より上は FIR の阻止域（出力ほぼ 0）で位相に意味がない
BAND = (300, 2700)


def fir(iq_delay_us=0.0, iq_gain_db=0.0):
    """tx_dsp.cpp の buildFilter() と同じ係数（int16 に丸めた後）"""
    c = (NTAP - 1) / 2; w0 = 2 * math.pi * F_CENTER / FS
    dI = iq_delay_us * 1e-6 * FS; gI = 10 ** (iq_gain_db / 20)
    def proto(t):
        u = t / c
        if abs(u) >= 1: return 0.0
        w = np.i0(BETA * math.sqrt(1 - u * u)) / np.i0(BETA); x = 2 * F_CUT / FS
        return (x if t == 0 else math.sin(math.pi * x * t) / (math.pi * t)) * w
    fI = np.array([2 * gI * proto(n - c - dI) * math.cos(w0 * (n - c - dI)) for n in range(NTAP)])
    fQ = np.array([2 * proto(n - c) * math.sin(w0 * (n - c)) for n in range(NTAP)])
    sh = 15
    while sh > 8 and max(abs(fI).sum(), abs(fQ).sum()) * (1 << sh) * 32767 > 2e9: sh -= 1
    hI, hQ = np.round(fI * (1 << sh)) / (1 << sh), np.round(fQ * (1 << sh)) / (1 << sh)
    z = np.exp(-2j * np.pi * np.outer(F, np.arange(NTAP)) / FS)
    return z @ hI, z @ hQ


def analog(dI=1.0, dQ=1.0, rload=500):
    """PDM 出力（R61・R63 の入力）→ 変調器入力（L11・L10）"""
    ngs.run(out_circuit(rload, dI=dI, dQ=dQ))
    f = np.array([x.real for x in ngs.vec('frequency')])
    hi = np.array(ngs.vec(pin('L11', '1'))); hq = np.array(ngs.vec(pin('L10', '1')))
    ip = lambda h: np.interp(F, f, h.real) + 1j * np.interp(F, f, h.imag)
    return ip(hi), ip(hq)


def metrics(I, Q):
    """位相誤差 [deg]（90° からのずれ）・振幅差 [dB]・逆側帯波の抑圧 [dB]"""
    r = I / Q
    pe = np.degrees(np.abs(np.angle(r))) - 90
    ae = 20 * np.log10(np.abs(r))
    k, th = np.abs(r), np.radians(pe)
    s = 10 * np.log10((1 + 2 * k * np.cos(th) + k * k) / (1 - 2 * k * np.cos(th) + k * k))
    return pe, ae, s


def fit(aI, aQ):
    """アナログ部の I/Q の違いを、遅延差 τ と利得差 g で近似する（af.py と同じ）"""
    m = (F >= BAND[0]) & (F <= BAND[1]); r = aI[m] / aQ[m]; f = F[m]
    tau = -np.sum(f * np.angle(r)) / np.sum(f * f) / (2 * np.pi)
    return tau, np.exp(np.mean(np.log(np.abs(r))))


def main():
    fI, fQ = fir()
    nI, nQ = analog()
    mI, mQ = analog(1.03, 0.97)
    tau, g = fit(mI, mQ)
    iqd, iqa = -tau * 1e6, -20 * math.log10(g)          # ファームウェアに入れる値（iqd µs・iqa dB）
    cI, cQ = fir(iqd, iqa)
    cases = [
        ('FIR だけ（U3 の計算）', fI, fQ, 'C0', '-'),
        ('FIR＋アナログ部（定数どおり）', fI * nI, fQ * nQ, 'C2', '-'),
        ('RC が I +3%・Q −3%（補正なし）', fI * mI, fQ * mQ, 'C3', '--'),
        (f'同上を iqd {iqd:+.2f}・iqa {iqa:+.2f} で補正', cI * mI, cQ * mQ, 'C1', '-'),
    ]
    fp = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=fp).get_name()
    fig, ax = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    m = (F >= BAND[0]) & (F <= BAND[1])
    print('通過域 300〜2700 Hz での最悪値')
    for name, I, Q, col, ls in cases:
        pe, ae, s = metrics(I, Q)
        ax[0].plot(F, pe, col, ls=ls, label=name)
        ax[1].plot(F, ae, col, ls=ls, label=name)
        ax[2].plot(F, np.minimum(s, 90), col, ls=ls, label=name)
        print(f'  {name}: 位相誤差 {np.max(np.abs(pe[m])):.3f}°  振幅差 {np.max(np.abs(ae[m])):.3f} dB  抑圧 {np.min(s[m]):.1f} dB')
    for a in ax:
        a.axvspan(*BAND, color='0.92', zorder=0); a.grid(True, alpha=0.4)
    ax[0].set_ylabel('位相誤差 [°]\n（I−Q 位相差 − 90°）'); ax[0].set_ylim(-2.5, 0.5)
    ax[1].set_ylabel('振幅差 I/Q [dB]'); ax[1].set_ylim(-1, 1)
    ax[2].set_ylabel('逆側帯波の抑圧 [dB]'); ax[2].set_ylim(0, 90)
    ax[2].axhline(40, color='k', lw=0.8, ls=':'); ax[2].text(120, 41, '40 dB', fontsize=9)
    ax[2].set_xlabel('音声周波数 [Hz]（灰色は通過域 300〜2700 Hz）'); ax[2].set_xlim(F[0], F[-1])
    ax[0].legend(fontsize=9, loc='upper center')
    fig.suptitle('PSN_TRX Ver 2.0 送信 AF の I/Q 位相差（シミュレーション）')
    fig.tight_layout()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iq_scan.png')
    fig.savefig(out, dpi=110); print('→', out)


if __name__ == '__main__':
    main()
