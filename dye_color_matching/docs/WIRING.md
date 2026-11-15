# 배선표와 네트워크 구성 — MCC 단자 ↔ 인터페이스 보드 ↔ 펌프·밸브·트랜스미터, 두 Pi 연결

그림: [WIRING.svg](WIRING.svg) (선 번호 W1~W38 이 아래 표와 같음). 회로도: [../hardware/kicad/](../hardware/kicad/). 조립 순서: [ASSEMBLY.md](ASSEMBLY.md).

## 1. MCC 보드 단자 사용 현황 (I/O 노드)

| 보드 (주소) | 단자 | 용도 | 코드 키 (`io_node.json`) |
|---|---|---|---|
| MCC 152 #1 (0) | DIO6 | P-101 접점 펄스 | `dio.P-101 = ["mcc152#1", 6]` |
| | DIO7 | P-102 접점 펄스 | `dio.P-102 = ["mcc152#1", 7]` |
| | DIO4 | XV-101 솔레노이드 | `dio.XV-101 = ["mcc152#1", 4]` |
| | DIO5 | XV-102 솔레노이드 | `dio.XV-102 = ["mcc152#1", 5]` |
| | DGND | 인터페이스 보드 GND_PI | |
| | DIO0~3, AO0/1 | 비움 (아날로그 펌프 모드에서만 OD/EF/AO 사용) | |
| MCC 152 #2 (1) | DIO0 | P-103 접점 펄스 | `dio.P-103 = ["mcc152#2", 0]` |
| | DIO4 | XV-103 솔레노이드 | `dio.XV-103 = ["mcc152#2", 4]` |
| | DIO5 | RUN_ENABLE (펌프 3대 Pause 공통) | `dio.RUN_ENABLE = ["mcc152#2", 5]` |
| | DIO6 / DIO7 | 예비 (P-104 / XV-104, 공침 단계 산 펌프) | |
| | AO1 | 예비 (교반기 0–5 V → XTR111, 추후) | |
| MCC 118 (2) | CH4 | 압력 트랜스미터 (250 Ω 션트, 1–5 V = 0–10 bar) | `ai.PRESSURE.ch = 4` |
| | GND | 션트 기준 (GND_24 와 여기서 결합) | |
| | CH0 / CH5 / CH6 | 예비 (pH / PT 2 / PT 3) | |
| MCC 134 (3) | CH0 H / L | K 열전대 (선택) | `tc.TEMP.ch = 0` |
| Pi 40핀 (스택 위 노출 핀) | 핀 2 (5 V), 핀 6 (GND) | 인터페이스 보드 +5V/GND_PI | |

주소 점퍼: #1 없음, #2 A0, MCC 118 A1, MCC 134 A0+A1. 바꾸면 `io_node.json` 의 `addresses` 를 맞춘다.

## 2. 배선표 (W1~W38)

전선: 신호 AWG 22 (0.3 mm²), 24 V 와 코일 AWG 18 (0.75 mm²), PT 루프는 2심 차폐선. 양 끝에 페룰을 끼우고 선 번호 라벨을 붙인다.

### 2-1. I/O 노드 → 인터페이스 보드 (3.3 V 로직, 짧게 ≤ 50 cm)

| W | 출발 | 도착 | 신호 | 색 |
|---|---|---|---|---|
| W1 | MCC 152 #1 DIO6 | J1-1 | DIO_P101 | 파랑 |
| W2 | MCC 152 #1 DIO7 | J1-2 | DIO_P102 | 파랑 |
| W3 | MCC 152 #2 DIO0 | J1-3 | DIO_P103 | 파랑 |
| W4 | MCC 152 #1 DIO4 | J1-4 | DIO_XV101 | 파랑 |
| W5 | MCC 152 #1 DIO5 | J1-5 | DIO_XV102 | 파랑 |
| W6 | MCC 152 #2 DIO4 | J1-6 | DIO_XV103 | 파랑 |
| W7 | MCC 152 #2 DIO5 | J1-7 | DIO_RUN | 파랑 |
| W8 | MCC 152 #1 DGND | J1-8 | GND_PI | 초록 |
| W9 | Pi 핀 2 (5 V) | J2-1 | +5V | 빨강/주황 |
| W10 | Pi 핀 6 (GND) | J2-2 | GND_PI | 초록 |
| W11 | J14-1 | MCC 118 CH4 | PT_LOOP (1–5 V) | 빨강 (차폐) |
| W12 | J14-2 | MCC 118 GND | GND_24 → 접지 결합점 | 초록 |

