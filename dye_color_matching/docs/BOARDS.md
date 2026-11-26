# 보드 세트 — 무엇을 만들고(납땜), 무엇을 그대로 쓰고, 어떻게 이어지나

올려 주신 자료(릴레이 32CH 보드 rev3, 릴레이 제어보드 Relay_module_v1, XTR111 2ch 보드, physical_ai_link)를 기준으로
I/O 노드 주변 보드를 정리했습니다. KiCad 파일은 `hardware/kicad/` 아래에 있고, 모두 KiCad 7 형식(7/8/9 에서 열림)입니다.

```
Pi 5 (I/O 노드) 40핀
 ├─ MCC 118  (주소 0) ──→ [새] mcc118_ai_board      ← 4–20 mA 트랜스미터 8채널 (PT, pH, 탁도, 펌프 피드백)
 ├─ MCC 152 a (주소 2) ──→ [새] mcc152_channel_board ← XTR111 2ch (기존 설계 그대로) + PC817 ×4 (DIO4~7) → 펌프 접점
 ├─ MCC 152 b (주소 3) ──→ [새] mcc152_channel_board    (같은 보드 2장)
 ├─ MCC 134  (주소 4) ──→ 보드 없음. K 열전대를 나사 단자에 직접
 └─ I2C (핀 3,5) ───────→ [기존] Relay_module_v1 (MCP23017 ×2 + ULN2803 ×4)
                            └─ 40핀 리본 → [기존] Relay_40pin_32CH (HF49FD ×32)
                                             └─ J1~J4 (L/N) → [새] valve_board (플라이백·LED) → 솔레노이드 XV-101~104
                                             └─ J34 ← valve_board J11 (+24 V / GND)
```

## 1. 보드별 역할

| 보드 | 상태 | 역할 | 파일 |
|---|---|---|---|
| **mcc118_ai_board** | 새로 제작 | MCC 118 앞단. 채널마다 PTC 50 mA → 루프 → 250 Ω 0.1 % 션트(GND 쪽) → RC → 5.1 V 제너 → 1 kΩ → CHn. 점퍼 빼면 ±10 V 전압 입력. 24 V 루프 전원(퓨즈·TVS) | `hardware/kicad/mcc118_ai_board/` |
| **mcc152_channel_board rev B** | 새로 제작 (XTR111 보드 확장) | 왼쪽: 올려 주신 XTR111 2ch 4–20 mA 회로 **그대로** (AO0/1, DIO0~3 OD/EF, J1·J2·J3). 오른쪽 추가: DIO4~7 → 470 Ω → PC817 → 무전압 접점 ×4 (J5~J8) + 상태 LED, 입력 단자 J4 | `hardware/kicad/mcc152_channel_board/` |
| **valve_board** | 새로 제작 | 24 V 솔레노이드 4채널 연결. 방식 A: 릴레이 접점 입력(32CH 보드 Jn L/N). 방식 B: 로직 입력 → IRLZ44N. 채널마다 1N4007 플라이백·LED·코일 단자. 24 V 입력(퓨즈 2 A·TVS), 릴레이 보드 J34 와 PT 루프로 24 V 분배 | `hardware/kicad/valve_board/` |
| Relay_module_v1 | 기존 (납땜 예정) | Pi I2C → MCP23017 ×2 → ULN2803 ×4 → S1~S32 싱크. J1 = Pi 40핀(3.3 V, SDA 핀3, SCL 핀5, RST GPIO27, INTA/B GPIO22/23), J2 = 릴레이 보드로 40핀, J3 = 5 V 입력 | 올려 주신 zip |
| Relay_40pin_32CH rev3 | 기존 | 32 릴레이, 단자 L–N–FG. 24 V 로 쓸 때 J34 L = +24 V, N = GND | 올려 주신 zip |
| MCC 134 | 보드 없음 | CH0 H/L 에 K 열전대(노랑 +, 빨강 −). 두 장이면 주소 4·5 | — |

## 2. 핀·채널 배정 (rev B, `hardware/io_node_rev_b.json`)

