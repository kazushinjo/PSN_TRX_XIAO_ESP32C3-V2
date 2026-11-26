# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 JA6FUF (kazushinjo)
"""
PSN TRX V2（50MHz 帯 SSB/AM、定格 1W）の新スプリアス規格の測定を、RIGOL DSA815-TG（LAN 接続）で自動化する。

測定の考え方は JARD「アマチュア無線機の測定 〜スプリアス発射および不要発射〜」（2019-04-25）に合わせた:
  1. 搬送波電力（基準）          … 無変調（J3E は 1.5kHz の単一トーン、A3E は搬送波だけ）
  2. 帯域外領域のスプリアス発射  … 無変調、fc ± 62.5kHz（50MHz 帯の J3E・A3E）、検波 PEAK
  3. スプリアス領域の不要発射    … 変調（擬似音声）をかけて MAX HOLD、9kHz〜1GHz（表 4）、RBW は表 6
許容値（無線設備規則 別表第三号、JARD 資料の表 3・表 7、50MHz 帯）:
  定格 1W 以下      : 帯域外 -10dBm 以下（100μW）           / スプリアス -13dBm 以下（50μW）
  1W を超え 50W 以下 : 帯域外 0dBm 以下 かつ -60dBc 以下      / スプリアス -60dBc 以下
  50W を超える       : 帯域外 0dBm 以下 かつ -60dBc 以下      / スプリアス -13dBm 以下 または -70dBc 以下

使い方（詳しくは同じフォルダの README.md）:
  python jard_spurious.py --host 192.168.0.50 idn
  python jard_spurious.py --host 192.168.0.50 pathloss              # TG で減衰器・ケーブルの損失を測る（任意）
  python jard_spurious.py --host 192.168.0.50 measure --freq 50.2 --mode J3E --rated-w 1 --att-db 30
  python jard_spurious.py --dry-run measure --freq 50.2 --mode J3E   # 測定器なしで流れと出力を確かめる
"""
import argparse, csv, datetime, json, math, os, random, socket, sys, time

# ------------------------------------------------------------------
# 規格（JARD 資料の別紙 表 1〜7、50MHz 帯）
# ------------------------------------------------------------------
OOB_HALF_HZ = 62.5e3                       # 表 1: 50MHz/144MHz 帯の J3E・A3E の帯域外領域 ±62.5kHz
NEC_BW_HZ = {'J3E': 3000.0, 'A3E': 6000.0}  # 表 1: 必要周波数帯幅（占有周波数帯幅）
SPUR_SEGMENTS = [                          # 表 4（送信 9kHz〜100MHz → 9kHz〜1GHz）・表 6（RBW）
    (9e3,    150e3, 1e3),
    (150e3,  30e6,  10e3),
    (30e6,   1e9,   100e3),
]
NEAR_SPAN_HZ = 4e6        # 基本波の近く（帯域外領域の外側 〜 ±2MHz）は RBW を絞って別に掃引する
NEAR_RBW_HZ = 10e3        # RBW 100kHz だと搬送波のすそが ±62.5kHz の外にかかるため（CW 性のスプリアスの値は同じ）


def limits(rated_w, carrier_dbm):
    """(帯域外の許容値 dBm, スプリアスの許容値 dBm, 帯域外の文言, スプリアスの文言)"""
    if rated_w <= 1.0:
        return -10.0, -13.0, '-10dBm 以下（100μW 以下）', '-13dBm 以下（50μW 以下）'
    oob = min(0.0, carrier_dbm - 60.0)
    if rated_w <= 50.0:
        return oob, carrier_dbm - 60.0, '0dBm 以下 かつ -60dBc 以下', '-60dBc 以下'
    return oob, max(-13.0, carrier_dbm - 70.0), '0dBm 以下 かつ -60dBc 以下', '-13dBm 以下 または -70dBc 以下'


