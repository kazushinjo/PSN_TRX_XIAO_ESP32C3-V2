// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 JA6FUF (kazushinjo)
//           LO (Si5351), RF/AF phasing, 1W PA, output LPF, power and control redesigned by JA6FUF
/*
 * PSN TRX VFO - Seeed Studio XIAO ESP32C3 (RISC-V 32-bit 160MHz) + Si5351
 * 50.000 ~ 52.900 MHz (6m Band。52.90〜54.00MHz は実験・研究用なので出さない)
 *
 * ---- V2: 受信は 12MHz の SSB シングルスーパー ----
 *   受信中: CLK0 = 第 1 局発（表示周波数 + RIT − BFO、38〜41MHz、PLLA）→ Q4 → L3 → R8・R9 → U1
 *           CLK2 = BFO（約 12MHz、PLLB）→ R19・R20 → U2（積検波）。CLK1 は止める
 *   送信中: CLK0（0°）・CLK1（90°）= 表示周波数（PSN 変調、従来どおり）。CLK2 は止める
 *           AM（sb am）では表示周波数 − DSP_AM_IF_HZ（4kHz）。DSP が局発 + 4kHz に搬送波を作る（tx_dsp.cpp）
 *           AM の受信は USB（表示周波数に搬送波を合わせると、上側の側帯波が聞こえる）
 *   BFO は USB ではラダーフィルタの通過域の下端の外、LSB では上端の外に置く（bfo コマンドで合わせる）
 *   Sメーター・AGC は IF 増幅（Q6・Q7）の出力を Q8 で増幅して AD8307 で測り、ADS1015（I2C 0x48、A0）で読む
 *
 * ---- コンパイル時ディスプレイ選択 ----
 *   #define USE_NEXTION_DISPLAY  → Nextion NX4832K035（TJC4832T135_011 も可）  Serial1: D6(TX) D7(RX)
 *   コメントアウト               → SSD1306 OLED I2C: D4(SDA) D5(SCL)
 *
 * ---- Nextion 画面構成 (Nextion Editor で作成) ----
 *   t0 : 周波数表示  (大テキスト)
 *   t1 : LOCK・AM（設定モード中はメニュー・設定値）。ステップは t0 の周波数の桁の下に白い下線（drawStepMark）
 *   t2 : 固定情報    (NEXTION_FIXED_LINE1 / LINE2 で内容を指定)
 *   電源投入直後は WELCOME_MS（5 秒）の間、t0・t1 に Welcome 表示（WELCOME_LINE1 / LINE2）
 *   電源電圧 : 周波数（t0）の右に右詰めで "12.9V"（t7、フォント 3 = 36 ドット、緑。VSUP_LOW_V〜VSUP_HIGH_V の外は赤）。
 *              t7 のない画面データでは VSUP_USE_T7 を外すと xstr で描く（USE_VSUP_DISPLAY を外すと出さない）
 *   Sメーター : アナログメーター。背景（ピクチャ 0、nextion/background.png）の目盛りの上に、
 *               スケッチが picq（メーター面の描き直し）と line（針）で針を描く
 *   t3 : Sメーター値 ("S7"、"S9+20" など)
 *   t4 : AGC 状態    ("AGC FAST" / "AGC SLOW" / "AGC OFF" / 送信中は赤い "TX"。文字色 pco はスケッチが変える)
 *   t6 : AGC の量    ("AGC -12dB"。AGC OFF・送信中は空欄)
 *   送信中はメーターが ALC メーターになる: 針 = マイク入力のピーク（ALC の効き始め = S9 の位置、
 *        赤い +dB の目盛り = ALC が絞った量）、t3 = "ALC 6dB"（絞った量）/ "ALC OFF"
 *   t5 : RIT         ("RIT +0.25k"、RIT 0 のときは空欄)
 *                     設定モードで RIT を選んでいる間は 0 でも "RIT +0.00k"
 *   追加表示（2026-11-25、画面データ（.tft）は変えずにスケッチだけで表示）:
 *     バンド外の警告 : 送信する電波がバンドプランの区分（SSB: SSB_MIN_HZ〜BAND_MAX_HZ、AM: AM_MIN_HZ〜BAND_MAX_HZ）から外れる周波数では t0 を赤にする
 *     送信時間       : 送信中は t6 に "TX 0:42"。TX_WARN_SEC を超えると赤
 *     ピークホールド : 受信中、直前のピークの位置に赤い短い線（針の先の部分）を PEAK_HOLD_MS 残す
 *     ダイヤルロック : 設定モードの LOCK で ON/OFF。ON のときは t1 に "LOCK" が付き、ダイヤルで周波数が変わらない
 *     変調           : t1 に "SSB" / "AM" をいつも出す（設定モードの SSB/AM、またはシリアルの sb usb|lsb|am。sb lsb のときは "LSB"）
 *   設定モード（ダイヤルを押す）: RIT → STEP → SSB/AM → AM DEPTH → AGC → LOCK → EXIT
 *     SSB/AM   : SSB（USB）/ AM（50MHz なので LSB はパネルでは選ばない。シリアルの sb lsb は残す）。
 *                設定モード（MENU）と紛らわしいので、項目名は MODE ではなく SSB/AM
 *     AM DEPTH : AM の変調度 10〜100 %（5 % 刻み）。変更中から送信に反映するので、送信しながら合わせられる
 *   配置（480x320）: font0 = 24 ドット、font1 = 32 ドット（半角英数）、page0 の背景 = ピクチャ 0（sta=image）
 *     t0 (16,16)   448x40  font1 maxl16 | t1 (16,72)   320x32 font0 maxl32 | t5 (344,72) 120x32 font0 maxl12
 *     メーター面 (16,112) 305x181（背景画像、部品は置かない）
 *     t3 (344,120) 120x32  font0 maxl8  | t4 (344,168) 120x32 font0 maxl12 | t6 (344,208) 120x32 font0 maxl12
 *     t2 (344,256) 120x32  font0 maxl12
 *     テキスト部品はすべて sta=crop image（ピクチャ 0）または bco=6372（背景と同じ色）
 *   LCD との通信は起動時に 9600bps → 115200bps に切り替える（baud= で一時的に変更、LCD には保存しない）
 *
 * ---- 操作 ----
 *   通常       : ダイヤル = 周波数（ステップより下の桁は 0 にそろえる）、押す = 設定モードへ、長押し = RIT を 0 に戻す
 *   設定モード : ダイヤル = 機能を選ぶ（RIT / STEP / AGC / LOCK / 戻る）、押す = その機能の値の変更へ
 *   値の変更   : ダイヤル = 値を変える、押す = 確定して通常に戻る
 *                RIT の値は t5 にだけ表示（t1 は "MENU > RIT"）
 *   設定モード・値の変更中に長押し、または 15 秒操作なし = 取り消して通常に戻る
 *   機能を増やすときは menuItems[] に 1 行足し、menuEnter/menuTurn/menuText/menuCommit に処理を足す
 *
 * Libraries:
 *   - Etherkit Si5351
 *   - Adafruit SSD1306 / Adafruit GFX  (OLED使用時のみ必要)
 *   - Preferences  (ESP32 標準内蔵・NVS フラッシュ保存)
 *
 * Wiring (XIAO ESP32C3):
 *   Si5351 SDA  -> D4 (GPIO6)
 *   Si5351 SCL  -> D5 (GPIO7)
 *   OLED  SDA   -> D4 (GPIO6)   ※ OLED使用時
 *   OLED  SCL   -> D5 (GPIO7)   ※ OLED使用時
 *   Encoder A   -> D3 (GPIO5)
 *   Encoder B   -> D1 (GPIO3)
 *   Encoder SW  -> D9 (GPIO9)   ※ 基板 Ver 1.3 から（Ver 1.2 以前は D2）
 *   マイク入力  -> D2/A2 (GPIO4, ADC1)  送信中のマイク（U5A → C65・R52）、R73/R74 で 1.65V にバイアス。処理は tx_dsp.cpp
 *                  ※ V2 では受信音は来ない（Sメーター・AGC は ADS1015 で測る）
 *   ADS1015     -> D4/D5 (I2C、Si5351 と共用、アドレス 0x48)  A0 = AD8307 の出力（25mV/dB）
 *                  A3 = 電源電圧（+12V を 47kΩ / 10kΩ で 1/5.7 に分圧。後付けの改造、VSUP_ADS_CH で A1・A2 にもできる）
 *   Si5351 CLK2 -> 受信中だけ BFO（R19・R20 → U2）
 *   AGC 出力    -> D10 (GPIO10) PWM → R75・C104 → R76 → Q21 で RF 増幅 Q3・IF 増幅 Q7 のゲートを下げる
 *                  送信中は I の PDM 出力（R53・C66・R54・C67 → C70 → Q15）
 *   Q 出力      -> D8 (GPIO8)   送信中だけ PDM（R55・C68・R56・C69 → C72 → Q16）
 *   送信検出    -> D0 (GPIO2)   送信中 LOW（Q22 が TX12V でオン）。基板 Ver 2.0 で D8 から移動
 *                  ※ 起動設定ピンなので、PTT を押したまま電源を入れないこと
 *   Nextion TX  -> D7 (GPIO20)  ※ Nextion 使用時（LCD の TX → XIAO の RX）
 *   Nextion RX  -> D6 (GPIO21)  ※ Nextion 使用時（XIAO の TX → LCD の RX）
 */

