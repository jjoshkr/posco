# 하드웨어 배선과 교정

## I/O 노드 보드 스택 (Raspberry Pi 5)

| 보드 | 주소(점퍼) | 역할 |
|---|---|---|
| MCC 152 #1 | 0 | AO0 P-101, AO1 P-102 (→ XTR111 → 4–20 mA), DIO0/2 OD(A/B), DIO1/3 EF(A/B), DIO4 XV-101, DIO5 XV-102 |
| MCC 152 #2 | 1 | AO0 P-103, AO1 교반기, DIO0/2 OD, DIO1/3 EF, DIO4 XV-103, DIO5 RUN_ENABLE(펌프 4대 공통 Pause), DIO6 P-104 펄스, DIO7 XV-104 |
| MCC 118 | 2 | CH0 pH, CH1~3 펌프 옵션 C 피드백, CH4 압력, CH5 탁도 (전부 4–20 mA, 250 Ω 션트 → 1–5 V) |
| MCC 134 | 3 | CH0 열전대 K (반응기 온도) |

주소가 다르면 `python -m cmysim.io_node_main init-config` 로 만든 `io_node.json` 의 `addresses`, `ao`, `od_pin`, `ef_pin`, `dio`, `ai`, `tc` 를 고칩니다.

## 펌프 인터페이스 보드 (XTR111 2채널, 보드 2장)

- MCC 152 AO 0–5 V → XTR111 (RSET 2.49 kΩ, 4.016 mA/V) → 펌프 mA 입력(저항 약 120 Ω). 1 V = 4.02 mA, 5 V = 20.08 mA.
- OD 핀: High = 출력 꺼짐. Pi 부팅 직후 DIO 가 입력(풀업)이라 자동으로 꺼져 있습니다. 코드가 AO 0 V 를 쓴 뒤 출력으로 바꿉니다.
- EF 핀: 오픈 드레인, Low = 부하 단선/과열. 코드는 입력(풀업)으로 읽어 `EF` 알람.
- 전원 투입 순서: Pi 와 보드 → 24 V. 끌 때는 역순.
- 펌프 설정: 아날로그 펌프는 Analog(4–20 mA) 모드, 신호 이상 처리 설정 확인(0 mA 가 되면 알람이 뜰 수 있음). Pause 접점은 RUN_ENABLE 선.

## 펄스 펌프 P-104 (산)

DIO6 → 470 Ω → PC817 → 펌프 외부 접점 입력(무전압 접점 요구, 개방 시 5 V·0.5 mA). 접점 닫힘 20 ms(`pulse_ms`), 펌프 매뉴얼의 최소 펄스폭
이상. 펌프는 Contact 모드. 1 펄스 = 1 스트로크(0.19 mL × 스트로크 길이).

## 밸브

2-way 상시닫힘(NC) 직동식 솔레노이드 × 4, 24 V. DIO → 470 Ω → PC817 → MOSFET/릴레이 → 코일(+ 플라이백 다이오드). PC817 입력에 10 kΩ 병렬로
부팅 중 희미한 ON 방지. 각 투입구 끝에 체크밸브(주입 밸브). Tier C 에서는 CaCl₂ 와 Na₂CO₃ 라인을 절대 합치지 않습니다.

## 계측

| 신호 | 트랜스미터 | 환산 (코드 기본) |
|---|---|---|
| pH | 절연형 4–20 mA | 0–14 |
| 압력 | 토출 쪽 압력 트랜스미터 4–20 mA | 0–10 bar |
| 탁도 | 4–20 mA 탁도계 | 0–1000 NTU |
| 온도 | 열전대 K | °C |
| 펌프 실제 스트로크 | gamma/X 옵션 C 4–20 mA | 0–200 spm |
| 스톡 질량 | HX711 로드셀 ×3 (+ 산 탱크용 4번째 권장) | g (tare, counts_per_g) |

pH 트랜스미터는 절연형이어야 펌프·모터 접지 루프를 피합니다. 프로브는 투입구 반대편, 임펠러 높이에.

## 로드셀

Arduino/ESP32 가 HX711 을 읽어 USB 시리얼로 보냅니다(`firmware/hx711_bridge.ino`, DOUT 2/4/6, SCK 3/5/7). I/O 노드 `loadcell.json`
에 `backend: serial`, `port`. 병은 받침대 위, 튜브는 느슨하게.

## 카메라 (AI 노드)

RealSense 는 USB 3.0. 노출·게인·화이트밸런스 수동 고정(`camera.json`). 흰 배경 반사형이면 글레어를 피하도록 비스듬히, 투과형이면
백색 LED 패널–반응기–카메라 일직선. 조명이나 위치를 바꾸면 `camera_tools reference` 부터 다시.

## 교정 절차 요약

| 대상 | 명령 | 언제 |
|---|---|---|
| 펌프 채널 mA (MCC 152 이득오차) | `io_node_main bench calib P-10x` (멀티미터) | 보드 조립 후, 채널마다 |
| 로드셀 | `loadcell tare --ch n`, `loadcell calib --ch n --mass 500` | 병 교체·재배치 시 |
| 카메라 E, I0 | `camera_tools reference` → `sample` ×(3×4~5) → `fit` → `check` | 조명·카메라·염료 변경 시 |
| 목표 시료 | `camera_tools target --save target.json` | 실험 세트마다 |
| pH 제어 이득 | 레시피 `mode: relay` (양방향이면 부하 불필요) | 새 배치/완충계마다 |