# ------------------------------------------------------------------
# DSA815（LAN、SCPI のソケット）
# ------------------------------------------------------------------
class DSA815:
    def __init__(self, host, port=5555, timeout=20.0, log=None):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(timeout)
        self.log = log
        self.snap_ok = True

    def write(self, cmd):
        if self.log: self.log(f'> {cmd}')
        self.s.sendall((cmd + '\n').encode('ascii'))

    def _readline(self):
        buf = b''
        while not buf.endswith(b'\n'):
            ch = self.s.recv(65536)
            if not ch: break
            buf += ch
        return buf

    def query(self, cmd):
        self.write(cmd)
        r = self._readline().decode('ascii', 'replace').strip()
        if self.log: self.log(f'< {r[:120]}')
        return r

    def _read_block(self):
        """IEEE 488.2 の #NLLLL... ブロックを読む"""
        head = b''
        while len(head) < 2: head += self.s.recv(2 - len(head))
        if head[:1] != b'#': raise IOError(f'block header {head!r}')
        n = int(head[1:2])
        ln = b''
        while len(ln) < n: ln += self.s.recv(n - len(ln))
        size = int(ln)
        data = b''
        while len(data) < size: data += self.s.recv(min(65536, size - len(data)))
        try:
            self.s.settimeout(0.3); self.s.recv(16)       # 末尾の改行
        except socket.timeout:
            pass
        finally:
            self.s.settimeout(20.0)
        return data

    def opc(self):
        return self.query('*OPC?')

    def idn(self):
        return self.query('*IDN?')

    def setup(self, start=None, stop=None, center=None, span=None, rbw=None, vbw=None,
              ref_dbm=None, offset_db=None, att_db=None, points=3001, det='POSitive'):
        self.write(':INITiate:CONTinuous OFF')
        self.write(':UNIT:POWer DBM')
        if offset_db is not None: self.write(f':DISPlay:WINdow:TRACe:Y:SCALe:RLEVel:OFFSet {offset_db:.2f}')
        if ref_dbm is not None: self.write(f':DISPlay:WINdow:TRACe:Y:SCALe:RLEVel {ref_dbm:.1f}')
        if att_db is not None: self.write(f':SENSe:POWer:RF:ATTenuation {att_db:.0f}')
        if center is not None: self.write(f':SENSe:FREQuency:CENTer {center:.0f}')
        if span is not None: self.write(f':SENSe:FREQuency:SPAN {span:.0f}')
        if start is not None: self.write(f':SENSe:FREQuency:STARt {start:.0f}')
        if stop is not None: self.write(f':SENSe:FREQuency:STOP {stop:.0f}')
        if rbw is not None: self.write(f':SENSe:BANDwidth:RESolution {rbw:.0f}')
        if vbw is not None: self.write(f':SENSe:BANDwidth:VIDeo {vbw:.0f}')
        self.write(f':SENSe:DETector:FUNCtion {det}')
        self.write(f':SENSe:SWEep:POINts {points}')
        self.write(':SENSe:SWEep:TIME:AUTO ON')
        self.opc()

    def actual(self):
        """実際に設定された値（RBW は機種で下限がある）"""
        return {
            'start': float(self.query(':SENSe:FREQuency:STARt?')),
            'stop': float(self.query(':SENSe:FREQuency:STOP?')),
            'rbw': float(self.query(':SENSe:BANDwidth:RESolution?')),
            'vbw': float(self.query(':SENSe:BANDwidth:VIDeo?')),
            'points': int(float(self.query(':SENSe:SWEep:POINts?'))),
            'sweep_s': float(self.query(':SENSe:SWEep:TIME?')),
            'att': float(self.query(':SENSe:POWer:RF:ATTenuation?')),
            'offset': float(self.query(':DISPlay:WINdow:TRACe:Y:SCALe:RLEVel:OFFSet?')),
        }

    def maxhold(self, seconds=None, sweeps=None, progress=None):
        self.write(':TRACe1:MODE WRITe')
        self.write(':INITiate:IMMediate'); self.opc()
        self.write(':TRACe1:MODE MAXHold')
        t0 = time.time(); k = 0
        while True:
            self.write(':INITiate:IMMediate'); self.opc(); k += 1
            if progress: progress(k, time.time() - t0)
            if sweeps is not None and k >= sweeps: break
            if seconds is not None and time.time() - t0 >= seconds: break
            if sweeps is None and seconds is None: break
        return k

    def trace(self):
        self.write(':FORMat:TRACe:DATA ASCii')
        self.write(':TRACe:DATA? TRACE1')
        raw = self._readline().decode('ascii', 'replace').strip()
        if raw.startswith('#'):
            n = int(raw[1]); raw = raw[2 + n:]
        y = [float(v) for v in raw.replace(' ', '').split(',') if v]
        a = self.actual()
        x = [a['start'] + (a['stop'] - a['start']) * i / (len(y) - 1) for i in range(len(y))]
        return x, y, a

    usb_dir = None                            # --usb-snap: 測定器の USB メモリにも画面を保存（例 'E:'）

    def screenshot(self, path):
        """測定器の画面を PNG/BMP で保存（:PRIVate:SNAP? は公開マニュアルにない命令なので、だめなら諦める）"""
        if self.usb_dir:
            name = os.path.splitext(os.path.basename(path))[0][:20] + '.png'
            self.write(f':MMEMory:STORe:SCReen {self.usb_dir}' + '\\' + name); self.opc()
            print(f'  測定器の USB メモリに保存: {self.usb_dir}' + '\\' + name)
        if not self.snap_ok: return None
        try:
            self.write(':PRIVate:SNAP? BMP')
            data = self._read_block()
            p = os.path.splitext(path)[0] + '.bmp'
            open(p, 'wb').write(data)
            try:
                from PIL import Image
                Image.open(p).save(os.path.splitext(path)[0] + '.png'); os.remove(p)
                p = os.path.splitext(path)[0] + '.png'
            except Exception:
                pass
            return p
        except Exception as e:
            print(f'  （測定器の画面の取り込みはできませんでした: {e}。グラフの PNG だけ作ります。'
                  f'提出用に画面が要るときは、測定器の Print で USB メモリに保存してください）')
            self.snap_ok = False
            return None

    def tg(self, on, level_dbm=-10):
        if on:
            self.write(f':SOURce:POWer:LEVel:IMMediate:AMPLitude {level_dbm}')
            self.write(':OUTPut:STATe ON')
        else:
            self.write(':OUTPut:STATe OFF')
        self.opc()


