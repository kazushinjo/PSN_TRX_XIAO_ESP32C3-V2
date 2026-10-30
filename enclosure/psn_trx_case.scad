// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 JA6FUF (kazushinjo)
// ============================================================
// PSN_TRX_XIAO_ESP32C3  ケース（筐体）  OpenSCAD パラメトリックモデル
//   基板: kicad/PSN_TRX.kicad_pcb  134.0 x 129.63 mm（V2 Ver 1.0）, M3 取付穴 4 か所（角から 4 mm）
//   構成: ベース（底板＋左右側板）／ふた／前面パネル／後面パネル（溝に差し込み）
//   操作部（LCD・TUNE・VOL・RF・POWER）と MIC・PHN はふたの上面、前面は機種名、電源・アンテナ・ヒューズは後面
//
//   表示・出力する部品は mode（数字）で選択（コマンドライン: -D mode=1 等）
//     0: 組立図（ふたを浮かせて表示）      ← 確認用
//     1: ベース（底板＋左右側板）          ← 3D 印刷用（そのままの向き）
//     2: ふた                            ← 3D 印刷用（外面を上、エンボス文字が上）
//     3: 前面パネル（ボス一体）            ← 3D 印刷用（上端を下にして立てる。ボスがベッドに立つのでサポート不要）
//     4: 後面パネル（ボス一体）            ← 3D 印刷用（同上）
//     5: 組立図（ふたを閉じた状態）         ← 確認用
//     6: ふたなし内部                           ← 確認用
//     7: 前面パネル穴あけ図（2D、DXF/SVG 出力用）
//     8: 後面パネル穴あけ図（2D、DXF/SVG 出力用）
//     9: LCD ベゼル（ふた上面に取付）       ← 3D 印刷用（表を下、ボスが上）
//   3D 印刷用（1〜4, 9）は Z=0 のベッド面上、X/Y が正の範囲に置いてある。
//
//   座標: X = 左→右（前から見て）、Y = 前→後（前面 Y=0）、Z = 下→上
//   ねじ: 基板固定 M3x6（4 本）、ふた固定 M3x10（8 本。うち 4 本は前後パネルのすぐ内側、左右の側面から 60mm のボスに留める）、LCD→ベゼル M3x6（4 本）、ベゼル→ふた M3x8（4 本、ふた裏から）。ボス・スタンドオフには M3 インサートナット（下穴 φ5.0）を熱圧入する。
//   ※ LCD・コネクタ類の寸法は代表値。実物を実測して下の値を修正してから出力すること。
// ============================================================

mode = 2;   // ← ここを 0〜9 に変えて F5/F6（上の一覧参照）
$fn = 64;

// ---------------- 外形 ----------------
W  = 220;      // 幅（220mm 角ベッドで印刷できる上限）
D  = 180;      // 奥行き
H  = 40;       // 高さ（ふた込み）。基板上の最も高い部品（放熱器 HS1、25mm）の上端は底から約 34.6mm
wall   = 3.0;  // 側板厚
floor_t = 3.0; // 底板厚
lid_t  = 3.0;  // ふた厚
panel_t = 3.0; // 前後パネル厚（3D プリント or アルミ 3mm）
groove_d = 1.5;          // パネル溝の深さ
groove_w = panel_t + 0.4;// パネル溝の幅
overhang = 2.0;          // 側板・天井(ふた)・底板を前後パネル外面より長くする量（前後それぞれ）
fit = 0.4;               // パネルのはめあいクリアランス
panel_inset = overhang - fit / 2;   // パネル溝の開始位置（パネル外面がケース端から overhang の位置に来る）

// ---------------- 基板 ----------------
pcb_u = 134.0;  // 基板 長辺（KiCad X）
pcb_v = 129.63; // 基板 短辺（KiCad Y）
pcb_t = 1.6;
standoff_h = 5;          // 基板下の高さ（基板裏のリード約 2mm より高く）
standoff_od = 9;         // インサートナット用に肉厚を確保
standoff_hole = 5.0;     // M3 インサートナット用の下穴
pcb_front_gap = 24;      // 前面パネル内面〜基板前端（基板後端と後面パネル固定ボスの隙間を確保）
bx = 43.3;                                     // 基板の X 位置（左端）。放熱器をなるべく右に置き、左にスピーカーを入れる（右は上面右列の部品の本体まで 1.5mm）
by = panel_inset + groove_w + pcb_front_gap;   // 基板の Y 位置（前端）
bz = floor_t + standoff_h;                     // 基板下面の Z
// 基板座標(u: KiCad X, v: KiCad Y、原点=基板左上) → ケース座標
// 基板の右辺（LCD/エンコーダ用ヘッダ J8/J7/J9）が前面、左辺（J1/J2）が後面を向く
function bp(u, v) = [bx + pcb_v - v, by + pcb_u - u];
mount_uv = [[4, 4], [130, 4], [4, 125.63], [130, 125.63]];

// ---------------- パネル内寸 ----------------
inner_w = W - 2 * wall;
panel_w = inner_w + 2 * groove_d - fit;              // パネル幅
panel_z0 = floor_t - groove_d + fit / 2;             // パネル下端の Z（底板の溝の中）
panel_h = H - lid_t - panel_z0 - fit / 2;           // パネル高さ（上端はふた裏面まで。上から差し込み、左右側板の溝と底板の溝で保持）
panel_x0 = wall - groove_d + fit / 2;                // パネル左端の X
// パネル座標 (x: 左端から, z: 下端から) → ケース X/Z
function pz(z) = panel_z0 + z;