W12 를 연결하면 보드의 R30(0 Ω) 은 **장착하지 않는다**. 접지는 한 곳에서만 만나야 한다. PT 가 아직 없으면 W11/W12 를 비우고 R30 을 장착한다.

### 2-2. 인터페이스 보드 → 펌프 (접점, 광절연)

gamma/X 범용 제어 케이블(5선) 기준. **선 색과 핀 번호는 펌프 매뉴얼의 표로 확인**한다. 아래는 ProMinent gamma 계열의 일반적 배정이다.

| 펌프 선 | 기능 | 이 프로젝트 |
|---|---|---|
| 1 갈색 | Pause | PC817 (J6~J8) 컬렉터 |
| 2 흰색 | External contact | PC817 (J3~J5) 컬렉터 |
| 3 파랑 | Auxiliary frequency | 미사용 (절연 처리) |
| 4 검정 | GND (공통) | PC817 이미터 두 개 공통 |
| 5 회색 | Analog 0/4–20 mA | 미사용 (아날로그 모드에서만) |

| W | 출발 | 도착 | 신호 |
|---|---|---|---|
| W13 | J3-1 (C+) | P-101 선 2 흰색 | External contact |
| W14 | J3-2 (C−) | P-101 선 4 검정 | GND (공통) |
| W15 | J6-1 (C+) | P-101 선 1 갈색 | Pause |
| W16 | J6-2 (C−) | P-101 선 4 검정 | GND — W14 와 같은 선에 함께 물림 |
| W17~W20 | J4, J7 | P-102 선 2 / 4 / 1 / 4 | 위와 동일 |
| W21~W24 | J5, J8 | P-103 선 2 / 4 / 1 / 4 | 위와 동일 |

펌프 설정: Contact 모드, 메모리 OFF, 1 펄스 = 1 스트로크, 스트로크 길이 100 %, Pause 접점 "닫힘 = 운전". 펌프 GND(검정)는 Pi 접지와 연결하지 않는다.

### 2-3. 인터페이스 보드 → 솔레노이드 (24 V)

| W | 출발 | 도착 | 신호 |
|---|---|---|---|
| W25 | J9-1 | XV-101 코일 1 | +24V |
| W26 | J9-2 | XV-101 코일 2 | COIL− (MOSFET 드레인) |
| W27 / W28 | J10-1 / J10-2 | XV-102 코일 | |
| W29 / W30 | J11-1 / J11-2 | XV-103 코일 | |

코일은 극성이 없다. 플라이백 다이오드는 보드에 있으므로 밸브 쪽에는 필요 없다. 밸브 본체는 접지하지 않아도 되지만 금속 패널에 고정되면 자연히 접지된다.

### 2-4. 압력 트랜스미터와 24 V 전원

| W | 출발 | 도착 | 신호 |
|---|---|---|---|
| W31 | J13-1 | PT + | +24V (루프 전원) |
| W32 | J13-2 | PT − | PT_LOOP (4–20 mA 귀환 → 250 Ω) |
| W33 | 24 V PSU +V | J12-1 | +24V_IN (퓨즈 앞) |
| W34 | 24 V PSU −V | J12-2 | GND_24 |
| W35 / W36 | 24 V PSU L / N | 220 V (별도 차단기, 접지선은 PSU FG 에) | |
| W37 / W38 | TE-101 K+ (노랑) / K− (빨강) | MCC 134 CH0 H / L | 열전대 (선택, 보드 안 거침) |

PSU −V 는 섀시 접지에 묶지 않는다. 접지 결합은 보드(W12 또는 R30) 한 곳이다. PT 케이블 차폐는 보드 쪽 GND_24 에만 연결한다.

## 3. 두 Pi 와 워크스테이션 연결

