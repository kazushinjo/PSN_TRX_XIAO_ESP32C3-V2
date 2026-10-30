# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 JA6FUF (kazushinjo)
"""
Nextion NX4832T035 用の背景画像（480x320、アナログ S メーターの目盛り入り）を作る。
  python3 make_background.py  → background.png（Nextion Editor でピクチャ 0 として取り込み、page0 の背景 sta=image, pic=0 にする）
目盛りの位置はスケッチの METER_* 定数と同じ値にすること。
必要: Pillow
"""
import math
from PIL import Image, ImageDraw, ImageFont

W, H = 480, 320
PANEL = (28, 30, 36)          # 画面の地の色（テキスト部品の bco = RGB565 で 6372）
FACE = (240, 232, 208)        # メーター面
INK = (20, 20, 20)
RED = (200, 30, 30)

# メーター（スケッチの METER_* と同じ）
FACE_BOX = (16, 112, 320, 292)   # メーター面 x0, y0, x1, y1
PIV = (168, 318)                 # 針の支点（メーター面の下に隠れる）
R_ARC = 165                      # 目盛り円弧の半径
ANG_L, ANG_R = 135.0, 45.0       # 左端（S0）・右端（S9+60）の角度（右向き 0°、反時計回り）
S9_POS = 0.6                     # S9 の位置（左端 0〜右端 1）


def pos_of_db(db):               # S9 = 0dB、S0 = -54dB、右端 = +60dB
    if db <= 0:
        return max(0.0, (db + 54) / 54 * S9_POS)
    return min(1.0, S9_POS + db / 60 * (1 - S9_POS))


def pt(p, r):
    a = math.radians(ANG_L + p * (ANG_R - ANG_L))
    return PIV[0] + r * math.cos(a), PIV[1] - r * math.sin(a)


def font(sz, bold=True):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", sz, index=1 if bold else 0)
    except OSError:
        return ImageFont.load_default()


img = Image.new("RGB", (W, H), PANEL)
d = ImageDraw.Draw(img)
d.rounded_rectangle(FACE_BOX, radius=10, fill=FACE, outline=(90, 90, 90), width=2)

# 円弧（S0〜S9 は黒、S9 から上は赤）
def arc(p0, p1, color, width):
    n = 80
    pts = [pt(p0 + (p1 - p0) * i / n, R_ARC) for i in range(n + 1)]
    d.line(pts, fill=color, width=width, joint="curve")

arc(0, S9_POS, INK, 3)
arc(S9_POS, 1, RED, 5)

# 目盛り
for s in range(0, 10):
    p = pos_of_db((s - 9) * 6)
    major = s % 2 == 1
    d.line([pt(p, R_ARC), pt(p, R_ARC + (12 if major else 7))], fill=INK, width=3 if major else 2)
    if major:
        x, y = pt(p, R_ARC + 24)
        d.text((x, y), str(s), font=font(18), fill=INK, anchor="mm")
for db in range(10, 61, 10):
    p = pos_of_db(db)
    major = db % 20 == 0
    d.line([pt(p, R_ARC), pt(p, R_ARC + (12 if major else 7))], fill=RED, width=3 if major else 2)
    if major:
        x, y = pt(p, R_ARC + 26)
        d.text((x, y), f"+{db}", font=font(16), fill=RED, anchor="mm")

d.text((FACE_BOX[0] + 14, FACE_BOX[3] - 14), "S", font=font(22), fill=INK, anchor="lm")
d.text((FACE_BOX[2] - 14, FACE_BOX[3] - 14), "dB", font=font(16), fill=RED, anchor="rm")
# 支点カバー
d.rounded_rectangle((PIV[0] - 22, FACE_BOX[3] - 18, PIV[0] + 22, FACE_BOX[3] - 2), radius=4, fill=(60, 60, 64))

img.save(__file__.replace("make_background.py", "background.png"))
print("background.png", W, H)