// ---------------- 上面部品（ふた上面、ケース X/Y 座標。前から見て読める向き） ----------------
// LCD: Nextion NX4832T035（3.5インチ 480×320 シリアル HMI、基板 J8 に接続）
//   外形・表示領域は Nextion NX4832T035 の公表値（100.5×54.94×5.45mm、表示領域 73.44×48.96mm）。
//   ※ 表示領域の中心ずれ（lcd_win_off）と取付穴（lcd_holes）は推定値。実物を実測して修正すること。
lcd_mod   = [100.5, 54.94];  // モジュール外形（基板）
lcd_win   = [74.5, 50.0];    // 表示窓（表示領域 73.44×48.96 ＋ 余裕）
lcd_win_off = [0, 0];        // 表示領域の中心ずれ（モジュール中心基準。ガラス 85.5mm が基板の左右中央と仮定）※要実測
lcd_holes = [94.5, 48.94];   // 取付穴ピッチ（ガラス左右の基板 4 隅、基板端から約 3mm と仮定）※要実測
lcd_depth = 10;              // ふた上面（ベゼル裏）から LCD 裏のコネクタ下端まで
// LCD の取付: ふた上面にベゼルを置き、LCD はベゼル裏のボス（M3 インサートナット）に LCD 基板の裏側からねじ止め。
//             ベゼルは別の 4 個のインサートナットで、ふた裏側からふたの穴を通したねじで固定する。
bezel      = [125, 62];      // ベゼル外形（高さは LCD 切り欠き 57mm ＋ 上下 2.5mm の重なり）
bezel_t    = 6.0;            // ベゼル厚（上面に出るフランジ）
bezel_r    = 4;              // 角の丸み
lcd_cut    = lcd_mod + [2, 2.06];  // ふたの LCD 用切り欠き（モジュール外形＋クリアランス 1mm）
lcd_boss_h  = 4.0;           // ベゼル裏〜LCD 基板（ガラス＋ベゼル厚。※要実測）
lcd_boss_od = 6.5;
lcd_insert  = 5.0;           // M3 インサートナット下穴
lcd_insert_depth = lcd_boss_h + bezel_t - 1.0;   // ベゼル前面に 1mm 残す止まり穴
bezel_screw = [bezel[0] / 2 - 6, 20];            // ベゼル固定ねじ位置（中心からのずれ。LCD の左右の帯に上下 2 本ずつ）
bezel_insert_depth = bezel_t - 1.0;              // ベゼル前面に 1mm 残す止まり穴
bezel_hole = 3.4;            // ふたのベゼル固定ねじ穴（M3）
lcd_c = [13 + bezel[0] / 2, 47 + bezel[1] / 2];  // LCD・ベゼル中心（ベゼル左端 X=13、前端 Y=47。手前に MIC・PHN、奥は放熱器の手前まで）

// LCD の右（基板の外側、X > 174 のふた裏は空いている）に縦 1 列（同じ X）: 奥から POWER・RF・VOL・TUNE
psw_c   = [184, 152]; psw_hole = 13.0; psw_body = 16;                   // 電源スイッチ（丸穴 φ13）
enc_c   = [psw_c[0], 45];  enc_hole = 7.2;  enc_knob = 32;  enc_body = 14;   // ロータリーエンコーダ（M7 ブッシュ）。enc_knob = 周波数ダイヤルのつまみ直径、enc_body = ふた裏の本体の幅
afv_c   = [psw_c[0], 85];  afv_hole = 7.2;  afv_knob = 20;  afv_body = 17;   // AF ボリューム
rfg_c   = [psw_c[0], 118]; rfg_hole = 7.2;  rfg_knob = 20;  rfg_body = 17;   // RF ゲイン（ボリューム、VOL と同じ寸法と仮定）
led_c   = [psw_c[0] + 20, psw_c[1]]; led_hole = 3.1;                    // 3mm 電源 LED（電源スイッチの右、LED ホルダ使用時は 5.0）
// LCD の手前（前面寄り）、LCD の中央付近に横 1 列: 左から MIC・PHN。
//   ふた裏の本体は基板の前端 6mm まで（X 60〜110 のこの範囲には部品なし。J8 は前端から 6.4mm）。MIC は左前の前面パネル固定ボス（X=60）の右にかわす
mic_c   = [74, 22];  mic_hole = 16.2; mic_flange = 20; mic_body = 20;   // 4P 丸型マイクコネクタ。mic_flange = つば・プラグの太さ、mic_body = ふた裏の本体の太さ
phone_c = [99, 22];  phone_hole = 6.2; phone_plug = 8; phone_body = 12; // 3.5mm イヤホンジャック（秋月 MJ-352W-C、M6 P0.5 ねじ長 3.5mm、スイッチ付き）。phone_plug = プラグ根元の太さ
phone_thin = 15; phone_thin_t = 1.8;   // PHN 穴を中心に 15x15mm を板厚 1.8mm に（ふた裏から座ぐり。ジャックのねじ長さ対策）

// 干渉チェック
knob_gap = 5;   // つまみ同士・つまみとほかの部品の最小隙間
assert(norm(afv_c - enc_c) >= enc_knob / 2 + afv_knob / 2 + knob_gap, "VOL つまみと TUNE つまみの隙間が 5mm 未満");
assert(norm(rfg_c - afv_c) >= afv_knob / 2 + rfg_knob / 2 + knob_gap, "RF つまみと VOL つまみの隙間が 5mm 未満");
assert(norm(psw_c - rfg_c) >= rfg_knob / 2 + psw_hole / 2 + knob_gap, "電源スイッチと RF つまみの隙間が 5mm 未満");
// 文字（穴の上＝奥側 4〜7.5mm、高さ約 3.2mm）が一つ奥のつまみにかからない
assert(enc_c[1] + enc_knob / 2 + 7.5 + 2 <= afv_c[1] - afv_knob / 2 - 1, "TUNE の文字が VOL つまみにかかる");
assert(afv_c[1] + afv_knob / 2 + 4 + 2 <= rfg_c[1] - rfg_knob / 2 - 1, "VOL の文字が RF つまみにかかる");
assert(rfg_c[1] + rfg_knob / 2 + 4 + 2 <= psw_c[1] - psw_hole / 2 - 1, "RF の文字が電源スイッチにかかる");
assert(psw_c[1] + psw_hole / 2 + 4.5 + 2 <= D - 3, "POWER の文字がふたの縁にかかる");
assert(lcd_c[0] + bezel[0] / 2 + knob_gap <= enc_c[0] - enc_knob / 2, "ベゼルと TUNE つまみの隙間が 5mm 未満");
for (c = [[enc_c, enc_body], [afv_c, afv_body], [rfg_c, rfg_body], [psw_c, psw_body]])
    assert(c[0][0] - c[1] / 2 >= bx + pcb_v + 1, "上面部品のふた裏の本体が基板の上にかかる");
for (c = [[mic_c, mic_body], [phone_c, phone_body]])
    assert(c[0][0] + c[1] / 2 <= bx - 1 || c[0][1] + c[1] / 2 <= by + 6, "MIC・PHN のふた裏の本体が基板の部品にかかる");
