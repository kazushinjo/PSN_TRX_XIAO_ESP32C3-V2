import ctypes, os
import sys
if sys.platform == 'win32':   # KiCad 10（Windows）
    LIB = r'C:/Program Files/KiCad/10.0/bin/ngspice.dll'
    os.environ.setdefault('SPICE_LIB_DIR', r'C:/Program Files/KiCad/10.0/lib/ngspice')
    os.add_dll_directory(r'C:/Program Files/KiCad/10.0/bin')
else:                         # macOS
    LIB = '/Applications/KiCad/KiCad.app/Contents/Frameworks/libngspice.0.dylib'
    os.environ.setdefault('SPICE_LIB_DIR', '/Applications/KiCad/KiCad.app/Contents/SharedSupport/ngspice')
_ng=ctypes.CDLL(LIB)
_out=[]
SendChar=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_void_p)
SendStat=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_void_p)
Exit=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_int,ctypes.c_bool,ctypes.c_bool,ctypes.c_int,ctypes.c_void_p)
def _sc(s,i,p):
    t=s.decode(errors='replace'); _out.append(t); return 0
_cb=[SendChar(_sc),SendStat(lambda s,i,p:0),Exit(lambda *a:0)]
_ng.ngSpice_Init(_cb[0],_cb[1],_cb[2],None,None,None,None)
class vecinfo(ctypes.Structure):
    _fields_=[('name',ctypes.c_char_p),('type',ctypes.c_int),('flags',ctypes.c_short),
              ('realdata',ctypes.POINTER(ctypes.c_double)),('compdata',ctypes.c_void_p),('length',ctypes.c_int)]
_ng.ngGet_Vec_Info.restype=ctypes.POINTER(vecinfo)
def cmd(c): _ng.ngSpice_Command(c.encode())
def run(netlist):
    """load netlist text and run; returns captured output"""
    _out.clear(); cmd('destroy all'); cmd('remcirc')
    lines=[l for l in netlist.strip().split('\n')]+['.end']
    arr=(ctypes.c_char_p*(len(lines)+1))(*[l.encode() for l in lines],None)
    _ng.ngSpice_Circ(arr); cmd('run')
    return '\n'.join(_out)
def vec(name):
    p=_ng.ngGet_Vec_Info(name.encode())
    if not p: raise KeyError(name)
    v=p.contents; n=v.length
    if v.realdata: return [v.realdata[i] for i in range(n)]
    c=ctypes.cast(v.compdata,ctypes.POINTER(ctypes.c_double))
    return [complex(c[2*i],c[2*i+1]) for i in range(n)]
