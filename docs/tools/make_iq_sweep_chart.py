import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator, FixedFormatter

plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "sans-serif"]

SURF = "#fcfcfb"; TXT = "#0b0b0b"; TXT2 = "#52514e"; GRID = "#e1e0d9"
C1 = "#2a78d6"; C2 = "#eb6834"

f = [300, 1000, 2700]
# 波形データの正弦波あてはめ（iqd 0）
amp0 = [-0.098, -0.205, -0.085]; ph0 = [89.68, 90.06, 89.96]; sup0 = [44.1, 38.7, 46.3]
amp1 = [+0.013, -0.106, +0.005]; ph1 = [89.75, 90.18, 89.85]; sup1 = [52.8, 44.1, 57.4]

fig, axes = plt.subplots(1, 3, figsize=(12, 4.4), facecolor=SURF)
fig.suptitle("送信 I/Q（Q15・Q16 のコレクタ）の I/Q のずれ　2026-11-23　波形データの正弦波あてはめ・iqd 0",
             color=TXT, fontsize=12, x=0.01, ha="left")

def style(ax, title, ylabel):
    ax.set_facecolor(SURF)
    ax.set_xscale("log")
    ax.set_xlim(220, 3700)
    ax.xaxis.set_major_locator(FixedLocator(f))
    ax.xaxis.set_major_formatter(FixedFormatter(["300", "1,000", "2,700"]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlabel("トーンの周波数 (Hz)", color=TXT2, fontsize=9)
    ax.set_ylabel(ylabel, color=TXT2, fontsize=9)
    ax.set_title(title, color=TXT, fontsize=11, loc="left")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(TXT2)
    ax.tick_params(colors=TXT2, labelsize=9, length=0)

def two(ax, y0, y1):
    ax.plot(f, y0, color=C1, lw=2, marker="o", ms=8, mec=SURF, mew=2, label="iqa 0 dB（調整前）")
    ax.plot(f, y1, color=C2, lw=2, marker="o", ms=8, mec=SURF, mew=2, label="iqa +0.15 dB（保存した値）")

# 1. 振幅の差
ax = axes[0]
style(ax, "振幅の差（CH2 / CH1）", "dB")
ax.axhline(0, color=TXT2, lw=1, ls="--")
two(ax, amp0, amp1)
ax.set_ylim(-0.3, 0.1)
ax.annotate("−0.21", (1000, amp0[1]), xytext=(0, -16), textcoords="offset points", ha="center", color=TXT, fontsize=9)
ax.annotate("−0.11", (1000, amp1[1]), xytext=(0, 10), textcoords="offset points", ha="center", color=TXT, fontsize=9)

# 2. 位相差
ax = axes[1]
style(ax, "位相差（CH2 → CH1）", "度")
ax.axhline(90, color=TXT2, lw=1, ls="--")
ax.text(3600, 90.03, "理想 90°", color=TXT2, fontsize=9, ha="right", va="bottom")
two(ax, ph0, ph1)
ax.set_ylim(89, 91)

# 3. 抑圧の目安
ax = axes[2]
style(ax, "不要側波帯の抑圧の目安*", "dB")
ax.axhline(40, color=TXT2, lw=1, ls="--")
ax.text(3600, 40.5, "合格の目安 40 dB", color=TXT2, fontsize=9, ha="right", va="bottom")
two(ax, sup0, sup1)
for x, y in zip(f, sup1):
    ax.annotate(f"{y:.0f}", (x, y), xytext=(0, 10), textcoords="offset points", ha="center", color=TXT, fontsize=9)
for x, y in zip(f, sup0):
    ax.annotate(f"{y:.0f}", (x, y), xytext=(0, -16), textcoords="offset points", ha="center", color=TXT, fontsize=9)
ax.set_ylim(30, 62)

h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper right", bbox_to_anchor=(0.99, 0.94), ncol=2, frameon=False, fontsize=9, labelcolor=TXT)
fig.text(0.01, 0.01, "* Q15・Q16 での振幅の差と位相のずれだけから計算（RF 側のずれは含まない）。"
         "オシロスコープの CH1・CH2 の波形データ（1,200 点）に既知の周波数の正弦波をあてはめ、3 回の中央値。ばらつきは位相で ±0.1° 程度。",
         color=TXT2, fontsize=8, ha="left")
fig.tight_layout(rect=(0, 0.05, 1, 0.88))
fig.savefig(sys.argv[1], dpi=110, facecolor=SURF)
print("ok")