// ============================================================
// ★ ここを編集してディスプレイを選択
// ============================================================
#define USE_NEXTION_DISPLAY

// Nextion 固定表示文字列（内容未定のため仮。確定後に変更）
#define NEXTION_FIXED_LINE1  "6m PSN TRX"
#define NEXTION_FIXED_LINE2  ""
// 電源投入直後の Welcome 表示（t0 = 1 行目、t1 = 2 行目）。この間は Si5351 を動かさない（電波を出さない）
#define WELCOME_LINE1  "Welcome JA6FUF"   // t0 は 14 文字まで
#define WELCOME_LINE2  "50MHz PSN SSB TRX V2"
#define WELCOME_MS     5000
// ============================================================

// ============================================================
// ★ Sメーター・AGC の調整値（実機で合わせる）
// ============================================================
// RF ゲイン VR 最大・AGC OFF で S9（-73dBm）の信号を入れたときの AD8307 の出力 [mV]
// （シリアルモニタに出る "rssi" の値を入れる。ngspice の見積もりでは約 1900mV（AD8307 の入力 −8.2dBm、
//   RF 増幅を 2SK192A-GR カスコード・L2 のタップ 3 回目にした後の値））
#define RSSI_S9_MV         1900.0f
// AD8307 の傾き [mV/dB]（データシートの値）
#define RSSI_MV_PER_DB     25.0f
// AGC が効き始める AD8307 の出力 [mV]（S9 の 6dB 下）
#define AGC_TARGET_MV      1750.0f
// BFO の初期値 [Hz]。USB はラダーフィルタの通過域の下端の外、LSB は上端の外
// （ngspice の見積もりで通過域は 12MHz の +220〜+2810Hz。水晶で変わるので bfo コマンドで合わせる）
#define BFO_USB_DEFAULT    11999900L
#define BFO_LSB_DEFAULT    12003100L
// Q21 が効き始める PWM 値と、Q3・Q7 のゲートをほぼ 0V まで下げる PWM 値（12 ビット、0〜4095）
#define AGC_DUTY_START     700
#define AGC_DUTY_FULL      1400
// AGC を最大に効かせたときのゲイン低下 [dB]（Sメーター換算用の目安。ngspice の見積もりで
//   RF 増幅 Q3 約 15.7dB ＋ IF 増幅 Q7 約 15.5dB = 約 31dB。28dB は控えめの値で、実機で合わせる）
#define AGC_RANGE_DB       28.0f
// ============================================================

// ============================================================
// ★ 電源電圧の表示（ADS1015 の空き入力で +12V を測る）
// ============================================================
// 配線: L20 の 1 番（+12V）─ 47kΩ ─ 線 ─ J4 の A3（10 番）、A3 と GND（J4 の 2 番）の間に 10kΩ と 0.1µF
//   ※ 47kΩ は必ず線の 12V 側（L20 側）に入れる。12V を J4 のピンに直接つなぐと ADS1015 が壊れる
// 分圧抵抗を付けていないときはコメントアウトする（入力が浮いていると、でたらめな電圧が出るため）
#define USE_VSUP_DISPLAY
// 測る入力（1 = A1、2 = A2、3 = A3）
#define VSUP_ADS_CH        3
// 分圧比（(47k + 10k) / 10k）。テスターの値に合わせるときはシリアルで vdc <電圧> と打つ（NVS に保存）
#define VSUP_DIV_DEFAULT   5.7f
// この電圧より低い・高いと赤で表示 [V]
#define VSUP_LOW_V         11.5f
#define VSUP_HIGH_V        15.0f
// これより低いときは分圧抵抗が付いていないとみなし、t2 は固定の文字（NEXTION_FIXED_LINE1）のまま [V]
#define VSUP_MIN_V         3.0f
// 測る間隔 [ms]（測るたびに S メーターの読み取りが約 3ms 止まる）
#define VSUP_PERIOD_MS     1000
// ============================================================

#include <Wire.h>
#include <si5351.h>
#include <Preferences.h>
#include "tx_dsp.h"

#ifndef USE_NEXTION_DISPLAY
  #include <Adafruit_GFX.h>
  #include <Adafruit_SSD1306.h>
  #define SCREEN_WIDTH  128
  #define SCREEN_HEIGHT  64
  Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
#endif

// ---- Si5351 ----
Si5351 si5351;

// ---- Preferences (NVS) ----
Preferences prefs;

// ---- Rotary Encoder ----
#define ENC_A  D3
#define ENC_B  D1
#define ENC_SW D9
#define ENC_STATES_PER_DETENT 4   // 1 クリックで A・B が 1 周期（状態 4 つ）進むエンコーダ。1 クリック = 半周期のものは 2

// ---- Sメーター・AGC・送信検出・送信音声（tx_dsp.cpp）----
#define AGC_PWM  D10           // 送信中は I の PDM 出力
#define PDM_Q    D8            // 送信中だけ Q の PDM 出力
#define TX_SENSE D0

#define RSSI_PERIOD_MS 2       // ADS1015 を読む間隔
#define RSSI_BLOCK_MS  16      // この間のピークで AGC・Sメーターを計算
#define ADS1015_ADDR   0x48
#define AGC_PWM_FREQ   19500
#define AGC_PWM_BITS   12
#define LONG_PRESS_MS  800
#define UI_TIMEOUT_MS  15000
#define RIT_MAX        9990    // ±9.99kHz
#define RIT_STEP       10

// ---- 周波数設定 ----
#define FREQ_MIN     50000000L
#define FREQ_MAX     52900000L   // 52.90〜54.00MHz は実験・研究用の区分なので出さない
#define FREQ_DEFAULT 50500000L

// ---- バンド外の警告（JARL のバンドプラン、令和 7 年 7 月 17 日施行）----
//   50.00〜50.07MHz CW / 50.07〜51.00MHz 狭帯域（3kHz 以下、A3E を除く）の全電波型式 /
//   51.00〜52.90MHz 全電波型式 / 52.90〜54.00MHz 全電波型式（実験・研究用）
// 送信する電波（USB は表示周波数〜+SSB_BW_HZ、LSB は −SSB_BW_HZ〜表示周波数、AM は表示周波数 ± DSP_AM_BW_HZ）が
// SSB は SSB_MIN_HZ〜BAND_MAX_HZ、AM は AM_MIN_HZ〜BAND_MAX_HZ を出ると周波数を赤くする
#define SSB_MIN_HZ   50070000L
#define AM_MIN_HZ    51000000L
#define BAND_MAX_HZ  52900000L
#define SSB_BW_HZ    3000L

// ---- 送信時間・ピークホールド ----
#define TX_WARN_SEC  180       // 送信時間がこれを超えると t6 を赤くする（0 = 赤くしない）
#define PEAK_HOLD_MS 2000      // Sメーターのピークを残す時間

long currentFreq = FREQ_DEFAULT;

// ---- ステップ ----
const long  stepValues[] = {10, 100, 1000, 10000, 100000};
const char* stepLabels[] = {"10Hz", "100Hz", "1kHz", "10kHz", "100kHz"};
const int   stepCount    = 5;
int stepIndex = 2;

