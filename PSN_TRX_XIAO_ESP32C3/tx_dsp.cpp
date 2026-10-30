// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 JA6FUF (kazushinjo)
/*
 * 送信音声の I/Q 生成（基板 Ver 2.0）と、受信音のサンプリング。説明は tx_dsp.h
 *
 * ---- 設定コマンド（USB シリアル、115200 bps。1 行ずつ。w で NVS に保存）----
 *   dsp          設定と動作状態の表示
 *   mic <dB>     マイク利得（-12〜+30 dB。IC2A で約 26 dB 増幅済み）
 *   out <%>      出力レベル（変調の深さ、5〜100 %）
 *   iqd <us>     I/Q の遅延補正（-20〜+20 µs。+ で I 側を遅らせる）
 *   iqa <dB>     I/Q の利得補正（-2〜+2 dB。+ で I 側を上げる）
 *   sb usb|lsb   側帯波（Q の符号を反転）
 *   tone <Hz>    試験トーン（送信中にマイクの代わりに正弦波を出す。0 で止める。保存しない）
 *   alc <dBFS>   ALC の効き始め（-24〜0 dBFS）。alc off で止める（そのときはクリップの手前で振り切れの表示だけ）
 *   w            保存
 *
 * ---- I/Q の補正の合わせ方 ----
 *   ダミーロードに送信し、tone 1000 で 1 kHz を出す。受信機で反対側の側帯波（搬送波から逆側に 1 kHz）が
 *   最小になるよう iqd → iqa の順に合わせ、w で保存する。希望の側帯波が逆なら sb で切り替える。
 *   2 段 RC（R61〜R64・C75〜C78）の部品のばらつき（I と Q で ±3%）は、iqd が数 µs・iqa が 0.2 dB 程度で打ち消せる。
 *
 * ---- ALC（デジタル）----
 *   マイク利得のあと・複素 FIR の前で、入力のピークが効き始めのレベルを超えた分だけ利得を下げる
 *   （ピークにはすぐ追従、戻りは約 0.26 秒）。超えた分（= 絞った量）を dspAlcLevelDb() で返し、LCD に出す。
 *   RF 出力は見ていない。変調器への入力が過大になってひずむのを防ぐもの。
 */
#include "tx_dsp.h"
#include <Preferences.h>
#include <math.h>
#include "esp_adc/adc_continuous.h"
#include "driver/i2s_pdm.h"

#define MIC_ADC_CH   ADC_CHANNEL_4     // D2/A2 = GPIO4
#define FS           16000             // 送信の処理と出力
#define ADC_FS       32000             // ADC（受信は 4 サンプル、送信は 2 サンプル平均）
#define NTAP         127               // 遅延 (NTAP-1)/2 = 63 サンプル = 3.9 ms
#define F_CENTER     1600.0f
#define F_CUT        1400.0f           // 原型 LPF のカットオフ。通過 300〜2700 Hz（200・3000 Hz で −6 dB、50 Hz で −21 dB）
                                       // 低域も I・Q 同じ特性で落とす（中心 1500・1500 では I が直流まで素通しで、ハムや送信開始の音の逆側帯波が抑圧されなかった）
#define KAISER_BETA  7.5f
#define BLOCK        32                // 送信 1 回分の出力サンプル（2 ms）
#define ADC_FRAME    (BLOCK * 2 * SOC_ADC_DIGI_RESULT_BYTES)
#define RAMP_N       1024              // 送信開始時に出力の平均を中点まで上げるサンプル数（64 ms）
#define MUTE_N       7200              // 送信開始から入力を無音にするサンプル数（0.45 秒）。TX12V でマイク系のバイアスが立ち上がる過渡（約 0.28 秒、部品のばらつき・温度で延びる分を見込む）を送らない
#define RX_RING      1024              // 受信音の受け渡し（8 kHz で 128 ms）
#define ALC_REL_SHIFT 12               // ALC の戻り（4096 サンプル = 約 0.26 秒の時定数）

static uint8_t pinTx, pinQ, pinI, agcBits;
static uint32_t agcFreq, agcDuty = 0;

static Preferences prefs;
static struct {
  float micDb = 0.0f, outPct = 10.0f, iqDelayUs = 0.0f, iqGainDb = 0.0f;   // 出力 10 % で旧回路の変調器入力（マイク 1 Pa で約 13 mVrms）と同程度
  bool lsb = false;
  bool alcOn = true;
  float alcDb = -20.0f;                   // ALC の効き始め [dBFS]。出力 10 % で変調器ドライブ（Q15・Q16）の歪み約 1 %（−6 では 7〜8 %）
} cfg;
static float toneHz = 0;