assert(mic_c[1] + mic_flange / 2 + 15 <= lcd_c[1] - bezel[1] / 2, "MIC とベゼルの隙間が 15mm 未満（プラグを抜き差しする指が入らない）");
assert(mic_c[1] + mic_flange / 2 + 4 + 2 + 3 <= lcd_c[1] - bezel[1] / 2, "MIC・PHN の文字がベゼルに近すぎる");
assert(phone_c[1] + phone_plug / 2 + 5 <= lcd_c[1] - bezel[1] / 2, "PHN とベゼルの隙間が 5mm 未満");
assert(phone_c[0] - phone_plug / 2 >= mic_c[0] + mic_flange / 2 + 10, "MIC と PHN の隙間が 10mm 未満");
assert(phone_thin > phone_hole + 1 && phone_thin_t < lid_t, "PHN の薄肉部の寸法が不正");
assert(phone_c[0] - phone_thin / 2 >= mic_c[0] + mic_hole / 2 + 2, "PHN の薄肉部が MIC の穴に近すぎる");
assert(phone_c[1] - phone_thin / 2 >= panel_inset + panel_t + 1, "PHN の薄肉部が前面パネルの上端にかかる");

// ---------------- 後面部品（ケース X 座標、Z は後面パネル座標） ----------------
// 高さは後面パネルの外から見える範囲（底板上面〜ふた裏面）の中央にそろえる
rear_zc = (floor_t - panel_z0 + H - lid_t - panel_z0) / 2;
fuse_c = [21, rear_zc];     fuse_hole = 12.5; fuse_flange = 18; fuse_body = 16;  // 5x20 パネル取付ヒューズホルダ（パネル裏に約 35mm）
dc_c   = [42, rear_zc];     dc_hole = 8.0;    dc_flange = 14;   dc_body = 12;    // 12V DC ジャック（パネル取付、2.1/2.5mm）。ヒューズの右隣（DC ジャック〜ヒューズの線を短く）
dc_thin = 15; dc_thin_t = 1.8;   // DC ジャック穴を中心に 15x15mm を板厚 1.8mm に（パネル内側から座ぐり。ジャックのねじ長さ対策）
j1_uv  = [11.1, 38.5];      // 基板 J1（アンテナ）の中心（kicad/PSN_TRX.kicad_pcb より）
l1_v   = 42.0;              // 基板 L1（T-50 縦置き、高さ約 14mm、基板の後端にかかる）の J1 側の端（v）
bnc_c  = [bp(j1_uv[0], j1_uv[1])[0] + 3.6, rear_zc]; bnc_hole = 9.6; bnc_flange = 14; bnc_body = 12;   // BNC（アンテナ）。J1 のすぐ後ろ（同軸を短く）、左の L1 をかわして 3.6mm 右
for (c = [[fuse_c, fuse_flange], [dc_c, dc_flange], [bnc_c, bnc_flange]]) {
    assert(c[0][1] - c[1] / 2 >= floor_t - panel_z0, "後面部品のつばが底板にかかる");
    assert(c[0][1] + c[1] / 2 <= H - lid_t - panel_z0, "後面部品のつばがふたにかかる");
}
assert(fuse_c[0] + fuse_body / 2 <= bx - 1, "ヒューズホルダの本体が基板の上にかかる");
for (c = [[bnc_c, bnc_body, 12], [dc_c, dc_body, 15]])   // [位置, 太さ, パネル内側への長さ]
    assert(abs(c[0][0] - psw_c[0]) >= c[1] / 2 + psw_body / 2 + 1 || psw_c[1] + psw_body / 2 + 2 <= D - panel_inset - fit / 2 - panel_t - c[2], "電源スイッチの本体が後面の BNC・DC ジャックにかかる");
assert(abs(fuse_c[0] - phone_c[0]) >= fuse_body / 2 + phone_body / 2 + 1 || phone_c[1] + phone_body / 2 + 1 <= D - panel_inset - fit / 2 - panel_t - 35, "PHN の本体がヒューズホルダの本体にかかる");
// DC ジャックの本体（パネル内面から 15mm、Z 14〜26mm）は基板の左後ろの角に平面で約 1.6mm かかるが、そこには取付穴 H3 しかない（基板上 4mm 以上離す）
assert(D - panel_inset - fit / 2 - panel_t - 15 >= by + pcb_u + 1 || pz(dc_c[1]) - dc_body / 2 >= bz + pcb_t + 4, "DC ジャックの本体が基板の後端の部品にかかる");
assert(dc_c[0] - dc_flange / 2 >= fuse_c[0] + fuse_flange / 2 + 5, "ヒューズと DC の間が狭い");
// BNC の本体（パネル内面から 12mm、Z 14〜26mm）は基板の後端に平面で約 1.2mm かかる。そこにある背の高い部品は L1 だけなので、L1 をかわす
assert(D - panel_inset - fit / 2 - panel_t - 12 >= by + pcb_u + 1 || bnc_c[0] - bnc_body / 2 >= bp(0, l1_v)[0] + 1, "BNC の本体が基板の L1 にかかる");
assert(abs(dc_c[0] - bnc_c[0]) >= dc_flange / 2 + bnc_flange / 2 + 5, "DC と BNC の間が狭い");
assert(dc_thin > dc_hole + 1 && dc_thin_t < panel_t, "DC ジャックの薄肉部の寸法が不正");
// 穴の上の文字（中心 +3mm、高さ約 3.2mm）がふた裏面より下、DC の下の文字（-3mm、高さ約 2.4mm）が底板より上に収まる
assert(fuse_c[1] + fuse_flange / 2 + 3 + 1.6 + 0.5 <= H - lid_t - panel_z0, "FUSE の文字がふたにかかる");
assert(bnc_c[1] + bnc_flange / 2 + 3 + 1.6 + 0.5 <= H - lid_t - panel_z0, "ANT の文字がふたにかかる");
assert(dc_c[1] + dc_flange / 2 + 3 + 1.6 + 0.5 <= H - lid_t - panel_z0, "DC の文字がふたにかかる");
assert(dc_c[1] - dc_flange / 2 - 3 - 1.2 - 0.5 >= floor_t - panel_z0, "+ CENTER の文字が底板にかかる");


