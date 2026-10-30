// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 JA6FUF (kazushinjo)
//           LO (Si5351), RF/AF phasing, 1W PA, output LPF, power and control redesigned by JA6FUF
/*
 * PSN TRX VFO - Seeed Studio XIAO ESP32C3 (RISC-V 32-bit 160MHz) + Si5351
 * 50.000 ~ 51.000 MHz (6m Band)
 *
 * ---- V2: 受信は 12MHz の SSB シングルスーパー ----
 *   受信中: CLK0 = 第 1 局発（表示周波数 + RIT − BFO、38〜39MHz、PLLA）→ Q11 → L9 → R68・R69 → U4
 *           CLK2 = BFO（約 12MHz、PLLB）→ R77・R78 → U5（積検波）。CLK1 は止める
 *   送信中: CLK0（0°）・CLK1（90°）= 表示周波数（PSN 変調、従来どおり）。CLK2 は止める
 *   BFO は USB ではラダーフィルタの通過域の下端の外、LSB では上端の外に置く（bfo コマンドで合わせる）
 *   Sメーター・AGC は Q2（IF 増幅）の出力を AD8307 で測り、ADS1015（I2C 0x48、A0）で読む
 *
 * ---- コンパイル時ディスプレイ選択 ----
 *   #define USE_NEXTION_DISPLAY  → Nextion NX4832T035  Serial1: D6(TX) D7(RX)
 *   コメントアウト               → SSD1306 OLED I2C: D4(SDA) D5(SCL)
 *
 * ---- Nextion 画面構成 (Nextion Editor で作成) ----
 *   t0 : 周波数表示  (大テキスト)
 *   t1 : ステップ表示（設定モード中はメニュー・設定値）
 *   t2 : 固定情報    (NEXTION_FIXED_LINE1 / LINE2 で内容を指定)
 *   Sメーター : アナログメーター。背景（ピクチャ 0、nextion/background.png）の目盛りの上に、
 *               スケッチが picq（メーター面の描き直し）と line（針）で針を描く
 *   t3 : Sメーター値 ("S7"、"S9+20" など)
 *   t4 : AGC 状態    ("AGC FAST" / "AGC SLOW" / "AGC OFF" / 送信中は赤い "TX"。文字色 pco はスケッチが変える)
 *   t6 : AGC の量    ("AGC -12dB"。AGC OFF・送信中は空欄)
 *   送信中はメーターが ALC メーターになる: 針 = マイク入力のピーク（ALC の効き始め = S9 の位置、
 *        赤い +dB の目盛り = ALC が絞った量）、t3 = "ALC 6dB"（絞った量）/ "ALC OFF"
 *   t5 : RIT         ("RIT +0.25k"、RIT 0 のときは空欄)
 *   配置（480x320）: font0 = 24 ドット、font1 = 32 ドット（半角英数）、page0 の背景 = ピクチャ 0（sta=image）
 *     t0 (16,16)   448x40  font1 maxl16 | t1 (16,72)   320x32 font0 maxl32 | t5 (344,72) 120x32 font0 maxl12
 *     メーター面 (16,112) 305x181（背景画像、部品は置かない）
 *     t3 (344,120) 120x32  font0 maxl8  | t4 (344,168) 120x32 font0 maxl12 | t6 (344,208) 120x32 font0 maxl12
 *     t2 (344,256) 120x32  font0 maxl12
 *     テキスト部品はすべて sta=crop image（ピクチャ 0）または bco=6372（背景と同じ色）
 *   LCD との通信は起動時に 9600bps → 115200bps に切り替える（baud= で一時的に変更、LCD には保存しない）
 *
 * ---- 操作 ----
 *   通常       : ダイヤル = 周波数、押す = 設定モードへ、長押し = RIT を 0 に戻す
 *   設定モード : ダイヤル = 機能を選ぶ（RIT / STEP / AGC / 戻る）、押す = その機能の値の変更へ
 *   値の変更   : ダイヤル = 値を変える、押す = 確定して通常に戻る
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
 *   マイク入力  -> D2/A2 (GPIO4, ADC1)  送信中のマイク（IC2A → C73・R59）、R38/R39 で 1.65V にバイアス。処理は tx_dsp.cpp
 *                  ※ V2 では受信音は来ない（Sメーター・AGC は ADS1015 で測る）
 *   ADS1015     -> D4/D5 (I2C、Si5351 と共用、アドレス 0x48)  A0 = AD8307 の出力（25mV/dB）
 *   Si5351 CLK2 -> 受信中だけ BFO（R77・R78 → U5）
 *   AGC 出力    -> D10 (GPIO10) PWM → R42・C61 → R44 → Q17 で Q2 の G2 を下げる
 *                  送信中は I の PDM 出力（R61・C75・R62・C76 → C49 → Q15）
 *   Q 出力      -> D8 (GPIO8)   送信中だけ PDM（R63・C77・R64・C78 → C48 → Q16）
 *   送信検出    -> D0 (GPIO2)   送信中 LOW（Q19 が TX12V でオン）。基板 Ver 2.0 で D8 から移動
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
// ============================================================

// ============================================================
// ★ Sメーター・AGC の調整値（実機で合わせる）
// ============================================================
// RF ゲイン VR 最大・AGC OFF で S9（-73dBm）の信号を入れたときの AD8307 の出力 [mV]
// （シリアルモニタに出る "rssi" の値を入れる。ngspice の見積もりでは約 1900mV（AD8307 の入力 −8dBm、
//   RF 増幅を J310 カスコードにした後の値））
#define RSSI_S9_MV         1900.0f
// AD8307 の傾き [mV/dB]（データシートの値）
#define RSSI_MV_PER_DB     25.0f
// AGC が効き始める AD8307 の出力 [mV]（S9 の 6dB 下）
#define AGC_TARGET_MV      1750.0f
// BFO の初期値 [Hz]。USB はラダーフィルタの通過域の下端の外、LSB は上端の外
// （ngspice の見積もりで通過域は 12MHz の +220〜+2810Hz。水晶で変わるので bfo コマンドで合わせる）
#define BFO_USB_DEFAULT    11999900L
#define BFO_LSB_DEFAULT    12003100L
// Q17 が効き始める PWM 値と、G2 をほぼ 0V まで下げる PWM 値（12 ビット、0〜4095）
#define AGC_DUTY_START     700
#define AGC_DUTY_FULL      1400
// AGC を最大に効かせたときのゲイン低下 [dB]（Sメーター換算用の目安。ngspice の見積もりで
//   RF 増幅 Q25 約 15dB ＋ IF 増幅 Q2 約 13dB）
#define AGC_RANGE_DB       28.0f
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
#define FREQ_MAX     51000000L
#define FREQ_DEFAULT 50500000L

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

// ---- BFO（CLK2）----
long bfoHz[2] = {BFO_USB_DEFAULT, BFO_LSB_DEFAULT};   // [0] = USB、[1] = LSB

// ---- 設定モード ----
enum UiMode { UI_NORMAL, UI_MENU, UI_EDIT };
enum MenuId { MENU_RIT, MENU_STEP, MENU_AGC, MENU_EXIT, MENU_COUNT };
const char* menuItems[MENU_COUNT] = {"RIT", "STEP", "AGC", "EXIT"};
UiMode        uiMode    = UI_NORMAL;
int           menuIndex = MENU_RIT;
long          editValue = 0;   // 値の変更中の仮の値（確定するまで本体の設定は変えない）
unsigned long lastUiMs  = 0;

// ---- エンコーダ ----
volatile int encCount  = 0;
int          lastCount = 0;

// ---- ボタン ----
bool          lastBtnState = HIGH;
unsigned long lastBtnTime  = 0;
unsigned long btnDownTime  = 0;
bool          longHandled  = false;

void updateDisplay();
void saveFreq();

// ---- 受信レベル測定（AD8307 → ADS1015）----
bool          adsOk      = false;
float         rssiMv     = 0;        // 前のブロックのピーク [mV]
float         rssiPeak   = 0;        // 今のブロックのピーク [mV]
unsigned long lastRssiMs = 0;
unsigned long lastBlockMs = 0;

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
int           shownBar    = -1;
char          shownText[12] = "";
const char*   shownAgc    = nullptr;
unsigned long lastMeterMs = 0;
float         alcLevelDb  = -60.0f;  // 送信中のマイク入力ピーク（ALC の効き始め = 0dB）

// ---- ISR ----
void IRAM_ATTR encoderISR() {
  static int lastA = HIGH;
  int a = digitalRead(ENC_A);
  int b = digitalRead(ENC_B);
  if (a != lastA) {
    encCount += (b != a) ? 1 : -1;
    lastA = a;
  }
}

// ---- Si5351 ----
#define QUAD_DIV 16            // 送信: 50MHz × 16 = 800〜816MHz（PLLA、CLK0・CLK1 の 90° 出力）
#define LO_DIV   20            // 受信の局発: 38〜39MHz × 20 = 760〜780MHz（PLLA）
#define BFO_DIV  64            // BFO: 12MHz × 64 = 768MHz（PLLB）

long shownBfo = -1;            // CLK2 に設定してある BFO（-1 = 未設定）

long currentBfo() { return bfoHz[dspLsb() ? 1 : 0]; }

// 送信: CLK0（0°）・CLK1（90°）= freq、CLK2 は止める
void setTxClocks(long freq) {
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
    case MENU_AGC:  editValue = agcMode;   break;
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
      editValue = ((editValue + diff) % stepCount + stepCount) % stepCount;
      break;
    case MENU_AGC:
      editValue = ((editValue + diff) % AGC_MODES + AGC_MODES) % AGC_MODES;
      break;
  }
}

void menuText(int id, long v, char* buf, size_t len) {
  switch (id) {
    case MENU_RIT:  snprintf(buf, len, "RIT: %+.2fkHz", v / 1000.0); break;
    case MENU_STEP: snprintf(buf, len, "STEP: %s", stepLabels[v]);   break;
    case MENU_AGC:  snprintf(buf, len, "%s", agcLabels[v]);          break;
    default:        snprintf(buf, len, "EXIT");                       break;
  }
}

void menuCommit(int id) {
  switch (id) {
    case MENU_RIT:  ritHz     = editValue;      break;
    case MENU_STEP: stepIndex = (int)editValue; break;
    case MENU_AGC:  agcMode   = (int)editValue; break;
  }
}

// t1 の内容（通常はステップ、設定モード中はメニュー）
void uiLine(char* buf, size_t len) {
  if (uiMode == UI_MENU) {
    snprintf(buf, len, "MENU > %s", menuItems[menuIndex]);
  } else if (uiMode == UI_EDIT) {
    char v[24];
    menuText(menuIndex, editValue, v, sizeof(v));
    snprintf(buf, len, "> %s  [PUSH=OK]", v);
  } else {
    snprintf(buf, len, "STEP: %s", stepLabels[stepIndex]);
  }
}

void ritText(char* buf, size_t len) {
  if (ritHz == 0) buf[0] = '\0';
  else snprintf(buf, len, "RIT %+.2fk", ritHz / 1000.0);
}

void leaveUi(bool commit) {
  if (commit && uiMode == UI_EDIT) {
    menuCommit(menuIndex);
    saveFreq();
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
// Nextion NX4832T035 ドライバ
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
  Serial1.begin(9600, SERIAL_8N1, D7, D6);
  delay(500);
  nxSend("baud=115200");
  Serial1.flush();
  delay(100);
  Serial1.updateBaudRate(115200);
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

void updateDisplay() {
  long f   = currentFreq;
  int  mhz = f / 1000000;
  int  khz = (f % 1000000) / 1000;
  int  hz  = f % 1000;

  char freqBuf[24];
  snprintf(freqBuf, sizeof(freqBuf), "%d.%03d.%03d MHz", mhz, khz, hz);
  nxSetText("t0", freqBuf);

  char line[40];
  uiLine(line, sizeof(line));
  nxSetText("t1", line);

  char rit[16];
  ritText(rit, sizeof(rit));
  nxSetText("t5", rit);
}

// 針を描く: メーター面を背景画像で描き直してから、黒い線 2 本（2 ドット幅）
void drawNeedle(int pos) {
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
}

// 変わった項目だけ送る
void updateMeter(int pos, const char* text, const char* agc, const char* agcAmt) {
  static char shownAmt[16] = "?";
  if (pos / 4 != shownBar / 4 || shownBar < 0) {   // 0.4% 未満の変化では描き直さない
    drawNeedle(pos);
    shownBar = pos;
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

#endif  // USE_NEXTION_DISPLAY

// ---- NVS 保存 ----
void saveFreq() {
  prefs.begin("psn_trx", false);
  prefs.putLong("freq", currentFreq);
  prefs.putInt("step", stepIndex);
  prefs.putInt("agc", agcMode);
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

void loadFreq() {
  prefs.begin("psn_trx", true);
  currentFreq = prefs.getLong("freq", FREQ_DEFAULT);
  stepIndex   = prefs.getInt("step", 2);
  agcMode     = prefs.getInt("agc", AGC_FAST);
  bfoHz[0]    = prefs.getLong("bfo_u", BFO_USB_DEFAULT);
  bfoHz[1]    = prefs.getLong("bfo_l", BFO_LSB_DEFAULT);
  prefs.end();

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
  Serial.printf("bfo: USB %ld Hz / LSB %ld Hz（今は %s）\n", bfoHz[0], bfoHz[1], dspLsb() ? "LSB" : "USB");
  return true;
}

// ---- ADS1015: A0 を連続変換（±4.096V、1600SPS）----
void adsBegin() {
  Wire.beginTransmission(ADS1015_ADDR);
  Wire.write(0x01);            // 設定レジスタ
  Wire.write(0x42);            // MUX = A0 対 GND、PGA = ±4.096V、連続変換
  Wire.write(0x83);            // 1600SPS、コンパレータ不使用
  adsOk = (Wire.endTransmission() == 0);
  Wire.beginTransmission(ADS1015_ADDR);
  Wire.write(0x00);            // 以後は変換結果レジスタを読む
  Wire.endTransmission();
  if (!adsOk) Serial.println("ADS1015 not found");
}

// AD8307 の出力 [mV]（読めなければ -1）
float adsReadMv() {
  if (!adsOk) return -1;
  if (Wire.requestFrom(ADS1015_ADDR, 2) != 2) return -1;
  int16_t raw = (int16_t)((Wire.read() << 8) | Wire.read()) >> 4;   // 12 ビット、1LSB = 2mV
  return raw * 2.0f;
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

  pinMode(ENC_A,  INPUT_PULLUP);
  pinMode(ENC_B,  INPUT_PULLUP);
  pinMode(ENC_SW, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(ENC_A), encoderISR, CHANGE);

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
  oled.setCursor(20, 28);
  oled.print("PSN TRX VFO");
  oled.display();
  delay(1000);
#endif

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
    applyFreq();
  }

  int cnt = encCount;
  if (cnt != lastCount) {
    int diff = cnt - lastCount;
    lastCount = cnt;
    if (uiMode == UI_NORMAL) {
      currentFreq += (long)diff * stepValues[stepIndex];
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

  // 設定コマンド（送信音声: dsp / mic / out / iqd / iqa / sb / tone / alc / w、受信: bfo）
  static String cmdLine;
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (cmdLine.length() && !bfoCommand(cmdLine)) {
        if (dspCommand(cmdLine))
          applyFreq();                     // sb で側帯波を変えたら BFO・局発も合わせる
        else
          Serial.println("コマンド: dsp / mic <dB> / out <%> / iqd <us> / iqa <dB> / sb usb|lsb / tone <Hz> / alc <dBFS>|off / w / bfo [usb|lsb <Hz>]");
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
      updateMeter(meterPos(alcLevelDb), text, "TX", "");
    } else {
      alcLevelDb = -60.0f;
      char text[12], amt[16] = "";
      smeterText(smeterDb, text, sizeof(text));
      if (agcMode != AGC_OFF) {
        int g = (int)(agcCtl * AGC_RANGE_DB / 1000.0f + 0.5f);
        snprintf(amt, sizeof(amt), g > 0 ? "AGC -%ddB" : "AGC %ddB", g);
      }
      updateMeter(meterPos(smeterDb), text, agcLabels[agcMode], amt);
    }
    if (!txNow) Serial.printf("rssi %.0f mV  agc %.0f  S %.1f dB\n", rssiMv, agcCtl, smeterDb);
  }
}