// ---- AGC モード ----
enum { AGC_FAST = 0, AGC_SLOW, AGC_OFF, AGC_MODES };
const char* agcLabels[] = {"AGC FAST", "AGC SLOW", "AGC OFF"};
// 1 ブロック(16ms)あたりのリリース量（制御量 0〜1000 に対して）
const float agcRelease[] = {12.0f, 3.0f, 0.0f};
int agcMode = AGC_FAST;

// ---- RIT ----
long ritHz = 0;                // 受信だけずらす量（電源投入時は 0）

// ---- ダイヤルロック ----
bool dialLock = false;         // true = ダイヤルで周波数を変えない（保存する）

// ---- BFO（CLK2）----
long bfoHz[2] = {BFO_USB_DEFAULT, BFO_LSB_DEFAULT};   // [0] = USB、[1] = LSB

// ---- 設定モード ----
enum UiMode { UI_NORMAL, UI_MENU, UI_EDIT };
enum MenuId { MENU_RIT, MENU_STEP, MENU_MODE, MENU_AMD, MENU_AGC, MENU_LOCK, MENU_EXIT, MENU_COUNT };
const char* menuItems[MENU_COUNT] = {"RIT", "STEP", "SSB/AM", "AM DEPTH", "AGC", "LOCK", "EXIT"};
#define AMD_STEP 5                     // AM DEPTH の 1 クリック [%]
long          amdBefore = 0;           // AM DEPTH の変更前の値（取り消しで戻す）
UiMode        uiMode    = UI_NORMAL;
int           menuIndex = MENU_RIT;
long          editValue = 0;   // 値の変更中の仮の値（確定するまで本体の設定は変えない）
unsigned long lastUiMs  = 0;

// ---- エンコーダ ----
volatile int encCount  = 0;
volatile uint8_t encPrev = 3;          // エンコーダの前の状態（A<<1 | B）。setup で読む
int          lastCount = 0;

// ---- ボタン ----
bool          lastBtnState = HIGH;
unsigned long lastBtnTime  = 0;
unsigned long btnDownTime  = 0;
bool          longHandled  = false;

void updateDisplay();
void updateSupply();
void saveFreq();

// ---- 受信レベル測定（AD8307 → ADS1015）----
bool          adsOk      = false;
float         rssiMv     = 0;        // 前のブロックのピーク [mV]
float         rssiPeak   = 0;        // 今のブロックのピーク [mV]
unsigned long lastRssiMs = 0;
unsigned long lastBlockMs = 0;

// ---- 電源電圧（ADS1015 の A3）----
float         vsupDiv    = VSUP_DIV_DEFAULT;
float         vsupV      = -1;       // 平均した電源電圧 [V]（まだ測っていない・読めないときは -1）
float         vsupAdcMv  = -1;       // 最後に読んだ ADS1015 の入力電圧 [mV]
unsigned long lastVsupMs = 0;

// ---- AGC ----
float agcCtl = 0;              // 0 = ゲイン最大、1000 = 最大に絞る
bool  txNow  = false;

// ---- アナログ Sメーター（nextion/make_background.py の値と同じにする）----
#define METER_X0     16      // メーター面（picq で描き直す範囲）
#define METER_Y0     112
#define METER_W      305
#define METER_H      181
#define METER_PIV_X  168     // 針の支点（メーター面の下に隠れる）
#define METER_PIV_Y  318
#define METER_R0     50      // 針の根元（支点からの距離）
#define METER_R1     160     // 針の先
#define METER_ANG_L  135.0f  // 左端（S0）の角度（右向き 0°、反時計回り）
#define METER_ANG_R  45.0f   // 右端（S9+60）の角度
#define METER_S9_POS 0.6f    // S9 の位置（左端 0〜右端 1）

// Sメーター [dB、S9 = 0] → 針の位置 0〜1000
int meterPos(float db) {
  float p;
  if (db <= 0) p = (db + 54.0f) / 54.0f * METER_S9_POS;
  else         p = METER_S9_POS + db / 60.0f * (1.0f - METER_S9_POS);
  if (p < 0) p = 0;
  if (p > 1) p = 1;
  return (int)(p * 1000.0f + 0.5f);
}

// ---- Sメーター表示 ----
float         smeterDb    = -60.0f;  // S9 = 0dB
bool          smeterHold  = false;   // 表示の確認用: シリアルの smeter で表示を固定する
float         smeterHoldDb = 0.0f;
int           shownBar    = -1;
char          shownText[12] = "";
const char*   shownAgc    = nullptr;
unsigned long lastMeterMs = 0;
float         alcLevelDb  = -60.0f;  // 送信中のマイク入力ピーク（ALC の効き始め = 0dB）
float         peakDb      = -60.0f;  // Sメーターのピーク（ピークホールド）
unsigned long peakMs      = 0;       // ピークを更新した時刻
int           peakPos     = -1;      // ピークの印の位置 0〜1000（-1 = 出さない）
int           shownPeak   = -1;
unsigned long txStartMs   = 0;       // 送信を始めた時刻

// ---- ISR ----
// A・B 両方の変化で 2 ビットの状態（AB）の遷移表を引く。チャタリングは +1・−1 で打ち消し合い、
// 飛び（2 ビット同時の変化）は 0 として捨てる。ENC_STATES_PER_DETENT 回分そろったら 1 クリック。
void IRAM_ATTR encoderISR() {
  static const int8_t tbl[16] = { 0, -1,  1,  0,
                                  1,  0,  0, -1,
                                 -1,  0,  0,  1,
                                  0,  1, -1,  0 };
  static int8_t acc = 0;
  uint8_t cur = (digitalRead(ENC_A) << 1) | digitalRead(ENC_B);
  acc += tbl[(encPrev << 2) | cur];
  encPrev = cur;
  if (acc >= ENC_STATES_PER_DETENT)       { encCount++; acc = 0; }
  else if (acc <= -ENC_STATES_PER_DETENT) { encCount--; acc = 0; }
}

// ---- Si5351 ----
#define QUAD_DIV 16            // 送信: 50〜52.9MHz × 16 = 800〜846MHz（PLLA、CLK0・CLK1 の 90° 出力）
#define LO_DIV   20            // 受信の局発: 38〜41MHz × 20 = 760〜818MHz（PLLA）
#define BFO_DIV  64            // BFO: 12MHz × 64 = 768MHz（PLLB）

long shownBfo = -1;            // CLK2 に設定してある BFO（-1 = 未設定）

long currentBfo() { return bfoHz[dspLsb() ? 1 : 0]; }

// 送信: CLK0（0°）・CLK1（90°）= freq（AM では freq − DSP_AM_IF_HZ）、CLK2 は止める
void setTxClocks(long freq) {
  if (dspAm()) freq -= DSP_AM_IF_HZ;
  uint64_t f   = (uint64_t)freq * 100ULL;
  uint64_t pll = f * QUAD_DIV;
  si5351.output_enable(SI5351_CLK2, 0);
  si5351.set_freq_manual(f, pll, SI5351_CLK0);
  si5351.set_freq_manual(f, pll, SI5351_CLK1);
  si5351.set_phase(SI5351_CLK0, 0);
  si5351.set_phase(SI5351_CLK1, QUAD_DIV);      // 90° = 分周比 (位相オフセット単位 Tvco/4)
  si5351.pll_reset(SI5351_PLLA);
}

// 受信: CLK0 = 局発（freq − BFO）、CLK2 = BFO、CLK1 は止める
// 局発は下側（受信周波数より 12MHz 低い）なので IF でも側帯波は反転しない
void setRxClocks(long freq) {
  long bfo = currentBfo();
  uint64_t lo = (uint64_t)(freq - bfo) * 100ULL;
  si5351.output_enable(SI5351_CLK1, 0);
  si5351.set_freq_manual(lo, lo * LO_DIV, SI5351_CLK0);
  si5351.set_phase(SI5351_CLK0, 0);
  if (bfo != shownBfo) {                        // BFO は変わったときだけ設定し直す（PLLB のリセットで途切れるので）
    uint64_t b = (uint64_t)bfo * 100ULL;
    si5351.set_freq_manual(b, b * BFO_DIV, SI5351_CLK2);
    si5351.pll_reset(SI5351_PLLB);
    shownBfo = bfo;
  } else {
    si5351.output_enable(SI5351_CLK2, 1);
  }
}

