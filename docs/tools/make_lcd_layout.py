# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 JA6FUF (kazushinjo)
"""LCD（Nextion NX4832K035、480x320）のテキスト部品 t0〜t7 の配置図を作る。

使い方（Pillow が入った Python で、リポジトリの一番上から）:
    python docs/tools/make_lcd_layout.py
背景画像 PSN_TRX_XIAO_ESP32C3/nextion/background.png の上に、画面データ作成手順 5 章の
x・y・w・h の枠を色分けして重ね、3 倍に拡大して docs/images/lcd_t0_t7_layout.png に保存する。
部品の位置を変えたときは、下の PARTS を直して作り直す。
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BG = os.path.join(ROOT, 'PSN_TRX_XIAO_ESP32C3', 'nextion', 'background.png')
OUT = os.path.join(ROOT, 'docs', 'images', 'lcd_t0_t7_layout.png')
K = 3   # 拡大率

# (名前, x, y, w, h, 表示する内容, 枠の色)
PARTS = [
    ('t0', 16, 16, 364, 56, '周波数 (font1, 1文字24px)', (255, 80, 80)),
    ('t1', 16, 76, 312, 32, 'SSB/AM・LOCK・メニュー', (255, 200, 0)),
    ('t2', 328, 256, 152, 32, '機種名 (font2)', (0, 200, 255)),
    ('t3', 328, 120, 148, 32, 'Sメーター/ALC', (80, 255, 80)),
    ('t4', 328, 168, 148, 32, 'AGC / TX', (255, 120, 255)),
    ('t5', 328, 76, 148, 32, 'RIT (右寄せ)', (255, 160, 60)),
    ('t6', 328, 208, 148, 32, 'AGC量/送信時間', (160, 160, 255)),
    ('t7', 380, 36, 96, 36, '電源電圧 (font3)', (0, 255, 200)),
]
METER = (16, 112, 320, 292)       # メーター面（部品を置かない。スケッチが針を描く）
STEP_MARK = (16, 72, 24, 3)       # ステップの下線を引くすき間（x0, y, 1 文字の幅, 高さ）


def font(name, size):
    for d in ('C:/Windows/Fonts', '/System/Library/Fonts', '/usr/share/fonts/opentype/noto'):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main():
    im = Image.open(BG).convert('RGB').resize((480 * K, 320 * K), Image.NEAREST)
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = font('meiryob.ttc', 22)
    fs = font('meiryo.ttc', 17)
    edge = dict(stroke_width=2, stroke_fill=(0, 0, 0, 255))

    x0, y0, x1, y1 = METER
    d.rectangle([x0 * K, y0 * K, x1 * K, y1 * K], outline=(220, 220, 220, 255), width=2, fill=(255, 255, 255, 30))
    d.text((20 * K, y1 * K - 30), 'メーター面 x16-320 y112-292（部品を置かない）', font=fs, fill=(240, 240, 240, 255), **edge)

    for n, x, y, w, h, label, c in PARTS:
        d.rectangle([x * K, y * K, (x + w) * K - 1, (y + h) * K - 1], outline=c + (255,), width=3, fill=c + (70,))
        d.text((x * K + 6, y * K + 3), f'{n}  {label}', font=f, fill=(255, 255, 255, 255), **edge)
        d.text((x * K + 6, (y + h) * K - 24), f'x{x} y{y} w{w} h{h}', font=fs, fill=c + (255,), **edge)

    # ステップの下線（例: 1kHz = "50.150.000" の 6 文字目）
    sx, sy, cw, sh = STEP_MARK
    col = 5
    d.rectangle([(sx + col * cw + 2) * K, sy * K, (sx + col * cw + cw - 2) * K - 1, (sy + sh) * K - 1], fill=(255, 255, 255, 255))
    d.text(((sx + 10 * cw) * K - 220, sy * K - 2), 'ステップの下線 y72-74（例: 1kHz）', font=fs, fill=(255, 255, 255, 255), **edge)

    Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB').save(OUT)
    print('saved', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()
