#!/bin/bash
# アナログ部の回路シミュレーション（KiCad 同梱の libngspice を Python から呼ぶ）
# 使い方: kicad/sim で ./run.sh  → results.txt に結果
set -e
cd "$(dirname "$0")"
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K sch export netlist --format kicadsexpr -o net.net ../PSN_TRX.kicad_sch >/dev/null
python3 parsenet.py net.net net.json > netlist.txt
{
  echo "# PSN_TRX アナログ部シミュレーション $(date '+%Y-%m-%d %H:%M')"
  echo "## 直流動作点"; python3 dc.py
  echo; echo "## 送信 AF 系・受信 AF 系"; python3 af.py
  echo; echo "## PA 出力 LPF・PA 入力・RFC1・DC-DC 入力フィルタ・AGC"; python3 rf.py
  echo; echo "## 過渡解析（大信号の歪み・飽和、PA の高調波、電源投入・送信開始）"; python3 tran.py
  echo; echo "## 受信部（V2: 12MHz の SSB スーパー。BPF・ラダーフィルタ・利得）"; python3 rx.py
  echo; echo "## 回路全体（受信: アンテナ → スピーカー、送信: 局発・変調器 → アンテナ）"; python3 full.py
} 2>&1 | grep -v -E '^\s*$|^stdout|^stderr' > results.txt
rm -f net.net
echo "results.txt に出力しました"