// ---- 受信中は RIT を足す ----
long activeRit() {
  if (uiMode == UI_EDIT && menuIndex == MENU_RIT) return editValue;  // 変更中は聞きながら合わせる
  return ritHz;
}

void applyFreq() {
  if (txNow) setTxClocks(currentFreq);
  else       setRxClocks(currentFreq + activeRit());
}

// ---- 設定モードの各機能 ----
void menuEnter(int id) {
  switch (id) {
    case MENU_RIT:  editValue = ritHz;     break;
    case MENU_STEP: editValue = stepIndex; break;
    case MENU_MODE: editValue = dspAm();   break;
    case MENU_AMD:  editValue = amdBefore = lrintf(dspAmDepth()); break;
    case MENU_AGC:  editValue = agcMode;   break;
    case MENU_LOCK: editValue = dialLock;  break;
  }
}

void menuTurn(int id, int diff) {
  switch (id) {
    case MENU_RIT:
      editValue += (long)diff * RIT_STEP;
      if (editValue >  RIT_MAX) editValue =  RIT_MAX;
      if (editValue < -RIT_MAX) editValue = -RIT_MAX;
      applyFreq();
      break;
    case MENU_STEP:
      // 右に回す = 下線が右へ（下の桁・小さいステップ）、左に回す = 上の桁へ
      editValue = ((editValue - diff) % stepCount + stepCount) % stepCount;
      break;
    case MENU_MODE:
      if (diff % 2) editValue = !editValue;
      break;
    case MENU_AMD:
      editValue += (long)diff * AMD_STEP;
      if (editValue > 100) editValue = 100;
      if (editValue < 10)  editValue = 10;
      dspSetAmDepth(editValue, false);     // 送信中なら聞きながら（モニターしながら）合わせられる
      break;
    case MENU_AGC:
      editValue = ((editValue + diff) % AGC_MODES + AGC_MODES) % AGC_MODES;
      break;
    case MENU_LOCK:
      if (diff % 2) editValue = !editValue;
      break;
  }
}

void menuText(int id, long v, char* buf, size_t len) {
  switch (id) {
    case MENU_RIT:  snprintf(buf, len, "RIT: %+.2fkHz", v / 1000.0); break;
    case MENU_STEP: snprintf(buf, len, "STEP: %s", stepLabels[v]);   break;
    case MENU_MODE: snprintf(buf, len, "SSB/AM: %s", v ? "AM" : "SSB"); break;   // 設定モード（MENU）と紛らわしいので MODE と呼ばない
    case MENU_AMD:  snprintf(buf, len, "AM DEPTH: %ld%%", v);         break;
    case MENU_AGC:  snprintf(buf, len, "%s", agcLabels[v]);          break;
    case MENU_LOCK: snprintf(buf, len, "LOCK: %s", v ? "ON" : "OFF"); break;
    default:        snprintf(buf, len, "EXIT");                       break;
  }
}

void menuCommit(int id) {
  switch (id) {
    case MENU_RIT:  ritHz     = editValue;      break;
    case MENU_STEP: stepIndex = (int)editValue; break;
    case MENU_MODE: dspSetAm(editValue != 0);   break;   // 側帯波・AM は tx_dsp 側に保存する
    case MENU_AMD:  dspSetAmDepth(editValue, true); break;
    case MENU_AGC:  agcMode   = (int)editValue; break;
    case MENU_LOCK: dialLock  = editValue != 0; break;
  }
}

// t1 の内容（通常はステップ、設定モード中はメニュー）
void uiLine(char* buf, size_t len) {
  if (uiMode == UI_MENU) {
    snprintf(buf, len, "MENU > %s", menuItems[menuIndex]);
  } else if (uiMode == UI_EDIT && menuIndex == MENU_RIT) {
    snprintf(buf, len, "MENU > RIT");      // RIT の値は t5 にだけ出す
#ifdef USE_NEXTION_DISPLAY
  } else if (uiMode == UI_EDIT && menuIndex == MENU_STEP) {
    snprintf(buf, len, "MENU > STEP");     // ステップは周波数の桁の下線で示す
#endif
  } else if (uiMode == UI_EDIT) {
    char v[24];
    menuText(menuIndex, editValue, v, sizeof(v));
    snprintf(buf, len, "> %s [OK]", v);   // 28 ドットで t1 の幅（22 文字）に収める
  } else {
#ifdef USE_NEXTION_DISPLAY
    snprintf(buf, len, "%s%s", dspAm() ? "AM" : (dspLsb() ? "LSB" : "SSB"), dialLock ? "  LOCK" : "");   // 変調はいつも出す。ステップは下線で示す
#else
    snprintf(buf, len, "STEP: %s%s%s", stepLabels[stepIndex], dialLock ? "  LOCK" : "", dspAm() ? "  AM" : "");
#endif
  }
}

// 送信する電波がバンドプランの区分から外れるか（側帯波で占有する側を見る。AM は上下とも）
bool outOfBand(long f) {
  if (dspAm()) return f - DSP_AM_BW_HZ < AM_MIN_HZ || f + DSP_AM_BW_HZ > BAND_MAX_HZ;
  long lo = dspLsb() ? f - SSB_BW_HZ : f;
  long hi = dspLsb() ? f : f + SSB_BW_HZ;
  return lo < SSB_MIN_HZ || hi > BAND_MAX_HZ;
}

void ritText(char* buf, size_t len) {
  if (ritHz == 0) buf[0] = '\0';
  else snprintf(buf, len, "RIT %+.2fk", ritHz / 1000.0);
}

// 設定モードで RIT を選んでいる（メニューで RIT を指している、または RIT を変更中）
bool ritSelected() {
  return uiMode != UI_NORMAL && menuIndex == MENU_RIT;
}

void leaveUi(bool commit) {
  if (commit && uiMode == UI_EDIT) {
    menuCommit(menuIndex);
    saveFreq();
  } else if (uiMode == UI_EDIT && menuIndex == MENU_AMD) {
    dspSetAmDepth(amdBefore, false);       // 取り消し: 変更中に反映した変調度を元に戻す
  }
  uiMode = UI_NORMAL;
  applyFreq();
  updateDisplay();
}

// ---- AGC 出力 ----
void writeAgc() {
  int duty = 0;
  if (agcCtl > 0.5f)
    duty = AGC_DUTY_START + (int)(agcCtl * (AGC_DUTY_FULL - AGC_DUTY_START) / 1000.0f);
  dspAgcWrite(duty);
}

// ---- Sメーター文字列 ----
void smeterText(float db, char* buf, size_t len) {
  if (db <= 0) {
    int s = 9 + (int)floorf(db / 6.0f + 0.5f);
    if (s < 0) s = 0;
    snprintf(buf, len, "S%d", s);
  } else {
    snprintf(buf, len, "S9+%d", ((int)(db + 5) / 10) * 10);
  }
}

// ============================================================
// Nextion NX4832K035 ドライバ
// ============================================================
#ifdef USE_NEXTION_DISPLAY

void nxSend(const char* cmd) {
  Serial1.print(cmd);
  Serial1.write(0xFF);
  Serial1.write(0xFF);
  Serial1.write(0xFF);
}

void nxSetText(const char* component, const char* value) {
  char buf[80];
  snprintf(buf, sizeof(buf), "%s.txt=\"%s\"", component, value);
  nxSend(buf);
}

void nxInit() {
  // ESP32C3: D6=GPIO21(TX), D7=GPIO20(RX)
  // 針の描画で送る量が増えるので 115200bps に上げる（LCD が既に 115200bps でも通るよう両方で送る）
  // 通信速度を変えた直後の最初の命令は、頭にごみが付いて LCD に捨てられることがある
  // （TJC は 1A = 命令エラーを返して無視する）。先に区切り（FF FF FF）だけを送ってごみを捨てさせる
  Serial1.begin(9600, SERIAL_8N1, D7, D6);
  delay(500);
  nxSend("");
  nxSend("baud=115200");
  Serial1.flush();
  delay(100);
  Serial1.updateBaudRate(115200);
  nxSend("");
  nxSend("baud=115200");
  delay(50);
  nxSend("page 0");
  char fixed[48];
  if (strlen(NEXTION_FIXED_LINE2) > 0)
    snprintf(fixed, sizeof(fixed), "%s  %s", NEXTION_FIXED_LINE1, NEXTION_FIXED_LINE2);
  else
    snprintf(fixed, sizeof(fixed), "%s", NEXTION_FIXED_LINE1);
  nxSetText("t2", fixed);
}