static int16_t hI[NTAP], hQ[NTAP];
static int coefShift = 15;
static int16_t xbuf[NTAP * 2];
static int xpos = 0;
static int32_t micGainQ8 = 256, outGainQ8 = 128, dcQ16 = 0;
static int16_t sineTab[1024];
static uint32_t tonePhase = 0, toneInc = 0;
static int32_t alcThr = 3277, alcEnv = 0;   // 効き始めのレベル（±32767 に対して）・入力のピーク追従
static bool alcActive = true;

static adc_continuous_handle_t adcH = nullptr;
static i2s_chan_handle_t txH = nullptr;
static volatile bool pdmOn = false;
static int rampLeft = 0, rampFromI = 0, rampFromQ = 0, muteLeft = 0;

static portMUX_TYPE rxMux = portMUX_INITIALIZER_UNLOCKED;
static int16_t rxRing[RX_RING];
static volatile int rxHead = 0, rxTail = 0;

// 状態表示用（書くのは dspTask だけ）
static uint32_t adcErrors = 0, clipCount = 0, txBlocks = 0;
static int32_t peakIn = 0, peakOut = 0;
static volatile int32_t alcPeak = 0;  // ALC 前の入力ピーク（dspAlcLevelDb で読んで 0 に戻す）

// ---- 係数（起動時と設定変更時）----
static float besselI0(float x) {
  float sum = 1, term = 1, y = x * x / 4;
  for (int k = 1; k < 30; k++) { term *= y / (k * k); sum += term; if (term < 1e-9f * sum) break; }
  return sum;
}

// 窓付き sinc の原型 LPF を、中心からの位置 t（サンプル、小数可）で求める
static float protoLpf(float t) {
  const float c = (NTAP - 1) / 2.0f;
  float u = t / c;
  if (u <= -1 || u >= 1) return 0;
  float w = besselI0(KAISER_BETA * sqrtf(1 - u * u)) / besselI0(KAISER_BETA);
  float x = 2 * F_CUT / FS;
  return ((t == 0) ? x : sinf(M_PI * x * t) / (M_PI * t)) * w;
}

static void buildFilter() {
  const float c = (NTAP - 1) / 2.0f, w0 = 2 * M_PI * F_CENTER / FS;
  const float dI = cfg.iqDelayUs * 1e-6f * FS, gI = powf(10, cfg.iqGainDb / 20), sQ = cfg.lsb ? -1 : 1;
  static float fI[NTAP], fQ[NTAP];
  float s1 = 0, s2 = 0;
  for (int n = 0; n < NTAP; n++) {
    float tI = n - c - dI, tQ = n - c;
    fI[n] = 2 * gI * protoLpf(tI) * cosf(w0 * tI);
    fQ[n] = 2 * sQ * protoLpf(tQ) * sinf(w0 * tQ);
    s1 += fabsf(fI[n]); s2 += fabsf(fQ[n]);
  }
  // 入力は ±32767。係数の絶対値の総和 × 32767 が int32 に収まるシフト量にする
  int sh = 15;
  while (sh > 8 && fmaxf(s1, s2) * (1 << sh) * 32767.0f > 2.0e9f) sh--;
  int16_t nI[NTAP], nQ[NTAP];
  for (int n = 0; n < NTAP; n++) { nI[n] = (int16_t)lrintf(fI[n] * (1 << sh)); nQ[n] = (int16_t)lrintf(fQ[n] * (1 << sh)); }
  noInterrupts();
  memcpy(hI, nI, sizeof(hI)); memcpy(hQ, nQ, sizeof(hQ)); coefShift = sh;
  micGainQ8 = (int32_t)lrintf(256 * powf(10, cfg.micDb / 20));
  outGainQ8 = (int32_t)lrintf(256 * cfg.outPct / 100);
  alcThr = cfg.alcOn ? (int32_t)lrintf(32767 * powf(10, cfg.alcDb / 20)) : 32767;   // off のときは振り切れの基準
  alcActive = cfg.alcOn;
  interrupts();
}

// ---- 入出力 ----
static bool adcOverflow(adc_continuous_handle_t, const adc_continuous_evt_data_t *, void *) { adcErrors++; return false; }