// ---------------- ふた固定 ----------------
ear_y = [32, D - 10.2]; // ふた固定ボスの Y 位置（左右側板の上端内側）。後ろは後面パネルの溝の手前（左後ろのスピーカーをかわす）
ear_d = 10; ear_h = 10; ear_hole = 5.0; // ボス外径 10mm、M3 インサートナット用の下穴 φ5・深さ ear_h（上端から）
ear_x = [wall + ear_d / 2 - 1, W - wall - ear_d / 2 + 1];  // 側板に 1mm 食い込ませる
// 前後パネル固定ボス: 前面・後面パネルの内面に密着させてパネルと一体で印刷（2 本ずつ、左右の側面から同じ距離 panel_boss_d）。
//   上端はふたから M3x10、下端は底板の裏から M3x10 皿ねじでインサートナットに留める（パネルをふたと底板に固定）
panel_boss_d = 60;
panel_boss_x = [panel_boss_d, W - panel_boss_d];
panel_boss_y = [panel_inset + groove_w + ear_d / 2, D - panel_inset - groove_w - ear_d / 2];
ear_pos = [for (x = ear_x, y = ear_y) [x, y]];                       // ベースのふた固定ボス（4 か所）
panel_boss_pos = [for (x = panel_boss_x, y = panel_boss_y) [x, y]];  // パネル一体ボス（4 か所）
boss_pos = concat(ear_pos, panel_boss_pos);                          // ふた固定ねじの位置（全 8 か所）
panel_boss_z = [floor_t + fit / 2, H - lid_t - fit / 2];             // パネル一体ボスの下端・上端（パネルと同じすき間）
panel_boss_bot_insert = 8;                                           // 底板側インサートの下穴深さ
for (c = [[fuse_c, fuse_body], [dc_c, dc_body], [bnc_c, bnc_body]], x = panel_boss_x)
    assert(abs(c[0][0] - x) >= c[1] / 2 + ear_d / 2 + 1, "後面部品の本体が後面パネル固定ボスにかかる");
for (c = [[fuse_c, fuse_body], [dc_c, dc_body], [bnc_c, bnc_body]], x = ear_x)
    assert(abs(c[0][0] - x) >= c[1] / 2 + ear_d / 2 + 1, "後面部品の本体が後ろのふた固定ボスにかかる");
for (x = panel_boss_x) {
    assert(abs(x - lcd_c[0]) >= bezel[0] / 2 + 3.3 + 7 || lcd_c[1] - bezel[1] / 2 >= panel_boss_y[0] + 3.3 + 7, "ベゼルと前面パネル固定ねじ頭の間が 7mm 未満（ドライバーが入らない）");
    assert(abs(x - lcd_c[0]) >= lcd_cut[0] / 2 + ear_d / 2 + 1 || lcd_c[1] - lcd_cut[1] / 2 >= panel_boss_y[0] + ear_d / 2 + 1, "LCD が前面パネル固定ボスにかかる");
    assert(x + ear_d / 2 + 1 <= bx || x - ear_d / 2 - 1 >= bx + pcb_v || by + pcb_u + 1 <= panel_boss_y[1] - ear_d / 2, "基板が後面パネル固定ボスにかかる");
}
assert(lcd_c[0] - bezel[0] / 2 >= ear_x[0] + 3.3 + 2, "ベゼルが左前のふた固定ねじ頭にかかる");
for (c = [[bnc_c, bnc_body], [dc_c, dc_body], [fuse_c, fuse_body], [phone_c, phone_body], [mic_c, mic_body], [enc_c, enc_body], [afv_c, afv_body], [rfg_c, rfg_body], [psw_c, psw_body]], x = ear_x, y = ear_y)
    assert(norm(c[0] - [x, y]) >= c[1] / 2 + ear_d / 2 + 1, "上面部品のふた裏の本体がふた固定ボスにかかる");
for (c = [[enc_c, enc_body], [afv_c, afv_body], [rfg_c, rfg_body], [psw_c, psw_body], [phone_c, phone_body], [mic_c, mic_body]], x = panel_boss_x, y = panel_boss_y)
    assert(norm(c[0] - [x, y]) >= c[1] / 2 + ear_d / 2 + 1, "上面部品のふた裏の本体がパネル固定ボスにかかる");
lid_screw = 3.4;        // M3x10（ふた 3mm ＋ ボス内 7mm）。皿ねじなら面一、なべねじも可

// ---------------- 文字 ----------------
font = "Liberation Sans:style=Bold";
emboss = 1.2;   // 機能表示文字の盛り上げ高さ（パネル外面からのエンボス）

// ============================================================
module rounded_box(size, r = 2) {
    hull() for (x = [r, size[0] - r], y = [r, size[1] - r])
        translate([x, y, 0]) cylinder(r = r, h = size[2]);
}

module groove_cut(y0) {
    // 底板・左右側板に通るパネル溝（前後とも）
    translate([wall - groove_d, y0, floor_t - groove_d]) cube([inner_w + 2 * groove_d, groove_w, H]);
}

// ---------------- ベース ----------------
module base() {
    hb = H - lid_t;
    difference() {
        union() {
            // 底板
            rounded_box([W, D, floor_t], 3);
            // 左右側板
            for (x = [0, W - wall]) translate([x, 0, 0]) cube([wall, D, hb]);
            // 基板スタンドオフ
            for (m = mount_uv) let(p = bp(m[0], m[1]))
                translate([p[0], p[1], 0]) cylinder(d = standoff_od, h = bz);
            // ふた固定ボス（側板の内側、底板から側板上端まで）
            for (b = ear_pos)
                translate([b[0], b[1], 0]) cylinder(d = ear_d, h = hb);
        }
        // パネル溝
        groove_cut(panel_inset);
        groove_cut(D - panel_inset - groove_w);
        // スタンドオフ穴
        for (m = mount_uv) let(p = bp(m[0], m[1]))
            translate([p[0], p[1], 1]) cylinder(d = standoff_hole, h = bz);   // 基板固定 M3x6: 基板 1.6 + 4.4mm がインサートに入る（穴深さ 7mm）
        // ボス穴
        for (b = ear_pos)
            translate([b[0], b[1], hb - ear_h - 1]) cylinder(d = ear_hole, h = ear_h + 2);
        // パネル一体ボスを留めるねじ穴（底板の裏から M3 皿ねじ）
        for (b = panel_boss_pos) translate([b[0], b[1], -1]) {
            cylinder(d = lid_screw, h = floor_t + 2);
            translate([0, 0, 1 - 0.01]) cylinder(d1 = 6.6, d2 = lid_screw, h = 1.81);
        }
        // 底面通風スロット（PA・放熱器の下）
        for (i = [-2:3]) let(p = bp(hs1_uv[0] - i * 4.5, hs1_uv[1]))
            translate([p[0] - 14, p[1] - 1, -1]) cube([28, 2.2, floor_t + 2]);
        // ゴム足の座ぐり
        for (x = [14, W - 14], y = [14, D - 14]) translate([x, y, -0.01]) cylinder(d = 12.5, h = 1);
    }
}