// 電源電圧: 周波数（t0）の右の t7（x 380, y 36, 96x36、フォント 3 = 36 ドット、右寄せ、緑）に "12.9V"。
// VSUP_LOW_V〜VSUP_HIGH_V の外は赤。t7 は PSN_TRX_K035.HMI（2026-11-28）で追加し、t0 の幅を 448 → 364 に詰めた。
// t7 のない画面データ（TJC 用など）は VSUP_USE_T7 をコメントアウトすると、同じ位置に xstr で直接描く
// （そのときは t0 を描き直すたびに消えるので描き直す（force）。フォントは VSUP_FONT）
#define VSUP_USE_T7
#define VSUP_COLOR 2016u  // 普段の文字色 = 緑（RGB565 の 0x07E0）。下回ったとき・上回ったときは赤 63488
#define VSUP_FONT  0      // xstr で描くときのフォント（t7 を使うときは t7 の font 属性 = 3）
#define VSUP_X     380    // t0 の左端 16 + 14 文字 × 26px（フォント 1）
#define VSUP_Y     40     // t0（y 16〜72）の下寄せ
#define VSUP_W     84     // 画面の t0 の右端 464 まで
#define VSUP_H     32
void updateSupply(bool force) {
  static char shown[12] = "?";
  static bool shownRed = false;
  char buf[12] = "";
  bool red = false;
  if (vsupV >= VSUP_MIN_V) {
    snprintf(buf, sizeof(buf), "%.1fV", vsupV);
    red = (vsupV < VSUP_LOW_V || vsupV > VSUP_HIGH_V);
  }
#ifdef VSUP_USE_T7
  (void)force;                             // t7 は t0 と重ならないので描き直し不要
  if (red != shownRed) {
    nxSend(red ? "t7.pco=63488" : "t7.pco=2016");
    shownRed = red;
  }
  if (strcmp(buf, shown) != 0) {
    nxSetText("t7", buf);
    strncpy(shown, buf, sizeof(shown) - 1);
  }
#else
  if (!force && red == shownRed && strcmp(buf, shown) == 0) return;
  // xstr x,y,w,h,フォント,文字色,背景（sta=0 のときピクチャ番号）,横寄せ（2 = 右）,縦寄せ（1 = 中央）,sta（0 = 背景を切り抜き）,"文字"
  char cmd[80];
  snprintf(cmd, sizeof(cmd), "xstr %d,%d,%d,%d,%d,%u,0,2,1,0,\"%s\"",
           VSUP_X, VSUP_Y, VSUP_W, VSUP_H, VSUP_FONT, red ? 63488u : VSUP_COLOR, buf);
  nxSend(cmd);
  strncpy(shown, buf, sizeof(shown) - 1);
  shownRed = red;
#endif
}
void updateSupply() { updateSupply(false); }

// ステップの下線: 周波数（t0、"50.150.000 MHz"、フォント 1 = consolas52.zi の 1 文字 24px）のステップの桁の下に白い線。
// t0 の中に引くと、LCD が t0 を描き直すときに消される（txt を送った後で描き直すので、後から引いても消える）。
// そのため t0（y 16〜72）と t1（y 76〜）のすき間に引く。消すときは背景画像（ピクチャ 0）で描き直す
#define STEP_MARK_X0   16      // t0 の左端（1 文字目の左端）
#define STEP_MARK_CW   24      // 1 文字の幅（.zi の文字幅。高さの半分の 26 ではない）
#define STEP_MARK_Y    72      // t0 の下端
#define STEP_MARK_H    3
#define STEP_MARK_GAP  2       // 線の左右を少し空ける
void drawStepMark() {
  static int shownCol = -1;
  static const int cols[] = {8, 7, 5, 4, 3};   // stepValues {10, 100, 1k, 10k, 100k} の桁（"50.150.000" の何文字目か）
  int idx = (uiMode == UI_EDIT && menuIndex == MENU_STEP) ? (int)editValue : stepIndex;   // 変更中は選んでいる値
  int col = cols[idx];
  if (col == shownCol) return;
  char buf[48];
  snprintf(buf, sizeof(buf), "picq %d,%d,%d,%d,0", STEP_MARK_X0, STEP_MARK_Y, 10 * STEP_MARK_CW, STEP_MARK_H);
  nxSend(buf);
  snprintf(buf, sizeof(buf), "fill %d,%d,%d,%d,65535", STEP_MARK_X0 + col * STEP_MARK_CW + STEP_MARK_GAP,
           STEP_MARK_Y, STEP_MARK_CW - 2 * STEP_MARK_GAP, STEP_MARK_H);
  nxSend(buf);
  shownCol = col;
}

void updateDisplay() {
  long f   = currentFreq;
  int  mhz = f / 1000000;
  int  khz = (f % 1000000) / 1000;
  int  hz  = f % 1000;

  char freqBuf[24];
  snprintf(freqBuf, sizeof(freqBuf), "%d.%03d.%03d MHz", mhz, khz, hz);
  static int shownOut = -1;              // バンド外のとき赤（63488）、範囲内は白（65535）
  int out = outOfBand(f);
  if (out != shownOut) {
    nxSend(out ? "t0.pco=63488" : "t0.pco=65535");
    shownOut = out;
  }
  nxSetText("t0", freqBuf);
  drawStepMark();                        // ステップが変わったときだけ引き直す
  updateSupply(true);                    // t0 を描き直すと電源電圧の表示が消えるので描き直す

  char line[40];
  uiLine(line, sizeof(line));
  nxSetText("t1", line);

  char rit[16];
  if (ritSelected()) {                   // 設定モードで RIT を選んでいる間は、0 でも t5 に RIT の値（変更中は変えている値）
    long v = (uiMode == UI_EDIT) ? editValue : ritHz;
    snprintf(rit, sizeof(rit), "RIT %+.2fk", v / 1000.0);
  } else {
    ritText(rit, sizeof(rit));
  }
  nxSetText("t5", rit);
}

// 針の角度上の点（支点から r）
void meterPoint(int pos, int r, int* x, int* y) {
  float a = (METER_ANG_L + pos / 1000.0f * (METER_ANG_R - METER_ANG_L)) * PI / 180.0f;
  *x = METER_PIV_X + (int)(r * cosf(a));
  *y = METER_PIV_Y - (int)(r * sinf(a));
}

// 針を描く: メーター面を背景画像で描き直してから、黒い線 2 本（2 ドット幅）
// peak >= 0 のときは、ピークの位置に針の先と同じ長さの短い印（支点から METER_R1−25〜METER_R1、
// 目盛りの円弧 R_ARC = 165 の内側）を赤い線 2 本で描く
void drawNeedle(int pos, int peak) {
  char buf[48];
  snprintf(buf, sizeof(buf), "picq %d,%d,%d,%d,0", METER_X0, METER_Y0, METER_W, METER_H);
  nxSend(buf);
  float a  = (METER_ANG_L + pos / 1000.0f * (METER_ANG_R - METER_ANG_L)) * PI / 180.0f;
  int   x0 = METER_PIV_X + (int)(METER_R0 * cosf(a));
  int   y0 = METER_PIV_Y - (int)(METER_R0 * sinf(a));
  int   x1 = METER_PIV_X + (int)(METER_R1 * cosf(a));
  int   y1 = METER_PIV_Y - (int)(METER_R1 * sinf(a));
  for (int dx = 0; dx <= 1; dx++) {
    snprintf(buf, sizeof(buf), "line %d,%d,%d,%d,0", x0 + dx, y0, x1 + dx, y1);
    nxSend(buf);
  }
  if (peak >= 0) {
    int px0, py0, px1, py1;
    meterPoint(peak, METER_R1 - 25, &px0, &py0);
    meterPoint(peak, METER_R1,      &px1, &py1);
    for (int dx = 0; dx <= 1; dx++) {
      snprintf(buf, sizeof(buf), "line %d,%d,%d,%d,63488", px0 + dx, py0, px1 + dx, py1);
      nxSend(buf);
    }
  }
}

