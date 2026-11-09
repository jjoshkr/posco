// HX711 × 3 → USB 시리얼 브리지 (Arduino Nano/Uno/ESP32). 라이브러리: "HX711" by bogde (Library Manager)
// 출력: "ms,raw0,raw1,raw2\n" 10 Hz. 읽기 실패 채널은 "nan".
// 배선: 각 HX711 의 DT→DOUT 핀, SCK→SCK 핀, VCC 5V(또는 3.3V), GND 공통. 로드셀 E+ E- A+ A- 는 HX711 에.
// 명령(선택): 'R' = 재시작, 'F' = 80 Hz (HX711 RATE 핀을 High 로 결선했을 때만 의미 있음)
#include "HX711.h"

const int N = 3;
const int DOUT[N] = {2, 4, 6};
const int SCK_[N] = {3, 5, 7};
HX711 cell[N];
unsigned long period_ms = 100;

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < N; i++) {
    cell[i].begin(DOUT[i], SCK_[i]);   // 채널 A, 128 배
  }
}

void loop() {
  static unsigned long next = 0;
  unsigned long now = millis();
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'F') period_ms = 12;
    if (c == 'R') period_ms = 100;
  }
  if (now < next) return;
  next = now + period_ms;
  Serial.print(now);
  for (int i = 0; i < N; i++) {
    Serial.print(',');
    if (cell[i].wait_ready_timeout(50)) Serial.print(cell[i].read());
    else Serial.print("nan");
  }
  Serial.println();
}