// ---------------- ふた（天板） ----------------
module lid() {
    // 上面の文字（エンボス）
    translate([0, 0, H - 0.01]) linear_extrude(emboss + 0.01) top_labels_2d();
    difference() {
        translate([0, 0, H - lid_t]) rounded_box([W, D, lid_t], 3);
        // LCD 切り欠き・ベゼル固定穴・つまみ・電源スイッチ・電源 LED
        translate([0, 0, H - lid_t - 1]) linear_extrude(lid_t + 2) top_holes_2d();
        // ねじ穴（皿もみ）
        for (b = boss_pos) translate([b[0], b[1], H - lid_t - 1]) {
            cylinder(d = lid_screw, h = lid_t + 2);
            translate([0, 0, lid_t + 1 - 1.8]) cylinder(d1 = lid_screw, d2 = 6.6, h = 1.81);
        }
        // PHN 周りの薄肉部（裏面から掘り、外面は平らのまま。印刷時は 15mm のブリッジになる）
        translate([phone_c[0], phone_c[1], H - lid_t - 1]) linear_extrude(1 + lid_t - phone_thin_t) square(phone_thin, center = true);
        // スピーカー取付穴（M3 皿ねじ、ふた上面から皿もみ）
        sp_screw_pos() translate([0, 0, H - lid_t - 1]) {
            cylinder(d = lid_screw, h = lid_t + 2);
            translate([0, 0, lid_t + 1 - 1.8]) cylinder(d1 = lid_screw, d2 = 6.6, h = 1.81);
        }
        // 通風スロット（ふたの後ろ寄り、放熱器の左端から中央まで）
        for (i = [0:lid_vent_n - 1])
            translate([lid_vent_x[0], lid_vent_y0 + i * lid_vent_pitch, H - lid_t - 1]) cube([lid_vent_x[1] - lid_vent_x[0], 2.5, lid_t + 2]);
    }
}

// 上面の穴と文字（上から見た向き、ケース X/Y 座標）
module top_holes_2d() {
    translate(lcd_c) square(lcd_cut, center = true);              // LCD モジュール用切り欠き
    bezel_screw_pos() circle(d = bezel_hole);
    translate(enc_c) circle(d = enc_hole);
    translate(afv_c) circle(d = afv_hole);
    translate(rfg_c) circle(d = rfg_hole);
    translate(psw_c) circle(d = psw_hole);
    translate(led_c) circle(d = led_hole);
    translate(tx_c) circle(d = tx_hole);
    translate(mic_c) circle(d = mic_hole);
    translate(phone_c) circle(d = phone_hole);
    sp_grille_2d();
}
// スピーカーの放音穴（六角配置、直径 sp_grille_d の円の中）
module sp_grille_2d() {
    n = ceil(sp_grille_d / sp_hole_pitch);
    rowh = sp_hole_pitch * sqrt(3) / 2;
    for (j = [-n:n], i = [-n:n]) let(p = [i * sp_hole_pitch + (j % 2) * sp_hole_pitch / 2, j * rowh])
        if (norm(p) <= (sp_grille_d - sp_hole) / 2) translate(sp_c + p) circle(d = sp_hole);
}
module sp_screw_pos() { for (sx = [-1, 1], sy = [-1, 1]) translate([sp_c[0] + sx * sp_pitch / 2, sp_c[1] + sy * sp_pitch / 2]) children(); }
module top_labels_2d() {
    module t(s, p, sz) translate(p) text(s, size = sz, font = font, halign = "center", valign = "center");
    // 文字は各穴の上（奥側）に置く
    t("TUNE", [enc_c[0], enc_c[1] + enc_knob / 2 + 4], 3.2);
    t("VOL", [afv_c[0], afv_c[1] + afv_knob / 2 + 4], 3.2);
    t("RF", [rfg_c[0], rfg_c[1] + rfg_knob / 2 + 4], 3.2);
    t("POWER", [psw_c[0], psw_c[1] + psw_hole / 2 + 4.5], 3.2);
    t("ON", [led_c[0], psw_c[1] + psw_hole / 2 + 4.5], 2.6);
    t("TX", [tx_c[0], mic_c[1] + mic_flange / 2 + 4], 3.2);   // MIC・PHN と高さをそろえる
    t("MIC", [mic_c[0], mic_c[1] + mic_flange / 2 + 4], 3.2);
    t("PHN", [phone_c[0], mic_c[1] + mic_flange / 2 + 4], 3.2);  // MIC と高さをそろえる
}