// 変わった項目だけ送る
void updateMeter(int pos, const char* text, const char* agc, const char* agcAmt) {
  static char shownAmt[16] = "?";
  static bool shownAmtRed = false;
  if (pos / 4 != shownBar / 4 || shownBar < 0 ||   // 0.4% 未満の変化では描き直さない
      peakPos / 4 != shownPeak / 4 || (peakPos < 0) != (shownPeak < 0)) {
    drawNeedle(pos, peakPos);
    shownBar = pos;
    shownPeak = peakPos;
  }
  if (strcmp(text, shownText) != 0) {
    nxSetText("t3", text);
    strncpy(shownText, text, sizeof(shownText) - 1);
  }
  if (agc != shownAgc) {
    // 送信中の "TX" は赤（63488 = 0xF800）、受信中は白（65535）
    nxSend(strcmp(agc, "TX") == 0 ? "t4.pco=63488" : "t4.pco=65535");
    nxSetText("t4", agc);
    shownAgc = agc;
  }
  // 送信時間が TX_WARN_SEC を超えたら t6 を赤（63488）に
  bool red = txNow && TX_WARN_SEC > 0 && millis() - txStartMs >= TX_WARN_SEC * 1000UL;
  if (red != shownAmtRed) {
    nxSend(red ? "t6.pco=63488" : "t6.pco=65535");
    shownAmtRed = red;
    shownAmt[0] = '?'; shownAmt[1] = '\0';      // 色を変えたら文字も送り直す
  }
  if (strcmp(agcAmt, shownAmt) != 0) {
    nxSetText("t6", agcAmt);
    strncpy(shownAmt, agcAmt, sizeof(shownAmt) - 1);
  }
}

// ============================================================
// SSD1306 OLED ドライバ
// ============================================================
#else

void drawMeter() {
  oled.fillRect(0, 44, 128, 20, SSD1306_BLACK);
  oled.setTextSize(1);
  oled.setCursor(0, 46);
  oled.print(shownText);
  oled.setCursor(80, 46);
  oled.print(shownAgc ? shownAgc : "");
  oled.drawRect(0, 56, 128, 8, SSD1306_WHITE);
  if (shownBar > 0)
    oled.fillRect(1, 57, shownBar * 126 / 1000, 6, SSD1306_WHITE);
}

void updateDisplay() {
  oled.clearDisplay();
  oled.setTextSize(2);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 4);

  long f   = currentFreq;
  int  mhz = f / 1000000;
  int  khz = (f % 1000000) / 1000;
  int  hz  = f % 1000;

  char buf[24];
  sprintf(buf, "%2d.%03d.%03d", mhz, khz, hz);
  oled.print(buf);

  oled.setTextSize(1);
  oled.setCursor(108, 10);
  oled.print("MHz");
  if (outOfBand(f)) {                    // バンド外の警告
    oled.setCursor(108, 20);
    oled.print("OUT");
  }
  if (vsupV >= VSUP_MIN_V) {             // 電源電圧（範囲外は "!" を付ける）
    bool bad = (vsupV < VSUP_LOW_V || vsupV > VSUP_HIGH_V);
    snprintf(buf, sizeof(buf), "%s%.1fV", bad ? "!" : "", vsupV);
    oled.setCursor(66, 20);
    oled.print(buf);
  }

  oled.drawLine(0, 28, 127, 28, SSD1306_WHITE);

  char line[40];
  uiLine(line, sizeof(line));
  oled.setTextSize(1);
  oled.setCursor(0, 32);
  oled.print(line);

  if (uiMode == UI_NORMAL) {
    char rit[16];
    ritText(rit, sizeof(rit));
    oled.setCursor(68, 32);
    oled.print(rit);
  }

  drawMeter();
  oled.display();
}

void updateMeter(int bar, const char* text, const char* agc, const char* agcAmt) {   // agcAmt は OLED では出さない
  if (bar == shownBar && strcmp(text, shownText) == 0 && agc == shownAgc) return;
  shownBar = bar;
  strncpy(shownText, text, sizeof(shownText) - 1);
  shownAgc = agc;
  drawMeter();
  oled.display();
}

// 電源電圧の表示が 0.1V 変わったときだけ描き直す
void updateSupply() {
  static int shown = -9999;
  int v = vsupV >= VSUP_MIN_V ? (int)lroundf(vsupV * 10) : -1;
  if (v == shown) return;
  shown = v;
  updateDisplay();
}

#endif  // USE_NEXTION_DISPLAY

// ---- NVS 保存 ----
void saveFreq() {
  prefs.begin("psn_trx", false);
  prefs.putLong("freq", currentFreq);
  prefs.putInt("step", stepIndex);
  prefs.putInt("agc", agcMode);
  prefs.putBool("lock", dialLock);
  prefs.end();
}

void saveBfo() {
  prefs.begin("psn_trx", false);
  prefs.putLong("bfo_u", bfoHz[0]);
  prefs.putLong("bfo_l", bfoHz[1]);
  prefs.end();
}

// ---- NVS 読み込み ----
#define BFO_MIN 11990000L
#define BFO_MAX 12010000L
#define VSUP_DIV_MIN 4.0f       // 分圧比の補正で受け付ける範囲（5.7 の約 ±30%）
#define VSUP_DIV_MAX 8.0f

void loadFreq() {
  prefs.begin("psn_trx", true);
  currentFreq = prefs.getLong("freq", FREQ_DEFAULT);
  stepIndex   = prefs.getInt("step", 2);
  agcMode     = prefs.getInt("agc", AGC_FAST);
  dialLock    = prefs.getBool("lock", false);
  bfoHz[0]    = prefs.getLong("bfo_u", BFO_USB_DEFAULT);
  bfoHz[1]    = prefs.getLong("bfo_l", BFO_LSB_DEFAULT);
  vsupDiv     = prefs.getFloat("vdiv", VSUP_DIV_DEFAULT);
  prefs.end();

  if (!(vsupDiv >= VSUP_DIV_MIN && vsupDiv <= VSUP_DIV_MAX)) vsupDiv = VSUP_DIV_DEFAULT;
  if (currentFreq < FREQ_MIN || currentFreq > FREQ_MAX)
    currentFreq = FREQ_DEFAULT;
  if (stepIndex < 0 || stepIndex >= stepCount)
    stepIndex = 2;
  if (agcMode < 0 || agcMode >= AGC_MODES)
    agcMode = AGC_FAST;
  if (bfoHz[0] < BFO_MIN || bfoHz[0] > BFO_MAX) bfoHz[0] = BFO_USB_DEFAULT;
  if (bfoHz[1] < BFO_MIN || bfoHz[1] > BFO_MAX) bfoHz[1] = BFO_LSB_DEFAULT;
}

// ---- BFO の設定コマンド: bfo（表示）/ bfo usb <Hz> / bfo lsb <Hz>（保存する）----
bool bfoCommand(String line) {
  line.trim();
  if (!line.startsWith("bfo")) return false;
  String arg = line.substring(3);
  arg.trim();
  int sp = arg.indexOf(' ');
  if (sp > 0) {
    String sb = arg.substring(0, sp);
    long hz = arg.substring(sp + 1).toInt();
    int i = sb.startsWith("l") || sb.startsWith("L") ? 1 : 0;
    if (hz < BFO_MIN || hz > BFO_MAX) {
      Serial.printf("bfo: %ld〜%ld Hz で指定\n", BFO_MIN, BFO_MAX);
      return true;
    }
    bfoHz[i] = hz;
    saveBfo();
    applyFreq();
  }
  Serial.printf("bfo: USB %ld Hz / LSB %ld Hz（今は %s）\n", bfoHz[0], bfoHz[1], dspLsb() ? "LSB" : dspAm() ? "USB (AM)" : "USB");
  return true;
}

// ---- 周波数の設定コマンド: freq（表示）/ freq <Hz>（設定して保存・LCD 更新）----
bool freqCommand(String line) {
  line.trim();
  if (!line.startsWith("freq")) return false;
  String arg = line.substring(4);
  arg.trim();
  if (arg.length()) {
    long hz = arg.toInt();
    if (hz < FREQ_MIN || hz > FREQ_MAX) {
      Serial.printf("freq: %ld〜%ld Hz で指定\n", FREQ_MIN, FREQ_MAX);
      return true;
    }
    currentFreq = hz;
    applyFreq();
    saveFreq();
    updateDisplay();
  }
  Serial.printf("freq: %ld Hz\n", currentFreq);
  return true;
}

