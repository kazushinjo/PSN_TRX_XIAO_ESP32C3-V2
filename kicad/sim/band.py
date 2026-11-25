"""バンドの全域（50.07〜52.90MHz）での受信・送信の計算（2026-11-25、周波数範囲を 52.9MHz まで広げたときの確認）
  JARL のバンドプラン（令和 7 年 7 月 17 日施行）: 50.07〜51.00MHz 狭帯域（SSB）、51.00〜52.90MHz 全電波型式（AM はここ）
  1. 受信の前段（TC1・TC2）を 50.5MHz と 51.45MHz（50.07〜52.9MHz の中央付近）で合わせたときの周波数特性
  2. 第 1 局発 L3（38.07〜40.9MHz）を 38.5MHz と 39.45MHz で合わせたときの U1 のキャリア入力
  3. 送信（L12〜L14 は 50.5MHz に合わせたまま）の出力と高調波。2 倍波トラップ TC4 を 6.5pF（今の計算の値）と 5.4pF（2 倍波が 103MHz = 51.5MHz × 2 で最小）で
回路・仮定は rx.py・blocks.py・full.py と同じ（full.py の 50.5MHz を各周波数に置き換えて計算する）。
"""
import os, io, contextlib, math
import ngs
with contextlib.redirect_stdout(io.StringIO()):
    import rx, blocks
db = lambda x: 20 * math.log10(max(abs(x), 1e-30))
FS = [50.07e6, 50.5e6, 51.0e6, 51.5e6, 52.0e6, 52.5e6, 52.9e6]
fmt = lambda vals: '  '.join(f'{f/1e6:.2f}: {x:+.1f}' for f, x in zip(FS, vals))

print('## バンドの全域（50.07〜52.90MHz）での確認（band.py）')
print('### 受信の前段（アンテナ → 混合器の入力、50.5MHz を 0dB とした利得 dB）')
for fc in (50.5e6, 51.45e6):
    rx.F0 = fc
    a, b = rx.tune(); fe = rx.front(a, b)
    rx.F0 = 50.5e6
    ref = abs(rx.resp(fe, 50.5e6, 50.5e6, 1)[1][0])
    print(f'  TC1・TC2 を {fc/1e6:.2f}MHz で合わせる（TC1 {a*1e12:.2f}pF・TC2 {b*1e12:.2f}pF）: '
          + fmt([db(abs(rx.resp(fe, f, f, 1)[1][0]) / ref) for f in FS]))

print('### 第 1 局発 L3（U1 のキャリア入力、L3 を 38.5MHz に合わせたときの 38.5MHz を 0dB。表示は受信周波数）')
def lo_tune(target):
    best = None
    for k in range(51):
        lp = blocks.L7_MIN + (blocks.L7_MAX - blocks.L7_MIN) * k / 50
        fr, h, pk = blocks.ac_peak(blocks.lo_net(lp), blocks.pin('C10', '2'), 30e6, 47e6, 171)
        if best is None or abs(pk - target) < abs(best[1] - target): best = (lp, pk, fr, h)
    return best
_, _, fr0, h0 = lo_tune(38.5e6); ref = abs(blocks.at(fr0, h0, 38.5e6))
for tgt in (38.5e6, 39.45e6):
    lp, pk, fr, h = lo_tune(tgt)
    print(f'  L3 {lp*1e6:.3f}µH（同調 {pk/1e6:.2f}MHz = 受信 {(pk+12e6)/1e6:.2f}MHz）: '
          + fmt([db(abs(blocks.at(fr, h, f - 12e6)) / ref) for f in FS]))

print('### 送信（電源 12V、L12〜L14 は 50.5MHz に合わせたまま。出力 W・2 倍波 dBc）')
src = (open('full.py', encoding='utf-8').read().replace('50.5e6', 'FTX').replace('101e6', '2*FTX')
       .replace('6.5e-12', 'TC4').replace("if __name__ == '__main__':", 'if False:'))
ns = {'__name__': 'full_band', 'FTX': 50.5e6, 'TC4': 6.5e-12}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, 'full_band', 'exec'), ns)
if 'lpf_h' in ns:                                   # 5W 版: 高調波は C98 の点の電圧 × LPF の通り方
    from rf import lpf
    _H = {}
    def lpf_h(m):
        k = (ns['FTX'], ns['TC4'], m)
        if k not in _H:
            ngs.run(lpf(1.0, 18e-12, 11e-12, 1.0, ns['TC4'], fr=ns['FTX'] * m))
            _H[k] = ngs.vec(blocks.pin('C102', '1'))[0] / ngs.vec(blocks.pin('C98', '1'))[0]
        return _H[k]
    ns['lpf_h'] = lpf_h
for vi in (0.2, 0.8):
    for tc4 in (6.5e-12, 5.4e-12):
        ns['TC4'] = tc4
        out = []
        for f in FS:
            ns['FTX'] = f
            r = ns['tx_point'](vi=vi, vq=0)
            h2 = r[2][0] if isinstance(r[2], list) else db(r[2] / abs(r[0]))
            out.append(f'{f/1e6:.2f}: {r[1]:.2f}W {h2:+.0f}dBc')
        print(f'  音声 {vi*1e3:.0f}mV・TC4 {tc4*1e12:.1f}pF: ' + '  '.join(out))
