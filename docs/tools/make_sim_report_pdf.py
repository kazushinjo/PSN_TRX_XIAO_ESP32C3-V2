"""docs/PSN_TRX_シミュレーション結果.md から PDF（A4）を作る

  使い方: リポジトリの一番上で  <markdown の入った python3> docs/tools/make_sim_report_pdf.py
  Google Chrome（headless）で印刷する。出力: docs/PSN_TRX_シミュレーション結果.pdf
"""
import os
import subprocess
import sys
import tempfile

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
SRC = os.path.join(DOCS, 'PSN_TRX_シミュレーション結果.md')
OUT = os.path.join(DOCS, 'PSN_TRX_シミュレーション結果.pdf')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
body { font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", sans-serif; font-size: 10pt; line-height: 1.6; color: #111; }
h1 { font-size: 17pt; margin: 0 0 8pt; }
h2 { font-size: 13pt; margin: 16pt 0 6pt; padding-bottom: 2pt; border-bottom: 1px solid #999; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 10pt 0 4pt; page-break-after: avoid; }
p, li { margin: 3pt 0; }
ul { padding-left: 18pt; }
table { border-collapse: collapse; margin: 6pt 0 8pt; page-break-inside: avoid; }
th, td { border: 1px solid #999; padding: 3pt 6pt; vertical-align: top; }
th { background: #eef0f3; }
code { font-family: Menlo, monospace; font-size: 9pt; background: #f2f2f2; padding: 0 2pt; }
img { max-width: 100%; display: block; margin: 6pt auto; page-break-inside: avoid; }
"""


def main() -> int:
    md = open(SRC, encoding='utf-8').read()
    body = markdown.markdown(md, extensions=['tables'])
    html = f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'
    # 画像の相対パス（images/…）が効くように docs に一時ファイルを置く
    fd, tmp = tempfile.mkstemp(suffix='.html', dir=DOCS)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(html)
    try:
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                        f'--print-to-pdf={OUT}', 'file://' + tmp], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        os.remove(tmp)
    print('→', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