| 신호 | 어디서 | 어디로 |
|---|---|---|
| P-101 펄스 | MCC 152 a DIO4 → 채널보드 a J5 | 펌프 1 External contact (C → 흰색, E → 검정) |
| P-102 펄스 | MCC 152 a DIO5 → J6 | 펌프 2 External contact |
| P-103 펄스 | MCC 152 a DIO6 → J7 | 펌프 3 External contact |
| 운전 허가 (Pause) | MCC 152 a DIO7 → J8, b DIO4 → J5, b DIO5 → J6 (세 핀 동시) | 펌프 1·2·3 Pause (C → 갈색, E → 검정) |
| XV-101~104 | Relay_module_v1 릴레이 1~4 (U1 GPB0~3 → S1~S4) → 32CH 보드 J1~J4 | valve_board J1~J4 → 코일 |
| 아날로그 펌프(옵션) | MCC 152 AO0/1 + DIO0~3 | XTR111 → 4–20 mA (채널보드 J3) |
| PT-101 압력 | 24 V 루프 → mcc118_ai_board CH4 | MCC 118 CH4 |
| TE-101 | K 열전대 | MCC 134 CH0 |

릴레이 번호 ↔ MCP23017 핀 (Relay_module_v1 넷리스트에서 확인): S1~8 = U1 GPB0~7, S9~16 = U1 GPA0~7, S17~24 = U2 GPB0~7, S25~32 = U2 GPA0~7.
U1/U2 주소는 JP1~JP6 점퍼로 서로 다르게 (예: U1 0x20 = 점퍼 없음, U2 0x21 = JP6 꽂음). 코드 `mcp23017.addr_u1/addr_u2`.

**I2C 주소 충돌 주의**: MCC 152 의 DIO 도 같은 I2C-1 버스의 MCP23017 이고 주소는 **0x20 + 보드 주소**입니다. 이 프리셋(MCC 152 a = 2, b = 3)에서는 0x22·0x23 을 쓰므로 릴레이 제어보드는 0x20·0x21 로 두면 겹치지 않습니다.
cmysim 기본값(152 가 주소 0·1)으로 두면 0x20·0x21 이 겹쳐 릴레이 명령이 MCC 152 DIO 에 들어갑니다. `i2cdetect -y 1` 로 네 주소가 모두 다르게 보이는지 먼저 확인하세요.
relay_panel.py 의 [버스 스캔]은 0x20~0x27 에서 응답하는 주소가 정확히 둘일 때만 자동으로 채우므로, MCC 스택이 꽂혀 있으면 주소를 손으로 지정해야 합니다(절대 0x22·0x23 을 고르지 말 것).

physical_ai_link 의 보드 주소(118=0, 172=1, 152a=2, 152b=3, 134=4)를 그대로 썼습니다. MCC 172 가 스택에 있어도 cmysim 은 건드리지 않습니다.

## 2b. 스택 순서와 보드별 시험 연결

릴레이 HAT(Relay_module_v1)는 40핀이 **관통(스태킹) 헤더가 아니라** 아래쪽 암 소켓만 있어 위에 아무것도 못 올린다. 따라서 **맨 위**에 둔다.
MCC 보드는 모두 스태킹 헤더(긴 핀)라 아래부터 쌓고, 마지막에 릴레이 HAT 를 그 핀에 꽂는다. 높이가 안 맞거나 릴레이 보드 가까이 두고 싶으면 맨 위 핀에 40핀 리본(암–암)을 꽂아 릴레이 HAT 를 옆에 둔다.

| 층 (아래→위) | 보드 | 주소 점퍼 | I2C 주소 | 시험할 때 무엇을 연결하나 | 확인 명령 |
|---|---|---|---|---|---|
| 1 | MCC 118 | 0 (없음) | — | CH4–GND 에 1.5 V 건전지 또는 mcc118_ai_board + PT | `python -m cmysim.io_node_main bench read` (아날로그·온도 연속 표시) |
| 2 | MCC 152 a | 2 (A1) | 0x22 | DIO4~7 에 LED+1 kΩ(→GND) 또는 채널보드 rev B | `bench dio 4 1`, `bench blink 4` |
| 3 | MCC 152 b | 3 (A0+A1) | 0x23 | 같음 (`--board mcc152#2`) | `bench dio 4 1 --board mcc152#2` |
| 4 | MCC 134 | 4 (A2) | — | CH0 H/L 에 K 열전대. 없으면 H–L 을 짧은 선으로 묶으면 실온이 읽힘 | `bench read` |
| 5 (맨 위) | 릴레이 HAT | JP4 (U2=0x24) | 0x20, 0x24 | 40핀 리본 → 32CH 릴레이 보드, J3 5 V | `python -m cmysim.relay_ctl scan`, `walk 1 1 9 17 25` |