class FakeDSA815:
    """--dry-run 用: 1W の送信機らしいスペクトルを作って返す（スクリプトの流れと出力の確認だけに使う）"""
    def __init__(self, carrier_dbm=30.0, fc=50.2e6, mode='J3E'):
        self.p = carrier_dbm; self.fc = fc; self.mode = mode
        self.cfg = dict(start=9e3, stop=1e9, rbw=100e3, vbw=100e3, points=3001, att=30, offset=0, sweep_s=0.1)
        self.snap_ok = False; self.tg_on = False; self.tone = True

    def idn(self): return 'RIGOL TECHNOLOGIES,DSA815 (DRY RUN),DSA8A000000000,00.01.19'
    def opc(self): return '1'
    def write(self, c): pass

    def setup(self, start=None, stop=None, center=None, span=None, rbw=None, vbw=None,
              ref_dbm=None, offset_db=None, att_db=None, points=3001, det='POSitive'):
        if center is not None and span is not None: start, stop = center - span / 2, center + span / 2
        if start is not None: self.cfg['start'] = max(9e3, start)
        if stop is not None: self.cfg['stop'] = stop
        if rbw is not None: self.cfg['rbw'] = max(100.0, rbw)   # DSA815 の RBW の下限は 100Hz
        if vbw is not None: self.cfg['vbw'] = max(1.0, vbw)
        if offset_db is not None: self.cfg['offset'] = offset_db
        if att_db is not None: self.cfg['att'] = att_db
        self.cfg['points'] = points

    def actual(self): return dict(self.cfg)
    def maxhold(self, seconds=None, sweeps=None, progress=None):
        if progress: progress(1, 0.0)
        return 1

    def set_tone(self, on): self.tone = on

    def _lines(self):
        fc = self.fc + (1500 if self.mode == 'J3E' else 0)
        if self.mode == 'J3E' and not self.tone:           # 無変調の J3E: 抑圧した搬送波の漏れだけ
            return [(self.fc, self.p - 50)]
        L = [(fc, self.p)]
        if self.mode == 'J3E': L.append((self.fc - 1500, self.p - 45)); L.append((self.fc, self.p - 50))
        else: L.append((self.fc - 4000, self.p - 55))
        for n, d in [(2, 72), (3, 80), (4, 95), (5, 98)]: L.append((n * fc, self.p - d))
        L.append((fc - 12e6, self.p - 85))           # 12MHz の IF 関係を模したもの
        return L

    def trace(self):
        c = self.cfg; n = c['points']; rbw = c['rbw']
        noise = -135 + 10 * math.log10(rbw / 100.0) + c['att'] + c['offset'] - 20
        x = [c['start'] + (c['stop'] - c['start']) * i / (n - 1) for i in range(n)]
        bin_w = (c['stop'] - c['start']) / (n - 1)
        y = []
        for f in x:
            v = 10 ** ((noise + random.uniform(-2, 4)) / 10)
            for fl, pl in self._lines():
                d = abs(f - fl) - bin_w / 2
                if d < 0: d = 0
                v += 10 ** ((pl - 60 * min(1.0, (d / (2.5 * rbw)) ** 2)) / 10) if d < 2.5 * rbw else 0
            y.append(10 * math.log10(v))
        return x, y, dict(c)

    def screenshot(self, path): return None
    def tg(self, on, level_dbm=-10): self.tg_on = on


# ------------------------------------------------------------------
# リグ（XIAO のシリアル、任意）
# ------------------------------------------------------------------
class Rig:
    def __init__(self, port):
        import serial                         # pyserial
        self.s = serial.Serial(port, 115200, timeout=0.3)
        time.sleep(0.3); self.s.reset_input_buffer()

    def cmd(self, line):
        self.s.write((line + '\n').encode()); time.sleep(0.4)
        out = self.s.read(4096).decode('utf-8', 'replace')
        return '\n'.join(l for l in out.splitlines() if not l.startswith('rssi'))

    def close(self): self.s.close()


# ------------------------------------------------------------------
# 補正（減衰器・ケーブルの損失）
# ------------------------------------------------------------------
class PathLoss:
    def __init__(self, att_db, table=None):
        self.att = att_db; self.t = table or []   # [(Hz, dB)]

    @classmethod
    def load(cls, path, att_db):
        t = []
        with open(path, encoding='utf-8') as f:
            for r in csv.DictReader(f): t.append((float(r['freq_hz']), float(r['loss_db'])))
        return cls(att_db, sorted(t))

    def at(self, f):
        if not self.t: return self.att
        if f <= self.t[0][0]: return self.t[0][1]
        if f >= self.t[-1][0]: return self.t[-1][1]
        for (f0, l0), (f1, l1) in zip(self.t, self.t[1:]):
            if f0 <= f <= f1: return l0 + (l1 - l0) * (f - f0) / (f1 - f0)
        return self.att


# ------------------------------------------------------------------
# 図
# ------------------------------------------------------------------
def plot(path, x, y, title, limit_dbm=None, mask=None, marks=(), xlabel_mhz=True, ref=None, note=''):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    jp = [n for n in ('Yu Gothic', 'Meiryo', 'MS Gothic', 'Hiragino Sans', 'Noto Sans CJK JP', 'IPAexGothic') if n in have]
    plt.rcParams['font.family'] = jp[:1] + ['sans-serif']
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=110)
    xs = [v / 1e6 for v in x] if xlabel_mhz else x
    ax.plot(xs, y, lw=0.8, color='#1f5fbf')
    if limit_dbm is not None:
        ax.axhline(limit_dbm, color='#c62828', lw=1.2, ls='--', label=f'許容値 {limit_dbm:.1f} dBm')
    if mask:
        for a, b in mask:
            ax.axvspan(a / 1e6, b / 1e6, color='#999999', alpha=0.18)
    for f, v, lab in marks:
        ax.plot([f / 1e6], [v], 'v', color='#c62828', ms=7)
        ax.annotate(lab, (f / 1e6, v), textcoords='offset points', xytext=(4, 6), fontsize=8)
    if ref is not None: ax.set_ylim(ref - 100, ref + 5)
    ax.set_xlabel('周波数 [MHz]'); ax.set_ylabel('レベル [dBm]（減衰器の分を補正済み）')
    ax.set_title(title, fontsize=11)
    ax.grid(True, alpha=0.35)
    if limit_dbm is not None: ax.legend(loc='upper right', fontsize=9)
    if note: fig.text(0.01, 0.01, note, fontsize=7.5, color='#444444')
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path); plt.close(fig)


def fmt_mhz(f): return f'{f / 1e6:.4f}'


def peaks(x, y, n=8, exclude=(), min_sep=None):
    """除外範囲の外で大きい順に n 個（近いものはまとめる）"""
    idx = [i for i in range(len(x)) if not any(a <= x[i] <= b for a, b in exclude)]
    idx.sort(key=lambda i: -y[i])
    sep = min_sep or (x[-1] - x[0]) / 200
    out = []
    for i in idx:
        if all(abs(x[i] - x[j]) > sep for j in out): out.append(i)
        if len(out) >= n: break
    return [(x[i], y[i]) for i in out]


