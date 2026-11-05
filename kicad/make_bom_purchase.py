# -*- coding: utf-8 -*-
"""購入先入り部品表を作る。

bom.csv（kicad-cli sch export bom の出力）に品名・購入先・購入先の型番を付けて
bom_purchase.csv（UTF-8 BOM 付き、Excel でそのまま開ける）に書き出し、
BOM.md の各表にも「購入先」「購入先の型番（販売コード）」列を入れる
（何度実行しても同じ結果になる）。

秋月電子の型番・販売コード・入数・価格は 2026-10-15 に秋月の通販サイトで確認したもの
（V2 で増えた部品と「要確認」だったものは 2026-11-04 に確認）。
「要確認」は秋月で扱いがなく、型番・在庫を確かめていない部品。

bom.csv の作り直し（回路図を変えたとき）:
  kicad-cli sch export bom --fields "Reference,Value,Footprint,${QUANTITY},${DNP}"
    --labels "Reference,Value,Footprint,Qty,DNP" --group-by "Value,Footprint"
    -o bom.csv PSN_TRX.kicad_sch
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKED = '2026-10-15・11-04'
AKI = '秋月電子'


def aki(model, code, unit, price, note=''):
    return (AKI, model, code, unit, price, note)


def other(shop, model, note=''):
    return (shop, model, '', '', '', note)


# 先頭の Reference → (品名, (購入先, 購入先の型番, 販売コード, 入数, 価格, 購入メモ))
PARTS = {
    # 抵抗（秋月 カーボン抵抗 1/4W 100 本入）
    'R4': ('カーボン抵抗 1/4W', aki('CF25J100KB', '125104', '100本', 200)),
    'R13': ('カーボン抵抗 1/4W', aki('CF25J1K5B', '125152', '100本', 170)),
    'R10': ('カーボン抵抗 1/4W', aki('CF25J1KB', '125102', '100本', 100)),
    'R16': ('カーボン抵抗 1/4W', aki('CF25J330RB', '125331', '100本', 200, 'R70 と同じ品')),
    'R2': ('カーボン抵抗 1/4W', aki('RD25S 10K', '125103', '100本', 100)),
    'R57': ('カーボン抵抗 1/4W', aki('CF25J1MB', '125105', '100本', 200)),
    'R3': ('カーボン抵抗 1/4W', aki('CF25J100RB', '125101', '100本', 200)),
    'R17': ('カーボン抵抗 1/4W', aki('CF25J20KB', '103940', '100本', 180)),
    'R7': ('カーボン抵抗 1/4W', aki('CF25J51RB', '125510', '100本', 200)),
    'R69': ('カーボン抵抗 1/4W', aki('CF25J10RB', '125100', '100本', 220)),
    'R70': ('カーボン抵抗 1/4W', aki('CF25J330RB', '125331', '100本', 200, 'R38・R46 と同じ品（足のピッチが違うので別の行）')),
    'R1': ('カーボン抵抗 1/4W', aki('CF25J4K7B', '125472', '100本', 170)),
    'R63': ('カーボン抵抗 1/4W', aki('CF25J47RB', '125470', '100本', 200)),
    'R58': ('カーボン抵抗 1/4W', aki('CF25J22RB', '103821', '100本', 200)),
    'R8': ('カーボン抵抗 1/4W', aki('CF25J470RB', '125471', '100本', 200)),
    'R76': ('カーボン抵抗 1/4W', aki('CF25J47KB', '118208', '100本', 150)),
    'R47': ('カーボン抵抗 1/4W 620Ω', other('千石電商／マルツ など（要確認）', '1/4W 620Ω', '秋月に 1/4W 620Ω の扱いなし（2026-11-04 確認）')),
    'R52': ('カーボン抵抗 1/4W', aki('CF25J22KB', '125223', '100本', 180)),
    'R53': ('カーボン抵抗 1/4W', aki('CF25J3K3B', '125332', '100本', 180,
            'I・Q の RC（R53〜R56）は同じ袋のものを使う')),
    'R41': ('超小型 金属皮膜抵抗 1W 100Ω', aki('MFU100F100RB', '108816', '100本', 300,
            '縦置き・2.54mm ピッチに入る小型品')),
    # 半固定抵抗
    'VR7': ('多回転半固定抵抗 Bourns 3266W', other('DigiKey／Mouser', '3266W-1-501LF',
            '秋月の 3296W は外形が大きく基板に合わない')),
    'VR5': ('半固定抵抗 TOCOS GF063P', aki('GF063P B102K', '114901', '1個', 30)),
    'VR3': ('半固定抵抗 TOCOS GF063P', aki('GF063P B501K', '114900', '1個', 30)),
    # セラミックコンデンサ（2.5mm 穴には 2.54mm ピッチ品、5mm 穴には 5mm ピッチ品）
    'C37': ('積層セラミックコンデンサ 1µF 50V X7R 2.54mm', aki('RD15W105K1HL2L-503', '115940', '10個', 170)),
    'C11': ('積層セラミックコンデンサ 0.1µF 50V X7R 2.54mm', aki('RDER71H104K0P1H03B', '113582', '10個', 100)),
    'C16': ('積層セラミックコンデンサ 15pF 50V NP0 2.54mm', aki('RD15N150J1HL2L', '104059', '10個', 100)),
    'C2': ('積層セラミックコンデンサ 0.01µF 50V X7R 2.54mm', aki('RD15W103K1HL2L-10', '104063', '10個', 100)),
    'C80': ('積層セラミックコンデンサ 1000pF 50V 2.54mm', aki('RD15N102J1HL2L-10', '104062', '10個', 100)),
    'C95': ('積層セラミックコンデンサ 0.1µF 250V X7R 5mm', aki('RDER72E104K2K1H03B', '110147', '1個', 25)),
    'C94': ('積層セラミックコンデンサ 1000pF 50V C0G 5mm', aki('RDE5C1H102J0K1H03B', '108114', '10個', 130)),
    'C92': ('積層セラミックコンデンサ 100pF 50V C0G 5mm', aki('RDE5C1H101J0K1H03B', '108063', '10個', 120)),
    'C93': ('積層セラミックコンデンサ 22pF 50V C0G 5mm', aki('RDE5C1H220J0K1H03B', '108094', '10個', 130)),
    'C76': ('積層セラミックコンデンサ 47pF 50V C0G 5mm', aki('RDE5C1H470J0K1H03B', '108045', '10個', 130,
            '2.54mm ピッチ品がないため 5mm ピッチ品の足を寄せて使う')),
    'C4': ('積層セラミックコンデンサ 5pF 50V C0G 2.54mm', aki('RDE5C1H5R0C0P1H03B', '131234', '10個', 150)),
    'C99': ('積層セラミックコンデンサ 82pF 50V C0G 5mm', aki('RDE5C1H820J0K1H03B', '108101', '10個', 150)),
    'C101': ('積層セラミックコンデンサ 100pF 50V C0G 5mm', aki('RDE5C1H101J0K1H03B', '108063', '10個', 120)),
    'C98': ('積層セラミックコンデンサ 39pF 50V C0G 5mm', aki('RDE5C1H390J0K1H03B', '108097', '10個', 100)),
    'C66': ('積層セラミックコンデンサ 3300pF 50V C0G 5mm', aki('RDE5C1H332J0K1H03B', '108120', '10個', 120,
            'PDM 出力の RC（C66〜C69）。I・Q で値がそろうよう同じ袋のものを使う。2.54mm ピッチの C0G 品がないため足を寄せて使う')),
    'C102': ('積層セラミックコンデンサ 68pF 50V C0G 5mm', aki('RDE5C1H680J0K1H03B', '108048', '10個', 100)),
    # 電解コンデンサ（ルビコン PX、φ5×11）
    'C47': ('電解コンデンサ 100µF 25V', aki('25PX100MEFC5X11', '117877', '1個', 10)),
    'C50': ('電解コンデンサ 10µF 50V', aki('50PX10MEFC5X11', '117897', '1個', 10)),
    'C57': ('電解コンデンサ 1µF 50V', aki('50PX1MEFC5X11', '117889', '1個', 10)),
    'C56': ('電解コンデンサ 47µF 35V', aki('35PX47MEFC5X11', '117887', '1個', 10)),
    'C60': ('フィルムコンデンサ 0.068µF 50V（ルビコン F2D）', aki('50F2D683J', '110342', '1個', 10,
            'マイク LPF。2mm ピッチに足を合わせる')),
    'C59': ('積層セラミックコンデンサ 0.01µF 50V', aki('RD15W103K1HL2L-10', '104063', '10個', 100,
            '2mm ピッチに足を合わせる')),
    # トリマコンデンサ
    'TC1': ('セラミックトリマコンデンサ 30pF', aki('TMCV01-30P100VBG', '115472', '1個', 25)),
    'TC4': ('セラミックトリマコンデンサ 10pF（3〜10pF）', aki('TMCV01-10P100VBW', '115470', '1個', 20,
            'TC3 と同じ TMCV01 系（同じ足）')),
    # コイル
    'L3': ('FCZ コイル 07S 50MHz（センタータップ付）', other('サトー電気 など（要確認）', '7S50',
           'FCZ 研究所の製品。類似品あり')),
    'L19': ('トロイダルコア T-50-10（0.6mm ポリウレタン線を巻く）', aki('T-50-10', '111948', '1個', 150,
           '線は別途')),
    'L16': ('トロイダルコア T-50-10（0.6mm ポリウレタン線を巻く）', aki('T-50-10', '111948', '1個', 150,
           '線は別途')),
    'L17': ('トロイダルコア T-50-10（0.6mm ポリウレタン線を巻く）', aki('T-50-10', '111948', '1個', 150,
            '線は別途')),
    'L18': ('トロイダルコア T-30-6（黄、0.4mm ポリウレタン線を巻く）', aki('T-30-6', '116458', '1個', 210,
            'Amidon。線は別途')),
    'L15': ('アキシャルインダクタ 47nH', other('DigiKey／Mouser（要確認）', 'Fastron SMCC 系 47nH',
           '秋月に扱いなし')),
    'L8': ('マイクロインダクタ 100nH', other('DigiKey／Mouser（要確認）', '100nH アキシャル（AL0510 相当）',
            '秋月に扱いなし。代替: 空芯 φ0.6mm 線・φ4.4mm 芯に 5 回巻き（線の中心で直径 5mm）'
            '・巻き幅 約3.9mm で約100nH（密巻き 3mm で約117nH、伸ばして合わせる）。'
            'L8 と L9 は軸を 90° ずらして付け、2 個の値をそろえる')),
    'L10': ('マイクロインダクタ 1mH', aki('AL0510-102K', '111367', '10本', 150)),
    'L7': ('マイクロインダクタ 15mH', aki('AL0510-153K', '111407', '10本', 110)),
    'L20': ('マイクロインダクタ 10µH', aki('AL0510-100K', '104922', '10本', 110)),
    'RFC1': ('マイクロインダクタ 10µH', aki('AL0510-100K', '104922', '10本', 110)),
    # ダイオード
    'D4': ('ゲルマニウムダイオード', other('サトー電気 など（要確認）', '1N60', '秋月に扱いなし')),
    'D1': ('整流ダイオード 1A', aki('1N4007-3485', '100934', '20本', 100, '1N4001 の代わりに 1N4007')),
    'D10': ('ショットキーダイオード 40V 1A', aki('1N5819', '117244', '10本', 100)),
    # トランジスタ・FET
    'Q13': ('NPN トランジスタ', aki('2SC2120-Y', '113829', '20個', 150)),
    'Q5': ('NPN トランジスタ', aki('2SC1815L-GR-T92', '106477', '20個', 100)),
    'Q12': ('PNP トランジスタ', aki('2SA950-Y', '113825', '20個', 150)),
    'Q4': ('RF 用 N-ch JFET', other('サトー電気 など（要確認）', '2SK439', '製造中止品')),
    'Q19': ('RF パワー MOSFET', other('DigiKey／RF 部品店（要確認）', 'RD06HVF1', '秋月に扱いなし')),
    'Q1': ('PNP トランジスタ', aki('2SA1015L-GR-T92', '106734', '20個', 100)),
    'Q2': ('N-ch JFET（TO-92 小型）', other('秋月電子／サトー電気 など（要確認）', '2SK192A-BL（東芝）',
           'Q2・Q3（RF 増幅）と Q6・Q7（IF 増幅）のカスコード。BL ランク（IDSS 12〜24mA）を 4 個そろえる（上段・下段の組で IDSS が近いもの）。ソース抵抗 R3・R18 は 100Ω。ピン 1 D・2 S・3 G（データシートで確認済み）。製造中止品の流通在庫')),
    # IC・モジュール
    'U8': ('DC-DC コンバータ 5V 1A（78xx 互換）', other('DigiKey／Mouser', 'R-78E5.0-1.0',
            '秋月は 0.5A 品 R-78E5.0-0.5（106353）のみ')),
    'U5': ('デュアルオペアンプ', aki('NJM2904D', '109216', '1個', 60)),
    'U9': ('3.3V LDO レギュレータ', aki('LP2950L-33-T92', '108749', '1個', 30)),
    'U6': ('Si5351A クロックジェネレータモジュール', aki('AE-Si5351A-B', '110679', '1セット', 650,
           'ピン配置を基板と照合してから取り付ける')),
    'U7': ('Seeed Studio XIAO ESP32C3', aki('113991054', '117454', '1個', 1080)),
    # リレー
    'K1': ('リレー DPDT 12V（オムロン G5V-2）', other('DigiKey／Mouser', 'G5V-2-DC12', '秋月に扱いなし')),
    # コネクタ（1×40 を切って全部に使う）
    'J1': ('同軸ケーブル（基板に直接はんだ付け）', other('（同軸ケーブル）', 'RG-174 など 50Ω', 'J1 はピンヘッダを使わず、穴 φ1.1mm に芯線と編組を直接はんだ付けする（編組の引き出しは短く）')),
    'J3': ('ピンヘッダ', aki('PH-1x40SG', '100167', '1本(40P)', 35, 'J3・J5〜J12 で 1 本')),
    # V2 受信部（12MHz の SSB スーパー、2026-10-29 追加）。購入先・型番は 2026-11-04 に確認
    'R11': ('カーボン抵抗 1/4W', aki('RD25S 27K', '125273', '100本', 100)),
    'R14': ('カーボン抵抗 1/4W', aki('CF25J33RB', '103941', '100本', 200)),
    'R15': ('カーボン抵抗 1/4W', aki('CF25J180RB', '125181', '100本', 100)),
    'R25': ('カーボン抵抗 1/4W', aki('CF25J220RB', '125221', '100本', 200)),
    'R19': ('カーボン抵抗 1/4W', aki('CF25J1K2B', '125122', '100本', 170)),
    'R5': ('カーボン抵抗 1/4W', aki('CF25J2K2B', '125222', '100本', 220)),
    'C38': ('積層セラミックコンデンサ 0.047µF 50V X7R 2.54mm', aki('RDER71H473K0P1H03B', '112059', '1個', 15,
             'AF 前置増幅の後の高域カット')),
    'R28': ('カーボン抵抗 1/4W', aki('CF25J8K2B', '125822', '100本', 100, 'AF 前置増幅 Q9 の入力')),
    'R24': ('カーボン抵抗 1/4W', aki('CF25J27RB', '114273', '100本', 100)),
    'R26': ('カーボン抵抗 1/4W', aki('CF25J10RB', '125100', '100本', 220, 'R69 と同じ品（足のピッチが違うので別の行）')),
    'C24': ('積層セラミックコンデンサ 33pF 50V C0G 2.54mm', aki('RDE5C1H330J0P1H03B', '113317', '10個', 180,
            'C24 は Q2 のドレイン同調、C31 は S メーター増幅の同調')),
    'C8': ('積層セラミックコンデンサ 27pF 50V C0G 5mm', aki('RDE5C1H270J0K1H03B', '108095', '10個', 100,
            'L3 を 38〜39MHz に同調（V2 で 15p から変更）。2.54mm ピッチ品がないため足を寄せて使う')),
    'C1': ('積層セラミックコンデンサ 10pF 50V NP0 2.54mm', aki('RD15N100J1HL2L-10', '104058', '10個', 100, '受信の入力同調')),
    'C17': ('積層セラミックコンデンサ 82pF 50V C0G 5mm', aki('RDE5C1H820J0K1H03B', '108101', '10個', 150,
            'ラダーフィルタ。値は水晶の運動定数を測ってから決める。2.54mm ピッチ品がないため足を寄せて使う')),
    'C18': ('積層セラミックコンデンサ 100pF 50V NP0 2.54mm', aki('RD15N101J1HL2L-10', '104061', '10個', 100,
            'ラダーフィルタ。値は水晶の運動定数を測ってから決める')),
    'C19': ('積層セラミックコンデンサ 120pF 50V C0G 5mm', aki('RDE5C1H121J0K1H03B', '108103', '10個', 100,
            'ラダーフィルタ。値は水晶の運動定数を測ってから決める。2.54mm ピッチ品がないため足を寄せて使う')),
    'D2': ('小信号ダイオード', aki('1N4148', '100941', '50本', 200, '受信入力の保護')),
    'L1': ('トロイダルコア T-30-6（黄、0.4mm ポリウレタン線 11 回、2 回目にタップ）', aki('T-30-6', '116458', '1個', 210,
            'Amidon。L18 と同じコア。線は別途')),
    'L2': ('トロイダルコア T-30-6（黄、0.4mm ポリウレタン線 11 回、3 回目にタップ）', aki('T-30-6', '116458', '1個', 210,
            'Amidon。L1 と同じコア（タップの位置だけ違う）。線は別途')),
    'L4': ('マイクロインダクタ 8.2µH', other('マルツ／DigiKey など（要確認）', 'AL0510-8R2K 相当（アキシャル 8.2µH）',
            '秋月に 8.2µH のマイクロインダクタの扱いなし（2026-11-04 確認）')),
    'L5': ('マイクロインダクタ 4.7µH', aki('AL0410-4R7K', '104931', '10本', 80,
            'AL0510 の 4.7µH は扱いなし。一回り小さい AL0410 を縦に立てる')),
    'U1': ('ダブルバランスドミキサ IC（SSOP8）', aki('NJM2594V', '111195', '1個', 150, '第 1 混合と積検波で 2 個。表面実装')),
    'U4': ('5V 3 端子レギュレータ', aki('TA78L05S', '108973', '1個', 20, '受信用 5V。78L05 と同じピン配置（TO-92）')),
    'U3': ('対数増幅器（S メーター）', aki('AD8307ANZ', '100195', '1個', 2000, 'DIP-8')),
    'J2': ('電源線（基板に直接はんだ付け）', other('（電線）', 'AWG20（0.5sq）', 'J2 はピンヘッダを使わず、穴 φ1.1mm に電線を直接はんだ付けする（電流は送信時でも 1A 弱）')),
    'J4': ('ADS1015 12 ビット I2C AD コンバータモジュール', aki('AE-ADS1015', '113838', '1個', 540,
            '付属のピンヘッダで基板に立てて差す。プルアップ抵抗のジャンパはつながない')),
    'Y1': ('水晶振動子 12MHz HC-49/S', aki('HUSG-12.000-20', '108669', '1個', 30,
           'ラダーフィルタ用に同じロットを 10〜20 個買い、直列共振が ±50Hz 以内の 6 個を選ぶ')),
    # パネル部品
    'LED1': ('3mm LED 黄', aki('OSY5JA3Z74A', '111639', '1個', 20)),
}

# 回路図に載っていない部品: 品名の先頭一致 → (購入先, 購入先の型番, 販売コード, 入数, 価格, 購入メモ)
EXTRA = [
    ('放熱器 17PB046', aki('17PB046-01025', '105050', '1個', 90)),
    ('RF ゲイン用 可変抵抗', aki('SH16K4B103L20KCCI', '118292', '1個', 80)),
    ('AF ボリューム', aki('SH16K4A103L20KCCI', '129553', '1個', 60)),
    ('ロータリーエンコーダ', aki('EC12E2420801', '106357', '1個', 100, '押しスイッチ付きか要確認')),
    ('LCD NX4832T035', other('Nextion 公式ストア（AliExpress・Amazon など）', 'NX4832T035_011')),
    ('マイクコネクタ', other('千石電商／マルツ など（要確認）', '4P 丸型マイクコネクタ（メス、パネル取付 φ16）')),
    ('イヤホンジャック', aki('MJ-352W-C', '117359', '1個', 175, 'M6 ナットでふたに固定。スイッチ付き')),
    ('電源スイッチ', other('要確認', 'φ13 穴に合うもの',
                      'LED は秋月 OSG5TA3Z74A（111635）、2.2kΩ は CF25J2K2B（125222）')),
    ('DC ジャック', aki('MJ-14 ／ MF-524M ／ B-014IF', '106342 ／ 107079 ／ 100093', '2個／1個／1個', '70／210／150',
                     'DC ジャック／ヒューズホルダ／BNC。ヒューズは MF51NR 250V 1（107129、40 円）')),
    ('IC ソケット', aki('2227-08-03', '100017', '10個', 110)),
    ('スピーカー', aki('DXYD50N-22Z-8A-F', '116024', '1個', 250)),
    ('M3×8 皿ねじ・M3 ナット', other('ホームセンター／モノタロウ', '')),
    ('M3 インサートナット', other('Amazon／モノタロウ', '')),
    ('M3×', other('ホームセンター／モノタロウ', '')),
]


def extra_info(name):
    for key, info in EXTRA:
        if name.startswith(key):
            return info
    return ('', '', '', '', '', '')


def section_of(ref, fp):
    if ref == 'U7':
        return 'マイコンモジュール'
    prefix = re.match(r'[A-Za-z]+', ref).group(0)
    if prefix == 'C':
        return 'コンデンサ（電解）' if 'cp_radial' in fp.lower() else 'コンデンサ（セラミック）'
    return {
        'R': '抵抗', 'VR': '半固定抵抗', 'TC': 'トリマコンデンサ', 'L': 'コイル', 'RFC': 'コイル',
        'D': 'ダイオード', 'Q': 'トランジスタ・FET', 'IC': 'IC・レギュレータ・モジュール',
        'U': 'IC・レギュレータ・モジュール', 'T': 'トランス・リレー',
        'K': 'トランス・リレー', 'J': 'コネクタ', 'Y': '水晶振動子', 'LED': 'パネル部品（基板非搭載）',
    }.get(prefix, 'その他')


SECTION_ORDER = ['抵抗', '半固定抵抗', 'コンデンサ（セラミック）', 'コンデンサ（電解）',
                 'トリマコンデンサ', 'コイル', 'ダイオード', 'トランジスタ・FET', '水晶振動子',
                 'IC・レギュレータ・モジュール', 'マイコンモジュール', 'トランス・リレー',
                 'コネクタ', 'パネル部品（基板非搭載）']


def first_ref(refs):
    first = refs.split(',')[0].split('-')[0].strip()
    return first


def expand_refs(refs):
    """'Q20,Q18,Q15-Q22' → ['Q20', 'Q18', 'Q15', ..., 'Q22']（kicad-cli は連番を範囲にまとめる）"""
    out = []
    for part in refs.split(','):
        m = re.match(r'([A-Za-z]+)(\d+)(?:-[A-Za-z]+(\d+))?$', part.strip())
        if not m:
            out.append(part.strip())
            continue
        out += [f'{m.group(1)}{n}' for n in range(int(m.group(2)), int(m.group(3) or m.group(2)) + 1)]
    return out


def lookup(first):
    if first in PARTS:
        return PARTS[first]
    if first.startswith('J') and first != 'J4':
        return PARTS['J3']
    raise SystemExit(f'購入先が決まっていない部品: {first}（PARTS に追加する）')


def ref_key(ref):
    m = re.match(r'([A-Za-z]+)(\d*)', ref)
    return (m.group(1), int(m.group(2) or 0))


def load_bom():
    rows = []
    with open(os.path.join(HERE, 'bom.csv'), encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            first = first_ref(r['Reference'])
            name, buy = lookup(first)
            rows.append({
                'section': section_of(first, r['Footprint']), 'refs': r['Reference'],
                'value': r['Value'], 'fp': r['Footprint'].split(':')[-1], 'qty': int(r['Qty']),
                'name': name, 'buy': buy, 'first': first,
            })
    rows.sort(key=lambda r: (SECTION_ORDER.index(r['section']), ref_key(r['first'])))
    return rows


def md_extra_rows():
    """BOM.md の「回路図に載っていない部品」表から (品名, 数量, 備考) を読む。"""
    out = []
    in_table = False
    with open(os.path.join(HERE, 'BOM.md'), encoding='utf-8') as fh:
        for line in fh:
            if line.startswith('## 回路図に載っていない部品'):
                in_table = True
                continue
            if in_table and line.startswith('## '):
                break
            if in_table and line.startswith('| ') and not line.startswith('| 品名'):
                cells = [c.strip() for c in line.strip()[1:-1].split('|')]
                out.append((cells[0], cells[1], cells[-1]))
    return out


def model_cell(buy):
    """BOM.md 用の「型番（販売コード）」表記。"""
    shop, model, code = buy[:3]
    if not model:
        return ''
    return f'{model}（{code}）' if code else model


def write_csv(rows, extras):
    path = os.path.join(HERE, 'bom_purchase.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh, lineterminator='\r\n')
        w.writerow(['区分', 'Reference', '品名', '値/型番', 'フットプリント', '数量',
                    '購入先', '購入先の型番', '販売コード', '入数', f'価格（税込、{CHECKED}）', '購入メモ'])
        for r in rows:
            w.writerow([r['section'], r['refs'], r['name'], r['value'], r['fp'], r['qty'], *r['buy']])
        for name, qty, _note in extras:
            w.writerow(['回路図に載っていない部品', '', name, '', '', qty, *extra_info(name)])
    return path


def update_md(rows):
    """BOM.md の表に「購入先」「購入先の型番（販売コード）」列を入れる（備考の手前）。"""
    by_ref = {}
    for r in rows:
        for ref in expand_refs(r['refs']):
            by_ref[ref] = r['buy']
    path = os.path.join(HERE, 'BOM.md')
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    # 表の行の間に挟まった空行を詰める（表が切れるのを防ぐ）
    text = re.sub(r'(\|\n)\n(\| )', r'\1\2', text)
    out = []
    mode = None  # 'parts' / 'extra'
    for line in text.split('\n'):
        if line.startswith('| Reference |'):
            mode = 'parts'
            line = '| Reference | 値 / 型番 | フットプリント | 数量 | 購入先 | 購入先の型番（販売コード） | 備考 |'
        elif line.startswith('| 品名 |'):
            mode = 'extra'
            line = '| 品名 | 数量 | 購入先 | 購入先の型番（販売コード） | 備考 |'
        elif mode and line.startswith('|---'):
            line = '|---' * (7 if mode == 'parts' else 5) + '|'
        elif mode and line.startswith('| '):
            cells = [c.strip() for c in line.strip()[1:-1].split('|')]
            if mode == 'parts':
                cells = cells[:4] + cells[-1:]  # 前回入れた列を外す
                first = re.split(r'[ ,]', cells[0])[0].split('-')[0]
                buy = by_ref.get(first, ('', '', ''))
                cells[4:4] = [buy[0], model_cell(buy)]
            else:
                cells = cells[:2] + cells[-1:]
                buy = extra_info(cells[0])
                cells[2:2] = [buy[0], model_cell(buy)]
            line = '| ' + ' | '.join(cells) + ' |'
        else:
            mode = None
        out.append(line)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write('\n'.join(out))


def main():
    rows = load_bom()
    extras = md_extra_rows()
    path = write_csv(rows, extras)
    update_md(rows)
    print(f'{os.path.basename(path)}: {len(rows)} 行（{sum(r["qty"] for r in rows)} 点）'
          f'＋回路図外 {len(extras)} 行')


if __name__ == '__main__':
    main()