// ---- RIT の設定コマンド: rit（表示）/ rit <Hz>（±9990、10Hz 単位。保存しない）----
bool ritCommand(String line) {
  line.trim();
  if (!line.startsWith("rit")) return false;
  String arg = line.substring(3);
  arg.trim();
  if (arg.length()) {
    long hz = arg.toInt();
    if (hz < -RIT_MAX || hz > RIT_MAX) {
      Serial.printf("rit: -%d〜%d Hz で指定\n", RIT_MAX, RIT_MAX);
      return true;
    }
    ritHz = hz / RIT_STEP * RIT_STEP;
    applyFreq();
    updateDisplay();
  }
  Serial.printf("rit: %+ld Hz\n", ritHz);
  return true;
}

// ---- 電源電圧: vdc（表示）/ vdc <テスターで測った電圧 V>（分圧比を合わせて保存）/ vdc reset ----
bool vdcCommand(String line) {
  line.trim();
  if (!line.startsWith("vdc")) return false;
#ifndef USE_VSUP_DISPLAY
  Serial.println("vdc: 電源電圧の表示は無効（USE_VSUP_DISPLAY をコメントアウト中）");
  return true;
#endif
  String arg = line.substring(3);
  arg.trim();
  if (arg == "reset") {
    vsupDiv = VSUP_DIV_DEFAULT;
  } else if (arg.length()) {
    float v = arg.toFloat();
    if (vsupAdcMv < 100) {
      Serial.println("vdc: ADS1015 の入力が読めていない（配線と分圧抵抗を確認）");
      return true;
    }
    float div = v / (vsupAdcMv / 1000.0f);
    if (!(div >= VSUP_DIV_MIN && div <= VSUP_DIV_MAX)) {
      Serial.printf("vdc: 分圧比 %.3f は範囲外（%.1f〜%.1f）。電圧か配線を確認\n", div, VSUP_DIV_MIN, VSUP_DIV_MAX);
      return true;
    }
    vsupDiv = div;
  }
  if (arg.length()) {
    prefs.begin("psn_trx", false);
    prefs.putFloat("vdiv", vsupDiv);
    prefs.end();
    if (vsupAdcMv >= 0) vsupV = vsupAdcMv / 1000.0f * vsupDiv;   // 平均をやり直す
    updateSupply();
  }
  Serial.printf("vdc: %.2f V（A%d = %.0f mV、分圧比 %.3f）\n", vsupV, VSUP_ADS_CH, vsupAdcMv, vsupDiv);
  return true;
}

// ---- Sメーター表示の固定（表示の確認用）: smeter s7 / smeter s9+20 / smeter off ----
bool smeterCommand(String line) {
  line.trim();
  if (!line.startsWith("smeter")) return false;
  String arg = line.substring(6);
  arg.trim();
  arg.toLowerCase();
  if (arg == "off") {
    smeterHold = false;
  } else if (arg.startsWith("s")) {
    int s = arg.substring(1).toInt();
    int plus = arg.indexOf('+');
    if (s < 0 || s > 9) {
      Serial.println("smeter: s0〜s9、s9+10〜s9+60、off で指定");
      return true;
    }
    smeterHoldDb = (s - 9) * 6.0f + (plus > 0 ? arg.substring(plus + 1).toInt() : 0);
    smeterHold = true;
  }
  if (smeterHold) Serial.printf("smeter: %.0f dB に固定（S9 = 0dB）\n", smeterHoldDb);
  else            Serial.println("smeter: 測定値を表示");
  return true;
}

// ---- ADS1015: 入力 ch（0〜3）対 GND を連続変換（±4.096V、1600SPS）----
bool adsSetMux(int ch) {
  Wire.beginTransmission(ADS1015_ADDR);
  Wire.write(0x01);                        // 設定レジスタ
  Wire.write(0x02 | ((4 + ch) << 4));      // MUX = Ach 対 GND（A0 で 0x42）、PGA = ±4.096V、連続変換
  Wire.write(0x83);                        // 1600SPS、コンパレータ不使用
  bool ok = (Wire.endTransmission() == 0);
  Wire.beginTransmission(ADS1015_ADDR);
  Wire.write(0x00);                        // 以後は変換結果レジスタを読む
  Wire.endTransmission();
  return ok;
}

// 普段は A0（AD8307）を連続変換
void adsBegin() {
  adsOk = adsSetMux(0);
  if (!adsOk) Serial.println("ADS1015 not found");
}

// AD8307 の出力 [mV]（読めなければ -1）
float adsReadMv() {
  if (!adsOk) return -1;
  if (Wire.requestFrom(ADS1015_ADDR, 2) != 2) return -1;
  int16_t raw = (int16_t)((Wire.read() << 8) | Wire.read()) >> 4;   // 12 ビット、1LSB = 2mV
  return raw * 2.0f;
}

// 電源電圧の入力（VSUP_ADS_CH）を 1 回読んで A0 に戻す [mV]（読めなければ -1）
// 入力を切り替えてから 3ms（1600SPS で 4 回分以上の変換）待ち、切り替え後の値を読む
float adsReadSupplyMv() {
  if (!adsOk) return -1;
  float mv = -1;
  if (adsSetMux(VSUP_ADS_CH)) {
    delay(3);
    mv = adsReadMv();
  }
  adsSetMux(0);
  return mv;
}

// ---- 1 ブロック（16ms）分の処理（AGC とSメーター）----
void processBlock() {
  rssiMv = rssiPeak;
  rssiPeak = 0;

  if (txNow) return;                       // 送信中は AGC を保持

  if (agcMode == AGC_OFF) {
    agcCtl = 0;
  } else {
    float over = (rssiMv - AGC_TARGET_MV) / RSSI_MV_PER_DB;
    if (over > 0) {
      agcCtl += over * 25.0f;              // アタック（1dB 超えで 2.5%）
    } else {
      agcCtl -= agcRelease[agcMode];       // リリース
    }
    if (agcCtl < 0)    agcCtl = 0;
    if (agcCtl > 1000) agcCtl = 1000;
  }
  writeAgc();

  // Sメーター: IF のレベル + AGC で絞った分（S9 = 0dB）
  float db = (rssiMv - RSSI_S9_MV) / RSSI_MV_PER_DB + agcCtl * AGC_RANGE_DB / 1000.0f;
  if (db > smeterDb) smeterDb = db;              // すぐ上がる
  else               smeterDb += (db - smeterDb) * 0.08f;  // ゆっくり下がる
}

// ============================================================
void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);    // USB をつないだまま PC で読んでいないとき、書き込みで待たされて全体が遅くなるのを防ぐ

  pinMode(ENC_A,  INPUT_PULLUP);
  pinMode(ENC_B,  INPUT_PULLUP);
  pinMode(ENC_SW, INPUT_PULLUP);
  encPrev = (digitalRead(ENC_A) << 1) | digitalRead(ENC_B);
  attachInterrupt(digitalPinToInterrupt(ENC_A), encoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_B), encoderISR, CHANGE);

  // AGC の PWM・送信音声の I/Q 生成（tx_dsp.cpp）
  dspBegin(TX_SENSE, PDM_Q, AGC_PWM, AGC_PWM_FREQ, AGC_PWM_BITS);

  Wire.begin();
  Wire.setClock(400000);       // Si5351・ADS1015 とも 400kHz 対応（ADS1015 を 2ms ごとに読むので速くする）
  adsBegin();

#ifdef USE_NEXTION_DISPLAY
  nxInit();
#else
  if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C))
    Serial.println("OLED not found");
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(20, 20);
  oled.print(WELCOME_LINE1);
  oled.setCursor(0, 36);
  oled.print(WELCOME_LINE2);
  oled.display();
#endif
  // Welcome 表示。Si5351 を設定する前に待つので、この間に PTT を押しても電波は出ない
#ifdef USE_NEXTION_DISPLAY
  nxSetText("t0", WELCOME_LINE1);
  nxSetText("t1", WELCOME_LINE2);