### 3-1. 물리 연결
- **권장**: 5포트 기가 스위치 하나에 워크스테이션, AI 노드, I/O 노드를 꽂는다. 한 서브넷(192.168.10.0/24)이라 SSH·scp·ZeroMQ 가 모두 된다.
- **최소**: 두 Pi 를 LAN 선으로 직결 (Pi 5 는 Auto-MDIX 라 일반 케이블). 워크스테이션은 각 Pi 의 Wi-Fi 로 접속.
- RealSense 는 AI 노드의 **파란 USB 3** 포트. Pi 전원은 각각 27 W USB-C.

### 3-2. 고정 IP (Raspberry Pi OS Bookworm, NetworkManager)

I/O 노드:

```bash
sudo nmcli con add type ethernet ifname eth0 con-name lab ipv4.method manual ipv4.addresses 192.168.10.2/24
sudo nmcli con up lab
sudo hostnamectl set-hostname io-node
```

AI 노드:

```bash
sudo nmcli con add type ethernet ifname eth0 con-name lab ipv4.method manual ipv4.addresses 192.168.10.3/24
sudo nmcli con up lab
sudo hostnamectl set-hostname ai-node
```

워크스테이션은 192.168.10.1/24 (Windows: 이더넷 어댑터 속성 → IPv4 수동). 게이트웨이는 비워 둔다 (인터넷은 Wi-Fi 로).

### 3-3. 접속과 포트

| 연결 | 방향 | 포트 | 비고 |
|---|---|---|---|
| SSH | 워크스테이션 → 두 Pi | 22 | `ssh-copy-id pi@192.168.10.2` 로 키 등록 |
| ZeroMQ cmd | AI → I/O (PUSH → PULL) | 5555 | I/O 노드가 바인드 |
| ZeroMQ tele | I/O → AI (PUB → SUB) | 5556 | I/O 노드가 바인드, 10 Hz |
| 하트비트 | AI → I/O | 5555 안 | 1 s 끊기면 I/O SAFE |

Pi 기본 방화벽은 없으므로 열 것이 없다. 외부 망에 붙일 경우에만 5555/5556 을 192.168.10.0/24 로 제한한다.

### 3-4. 확인 순서

```bash
ping -c 3 192.168.10.2            # AI 노드에서
python -m cmysim.io_node_main run --sim --sim-camera -v        # I/O 노드 (보드 없이)
python -m cmysim.ai_node_main --io-ip 192.168.10.2 --monitor   # AI 노드: 텔레메트리 수신 확인
```

그다음 LAN 선을 뽑아 I/O 노드 로그에 1 s 뒤 `SAFE: watchdog` 가 뜨는지 본다. 마지막으로 I/O 노드를 `run --pump-mode pulse -v` 로 바꿔 실보드로 간다.

## 4. 전원 순서와 비상 정지
- 켜기: I/O 노드 Pi → AI 노드 Pi → 24 V → 펌프 전원. 끄기: 역순.
- 비상: 24 V 차단기 하나로 밸브가 닫히고(NC) Pause 접점이 열려 펌프가 멈춘다. Pi 는 그대로 둬도 된다.
- 소프트웨어: UI 또는 AI 노드의 전체 정지(SAFE), I/O 노드 종료(Ctrl-C)도 같은 SAFE 순서를 밟는다.

## 5. 단자별 점검값 (멀티미터)

| 위치 | 상태 | 기대값 |
|---|---|---|
| J1-n ↔ J1-8 | `bench dio <n> 1` | 3.3 V (0 이면 0 V) |
| J3-1 ↔ J3-2 (다이오드 모드) | DIO6 = 1 | 도통 (수십 Ω) / DIO6 = 0 이면 OL |
| J9-2 ↔ J12-2 | DIO4 = 1, 24 V 켬 | ≈ 0 V (MOSFET ON), 코일 전류 ≈ 0.5 A |
| J14-1 ↔ J14-2 | PT 연결, 무압 | ≈ 1.0 V (4 mA); 10 bar 에서 5.0 V |
| J12-1 ↔ J12-2 | 24 V 켬 | 24 V (퓨즈 앞) |