// ---------------- 前面パネル（2D、外から見た向き） ----------------
module front_holes_2d() {
}
module front_labels_2d() {
    module t(s, p, sz = 3.2, ha = "center") translate(p) text(s, size = sz, font = font, halign = ha, valign = "center");
    translate([panel_w / 2, panel_h / 2]) text("PSN TRX  50MHz SSB", size = 8, font = font, halign = "center", valign = "center");
}
module front_2d() {
    difference() { square([panel_w, panel_h]); front_holes_2d(); }
}
// パネル実体（2D の x→X、y→Z、厚み方向 +z = 外側）。エンボス文字は外面に盛り上げ
module lcd_boss_pos() { for (sx = [-1, 1], sz = [-1, 1]) translate(lcd_c + [sx * lcd_holes[0] / 2, sz * lcd_holes[1] / 2]) children(); }
module bezel_screw_pos() { for (sx = [-1, 1], sz = [-1, 1]) translate(lcd_c + [sx * bezel_screw[0], sz * bezel_screw[1]]) children(); }
// 前面パネルの板: z=0〜panel_t が板、+z 側（外面）にエンボス文字
module front_print() {
    linear_extrude(panel_t) front_2d();
    translate([0, 0, panel_t - 0.01]) linear_extrude(emboss + 0.01) front_labels_2d();
}
// ベゼル実体（パネル座標、+z = 前面）。z=0 がベゼル裏面（パネル外面に当たる）、裏面から LCD 用ボスが出る
module bezel_body() {
    difference() {
        union() {
            translate(lcd_c - bezel / 2) linear_extrude(bezel_t) offset(r = bezel_r) offset(delta = -bezel_r) square(bezel);
            lcd_boss_pos() translate([0, 0, -lcd_boss_h]) cylinder(d = lcd_boss_od, h = lcd_boss_h + 0.01);
        }
        // 表示窓（前面側を 45° 面取り）
        translate(concat(lcd_c + lcd_win_off, [-0.01])) {
            linear_extrude(bezel_t + 0.02) square(lcd_win, center = true);
            translate([0, 0, bezel_t - 1.5]) linear_extrude(1.52, scale = [(lcd_win[0] + 3) / lcd_win[0], (lcd_win[1] + 3) / lcd_win[1]]) square(lcd_win, center = true);
        }
        // LCD 固定用インサート（ボス側から、前面 1mm 残し）
        lcd_boss_pos() translate([0, 0, -lcd_boss_h - 0.01]) cylinder(d = lcd_insert, h = lcd_insert_depth + 0.01);
        // ベゼル固定用インサート（裏面から、前面 1mm 残し）
        bezel_screw_pos() translate([0, 0, -0.01]) cylinder(d = lcd_insert, h = bezel_insert_depth + 0.01);
    }
}
// 3D 印刷用: 前面を下にしてベッドへ（ボスが上、サポート不要）
module bezel_print() translate([bezel[0] / 2 - lcd_c[0], bezel[1] / 2 - lcd_c[1], bezel_t]) mirror([0, 0, 1]) bezel_body();
// パネル一体ボス（ケース座標）。side 0 = 前面、1 = 後面。ボスの側面をパネル内面に密着させ、上下にインサート下穴
module panel_bosses(side) {
    yi = side == 0 ? panel_inset + fit / 2 + panel_t : D - panel_inset - fit / 2 - panel_t;   // パネル内面
    for (x = panel_boss_x) difference() {
        hull() {
            translate([x, panel_boss_y[side], panel_boss_z[0]]) cylinder(d = ear_d, h = panel_boss_z[1] - panel_boss_z[0]);
            translate([x - ear_d / 2, yi - 0.01, panel_boss_z[0]]) cube([ear_d, 0.02, panel_boss_z[1] - panel_boss_z[0]]);
        }
        translate([x, panel_boss_y[side], panel_boss_z[1] - ear_h]) cylinder(d = ear_hole, h = ear_h + 1);                // ふた側
        translate([x, panel_boss_y[side], panel_boss_z[0] - 1]) cylinder(d = ear_hole, h = panel_boss_bot_insert + 1);   // 底板側
    }
}
module front_panel() {
    // 外面を Y = panel_inset + fit/2 に置き、エンボスはその前方（引っ込み 2mm 内）に出る
    translate([panel_x0, panel_inset + fit / 2 + panel_t, panel_z0]) rotate([90, 0, 0]) front_print();
    panel_bosses(0);
}
// 3D 印刷用: 上端（ボスの上端とそろう）を下にして立てる
module front_panel_print() translate([panel_x0 + panel_w, -(panel_inset + fit / 2 - emboss), panel_boss_z[1]]) rotate([0, 180, 0]) front_panel();
module bezel_part() translate([0, 0, H]) bezel_body();   // ベゼル裏面をふた上面に合わせる

// ---------------- 後面パネル ----------------
// 2D は「後ろから見た向き」で作図（ケース X を左右反転）
function rx(x) = panel_w - (x - panel_x0);
module rear_holes_2d() {
    translate([rx(fuse_c[0]), fuse_c[1]]) circle(d = fuse_hole);
    translate([rx(dc_c[0]), dc_c[1]]) circle(d = dc_hole);
    translate([rx(bnc_c[0]), bnc_c[1]]) circle(d = bnc_hole);
    // 通風スロット（左後ろのパネル固定ボスの右から BNC の左まで）
    for (x = [panel_boss_x[0] + ear_d / 2 + 3 : 6 : bnc_c[0] - bnc_flange / 2 - 4]) translate([rx(x), rear_zc]) square([2.5, 22], center = true);
}
module rear_labels_2d() {
    module t(s, p, sz = 3.2) translate(p) text(s, size = sz, font = font, halign = "center", valign = "center");
    // 文字は各穴の上に置く（DC の極性表示だけ穴の下）
    t("FUSE 1A", [rx(fuse_c[0]), fuse_c[1] + fuse_flange / 2 + 3]);
    t("DC 12V", [rx(dc_c[0]), dc_c[1] + dc_flange / 2 + 3]);
    t("+ CENTER", [rx(dc_c[0]), dc_c[1] - dc_flange / 2 - 3], 2.4);   // 極性表示は穴の下
    t("ANT", [rx(bnc_c[0]), bnc_c[1] + bnc_flange / 2 + 3]);
}
module rear_2d() { difference() { square([panel_w, panel_h]); rear_holes_2d(); } }
module rear_print() {
    difference() {
        linear_extrude(panel_t) rear_2d();
        // DC ジャック周りの薄肉部（内面 z=0 側から掘り、外面は平らのまま）
        translate([rx(dc_c[0]), dc_c[1], -0.01]) linear_extrude(panel_t - dc_thin_t + 0.01) square(dc_thin, center = true);
    }
    translate([0, 0, panel_t - 0.01]) linear_extrude(emboss + 0.01) rear_labels_2d();
}
module rear_panel() {
    // 後ろから見た 2D を、外面が Y = D - panel_inset - fit/2 となるよう配置
    translate([panel_x0 + panel_w, D - panel_inset - fit / 2 - panel_t, panel_z0]) rotate([90, 0, 180]) rear_print();
    panel_bosses(1);
}
// 3D 印刷用: 上端を下にして立てる
module rear_panel_print() translate([panel_x0 + panel_w, -(panel_boss_y[1] - ear_d / 2), panel_boss_z[1]]) rotate([0, 180, 0]) rear_panel();

