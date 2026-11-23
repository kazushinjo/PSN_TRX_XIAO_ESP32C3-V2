"""Fetch CH1/CH2 screen waveforms from RIGOL DS1202Z-E (SCPI port 5555) and fit a sine
at a known frequency. Prints: f, vpp1, vpp2, amp_ratio_dB(ch2/ch1), phase(ch2 - ch1, deg).
usage: scopefit.py <freq_hz> [repeats]
"""
import socket, sys, time
import numpy as np

HOST = "192.168.0.141"
f0 = float(sys.argv[1])
reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3

def cmd(s, q):
    s.sendall((q + "\n").encode())

def readline(s):
    b = b""
    while not b.endswith(b"\n"):
        b += s.recv(1)
    return b.decode().strip()

def query(s, q):
    cmd(s, q)
    return readline(s)

def block(s, q):
    cmd(s, q)
    h = s.recv(2)
    while len(h) < 2:
        h += s.recv(2 - len(h))
    nd = int(chr(h[1]))
    ln = b""
    while len(ln) < nd:
        ln += s.recv(nd - len(ln))
    n = int(ln)
    d = b""
    while len(d) < n:
        d += s.recv(n - len(d))
    s.recv(1)  # trailing newline
    return d

def wave(s, ch):
    cmd(s, f":WAV:SOUR CHAN{ch}")
    cmd(s, ":WAV:MODE NORM")
    cmd(s, ":WAV:FORM BYTE")
    pre = query(s, ":WAV:PRE?").split(",")
    xinc, xor, xref = float(pre[4]), float(pre[5]), float(pre[6])
    yinc, yor, yref = float(pre[7]), float(pre[8]), float(pre[9])
    raw = np.frombuffer(block(s, ":WAV:DATA?"), dtype=np.uint8).astype(float)
    v = (raw - yor - yref) * yinc
    t = (np.arange(len(v)) - xref) * xinc + xor
    return t, v

def fit(t, v):
    w = 2 * np.pi * f0
    A = np.column_stack([np.sin(w * t), np.cos(w * t), np.ones_like(t)])
    (a, b, c), *_ = np.linalg.lstsq(A, v, rcond=None)
    amp = np.hypot(a, b)
    ph = np.degrees(np.arctan2(b, a))
    return amp, ph

s = socket.create_connection((HOST, 5555), timeout=10)
res = []
for _ in range(reps):
    cmd(s, ":STOP")
    time.sleep(0.2)
    t1, v1 = wave(s, 1)
    t2, v2 = wave(s, 2)
    cmd(s, ":RUN")
    a1, p1 = fit(t1, v1)
    a2, p2 = fit(t2, v2)
    d = (p2 - p1 + 180) % 360 - 180
    res.append((2 * a1, 2 * a2, 20 * np.log10(a2 / a1), d))
    time.sleep(0.6)
s.close()
r = np.array(res)
m = np.median(r, axis=0)
print(f"{f0:.0f} {m[0]:.3f} {m[1]:.3f} {m[2]:+.3f} {m[3]:+.2f} spread={np.ptp(r[:,3]):.2f}")