static void startAdc() {
  adc_continuous_handle_cfg_t hc = {};
  hc.max_store_buf_size = ADC_FRAME * 16;   // 32 ms 分
  hc.conv_frame_size = ADC_FRAME;
  ESP_ERROR_CHECK(adc_continuous_new_handle(&hc, &adcH));
  adc_digi_pattern_config_t pat = {};
  pat.atten = ADC_ATTEN_DB_12;              // 約 0〜2.5 V。AF_ADC は R38/R39 で 1.65 V にバイアス
  pat.channel = MIC_ADC_CH;
  pat.unit = ADC_UNIT_1;
  pat.bit_width = SOC_ADC_DIGI_MAX_BITWIDTH;
  adc_continuous_config_t dc = {};
  dc.sample_freq_hz = ADC_FS;
  dc.conv_mode = ADC_CONV_SINGLE_UNIT_1;
  dc.format = ADC_DIGI_OUTPUT_FORMAT_TYPE2;
  dc.pattern_num = 1;
  dc.adc_pattern = &pat;
  ESP_ERROR_CHECK(adc_continuous_config(adcH, &dc));
  adc_continuous_evt_cbs_t cbs = {};
  cbs.on_pool_ovf = adcOverflow;
  ESP_ERROR_CHECK(adc_continuous_register_event_callbacks(adcH, &cbs, nullptr));
  ESP_ERROR_CHECK(adc_continuous_start(adcH));
}

// 送信へ: D10 の AGC PWM を外して PDM（D8 = Q、D10 = I）を始める
static void pdmStart() {
  ledcDetach(pinI);
  i2s_chan_config_t cc = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
  cc.dma_desc_num = 8;
  cc.dma_frame_num = BLOCK * 2;             // 32 ms 分
  ESP_ERROR_CHECK(i2s_new_channel(&cc, &txH, nullptr));
  i2s_pdm_tx_config_t pc = {
    .clk_cfg = I2S_PDM_TX_CLK_DAC_DEFAULT_CONFIG(FS),
    .slot_cfg = I2S_PDM_TX_SLOT_DAC_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
    .gpio_cfg = {
      .clk = I2S_GPIO_UNUSED,
      .dout = (gpio_num_t)pinQ,             // 左 = Q（D8）
      .dout2 = (gpio_num_t)pinI,            // 右 = I（D10）
      .invert_flags = { .clk_inv = false },
    },
  };
  ESP_ERROR_CHECK(i2s_channel_init_pdm_tx_mode(txH, &pc));
  ESP_ERROR_CHECK(i2s_channel_enable(txH));
  // 受信中の平均電圧（D8 = 0 V、D10 = AGC のデューティ）から中点（1.65 V）へゆっくり上げる
  rampFromQ = -32767;
  rampFromI = (int)((int64_t)agcDuty * 65534 / ((1 << agcBits) - 1)) - 32767;
  rampLeft = RAMP_N;
  muteLeft = MUTE_N;
  for (int i = 0; i < NTAP * 2; i++) xbuf[i] = 0;
  alcEnv = 0;
  pdmOn = true;
}

// 受信へ: PDM を止め、D10 を AGC の PWM に戻す
static void pdmStop() {
  pdmOn = false;
  i2s_channel_disable(txH);
  i2s_del_channel(txH);
  txH = nullptr;
  pinMode(pinQ, OUTPUT);
  digitalWrite(pinQ, LOW);
  ledcAttach(pinI, agcFreq, agcBits);
  ledcWrite(pinI, agcDuty);
}

static inline int16_t sat16(int32_t v) {
  if (v > 32767) { clipCount++; return 32767; }
  if (v < -32768) { clipCount++; return -32768; }
  return (int16_t)v;
}

static void rxPush(int16_t v) {
  portENTER_CRITICAL(&rxMux);
  int nh = (rxHead + 1) % RX_RING;
  if (nh != rxTail) { rxRing[rxHead] = v; rxHead = nh; }
  portEXIT_CRITICAL(&rxMux);
}