// ---------------- 組立図用ダミー ----------------
// 基板上の背の高い部品の位置（基板座標 u,v = コートヤード中心、kicad/PSN_TRX.kicad_pcb より）
hs1_uv = [35.6, 88.93];  // 放熱器 HS1（20PB020）
hs1_h  = 25;             // 放熱器の高さ
assert(bz + pcb_t + hs1_h + 2 <= H - lid_t, "放熱器とふた裏の隙間が 2mm 未満");
assert(lcd_c[1] + lcd_cut[1] / 2 + 2 <= bp(hs1_uv[0], hs1_uv[1])[1] - 20.1 / 2, "LCD が放熱器の上にかかる");
// ふたの通風スロット（2.5mm 幅）
lid_vent_x = [bp(hs1_uv[0], hs1_uv[1])[0] - 10, W / 2 + 38];   // 左端は放熱器の左 10mm（放熱器の左端の少し左）、右端は右後ろのパネル固定ボスの手前
lid_vent_y0 = 123; lid_vent_n = 7; lid_vent_pitch = 5;             // 1 本目の前端 Y、本数、ピッチ（発熱は少ないので後面パネル寄りに置く）
// スピーカー（秋月 116024 DXYD50N-22Z-8A-F、8Ω 0.5W）: 通風スロットの左、ふた裏に M3 皿ねじ＋ナットで固定
sp_c = [41, 138];        // 中心。マグネットの左はヒューズホルダ本体、枠の右は Q3（TO-220）、前は LCD
sp_size = 50;            // 外形 50 × 50
sp_pitch = 40;           // 取付穴 φ4 のピッチ（対角 56.5 mm）
sp_depth = 17.5;         // 枠の前面からマグネット後端まで
sp_magnet = 22;          // マグネット直径
sp_grille_d = 35;        // 放音穴を並べる範囲の直径
sp_hole = 2.5; sp_hole_pitch = 4.5;   // 放音穴（六角配置）
// 送信表示 LED（基板 J3）: MIC の左 30mm、MIC の穴と同じ高さ
tx_c = [mic_c[0] - 30, mic_c[1]]; tx_hole = 3.0;
tx_depth = 6;   // ふた裏から LED 本体・足の曲げ部の下端まで
for (b = boss_pos) assert(norm(tx_c - b) >= 3.3 + 5, "TX LED の穴がふた固定ねじ頭に近すぎる");
assert(H - lid_t - tx_depth >= bz + pcb_t + 14 + 2, "TX LED と基板上の部品（高さ 14mm）の隙間が 2mm 未満");
assert(tx_c[0] + tx_hole / 2 + 3 <= mic_c[0] - mic_flange / 2, "TX LED の穴が MIC に近すぎる");
// スピーカー
assert(sp_c[0] + sp_size / 2 + 3 <= lid_vent_x[0], "スピーカーが通風スロットに近すぎる");
assert(sp_c[1] - sp_size / 2 >= lcd_c[1] + lcd_cut[1] / 2 + 2, "スピーカーが LCD にかかる");
assert(sp_c[1] - sp_pitch / 2 - 6.6 / 2 >= lcd_c[1] + bezel[1] / 2 + 2, "スピーカー取付ねじの頭がベゼルに近すぎる");
assert(sp_c[1] + sp_size / 2 + 1 <= D - panel_inset - fit / 2 - panel_t, "スピーカーが後面パネルにかかる");
assert(sp_c[0] - sp_size / 2 >= wall + 1, "スピーカーが左の側板にかかる");
for (b = boss_pos) let(dx = max(abs(b[0] - sp_c[0]) - sp_size / 2, 0), dy = max(abs(b[1] - sp_c[1]) - sp_size / 2, 0))
    assert(norm([dx, dy]) >= ear_d / 2 + 1, "スピーカーがふた固定ボスにかかる");
// ヒューズホルダ本体（後面パネル内面から 35mm、φ16）とマグネット: 平面で 1mm 以上離すか、マグネットの下端がヒューズの上端より上
assert(sp_c[0] - sp_magnet / 2 - 1 >= fuse_c[0] + fuse_body / 2 || H - lid_t - sp_depth >= pz(fuse_c[1]) + fuse_body / 2 + 1, "スピーカーのマグネットがヒューズホルダにかかる");
// 基板の上でマグネットの下に来る部品: C13（100µF）は寝かせて付けるか高さ 7mm 以下。RFC1（横置き φ4）はそのままでよい。
// 枠の下には J3・R9・Q6・VR2・L3（T-50 縦置き、枠の右後ろの角）などが来るが、枠はふた裏に密着しているので当たらない。Q3 は枠の外（右）
assert(H - lid_t - sp_depth >= bz + pcb_t + 7 + 2, "マグネットと基板上の部品（高さ 7mm）の隙間が 2mm 未満");
assert(lid_vent_y0 >= lcd_c[1] + bezel[1] / 2 + 3, "ふたの通風スロットがベゼルにかかる");
assert(lid_vent_y0 + (lid_vent_n - 1) * lid_vent_pitch + 2.5 + 3 <= D - panel_inset - fit / 2 - panel_t, "ふたの通風スロットが後面パネルにかかる");
for (x = panel_boss_x)
    assert(x + ear_d / 2 + 2 <= lid_vent_x[0] || x - ear_d / 2 - 2 >= lid_vent_x[1], "ふたの通風スロットが後面パネル固定ボス・ねじ頭にかかる");
