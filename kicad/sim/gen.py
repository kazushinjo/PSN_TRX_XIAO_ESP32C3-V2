"""回路図ネットリスト(net.json)から SPICE 素子行を作る"""
import json, re, os
D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'net.json')))
COMPS, PINS = D['comps'], D['pins']

def pin(ref, p):
    for num, fn, net in PINS[ref]:
        if num == p or fn.split('_')[0] == p: return node(net)
    raise KeyError((ref, p))

# 回路図でラベルをやめて線で結んだネット（名前が自動名になった）を、計算では元の名前で呼ぶ（代表のピンで見分ける）
ALIAS_PIN = {'TX12V': ('C13', '1'), 'XIAO_3V3': ('R38', '1'), 'AF_ADC': ('R39', '1'), 'AGC_PWM': ('R42', '1'),
             'Q2_G2': ('C5', '1'), 'TX_SENSE': ('R50', '2'), 'PWR_IN': ('L12', '1'), 'DCDC_IN': ('L12', '2')}
ALIAS = {}
for _n, (_r, _p) in ALIAS_PIN.items():
    for _num, _fn, _net in PINS.get(_r, []):
        if _num == _p: ALIAS[_net] = '/' + _n


def node(net):
    net = ALIAS.get(net, net)
    if net == 'GND': return '0'
    # 先頭以外の '+' は 'P' にする（自動名の Net-(IC2A--) と Net-(IC2A-+) を別ノードにするため。+5V などは従来どおり）
    net = net[:1] + net[1:].replace('+', 'P')
    return 'n_' + re.sub(r'[^A-Za-z0-9]', '_', net)

MULT = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'm': 1e-3, 'k': 1e3, 'K': 1e3, 'M': 1e6, '': 1}
OVERRIDE = {}       # 部品の値を計算だけで差し替える（変更案の比較用）{部品: '値'}


def val(ref):
    """部品値を数値に（'0.01u film'→1e-8、'47PF'→4.7e-11、'100 1W'→100、'15mH'→0.015）"""
    v = OVERRIDE.get(ref, COMPS[ref]).strip()
    m = re.match(r'([0-9.]+)\s*([fpnuµmkKM]?)', v.replace('PF', 'p').replace('pF', 'p').replace('uF', 'u'))
    if not m: raise ValueError((ref, v))
    return float(m.group(1)) * MULT[m.group(2)]

used = {}
def R(ref, v=None):
    v = val(ref) if v is None else v; used[ref] = v
    return f"R{ref} {pin(ref,'1')} {pin(ref,'2')} {v:g}"
def C(ref, v=None):
    v = val(ref) if v is None else v; used[ref] = v
    return f"C{ref} {pin(ref,'1')} {pin(ref,'2')} {v:g}"
def L(ref, dcr, v=None):
    v = val(ref) if v is None else v; used[ref] = v
    a, b = pin(ref, '1'), pin(ref, '2'); m = f"m_{ref}"
    return f"L{ref} {a} {m} {v:g}\nRL{ref} {m} {b} {dcr:g}"
def POT(ref, pos, v=None):
    """可変抵抗: pos=0 で 2 番が 1 番側、1 で 3 番側"""
    v = val(ref) if v is None else v; used[ref] = v
    r12, r23 = max(v * pos, 1e-3), max(v * (1 - pos), 1e-3)
    return f"R{ref}a {pin(ref,'1')} {pin(ref,'2')} {r12:g}\nR{ref}b {pin(ref,'2')} {pin(ref,'3')} {r23:g}"
def BJT(ref, model):
    used[ref] = COMPS[ref]
    return f"Q{ref} {pin(ref,'C')} {pin(ref,'B')} {pin(ref,'E')} {model}"
def JFET(ref, model):
    used[ref] = COMPS[ref]
    return f"J{ref} {pin(ref,'D')} {pin(ref,'G')} {pin(ref,'S')} {model}"
def WIND(ref, r=0.1):
    """7T50 の巻線を直流抵抗だけで表す（SA-SB、CT 接続時は二分割、AA-AB）"""
    sa, sb, ct = pin(ref, 'SA'), pin(ref, 'SB'), pin(ref, 'CT')
    out = []
    if ct.startswith('n_unconnected'): out.append(f"RW{ref}s {sa} {sb} {r}")
    else: out += [f"RW{ref}s1 {sa} {ct} {r/2}", f"RW{ref}s2 {ct} {sb} {r/2}"]
    out.append(f"RW{ref}l {pin(ref,'AA')} {pin(ref,'AB')} {r}")
    return '\n'.join(out)

MODELS = """
.model Q2SC1815 NPN(IS=2e-14 BF={hfe1815} VAF=100 BR=3 RB=50 RC=1 CJE=10p CJC=3.5p TF=0.5n)
.model Q2SC1923 NPN(IS=1e-15 BF={hfe1923} VAF=50 BR=2 RB=30 CJE=1.5p CJC=0.9p TF=0.15n)
.model Q2SC2120 NPN(IS=1e-13 BF={hfe2120} VAF=100 BR=5 RB=10 CJE=50p CJC=20p TF=2n)
.model Q2SA950 PNP(IS=1e-13 BF={hfe2120} VAF=100 BR=5 RB=10 CJE=50p CJC=25p TF=2n)
.model J3819 NJF(VTO=-3 BETA=1.1m LAMBDA=0.01 CGS=4p CGD=2p RS=10 RD=10)
.model J2SK439 NJF(VTO=-1.5 BETA=4.44m LAMBDA=0.01 CGS=5p CGD=1p)
.model JJ310 NJF(VTO={vp310} BETA={b310} LAMBDA=0.01 CGS=5p CGD=2p)
.model D1N60 D(IS=1u N=1.1 RS=5 CJO=1p)
"""
OPAMP = """
.subckt OA inp inn out
Rin inp inn 1e8
E1 a 0 inp inn 1e5
R1 a b 1k
C1 b 0 26.5u
E2 out 0 b 0 1
.ends
"""
def OPA(half, ref='IC2'):
    """NJM2904 の片側: half='A'(1,2,3) or 'B'(7,6,5)。ref は IC2 または IC3"""
    o, n, p = ('1', '2', '3') if half == 'A' else ('7', '6', '5')
    used[ref] = COMPS[ref]
    return f"X{ref}{half} {pin(ref,p)} {pin(ref,n)} {pin(ref,o)} OA"
