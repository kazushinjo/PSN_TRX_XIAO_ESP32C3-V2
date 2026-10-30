PSN_TRX_XIAO_ESP32C3-V2 完全KiCadプロジェクト（V2 Ver 1.0）

【このフォルダの開き方】
1. KiCad 10 のプロジェクトマネージャで「ファイルを開く」→ PSN_TRX.kicad_pro を選択
   （※ .kicad_sch や .kicad_pcb を直接開くとライブラリが解決されません。
      必ず .kicad_pro から開いてください）
2. 基板エディタで「検査 → デザインルールチェッカー(DRC)」を実行
   （シルク警告3件は修正済み。残る場合は除外で可）
3. 発注時は「ファイル → 製造用出力 → Gerber/ドリル」で再出力してください
   （同梱の production/ は 2026-10-30 に基板 V2 Ver 1.0 から DRC エラー0・未配線0・回路図との不一致0 の状態で出力済み）

【含まれるもの】
- PSN_TRX.kicad_pro / .kicad_sch / .kicad_pcb / .kicad_sym / .kicad_prl
- sym-lib-table / fp-lib-table（カスタムライブラリは ${KIPRJMOD} 参照＝このフォルダ内完結）
- PSN_TRX.pretty/（カスタムフットプリント17種: 3SK59, J310, RD06HVF1, XIAOソケット, 7T50コイル, Heatsink_20PB020, Heatsink_17PB046 等）
- blank.kicad_wks（図枠テンプレート）
- report.txt（回路図→基板 反映ログ: 警告0/エラー0）
- BOM.md / bom.csv（部品表）
- refdes_map_2026-10-15.csv（部品番号の新旧対応表。2026-10-15 に部品番号を回路図の位置順に振り直した）
- bom_purchase.csv（購入用部品表: 購入先・型番・秋月の販売コード・入数・価格）／make_bom_purchase.py（その作成スクリプト）
- production/（JLCPCB 用製造データ、2026-10-30 に V2 Ver 1.0 から出力）
    PSN_TRX_Gerber_JLCPCB.zip … ガーバー11層＋ドリル(PTH/NPTH)＋ジョブファイル。発注時はこれだけアップロード
    PSN_TRX_BOM_JLCPCB.csv / PSN_TRX_CPL_JLCPCB.csv … 実装も頼む場合の部品表・座標（LCSC 番号は未記入）
    発注指定: 4層、1.6mm、134.1×129.7mm、最小穴 0.3mm、最小線幅 0.25mm・間隔 0.2mm（いずれも標準仕様内）
- PSN_TRX_部品配置図.pdf（A3・1ページ: 上面から見た部品外形と番号、裏面の Q4/Q5 は Q2 の真裏、2026-10-28 に基板 Ver 2.1 から出力。値は入れず部品番号のみ。値は docs/PSN_TRX_部品実装図.pdf の各ページの表を参照）

【標準ライブラリについて】
回路図・基板は KiCad標準ライブラリ（Device, Transistor_BJT, Regulator_Linear,
Diode_THT, Resistor_THT, Connector_PinHeader 等）も使用しています。
これらはKiCad 10インストーラに同梱されています。
「ライブラリが見つかりません」と出る場合は、KiCadインストール時に
「Libraries」にチェックが入っていなかった可能性があります。
その場合はKiCadインストーラを再実行し Libraries を追加してください。