static void dspTask(void *) {
  static uint8_t raw[ADC_FRAME];
  static int16_t out[BLOCK * 2];
  int32_t acc = 0; int cnt = 0;
  for (;;) {
    uint32_t got = 0;
    esp_err_t e = adc_continuous_read(adcH, raw, ADC_FRAME, &got, 50);
    bool tx = digitalRead(pinTx) == LOW;
    if (tx && !pdmOn) { pdmStart(); acc = cnt = 0; }
    if (!tx && pdmOn) { pdmStop(); acc = cnt = 0; }
    if (e != ESP_OK) continue;
    int n = got / SOC_ADC_DIGI_RESULT_BYTES;
    if (!pdmOn) {
      // 受信: 4 サンプル平均で 8 kHz（0〜4095）
      for (int i = 0; i < n; i++) {
        adc_digi_output_data_t *d = (adc_digi_output_data_t *)&raw[i * SOC_ADC_DIGI_RESULT_BYTES];
        if (d->type2.channel != MIC_ADC_CH) continue;
        acc += d->type2.data;
        if (++cnt == 4) { rxPush((int16_t)(acc >> 2)); acc = cnt = 0; }
      }
      continue;
    }
    // 送信: 2 サンプル平均で 16 kHz → 複素 FIR → PDM
    int k = 0;
    for (int i = 0; i < n && k < BLOCK; i++) {
      adc_digi_output_data_t *d = (adc_digi_output_data_t *)&raw[i * SOC_ADC_DIGI_RESULT_BYTES];
      if (d->type2.channel != MIC_ADC_CH) continue;
      acc += d->type2.data;
      if (++cnt < 2) continue;
      int32_t xq = acc << 16; acc = cnt = 0;          // 2 サンプルの和（0〜8190）
      dcQ16 += (xq - dcQ16) >> 12;                    // 直流分（約 0.1 秒で追従）
      int32_t x = (xq - dcQ16) >> 13;                 // ×8 で ±32760 相当
      if (toneHz > 0) { tonePhase += toneInc; x = sineTab[tonePhase >> 22] >> 2; }   // 約 -12 dBFS
      else x = (x * micGainQ8) >> 8;
      if (muteLeft > 0) { muteLeft--; x = 0; }        // 送信開始直後は ALC・FIR に入れない
      // ALC: ピークがすぐ上がり・ゆっくり下がる包絡線が効き始めを超えた分だけ絞る
      int32_t ax = abs(x);
      if (ax > alcEnv) alcEnv = ax; else alcEnv -= alcEnv >> ALC_REL_SHIFT;
      if (ax > alcPeak) alcPeak = ax;
      if (alcActive && alcEnv > alcThr) {
        int32_t gQ15 = (alcThr << 15) / alcEnv;       // alcThr ≦ 32767 なので int32 に収まる
        x = (int32_t)(((int64_t)x * gQ15) >> 15);
      }
      int16_t xs = sat16(x);
      if (abs(xs) > peakIn) peakIn = abs(xs);
      xbuf[xpos] = xs; xbuf[xpos + NTAP] = xs;
      if (++xpos >= NTAP) xpos = 0;
      const int16_t *xp = &xbuf[xpos];               // xp[0] が最も古い
      int32_t yi = 0, yq = 0;
      for (int t = 0; t < NTAP; t++) { int32_t v = xp[NTAP - 1 - t]; yi += hI[t] * v; yq += hQ[t] * v; }
      yi = ((yi >> coefShift) * outGainQ8) >> 8;
      yq = ((yq >> coefShift) * outGainQ8) >> 8;
      if (rampLeft > 0) {                             // 送信開始直後は無音のまま平均を中点へ
        int32_t r = rampLeft--;
        yi = (int32_t)((int64_t)rampFromI * r / RAMP_N);
        yq = (int32_t)((int64_t)rampFromQ * r / RAMP_N);
      }
      int16_t oi = sat16(yi), oq = sat16(yq);
      if (abs(oi) > peakOut) peakOut = abs(oi);
      out[k * 2] = oq;
      out[k * 2 + 1] = oi;
      k++;
    }
    if (k) { size_t w = 0; i2s_channel_write(txH, out, k * 2 * sizeof(int16_t), &w, 50); txBlocks++; }
  }
}

// ---- 公開関数 ----
static void loadSettings() {
  prefs.begin("psndsp", true);
  cfg.micDb     = prefs.getFloat("mic", cfg.micDb);
  cfg.outPct    = prefs.getFloat("out", cfg.outPct);
  cfg.iqDelayUs = prefs.getFloat("dly", cfg.iqDelayUs);
  cfg.iqGainDb  = prefs.getFloat("gain", cfg.iqGainDb);
  cfg.lsb       = prefs.getBool("lsb", cfg.lsb);
  cfg.alcOn     = prefs.getBool("alc", cfg.alcOn);
  cfg.alcDb     = prefs.getFloat("alcdb", cfg.alcDb);
  prefs.end();
}

