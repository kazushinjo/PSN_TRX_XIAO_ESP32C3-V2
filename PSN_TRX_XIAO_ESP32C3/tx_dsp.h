// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 JA6FUF (kazushinjo)
/*
 * 送信音声の I/Q 生成（基板 Ver 2.0）と、受信音のサンプリング
 *
 * D2/A2 を ADC の連続変換（32 kHz）で読み続け、
 *   受信中: 4 サンプル平均で 8 kHz にして dspReadRx() で渡す（V1 の Sメーター・AGC 用。V2 では A2 に受信音が来ないので使わない）
 *   送信中: 2 サンプル平均で 16 kHz にし、複素 FIR（中心 1600 Hz・通過 300〜2700 Hz、127 タップ）で
 *           90° 位相の違う I・Q を作って、I2S の PDM 2 線 DAC モードで D8（Q）・D10（I）に出す
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
bool dspLsb();                              // 側帯波が LSB か（sb コマンド。受信の BFO もこれに合わせる）
float dspAlcLevelDb();                      // 前回からの入力ピーク [dB、ALC の効き始め = 0]。正なら ALC がその分絞った
bool dspCommand(String line);               // 設定コマンド。処理したら true
void dspPrintStatus();