#endif
  delay(WELCOME_MS);
  lastCount = encCount;        // Welcome 中に回したダイヤルは無視する

  if (!si5351.init(SI5351_CRYSTAL_LOAD_8PF, 25000000, 0))
    Serial.println("Si5351 not found");
  si5351.drive_strength(SI5351_CLK0, SI5351_DRIVE_8MA);
  si5351.drive_strength(SI5351_CLK1, SI5351_DRIVE_8MA);
  si5351.drive_strength(SI5351_CLK2, SI5351_DRIVE_8MA);
  si5351.set_ms_source(SI5351_CLK2, SI5351_PLLB);   // BFO は PLLB（局発・送信の PLLA と別）
  si5351.output_enable(SI5351_CLK2, 0);

  loadFreq();
  applyFreq();
  updateDisplay();
}

// ============================================================
void loop() {
  unsigned long now = millis();

  // 送信・受信の切り替わりで RIT を外す／戻す
  bool tx = (digitalRead(TX_SENSE) == LOW);
  if (tx != txNow) {
    txNow = tx;
    if (tx) txStartMs = now;
    applyFreq();
    Serial.printf("%s %lu ms\n", tx ? "tx: 送信" : "tx: 受信", now);
    lastMeterMs = 0;                        // LCD の表示（TX・ALC メーター）をすぐ切り替える
  }

  int cnt = encCount;
  if (cnt != lastCount) {
    int diff = cnt - lastCount;
    lastCount = cnt;
    if (uiMode == UI_NORMAL) {
      if (dialLock) diff = 0;               // ダイヤルロック中は周波数を変えない
      if (diff) {                           // ステップより下の桁は 0 にそろえる（50.150.123 → 上: 50.151.000、下: 50.150.000）
        long st   = stepValues[stepIndex];
        long base = currentFreq / st * st;
        if (base != currentFreq && diff < 0) diff++;   // 端数を切り捨てるだけで 1 ステップ下がる
        currentFreq = base + (long)diff * st;
      }
      if (currentFreq < FREQ_MIN) currentFreq = FREQ_MIN;
      if (currentFreq > FREQ_MAX) currentFreq = FREQ_MAX;
      applyFreq();
      saveFreq();
    } else if (uiMode == UI_MENU) {
      menuIndex = ((menuIndex + diff) % MENU_COUNT + MENU_COUNT) % MENU_COUNT;
    } else {
      menuTurn(menuIndex, diff);
    }
    lastUiMs = now;
    updateDisplay();
  }

  // ボタン: 押す = 設定モードへ／機能を選ぶ／確定、長押し = 取り消し（通常時は RIT を 0 に）
  bool btn = digitalRead(ENC_SW);
  if (btn == LOW && lastBtnState == HIGH && now - lastBtnTime > 50) {
    btnDownTime = now;
    longHandled = false;
  }
  if (btn == LOW && !longHandled && now - btnDownTime >= LONG_PRESS_MS) {
    longHandled = true;
    if (uiMode == UI_NORMAL) ritHz = 0;
    leaveUi(false);
  }
  if (btn == HIGH && lastBtnState == LOW) {
    if (!longHandled && now - btnDownTime > 50) {
      if (uiMode == UI_NORMAL) {
        uiMode = UI_MENU;
        menuIndex = MENU_RIT;
        updateDisplay();
      } else if (uiMode == UI_MENU) {
        if (menuIndex == MENU_EXIT) {
          leaveUi(false);
        } else {
          menuEnter(menuIndex);
          uiMode = UI_EDIT;
          updateDisplay();
        }
      } else {
        leaveUi(true);
      }
      lastUiMs = now;
    }
    lastBtnTime = now;
  }
  lastBtnState = btn;

  if (uiMode != UI_NORMAL && now - lastUiMs >= UI_TIMEOUT_MS) leaveUi(false);

  // IF のレベル（AD8307 → ADS1015）を 2ms ごとに読み、16ms ごとのピークで AGC・Sメーター
  if (now - lastRssiMs >= RSSI_PERIOD_MS) {
    lastRssiMs = now;
    float mv = adsReadMv();
    if (mv > rssiPeak) rssiPeak = mv;
  }
  if (now - lastBlockMs >= RSSI_BLOCK_MS) {
    lastBlockMs = now;
    processBlock();
  }

#ifdef USE_VSUP_DISPLAY
  // 電源電圧（VSUP_PERIOD_MS ごとに ADS1015 の入力を切り替えて読む。送信中も測る）
  if (now - lastVsupMs >= VSUP_PERIOD_MS) {
    lastVsupMs = now;
    vsupAdcMv = adsReadSupplyMv();
    lastRssiMs = millis();                 // A0 に戻した直後の変換結果（A3 の値が残る）を読まない
    if (vsupAdcMv < 0) {
      vsupV = -1;
    } else {
      float v = vsupAdcMv / 1000.0f * vsupDiv;
      vsupV = (vsupV < 0) ? v : vsupV + (v - vsupV) * 0.5f;   // 表示がちらつかないよう軽く平均
    }
    updateSupply();
  }
#endif

  // 設定コマンド（送信音声: dsp / mic / out / iqd / iqa / sb / amd / tone / alc / w、受信: bfo、表示: freq / rit / smeter）
  static String cmdLine;
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (cmdLine.length() && !bfoCommand(cmdLine) && !freqCommand(cmdLine) &&
          !ritCommand(cmdLine) && !smeterCommand(cmdLine) && !vdcCommand(cmdLine)) {
        if (dspCommand(cmdLine)) {
          applyFreq();                     // sb で側帯波を変えたら BFO・局発も合わせる
          updateDisplay();                 // バンド外の判定も側帯波で変わる
        }
        else
          Serial.println("コマンド: dsp / mic <dB> / out <%> / iqd <us> / iqa <dB> / sb usb|lsb|am / amd <%> / tone <Hz> / alc <dBFS>|off / w / bfo [usb|lsb <Hz>] / freq [<Hz>] / rit [<Hz>] / smeter s7|s9+20|off / vdc [<V>|reset]");
      }
      cmdLine = "";
    } else if (cmdLine.length() < 40) cmdLine += ch;
  }

  // Sメーター表示（100ms ごと）
  if (now - lastMeterMs >= 100) {
    lastMeterMs = now;
    if (txNow) {
      // ALC メーター: すぐ上がり、ゆっくり下がる
      float a = dspAlcLevelDb();
      if (a > alcLevelDb) alcLevelDb = a;
      else                alcLevelDb += (a - alcLevelDb) * 0.3f;
      char text[12];
      if (dspAlcOn()) snprintf(text, sizeof(text), "ALC %ddB", alcLevelDb > 0 ? (int)(alcLevelDb + 0.5f) : 0);
      else            snprintf(text, sizeof(text), "ALC OFF");
      unsigned long sec = (now - txStartMs) / 1000;
      char txTime[16];
      snprintf(txTime, sizeof(txTime), "TX %lu:%02lu", sec / 60, sec % 60);
      peakPos = -1;                          // 送信中はピークの印を出さない
      peakDb = -60.0f;
      updateMeter(meterPos(alcLevelDb), text, "TX", txTime);
    } else {
      alcLevelDb = -60.0f;
      char text[12], amt[16] = "";
      float db = smeterHold ? smeterHoldDb : smeterDb;
      smeterText(db, text, sizeof(text));
      // ピークホールド: 上がったらすぐ追い、PEAK_HOLD_MS 残してからゆっくり針に戻す
      if (db >= peakDb) { peakDb = db; peakMs = now; }
      else if (now - peakMs >= PEAK_HOLD_MS) peakDb += (db - peakDb) * 0.3f;
      int pp = meterPos(peakDb), np = meterPos(db);
      peakPos = (pp - np >= 8) ? pp : -1;    // 針とほぼ重なるときは出さない
      if (agcMode != AGC_OFF) {
        int g = (int)(agcCtl * AGC_RANGE_DB / 1000.0f + 0.5f);
        snprintf(amt, sizeof(amt), g > 0 ? "AGC -%ddB" : "AGC %ddB", g);
      }
      updateMeter(meterPos(db), text, agcLabels[agcMode], amt);
    }
    if (!txNow) Serial.printf("rssi %.0f mV  agc %.0f  S %.1f dB\n", rssiMv, agcCtl, smeterDb);
  }
}