static void saveSettings() {
  prefs.begin("psndsp", false);
  prefs.putFloat("mic", cfg.micDb);
  prefs.putFloat("out", cfg.outPct);
  prefs.putFloat("dly", cfg.iqDelayUs);
  prefs.putFloat("gain", cfg.iqGainDb);
  prefs.putBool("lsb", cfg.lsb);
  prefs.putBool("alc", cfg.alcOn);
  prefs.putFloat("alcdb", cfg.alcDb);
  prefs.end();
  Serial.println("dsp: 保存しました");
}

void dspBegin(uint8_t pTx, uint8_t pQ, uint8_t pI, uint32_t fAgc, uint8_t bAgc) {
  pinTx = pTx; pinQ = pQ; pinI = pI; agcFreq = fAgc; agcBits = bAgc;
  pinMode(pinTx, INPUT);                    // R50（10 kΩ）で 3.3 V に引き上げ済み
  pinMode(pinQ, OUTPUT);
  digitalWrite(pinQ, LOW);
  ledcAttach(pinI, agcFreq, agcBits);
  ledcWrite(pinI, 0);
  for (int i = 0; i < 1024; i++) sineTab[i] = (int16_t)lrintf(32767 * sinf(2 * M_PI * i / 1024));
  loadSettings();
  buildFilter();
  startAdc();
  xTaskCreate(dspTask, "dsp", 4096, nullptr, configMAX_PRIORITIES - 2, nullptr);
}

bool dspTxActive() { return pdmOn; }

bool dspAlcOn() { return cfg.alcOn; }

float dspAlcLevelDb() {
  int32_t p = alcPeak;
  alcPeak = 0;
  if (p <= 0) return -90.0f;
  return 20.0f * log10f((float)p / alcThr);
}

int dspReadRx(int16_t *buf, int maxn) {
  int n = 0;
  portENTER_CRITICAL(&rxMux);
  while (n < maxn && rxTail != rxHead) { buf[n++] = rxRing[rxTail]; rxTail = (rxTail + 1) % RX_RING; }
  portEXIT_CRITICAL(&rxMux);
  return n;
}

bool dspLsb() { return cfg.lsb; }

void dspAgcWrite(uint32_t duty) {
  agcDuty = duty;
  if (!pdmOn) ledcWrite(pinI, duty);
}

void dspPrintStatus() {
  Serial.printf("dsp: マイク %+.1f dB / 出力 %.0f %% / I/Q 遅延 %+.2f us / I/Q 利得 %+.2f dB / %s / トーン %.0f Hz\n",
                cfg.micDb, cfg.outPct, cfg.iqDelayUs, cfg.iqGainDb, cfg.lsb ? "LSB" : "USB", toneHz);
  if (cfg.alcOn) Serial.printf("dsp: ALC %+.1f dBFS から\n", cfg.alcDb);
  else           Serial.println("dsp: ALC off");
  Serial.printf("dsp: %s / 入力ピーク %ld / 出力ピーク %ld / クリップ %lu / ADC あふれ %lu / 送信ブロック %lu / 係数シフト %d\n",
                pdmOn ? "送信中" : "受信中", (long)peakIn, (long)peakOut, (unsigned long)clipCount,
                (unsigned long)adcErrors, (unsigned long)txBlocks, coefShift);
  peakIn = 0; peakOut = 0;
}

bool dspCommand(String line) {
  line.trim();
  int sp = line.indexOf(' ');
  String cmd = sp < 0 ? line : line.substring(0, sp);
  String arg = sp < 0 ? "" : line.substring(sp + 1);
  arg.trim();
  float v = arg.toFloat();
  if      (cmd == "dsp")  { dspPrintStatus(); return true; }
  else if (cmd == "mic")  cfg.micDb = constrain(v, -12, 30);
  else if (cmd == "out")  cfg.outPct = constrain(v, 5, 100);
  else if (cmd == "iqd")  cfg.iqDelayUs = constrain(v, -20, 20);
  else if (cmd == "iqa")  cfg.iqGainDb = constrain(v, -2, 2);
  else if (cmd == "sb")   cfg.lsb = arg.startsWith("l") || arg.startsWith("L");
  else if (cmd == "alc") {
    if (arg.startsWith("off") || arg.startsWith("OFF")) cfg.alcOn = false;
    else { cfg.alcOn = true; if (arg.length()) cfg.alcDb = constrain(v, -24, 0); }
  }
  else if (cmd == "tone") { toneHz = constrain(v, 0, 3000); toneInc = (uint32_t)(toneHz / FS * 4294967296.0); }
  else if (cmd == "w")    { saveSettings(); return true; }
  else return false;
  buildFilter();
  dspPrintStatus();
  return true;
}
