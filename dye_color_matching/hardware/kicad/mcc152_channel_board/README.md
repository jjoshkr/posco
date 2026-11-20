# mcc152_channel_board rev B

올려 주신 `xtr111_4-20mA` 프로젝트(XTR111 2채널 4–20 mA)를 **그대로 포함**하고, 오른쪽에 DIO4~7 → PC817 절연 접점 출력 4채널을 더한 것입니다. MCC 152 한 장당 한 장, 두 장 제작.

| 부분 | 내용 |
|---|---|
| 왼쪽 (기존) | J1 ← MCC 152 (AO0/1, GND, OD/EF DIO0~3, VIO), J2 24 V, J3 펌프 4–20 mA ×2. 부품 번호 1xx/2xx |
| 오른쪽 (rev B) | J4 ← MCC 152 DIO4~7 + GND. 채널마다 R30x 470 Ω → U30x PC817 → J5~J8 (C, E). R305~308 + D301~304 상태 LED. 부품 번호 3xx |

접점 배정 (보드 a = MCC 152 주소 2, 보드 b = 주소 3): a J5 P-101 펄스 · a J6 P-102 펄스 · a J7 P-103 펄스 · a J8 P-101 Pause · b J5 P-102 Pause · b J6 P-103 Pause.
PC817 C(4번) → 펌프 신호선(External contact 흰색 / Pause 갈색), E(3번) → 펌프 GND(검정).

펄스 모드만 쓸 때는 XTR111 부분(U1xx/U2xx, Q, D, R1xx/2xx, C)을 실장하지 않아도 됩니다. 그때 J1 은 3번(GND)만 쓰고 J2(24 V) 도 비워 둡니다.

파일: `mcc152_channel_board.kicad_pro/.kicad_sch` (KiCad 7 형식), `xtr111_board.kicad_sym` + `sym-lib-table` (프로젝트 심볼), `bom.csv` (원본 BOM + rev B 추가분), `mcc152_channel_board_preview.svg`.