쌓은 뒤 한 번: `sudo daqhats_read_eeproms && daqhats_list_boards` (주소 0 외의 MCC 보드를 등록). `i2cdetect -y 1` 에 20, 22, 23, 24 가 보여야 한다.
MCC 134 는 발열원에서 멀수록 좋다. 릴레이 HAT 의 ULN2803 은 릴레이 32개 전부 ON 일 때도 1 W 안이라 바로 위에 있어도 큰 영향은 없지만, 정밀 온도가 필요해지면 릴레이 HAT 를 리본으로 떼어 둔다.

## 3. 소프트웨어 (cmysim)
- `io_node.json` 에 `mcp23017` 항목이 있으면 밸브·운전허가를 릴레이 제어보드로 보냅니다 (smbus2 필요: `pip install smbus2`, I2C 켜기 `raspi-config`).
- `dio.RUN_ENABLE` 는 핀 하나 또는 `[[보드, 핀], ...]` 목록 — 펌프마다 PC817 하나씩.
- 부팅 때 MCP23017 은 입력 상태(릴레이 OFF)이고, 코드는 쓰는 핀만 출력으로 바꾸면서 OFF 래치를 먼저 씁니다. 종료·SAFE 때 전부 OFF.
- 시작: `cp hardware/io_node_rev_b.json io_node.json` 후 `python -m cmysim.io_node_main run --pump-mode pulse -v`.
  릴레이만 시험: `python -c "from cmysim.daqhats_hal import MCP23017Relays; m=MCP23017Relays({'relays':{'x':1}}); m.set(1,True)"`.

## 4. 납땜 순서 (권장)
1. **Relay_module_v1** (SMD 0805/1206, SOIC-18 ×4, SOIC-28 ×2 또는 DIP-28): 저항·콘덴서 → ULN2803 → MCP23017 → 헤더. 점퍼 JP1~6 으로 두 칩 주소를 다르게. 5 V 넣고 `i2cdetect -y 1` 에 0x20, 0x21 보이면 OK.
2. **mcc152_channel_board rev B** ×2: 기존 XTR111 부분은 BOM 대로(SMD). 추가 부분은 PC817 소켓, 0805 저항, LED, 단자대. 펄스만 쓸 거면 XTR111 부분은 **비워 둬도** 됩니다 (J1 의 GND 만 필요).
3. **mcc118_ai_board**: 션트 250 Ω 0.1 % 는 축방향 1/2 W, 나머지 스루홀. 점퍼 꽂음 = 4–20 mA.
4. **valve_board**: 방식 A(릴레이)면 Q1~Q4·R1~R8·R20·J9 비움, JP1~8 을 A 쪽(1-2). 방식 B 면 반대.
5. 점검: 보드마다 전원 없이 단락 확인 → 5 V/24 V 만 → MCC 연결 → `bench dio` / `i2cdetect`.

## 5. KiCad 에서
각 폴더의 `.kicad_pro` 를 열고 ERC → F8 로 PCB. 풋프린트는 KiCad 표준 라이브러리 이름입니다. 채널보드는 XTR111 보드의 프로젝트 심볼 라이브러리(`xtr111_board.kicad_sym`, `sym-lib-table`)를 그대로 포함하고 있어 외부 라이브러리 없이 열립니다.
확인하지 못한 것: 이 환경에 KiCad 가 없어 ERC 를 직접 돌리지 못했습니다. 파일 파서(kiutils)로 읽기·쓰기와 끊긴 넷 0 은 확인했습니다. 전원 네트에 PWR_FLAG 경고가 나오면 PWR_FLAG 를 붙이면 됩니다.

## 6. 미리보기
`hardware/kicad/<보드>/<보드>_preview.svg` (KiCad 없이 보는 간이 그림), `BOM.md` / `bom.csv`.