# ------------------------------------------------------------------
# 測定の手順
# ------------------------------------------------------------------
def ask(msg, auto):
    print('\n' + msg)
    if auto: print('  （--yes: そのまま続けます）'); return
    input('  準備ができたら Enter > ')


def measure(sa, a, out, rig=None):
    fc = a.freq * 1e6
    mode = a.mode
    pl = PathLoss.load(a.pathloss, a.att_db) if a.pathloss else PathLoss(a.att_db)
    off_fc = pl.at(fc)
    corr = lambda f: pl.at(f) - off_fc            # 測定器のオフセット（fc の損失）からの差
    res = dict(freq_mhz=a.freq, mode=mode, rated_w=a.rated_w, att_db=a.att_db, offset_at_fc_db=off_fc,
               int_att_db=a.int_att, started=datetime.datetime.now().isoformat(timespec='seconds'))
    note = f'{mode} {a.freq:.4f}MHz  定格 {a.rated_w:g}W  外部減衰 {off_fc:.1f}dB  内部 ATT {a.int_att:g}dB  {res["started"]}'
    try:
        res['idn'] = sa.idn()
    except Exception as e:
        res['idn'] = f'? ({e})'
    print(f'測定器: {res["idn"]}')

    # ---- 1. 搬送波電力（無変調） ----
    if rig:
        print(rig.cmd(f'freq {int(round(fc))}'))
        print(rig.cmd('sb usb' if mode == 'J3E' else 'sb am'))
        print(rig.cmd('tone 1500' if mode == 'J3E' else 'tone 0'))
    unmod = ('リグを「無変調」にします: J3E はシリアルで tone 1500（1.5kHz の単一トーン、マイクは外すか音を入れない）、'
             'A3E は tone 0 でマイクに音を入れない（搬送波だけ）。' if not rig else
             'リグに freq・sb・tone を送りました（J3E は tone 1500、A3E は tone 0。マイクに音を入れない）。')
    ask(f'[1/3] 搬送波電力と帯域外領域（無変調）\n  {unmod}\n  ダミーロード側の減衰器を通して DSA815 につなぎ、PTT を押して送信したままにしてください。', a.yes)
    sa.setup(center=fc + (1500 if mode == 'J3E' else 0), span=50e3, rbw=1e3, vbw=1e3,
             ref_dbm=a.ref, offset_db=off_fc, att_db=a.int_att, points=601)
    sa.maxhold(sweeps=3)
    x, y, act = sa.trace()
    i = max(range(len(y)), key=lambda k: y[k])
    pc, fpk = y[i], x[i]
    res['carrier'] = dict(freq_hz=fpk, dbm=pc, watt=10 ** ((pc - 30) / 10))
    print(f'  搬送波電力: {pc:.2f} dBm（{10 ** ((pc - 30) / 10):.2f} W） @ {fmt_mhz(fpk)} MHz')
    lim_oob, lim_sp, txt_oob, txt_sp = limits(a.rated_w, pc)
    res['limits'] = dict(oob_dbm=lim_oob, spur_dbm=lim_sp, oob_text=txt_oob, spur_text=txt_sp)
    sa.screenshot(os.path.join(out, '1_carrier.png'))
    plot(os.path.join(out, '1_carrier_graph.png'), x, y, f'搬送波電力（無変調） {pc:.2f} dBm', ref=pc,
         marks=[(fpk, pc, f'{pc:.2f} dBm')], note=note)
    ref = math.ceil(pc + 3)

    # ---- 2. 帯域外領域（無変調） ----
    if mode == 'J3E' and a.j3e_oob == 'none':
        if rig: print(rig.cmd('tone 0'))
        ask('  J3E の帯域外領域は、変調をかけない状態（tone 0、マイクに音を入れない）で測ります。'
            '\n  PTT を押したまま（押し直してもよい）にしてください。', a.yes)
        getattr(sa, 'set_tone', lambda on: None)(False)
    bn = NEC_BW_HZ[mode]
    nec = (fc, fc + bn) if mode == 'J3E' else (fc - bn / 2, fc + bn / 2)   # 必要周波数帯幅（USB は上側）
    span = 2 * OOB_HALF_HZ * 1.2
    sa.setup(center=fc, span=span, rbw=a.oob_rbw, vbw=a.oob_rbw, ref_dbm=ref, points=3001)
    act = sa.actual()
    print(f'  帯域外領域: fc ±{OOB_HALF_HZ / 1e3:.1f}kHz、RBW {act["rbw"]:.0f}Hz、掃引 {act["sweep_s"]:.1f}s × {a.oob_sweeps} 回（MAX HOLD）')
    sa.maxhold(sweeps=a.oob_sweeps, progress=lambda k, t: print(f'    掃引 {k}/{a.oob_sweeps}', end='\r'))
    print()
    x, y, act = sa.trace()
    inside = [(xi, yi) for xi, yi in zip(x, y) if fc - OOB_HALF_HZ <= xi <= fc + OOB_HALF_HZ and not (nec[0] <= xi <= nec[1])]
    fw, yw = max(inside, key=lambda t: t[1])
    floor = sorted(v for _, v in inside)[len(inside) // 10]
    ok = yw <= lim_oob
    res['oob'] = dict(freq_hz=fw, dbm=yw, dbc=yw - pc, limit_dbm=lim_oob, ok=ok, rbw=act['rbw'], noise_dbm=floor,
                      state=('トーンなし' if mode == 'J3E' and a.j3e_oob == 'none' else
                             '1.5kHz 単一トーン' if mode == 'J3E' else '搬送波のみ'),
                      range=f'fc±{OOB_HALF_HZ / 1e3:.1f}kHz（必要周波数帯幅 {nec[0] / 1e6:.4f}〜{nec[1] / 1e6:.4f}MHz を除く）')
    if mode == 'J3E':
        near = [(xi, yi) for xi, yi in zip(x, y) if abs(xi - fc) <= 300]
        fl, yl = max(near, key=lambda t: t[1])
        res['oob']['leak'] = dict(freq_hz=fl, dbm=yl, dbc=yl - pc)
        print(f'  （参考）抑圧した搬送波の漏れ: {yl:.1f} dBm（{yl - pc:.1f} dBc） @ {fmt_mhz(fl)} MHz（必要周波数帯幅の下端。帯域外の判定にはこの点も含めている）')
    print(f'  帯域外の最大: {yw:.1f} dBm（{yw - pc:.1f} dBc） @ {fmt_mhz(fw)} MHz → 許容値 {lim_oob:.1f} dBm: {"適合" if ok else "不適合"}')
    if floor > lim_oob - 6: print('  ※ 雑音レベルが許容値に近いので、RBW を下げるか内部 ATT を減らして測り直してください')
    sa.screenshot(os.path.join(out, '2_oob.png'))
    plot(os.path.join(out, '2_oob_graph.png'), x, y,
         f'帯域外領域（無変調） fc ±{OOB_HALF_HZ / 1e3:.1f}kHz  最大 {yw:.1f}dBm（{yw - pc:.1f}dBc）  {"適合" if ok else "不適合"}',
         limit_dbm=lim_oob, mask=[nec, (x[0], fc - OOB_HALF_HZ), (fc + OOB_HALF_HZ, x[-1])],
         marks=[(fw, yw, f'{yw:.1f}dBm')], ref=ref, note=note + f'  RBW {act["rbw"]:.0f}Hz  灰色 = 判定から外す範囲')
    save_csv(os.path.join(out, '2_oob.csv'), x, y)

    # ---- 3. スプリアス領域（変調） ----
    if rig:
        print(rig.cmd('tone 0'))
    getattr(sa, 'set_tone', lambda on: None)(True)
    mod = ('J3E: 1.5kHz の正弦波で空中線電力が飽和の 80% になる入力レベルにしてから、同じレベルの擬似音声に切り替える。'
           if mode == 'J3E' else
           'A3E: 1kHz の正弦波で変調度 60%（側波帯が搬送波の -10.5dBc）にしてから、同じレベルの擬似音声に切り替える。')
    ask(f'[2/3] スプリアス領域（変調をかける、JARD 資料の表 5）\n  {mod}\n'
        f'  擬似音声をマイク端子に入れ続け、PTT を押したままにしてください（各区間 {a.hold:g} 秒 MAX HOLD）。', a.yes)
    excl = (fc - OOB_HALF_HZ, fc + OOB_HALF_HZ)
    found = []
    for k, (f0, f1, rbw) in enumerate(SPUR_SEGMENTS, 1):
        rbw_use = min(rbw, a.spur_rbw_max) if a.spur_rbw_max else rbw
        sa.setup(start=f0, stop=f1, rbw=rbw_use, vbw=rbw_use, ref_dbm=ref, points=3001)
        act = sa.actual()
        print(f'  区間 {k}: {f0 / 1e6:g}〜{f1 / 1e6:g} MHz  RBW {act["rbw"] / 1e3:g}kHz  掃引 {act["sweep_s"]:.2f}s')
        sa.maxhold(seconds=a.hold, progress=lambda n, t: print(f'    {t:5.1f}s / {a.hold:g}s', end='\r'))
        print()
        x, y, act = sa.trace()
        y = [v + corr(f) for f, v in zip(x, y)]
        ex = [(fc - NEAR_SPAN_HZ / 2, fc + NEAR_SPAN_HZ / 2)] if f0 <= fc <= f1 else []
        pk = peaks(x, y, n=6, exclude=ex)
        floor = sorted(y)[len(y) // 10]
        found += [(f, v, act['rbw'], k) for f, v in pk]
        sa.screenshot(os.path.join(out, f'3_spur_{k}.png'))
        plot(os.path.join(out, f'3_spur_{k}_graph.png'), x, y,
             f'スプリアス領域（変調・MAX HOLD） {f0 / 1e6:g}〜{f1 / 1e6:g} MHz  RBW {act["rbw"] / 1e3:g}kHz',
             limit_dbm=lim_sp, mask=ex, marks=[(f, v, f'{fmt_mhz(f)}MHz {v:.1f}dBm') for f, v in pk[:3]],
             ref=ref, note=note + f'  雑音 約 {floor:.0f}dBm' + ('  灰色 = 基本波の近く（区間 N で測る）' if ex else ''))
        save_csv(os.path.join(out, f'3_spur_{k}.csv'), x, y)
        if floor > lim_sp - 6: print(f'  ※ この区間の雑音（約 {floor:.0f}dBm）が許容値に近い。--spur-rbw-max で RBW を絞るか内部 ATT を下げる')

    # 基本波の近く（帯域外領域の外側 〜 ±2MHz）
    sa.setup(center=fc, span=NEAR_SPAN_HZ, rbw=NEAR_RBW_HZ, vbw=NEAR_RBW_HZ, ref_dbm=ref, points=3001)
    print(f'  区間 N: fc ±{NEAR_SPAN_HZ / 2e6:g} MHz（±{OOB_HALF_HZ / 1e3:.1f}kHz の内側は除く）RBW {NEAR_RBW_HZ / 1e3:g}kHz')
    sa.maxhold(seconds=a.hold)
    x, y, act = sa.trace()
    pk = peaks(x, y, n=4, exclude=[excl])
    found += [(f, v, act['rbw'], 'N') for f, v in pk]
    sa.screenshot(os.path.join(out, '3_spur_near.png'))
    plot(os.path.join(out, '3_spur_near_graph.png'), x, y,
         f'スプリアス領域（変調） 基本波の近く fc ±{NEAR_SPAN_HZ / 2e6:g}MHz', limit_dbm=lim_sp, mask=[excl],
         marks=[(f, v, f'{v:.1f}dBm') for f, v in pk[:3]], ref=ref, note=note + '  灰色 = 帯域外領域（判定から外す）')
    save_csv(os.path.join(out, '3_spur_near.csv'), x, y)

    # 高調波と大きいものを、スパンを絞って測り直す
    ask('[3/3] 高調波と大きいスプリアスを、スパンを絞って測り直します（変調・PTT はそのまま）', True)
    targets = [(n * (fc + (1500 if mode == 'J3E' else 0)), f'{n} 倍波') for n in range(2, 11) if n * fc <= 1e9]
    for f, v, rbw, seg in sorted(found, key=lambda t: -t[1])[:a.zoom]:
        if all(abs(f - t) > 1e6 for t, _ in targets): targets.append((f, f'区間 {seg} の最大付近'))
    zoom = []
    for f, label in targets:
        rbw = next(r for f0, f1, r in SPUR_SEGMENTS if f0 <= f <= f1) if f > 9e3 else 1e3
        rbw = min(rbw, a.spur_rbw_max) if a.spur_rbw_max else rbw
        span = max(20 * rbw, 200e3) if f > 30e6 else max(20 * rbw, 20e3)
        sa.setup(center=f, span=span, rbw=rbw, vbw=rbw, ref_dbm=ref, points=601)
        sa.maxhold(seconds=a.zoom_hold)
        x, y, act = sa.trace()
        i = max(range(len(y)), key=lambda k: y[k])
        fv, yv = x[i], y[i] + corr(x[i])
        ok = yv <= lim_sp
        zoom.append(dict(label=label, freq_hz=fv, dbm=yv, dbc=yv - pc, rbw=act['rbw'], ok=ok))
        print(f'  {label:14s} {fmt_mhz(fv):>10s} MHz  {yv:7.1f} dBm  {yv - pc:7.1f} dBc  {"適合" if ok else "不適合"}')
    worst = max(zoom, key=lambda z: z['dbm'])
    res['spur'] = dict(points=zoom, worst=worst, limit_dbm=lim_sp)
    sa.setup(center=worst['freq_hz'], span=max(20 * worst['rbw'], 200e3), rbw=worst['rbw'], vbw=worst['rbw'], ref_dbm=ref, points=601)
    sa.maxhold(seconds=a.zoom_hold)
    x, y, act = sa.trace()
    sa.screenshot(os.path.join(out, '4_spur_worst.png'))
    plot(os.path.join(out, '4_spur_worst_graph.png'), x, [v + corr(f) for f, v in zip(x, y)],
         f'スプリアス領域の最大 {worst["label"]} {fmt_mhz(worst["freq_hz"])}MHz {worst["dbm"]:.1f}dBm（{worst["dbc"]:.1f}dBc）',
         limit_dbm=lim_sp, marks=[(worst['freq_hz'], worst['dbm'], f'{worst["dbm"]:.1f}dBm')], ref=ref, note=note)
    if rig: print(rig.cmd('tone 0'))
    print('\n測定はここまでです。PTT を離してください。')
    return res


def save_csv(path, x, y):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['freq_hz', 'dbm'])
        for a, b in zip(x, y): w.writerow([f'{a:.1f}', f'{b:.2f}'])


def report(res, out, a):
    c, o, s, L = res['carrier'], res['oob'], res['spur'], res['limits']
    w = s['worst']
    band = '50MHz'
    rows = [
        [band, f'{res["freq_mhz"]:.4f}', '無変調', fmt_mhz(o['freq_hz']), f'{o["dbm"]:.1f}', f'{o["dbc"]:.1f}', L['oob_text'],
         '', '', '', '', '適合' if o['ok'] else '不適合', f'{a.rated_w:g}'],
        [band, f'{res["freq_mhz"]:.4f}', res['mode'], '', '', '', '', fmt_mhz(w['freq_hz']), f'{w["dbm"]:.1f}',
         f'{w["dbc"]:.1f}', L['spur_text'], '適合' if all(z['ok'] for z in s['points']) else '不適合', f'{a.rated_w:g}'],
    ]
    head = ['周波数帯', '周波数(MHz)', '電波型式', '帯域外 測定周波数(MHz)', '帯域外 実測値(dBm)', '帯域外 減衰値(dBc)',
            '帯域外 規格限度値', 'スプリアス 測定周波数(MHz)', 'スプリアス 実測値(dBm)', 'スプリアス 減衰値(dBc)',
            'スプリアス 規格限度値', '無線設備規則第7条の基準への適合', '定格出力(W)']
    with open(os.path.join(out, 'summary.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        wr = csv.writer(f); wr.writerow(head); wr.writerows(rows)
    md = [f'# 新スプリアス規格の測定結果（{res["mode"]} {res["freq_mhz"]:.4f} MHz）', '',
          f'- 測定日時: {res["started"]}',
          f'- 被試験機器: PSN_TRX_XIAO_ESP32C3（自作、定格出力 {a.rated_w:g}W）',
          f'- 測定器: {res["idn"]}',
          f'- 外部減衰器・ケーブル: fc で {res["offset_at_fc_db"]:.1f} dB（測定器のリファレンスオフセットに設定）'
          + ('、ほかの周波数は TG で測った損失で補正' if a.pathloss else ''),
          f'- 内部 ATT: {res["int_att_db"]:g} dB、検波: Positive Peak、MAX HOLD', '',
          '## 結果', '',
          '| 項目 | 測定周波数 (MHz) | 実測値 (dBm) | 減衰値 (dBc) | 許容値 | 判定 |', '|---|---|---|---|---|---|',
          f'| 搬送波電力（無変調） | {fmt_mhz(c["freq_hz"])} | {c["dbm"]:.2f}（{c["watt"]:.2f} W） | — | — | — |',
          f'| 帯域外領域（無変調 = {o["state"]}、{o["range"]}、RBW {o["rbw"]:.0f}Hz） | {fmt_mhz(o["freq_hz"])} | {o["dbm"]:.1f} | {o["dbc"]:.1f} | {L["oob_text"]}（{o["limit_dbm"]:.1f} dBm） | {"適合" if o["ok"] else "**不適合**"} |',
          f'| スプリアス領域の最大（変調、9kHz〜1GHz） | {fmt_mhz(w["freq_hz"])} | {w["dbm"]:.1f} | {w["dbc"]:.1f} | {L["spur_text"]}（{s["limit_dbm"]:.1f} dBm） | {"適合" if w["ok"] else "**不適合**"} |',
          *([f'| （参考）抑圧した搬送波の漏れ | {fmt_mhz(o["leak"]["freq_hz"])} | {o["leak"]["dbm"]:.1f} | {o["leak"]["dbc"]:.1f} | — | 帯域外の判定に含めている（VR5・VR6 で抑える） |'] if 'leak' in o else []),
          f'- J3E の搬送波電力は 1.5kHz の単一トーン（尖頭電力に等しい）で測った値' if res['mode'] == 'J3E' else '- A3E の搬送波電力は無変調の搬送波',
          '', '## スプリアス領域の内訳（スパンを絞って測った値）', '',
          '| 対象 | 周波数 (MHz) | 実測値 (dBm) | 減衰値 (dBc) | RBW | 判定 |', '|---|---|---|---|---|---|']
    md += [f'| {z["label"]} | {fmt_mhz(z["freq_hz"])} | {z["dbm"]:.1f} | {z["dbc"]:.1f} | {z["rbw"] / 1e3:g} kHz | {"適合" if z["ok"] else "**不適合**"} |' for z in s['points']]
    md += ['', '## 画像', '',
           '- `1_carrier*.png` 搬送波電力 / `2_oob*.png` 帯域外領域（JARD の「基本波の近傍」） / '
           '`3_spur_*.png`・`4_spur_worst*.png` スプリアス領域（JARD の「その外側」）',
           '- `*_graph.png` はトレースのデータから描いたグラフ（赤い破線が許容値）。'
           '測定器の画面そのもの（`1_carrier.png` など、取り込めた場合）と合わせて提出する']
    open(os.path.join(out, 'summary.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    json.dump(res, open(os.path.join(out, 'result.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------
def cmd_pathloss(sa, a):
    """TG で減衰器（とケーブル）の損失を測る。1) 直結 2) 減衰器を入れる の差を損失とする"""
    f0, f1 = 100e3, 1e9                                    # DSA815-TG の TG は 100kHz から
    def sweep(msg):
        ask(msg, a.yes)
        sa.setup(start=f0, stop=f1, rbw=100e3, vbw=100e3, ref_dbm=0, offset_db=0, att_db=10, points=3001)
        sa.tg(True, a.tg_level)
        sa.maxhold(sweeps=1)
        x, y, _ = sa.trace()
        sa.tg(False)
        return x, y
    x, thru = sweep('[1/2] TG OUTPUT と RF INPUT を、測定で使うケーブル（と変換コネクタ）だけで直結してください。')
    _, att = sweep('[2/2] ケーブルの途中に、測定で使う減衰器（とダミーロードの分岐など）を入れてください。'
                   '\n  ※ 減衰器の入力側を TG OUTPUT に。TG の出力は小さいので減衰器は壊れません。')
    loss = [t - v for t, v in zip(thru, att)]
    path = a.out_file
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['freq_hz', 'loss_db'])
        for i in range(0, len(x), 10): w.writerow([f'{x[i]:.0f}', f'{loss[i]:.2f}'])
    plot(os.path.splitext(path)[0] + '.png', x, loss, '減衰器・ケーブルの損失（TG で測定）')
    for f in (50e6, 100e6, 150e6, 500e6, 1e9):
        print(f'  {f / 1e6:6.0f} MHz: {PathLoss.load(path, 0).at(f):.2f} dB')
    print(f'保存しました: {path}（measure の --pathloss に指定）')


def cmd_monitor(sa, a):
    """変調の深さを合わせるための表示（Ctrl+C で終わる）
    J3E: 出力（尖頭電力）を表示。トーンの入力を上げて飽和の電力を確かめ、その 80% に合わせる
    A3E: 搬送波と側波帯（±tone）の差から変調度を表示（60% = 側波帯が搬送波の -10.5dBc）"""
    fc = a.freq * 1e6
    sa.setup(center=fc, span=a.span * 1e3, rbw=100, vbw=100, ref_dbm=a.ref, offset_db=a.att_db, att_db=a.int_att, points=601)
    sa.write(':INITiate:CONTinuous ON')
    pmax = -999
    try:
        while True:
            x, y, _ = sa.trace()
            i = max(range(len(y)), key=lambda k: y[k]); p = y[i]
            pmax = max(pmax, p)
            line = f'ピーク {p:6.2f} dBm（{10 ** ((p - 30) / 10):5.2f} W） @ {fmt_mhz(x[i])} MHz  最大 {10 ** ((pmax - 30) / 10):5.2f} W'
            if a.mode == 'J3E':
                line += f'  最大の 80% = {0.8 * 10 ** ((pmax - 30) / 10):5.2f} W'
            else:
                def at(f):
                    return max(v for xx, v in zip(x, y) if abs(xx - f) <= 150)
                c = at(fc); sb = max(at(fc - a.tone), at(fc + a.tone))
                m = 2 * 10 ** ((sb - c) / 20)
                line += f'  側波帯 {sb - c:6.1f} dBc → 変調度 {100 * m:5.1f} %（目標 60% = -10.5dBc）'
            print(line, end='\r', flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
    finally:
        sa.write(':INITiate:CONTinuous OFF')


def main():
    p = argparse.ArgumentParser(description='DSA815-TG（LAN）で新スプリアス規格の測定（JARD 提出用）')
    p.add_argument('--host', help='DSA815 の IP アドレス（Utility → Interface → LAN で確かめる）')
    p.add_argument('--port', type=int, default=5555, help='SCPI のソケットのポート（初期値 5555）')
    p.add_argument('--dry-run', action='store_true', help='測定器なしで、作った模擬のスペクトルで流れを確かめる')
    p.add_argument('--verbose', action='store_true', help='SCPI のやりとりを表示')
    sp = p.add_subparsers(dest='cmd', required=True)
    sp.add_parser('idn', help='接続の確認（*IDN?）')
    q = sp.add_parser('pathloss', help='TG で減衰器・ケーブルの損失を測る')
    q.add_argument('--tg-level', type=int, default=-10, help='TG の出力 dBm（-40〜0）')
    q.add_argument('--out-file', default='pathloss.csv')
    q.add_argument('--yes', action='store_true')
    mo = sp.add_parser('monitor', help='変調の深さを合わせるための連続表示（J3E は電力、A3E は変調度）')
    mo.add_argument('--freq', type=float, required=True)
    mo.add_argument('--mode', choices=['J3E', 'A3E'], required=True)
    mo.add_argument('--att-db', type=float, default=30.0)
    mo.add_argument('--int-att', type=float, default=30.0)
    mo.add_argument('--ref', type=float, default=33.0)
    mo.add_argument('--span', type=float, default=10.0, help='スパン kHz')
    mo.add_argument('--tone', type=float, default=1000.0, help='A3E の変調音の周波数 Hz')
    m = sp.add_parser('measure', help='搬送波・帯域外領域・スプリアス領域をまとめて測る')
    m.add_argument('--freq', type=float, required=True, help='表示周波数 MHz（例 50.2）')
    m.add_argument('--mode', choices=['J3E', 'A3E'], required=True)
    m.add_argument('--rated-w', type=float, default=1.0, help='定格出力 W（許容値の区分を決める。V2 は 1W）')
    m.add_argument('--att-db', type=float, default=30.0, help='外部の減衰器・ケーブルの損失 dB（--pathloss がなければこの値）')
    m.add_argument('--pathloss', help='pathloss で作った CSV（周波数ごとに補正する）')
    m.add_argument('--int-att', type=float, default=30.0, help='測定器の内部 ATT dB（JARD の例は 30dB）')
    m.add_argument('--ref', type=float, default=33.0, help='最初のリファレンスレベル dBm（1W = 30dBm）')
    m.add_argument('--oob-rbw', type=float, default=100.0, help='帯域外領域の RBW Hz（JARD: 10Hz〜1kHz）')
    m.add_argument('--oob-sweeps', type=int, default=3)
    m.add_argument('--hold', type=float, default=20.0, help='スプリアス領域の各区間の MAX HOLD 秒')
    m.add_argument('--zoom', type=int, default=5, help='高調波のほかにスパンを絞って測るスプリアスの数')
    m.add_argument('--zoom-hold', type=float, default=5.0)
    m.add_argument('--spur-rbw-max', type=float, help='スプリアス領域の RBW の上限 Hz（雑音が許容値に近いとき 30000 など）')
    m.add_argument('--j3e-oob', choices=['none', 'tone'], default='none',
                   help='J3E の帯域外領域を測る状態: none = 変調なし（JARD の「無変調」、初期値）、tone = 1.5kHz の単一トーン（逆側の側波帯も入る）')
    m.add_argument('--rig', help='リグのシリアルポート（例 COM5）。freq・sb・tone を自動で送る（pyserial が必要）')
    m.add_argument('--outdir', default='results')
    m.add_argument('--usb-snap', help=r'測定器の USB メモリにも画面を保存する（ドライブ名。例 E:）')
    m.add_argument('--yes', action='store_true', help='確認の Enter を待たない（--dry-run の確認用）')
    a = p.parse_args()

    log = (lambda s: print('   ' + s)) if a.verbose else None
    if a.dry_run:
        sa = FakeDSA815(fc=getattr(a, 'freq', 50.2) * 1e6, mode=getattr(a, 'mode', 'J3E'))
    else:
        if not a.host: p.error('--host（DSA815 の IP アドレス）を指定してください')
        sa = DSA815(a.host, a.port, log=log)

    if a.cmd == 'idn':
        print(sa.idn()); return
    if a.cmd == 'pathloss':
        cmd_pathloss(sa, a); return
    if a.cmd == 'monitor':
        cmd_monitor(sa, a); return
    if getattr(a, 'usb_snap', None) and not a.dry_run:
        sa.usb_dir = a.usb_snap.rstrip('\\')

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(a.outdir, f'{stamp}_{a.freq:.4f}MHz_{a.mode}' + ('_dryrun' if a.dry_run else ''))
    os.makedirs(out, exist_ok=True)
    rig = Rig(a.rig) if a.rig else None
    try:
        res = measure(sa, a, out, rig)
    finally:
        if rig: rig.close()
    report(res, out, a)
    print(f'\n結果: {os.path.abspath(out)}')
    print(open(os.path.join(out, 'summary.md'), encoding='utf-8').read())


if __name__ == '__main__':
    main()