assert(lid_vent_x[1] + 5 <= psw_c[0] - psw_body / 2, "ふたの通風スロットが電源スイッチにかかる");
assert(H - lcd_depth >= bz + pcb_t + 14 + 2, "LCD 裏のコネクタと基板上の部品（高さ 14mm）の隙間が 2mm 未満");
module pcb_dummy() {
    color("darkgreen") hull() for (m = mount_uv) let(p = bp(m[0], m[1])) translate([p[0], p[1], bz]) cylinder(r = 4, h = pcb_t);
    // 部品ブロック: [u, v, ケース X 方向の幅, ケース Y 方向の奥行き, 高さ, 色]
    for (c = [[hs1_uv[0], hs1_uv[1], 25.1, 20.1, hs1_h, "dimgray"],     // HS1 放熱器（＋Q3）
              [19.1, 43.63, 20.9, 10.7, 10, "white"],                 // K1 リレー
              [97.5, 112.13, 19.1, 21.3, 14, "tan"],                   // T1 トランス
              [108.6, 73.73, 18.1, 21.6, 12, "royalblue"],            // XIAO（ソケット込み）
              [111.4, 59.43, 9.1, 12.2, 10.4, "orange"]])             // IC1 DC-DC（R-78E）
        let(p = bp(c[0], c[1])) color(c[5]) translate([p[0] - c[2] / 2, p[1] - c[3] / 2, bz + pcb_t]) cube([c[2], c[3], c[4]]);
}
module top_parts_dummy() {
    // LCD: ガラスはふたの切り欠きの中（ベゼル裏〜lcd_boss_h）、その下に LCD 基板とコネクタ
    color([0.2, 0.3, 0.6]) translate([lcd_c[0] - 42.75, lcd_c[1] - lcd_mod[1] / 2, H - lcd_boss_h]) cube([85.5, lcd_mod[1], lcd_boss_h]);
    color("black") translate([lcd_c[0] - lcd_mod[0] / 2, lcd_c[1] - lcd_mod[1] / 2, H - lcd_boss_h - 1.6]) cube([lcd_mod[0], lcd_mod[1], 1.6]);
    color("dimgray") translate([lcd_c[0] - lcd_mod[0] / 2 + 5, lcd_c[1] - 10, H - lcd_depth]) cube([10, 20, lcd_depth - lcd_boss_h - 1.6]);
    // エンコーダ・ボリューム: シャフト（つまみは付けない）とふた裏の本体
    color("silver") translate([enc_c[0], enc_c[1], H]) cylinder(d = 6, h = 15);
    color("silver") translate([afv_c[0], afv_c[1], H]) cylinder(d = 6, h = 12);
    color("silver") translate([rfg_c[0], rfg_c[1], H]) cylinder(d = 6, h = 12);
    color("gray") translate([enc_c[0] - enc_body / 2, enc_c[1] - enc_body / 2, H - lid_t - 12]) cube([enc_body, enc_body, 12]);
    color("gray") translate([afv_c[0], afv_c[1], H - lid_t - 10]) cylinder(d = afv_body, h = 10);
    color("gray") translate([rfg_c[0], rfg_c[1], H - lid_t - 10]) cylinder(d = rfg_body, h = 10);
    // 電源スイッチ・LED
    color("lightgray") translate([psw_c[0], psw_c[1], H]) cylinder(d = 15, h = 4);
    color("gray") translate([psw_c[0], psw_c[1], H - lid_t - 20]) cylinder(d = psw_body, h = 20);
    color("lime") translate([led_c[0], led_c[1], H]) cylinder(d = 3, h = 2);
    color("red") translate([tx_c[0], tx_c[1], H]) cylinder(d = 3, h = 2);
    // スピーカー: 枠（ふた裏に密着）・コーン部・マグネット
    color("black") translate([sp_c[0] - sp_size / 2, sp_c[1] - sp_size / 2, H - lid_t - 1.5]) cube([sp_size, sp_size, 1.5]);
    color("dimgray") translate([sp_c[0], sp_c[1], H - lid_t - sp_depth + 6]) cylinder(d1 = sp_magnet + 2, d2 = sp_size - 4, h = sp_depth - 7.5);
    color("silver") translate([sp_c[0], sp_c[1], H - lid_t - sp_depth]) cylinder(d = sp_magnet, h = 6);
    // コネクタ類（ふた上面に出る部分とふた裏の本体）: [中心, 上の太さ, 上の高さ, 裏の太さ, 裏の深さ, 色]
    for (c = [[mic_c, mic_flange, 6, mic_body, 25, "gray"],
              [phone_c, phone_plug, 3, phone_body, 15, "gray"]])
        color(c[5]) translate([c[0][0], c[0][1], 0]) {
            translate([0, 0, H]) cylinder(d = c[1], h = c[2]);
            translate([0, 0, H - lid_t - c[4]]) cylinder(d = c[3], h = c[4]);
        }
}
module rear_parts_dummy() {
    yo = D - panel_inset;                      // パネル外面付近
    yi = D - panel_inset - fit / 2 - panel_t;  // パネル内面
    // [位置, 外の太さ, 外の長さ, 内の太さ, 内の深さ, 色]
    for (c = [[fuse_c, 15, 12, fuse_body, 35, "black"],
              [dc_c, 12, 4, dc_body, 15, "black"],
              [bnc_c, 10, 12, bnc_body, 12, "silver"]])
        color(c[5]) translate([c[0][0], 0, pz(c[0][1])]) {
            translate([0, yo, 0]) rotate([-90, 0, 0]) cylinder(d = c[1], h = c[2]);
            translate([0, yi - c[4], 0]) rotate([-90, 0, 0]) cylinder(d = c[3], h = c[4]);
        }
}

module assembly(explode = 0) {
    color([0.85, 0.85, 0.88]) base();
    color([0.25, 0.25, 0.28]) { front_panel(); rear_panel(); }
    rear_parts_dummy();
    translate([0, 0, explode]) {
        color([0.85, 0.85, 0.88, 0.35]) lid();
        color([0.15, 0.15, 0.17]) bezel_part();
        top_parts_dummy();
    }
    pcb_dummy();
}

// ---------------- 出力選択（mode） ----------------
module lid_print() translate([0, 0, -(H - lid_t)]) lid();   // 外面（エンボス文字）を上、裏面をベッドへ（PHN 周りの座ぐりは 15mm のブリッジ、サポート不要）

if      (mode == 0) assembly(40);
else if (mode == 1) base();
else if (mode == 2) lid_print();
else if (mode == 3) front_panel_print();
else if (mode == 4) rear_panel_print();
else if (mode == 5) assembly(0);
else if (mode == 6) { color([0.85, 0.85, 0.88]) base(); color([0.25, 0.25, 0.28]) { front_panel(); rear_panel(); } color([0.15, 0.15, 0.17]) bezel_part(); pcb_dummy(); top_parts_dummy(); rear_parts_dummy(); }
else if (mode == 7) front_2d();
else if (mode == 8) rear_2d();
else if (mode == 9) bezel_print();
else echo("mode は 0〜9 を指定してください");
