// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 JA6FUF (kazushinjo)
/*
 * 送信音声の I/Q 生成（基板 Ver 2.0）と、受信音のサンプリング
 *
 * D2/A2 を ADC の連続変換（32 kHz）で読み続け、
 *   受信中: 4 サンプル平均で 8 kHz にして dspReadRx() で渡す（V1 の Sメーター・AGC 用。V2 では A2 に受信音が来ないので使わない）
 *   送信中: 2 サンプル平均で 16 kHz にし、複素 FIR（中心 1600 Hz・通過 300〜2700 Hz、127 タップ）で
 *           90° 位相の違う I・Q を作って、I2S の PDM 2 線 DAC モードで D8（Q）・D10（I）に出す
 *           AM（sb am）では「(搬送波 + 音声) × cos(4 kHz)」を同じ FIR（中心 4 kHz）に通し、局発 + 4 kHz に AM を作る
 * D10 は受信中は AGC の PWM（dspAgcWrite で書く）。送信中だけ PDM に切り替える。
 * 処理は優先度の高いタスクで行うので、loop() の表示処理などで音が途切れない。
 */
#pragma once
#include <Arduino.h>

void dspBegin(uint8_t pinTxSense, uint8_t pinPdmQ, uint8_t pinAgcPdmI, uint32_t agcFreq, uint8_t agcBits);
bool dspTxActive();                         // PDM 出力中（送信中）
int  dspReadRx(int16_t *buf, int maxn);     // 受信音（8 kHz、0〜4095）。受け取った数を返す
void dspAgcWrite(uint32_t duty);            // AGC の PWM 値（送信中は覚えておき、受信に戻ったら出す）
bool dspAlcOn();                            // ALC が有効か
#define DSP_AM_IF_HZ 4000                   // AM: 搬送波を送信局発からずらす量（= FS/4。送信局発は表示周波数 − これ）
#define DSP_AM_BW_HZ 2500                   // AM: 音声の上限（−6 dB）。占有は表示周波数 ± これ
bool dspLsb();                              // 側帯波が LSB か（sb コマンド。受信の BFO もこれに合わせる。AM では false）
bool dspAm();                               // AM か（sb am。受信は USB、送信局発は表示周波数 − DSP_AM_IF_HZ）
void dspSetAm(bool am);                     // USB / AM を切り替えて保存（パネルの MODE。LSB は使わないので USB に戻す）
float dspAmDepth();                         // AM の変調度 [%]
void dspSetAmDepth(float pct, bool save);   // AM の変調度を変える（10〜100 %）。save = true で保存
float dspAlcLevelDb();                      // 前回からの入力ピーク [dB、ALC の効き始め = 0]。正なら ALC がその分絞った
bool dspCommand(String line);               // 設定コマンド。処理したら true
void dspPrintStatus();
