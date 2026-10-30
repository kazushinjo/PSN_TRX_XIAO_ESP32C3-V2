"""不要側波帯（逆側帯波）の抑圧比をグラフにする（Ver 2.0）

  上: 音声周波数ごとの抑圧比（iq_scan.py と同じ計算: U3 の複素 FIR × PDM 出力〜変調器入力のアナログ部）
  下: 1 kHz の試験トーン（tone 1000、USB）を送信したときの、搬送波付近のスペクトルの見え方
  RF 側（Si5351 の 2 出力の位相・変調器の平衡）のずれは基板の計算に入らないので、参考に 1°・0.1 dB の場合を重ねる。

  使い方: kicad/sim で  <numpy と matplotlib の入った python3> sideband.py  → sideband_suppression.png
"""
import math, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import iq_scan as s

s.F = np.linspace(100, 3200, 621)
F = s.F


def supp(I, Q):
    return np.minimum(s.metrics(I, Q)[2], 90)


def main():
    fI, fQ = s.fir()
    nI, nQ = s.analog()
    mI, mQ = s.analog(1.03, 0.97)
    tau, g = s.fit(mI, mQ)
    iqd, iqa = -tau * 1e6, -20 * math.log10(g)
    cI, cQ = s.fir(iqd, iqa)
    rf = 10 ** (0.1 / 20) * np.exp(1j * math.radians(1.0))     # RF 側 1°・0.1 dB
    cases = [
        ('定数どおり（FIR＋アナログ部）', fI * nI, fQ * nQ, 'C2', '-'),
        ('RC が I +3%・Q −3%（iqd・iqa の補正なし）', fI * mI, fQ * mQ, 'C3', '--'),
        (f'同上を iqd {iqd:+.2f} µs・iqa {iqa:+.2f} dB で補正', cI * mI, cQ * mQ, 'C1', '-'),
        ('参考: さらに RF 側に 1°・0.1 dB のずれ', cI * mI * rf, cQ * mQ, 'C0', ':'),
    ]
    fp = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=fp).get_name()
    fig, ax = plt.subplots(2, 1, figsize=(9, 9.5), gridspec_kw=dict(height_ratios=[1.15, 1]))

    # 上: 抑圧比 対 音声周波数
    a = ax[0]
    a.axvspan(*s.BAND, color='0.92', zorder=0)
    m = (F >= s.BAND[0]) & (F <= s.BAND[1])
    print('通過域 300〜2700 Hz での抑圧比の最悪値 / 1 kHz での値')
    for name, I, Q, col, ls in cases:
        sp = supp(I, Q)
        a.plot(F, sp, col, ls=ls, lw=1.8, label=f'{name}（最悪 {np.min(sp[m]):.0f} dB）')
        print(f'  {name}: {np.min(sp[m]):.1f} dB / {np.interp(1000, F, sp):.1f} dB')
    a.axhline(40, color='k', lw=0.8, ls=':'); a.text(2950, 41, '40 dB', fontsize=9)
    a.set_xlim(F[0], F[-1]); a.set_ylim(0, 90)
    a.set_xlabel('音声周波数 [Hz]（灰色は通過域 300〜2700 Hz）')
    a.set_ylabel('不要側波帯の抑圧比 [dB]')
    a.set_title('音声周波数ごとの抑圧比（90 dB で打ち切り）', fontsize=11)
    a.grid(True, alpha=0.4); a.legend(fontsize=8.5, loc='lower center')

    # 下: 1 kHz トーンを USB で送信したときのスペクトル（搬送波からの離調）
    a = ax[1]
    shown = cases
    w = 0.1
    for k, (name, I, Q, col, ls) in enumerate(shown):
        sp = float(np.interp(1000, F, supp(I, Q)))
        x = (k - 1.5) * w
        a.vlines([1 + x], -100, 0, color=col, lw=3)
        a.vlines([-1 + x], -100, -sp, color=col, lw=3, label=f'{name}: −{sp:.0f} dB')
        a.text(-1 + x, -sp + 2, f'−{sp:.0f}', ha='center', fontsize=9, color=col)
    a.text(1, 3, '希望波（USB）0 dB', ha='center', fontsize=9)
    a.text(-1, 6, '不要側波帯（LSB 側）', ha='center', fontsize=9)
    a.axvline(0, color='0.5', lw=0.8, ls='--'); a.text(0.05, -96, '搬送波の位置', fontsize=8.5, color='0.4')
    a.set_xlim(-3.5, 3.5); a.set_ylim(-100, 12)
    a.set_xlabel('搬送波からの周波数 [kHz]'); a.set_ylabel('相対レベル [dB]')
    a.set_title('試験トーン 1 kHz（tone 1000、USB）を送信したときのスペクトル', fontsize=11)
    a.grid(True, alpha=0.4); a.legend(fontsize=8.5, loc='upper right', bbox_to_anchor=(1, 0.78))

    fig.suptitle('PSN_TRX Ver 2.0 不要側波帯の抑圧比（シミュレーション）', fontsize=13)
    fig.text(0.01, 0.005, '計算: U3 の複素 FIR（tx_dsp.cpp と同じ係数）× PDM 出力〜変調器入力（ngspice）。'
             '搬送波の漏れと RF 側のずれ（参考の線を除く）は含まない。', fontsize=8, color='0.35')
    fig.tight_layout(rect=(0, 0.02, 1, 0.98))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sideband_suppression.png')
    fig.savefig(out, dpi=110); print('→', out)


if __name__ == '__main__':
    main()
