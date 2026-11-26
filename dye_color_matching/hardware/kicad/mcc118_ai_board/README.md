# mcc118_ai_board — MCC 118 앞단 8채널 (4–20 mA 루프 / 전압)

채널 n: +24V → F(n) PTC 50 mA → J(n)-1 (트랜스미터 +) ; J(n)-2 (트랜스미터 −) → JP(n)(꽂음) → R(n) 250 Ω 0.1 % → GND ; 같은 점에서 C 100 nF, D 5.1 V 제너, R 1 kΩ → J9 → MCC 118 CHn.
JP(n) 을 빼면 J(n)-2 가 ±10 V 전압 입력이 됩니다 (션트 분리).
J9: CH0~CH7, GND. J10: 24 V 입력 (F9 500 mA, D9 TVS, C9).
배정: CH0 pH · CH1~3 펌프 피드백(옵션) · CH4 PT-101 압력 · CH5 탁도 · CH6/7 예비.
접지: 이 보드 GND = MCC 118 GND = 24 V GND. 다른 곳에서 또 묶지 않습니다.
