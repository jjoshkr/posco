# coprecip_sim — CMY 식용색소 도징 · target color 매칭 시뮬레이터

전구체 공침 반응기 실험의 1단계(식용색소 실험)를 보드 없이 통째로 돌려 보는 코드입니다.
시안·마젠타·옐로 스톡을 gamma/X 펌프 3대로 반응기에 넣어 **목표색을 만들고**, 펌프 유량(=흘려주는 색소 양)을
바꿔 가며 **목표색에 얼마나 가까워지는지(ΔE2000)** 를 카메라 모델로 비교합니다. 제어 구조는 실제 하드웨어
(Pi 5 + AI HAT+ ↔ Pi 5 + MCC 118/134/152×2, 이더넷)와 같게 두 노드로 나눠 놓았습니다.

```
AI 노드 (Pi 5 + AI HAT+, RealSense)              I/O 노드 (Pi 5 + MCC 118 + MCC 134 + MCC 152 ×2)
┌──────────────────────────────┐   cmd (JSON)   ┌────────────────────────────────────────────────┐
│ 카메라 ROI RGB → 흡광도      │ ─────────────▶ │ 인터록 · 운전허가 · 밸브 · 펌프 mA · 스트로크 계수 │
│ → NNLS 로 ĉ(C,M,Y)           │   telemetry    │ MCC 152 AO → XTR111 → 4–20 mA → gamma/X          │
│ 레시피 계획 / 피드포워드 /   │ ◀───────────── │ MCC 118: 펌프 피드백(옵션 C)·pH·압력, MCC 134: 온도│
│ 카메라 폐루프 트림           │   하트비트     │ 하트비트 1 s 끊기면 SAFE (Pause → 0 mA → 밸브 닫힘) │
└──────────────────────────────┘                └────────────────────────────────────────────────┘
                                                          │ 스톡 C/M/Y (2 L, 1 g/L)  →  반응기 5 L (heel 2 L)
```

## 빠른 시작

```bash
cd coprecip_sim
python -m cmysim plan  --target "#5A8F7B"                       # 투입량·유량·mA 계획만
python -m cmysim run   --target "#5A8F7B" --mode closed --plot run.png --csv run.csv --dataset ds/
python -m cmysim run   --target "#5A8F7B" --mode open  --fault stock_conc:P-101=900 --e-cal-err 0.03
python -m cmysim sweep --target "#5A8F7B" --factors 0.7,0.85,1,1.15,1.3 --csv sweep.csv
python -m cmysim calib                                           # MCC 152 이득오차 2점 교정 시연
python -m pytest -q tests                                        # 10개 테스트
```

필요한 것: Python 3.10+, numpy. 그래프는 matplotlib(선택). 목표는 `--target '#RRGGBB'` 또는 `--cmy 30,10,25`(mg/L).

## 무엇을 시뮬레이션하나

| 층 | 모듈 | 모델 |
|---|---|---|
| 광학 | `optics.py` | PDF 보고서 7장 절차 그대로: 감마 제거 → 흡광도 A = −log10(I/I0) → A = E c (3×3) → 비음수 최소제곱. 색차는 CIEDE2000/ΔE76 |
| 펌프 | `hardware.py` | gamma/X Analog 모드: 4.4 mA 첫 스트로크, 19.6 mA 200 spm, 3.8 mA 아래 신호 알람, 1 스트로크 = 0.19 mL × 스트로크 길이 × (1 ± 1 %), 옵션 C 피드백 4–20 mA, 수위 입력, 토출 막힘 시 릴리프 3 bar |
| DAC 체인 | `hardware.py` | MCC 152 AO 12 bit 0–5 V(이득오차 ±1.5 %) → XTR111 4.016 mA/V, OD 핀 페일세이프, 2점 교정 |
| 계측 | `hardware.py` | MCC 118 12 bit ±10 V + 250 Ω 션트, MCC 134 열전대 잡음 |
| 공정 | `process.py` | 스톡 탱크 잔량·수위 스위치, 반응기 물질수지(semi-batch), 교반 혼합 지연 t_m = 3000/rpm [s] |
| 비전 | `vision.py` | RealSense 대역 합성 프레임(비네팅·잡음·기포), ROI 평균, YOLO 라벨 데이터셋 기록 |
| 노드 | `nodes.py` | Bus(ZeroMQ 대역), HAL(SimHAL / DaqHatsHAL), IONode(인터록·워치독·스트로크 계수 도징), AINode |
| 제어 | `control.py` | 계획: V_f = V_heel/(1 − Σc_j/c_s), V_j = c_j V_f / c_s. 상태기계 PLAN→PRIME→DOSE→SETTLE→MEASURE→TRIM→DONE |
| 실행 | `experiment.py` | 고장 주입, 유량 스윕, 그래프, CSV/JSON, 데이터셋 |

## 실험 1: 유량(투입량)을 바꾸면 색이 얼마나 비껴가나 (`sweep`)

같은 도징 시간에 펌프 하나의 유량만 ×0.7~×1.3 으로 바꾼 결과(목표 #5A8F7B, 개루프, 매칭 기준 ΔE2000 < 1.5):

| 펌프(염료) | ×0.7 | ×0.85 | ×1.0 | ×1.15 | ×1.3 |
|---|---|---|---|---|---|
| P-101 (C) | 6.6 | 2.6 | 0.0 | 2.4 | 4.4 |
| P-102 (M) | 5.5 | 3.0 | 0.0 | 3.0 | 5.4 |
| P-103 (Y) | 9.3 | 4.4 | 0.0 | 3.5 | 6.1 |

유량 15 % 오차면 이미 ΔE 2~4 로 육안 식별 수준입니다. 옐로(황색 4호 역할)가 가장 민감한데, 이 색에서 Y 농도가
B 채널 흡광도를 거의 혼자 정하기 때문입니다. 이 표가 "펌프 교정·스톡 농도 관리가 얼마나 정확해야 하는가"의 답입니다.

## 실험 2: 개루프 vs 카메라 폐루프 (`run --mode open|closed`)

스톡이 라벨보다 묽고(C 900, Y 920 mg/L) AI 노드의 보정 행렬 E 에 3 % 오차가 있을 때:

| | 최종 ΔE2000 | 트림 | 비고 |
|---|---|---|---|
| open (피드포워드만) | 2.0 | – | 계획대로 넣었지만 스톡 오차만큼 빗나감 |
| closed (카메라 트림) | 0.4 | 1회 | 카메라 추정 ĉ 와 목표 차이만큼 추가 투입 (C +8.9 mL, Y +6.2 mL) |

![closed loop with stock error](docs/example_closed_stock_error.png)

폐루프는 **부족분만 메울 수 있습니다.** 오버슈트는 물 펌프가 없으면 못 돌리므로, 피드포워드는 일부러 약간 적게
넣도록 `flow_factor`(예 0.97)를 쓰는 것이 실제 운용에서 안전합니다.

## 실험 3: 고장 주입 (`--fault`)

| 지정 | 무엇이 일어나나 | 코드가 어떻게 잡나 |
|---|---|---|
| `tank_empty:P-101@30` | 30 s 에 C 스톡이 수위 스위치 직전까지 줄어듦 → 펌프 수위 입력으로 자체 정지 | I/O 노드 `NO_STROKE` 알람(지령 18 mA, 피드백 4 mA), AI 노드 DOSE 타임아웃 → 중단 |
| `valve_stuck:XV-101` | 코일은 켜지는데 밸브가 안 열림 → 데드헤드 | 릴리프 3 bar 로 탱크 복귀(반응기엔 안 들어감). 압력 트랜스미터가 2.7 bar 넘기면 I/O 노드가 도징 펌프 전부 정지 + `RELIEF` 알람 |
| `signal_loss:P-103@40` | 4–20 mA 케이블 단선 | 펌프가 0 mA 를 보고 정지, `NO_STROKE` |
| `ai_crash@150` | AI 노드 프로세스 사망(하트비트 중단) | I/O 노드 워치독 1 s → SAFE(Pause → 0 mA → 밸브 닫힘) |
| `camera_drift:0.9@60` | 조명/노출 10 % 변화 | 실제 농도는 맞는데 ĉ 가 전부 커 보여 카메라 ΔE 2.4 로 '불일치' 판정, 트림도 못 함(= 수동 노출 고정과 기준 영상 I0 재촬영이 왜 필수인지) |
| `stock_conc:P-101=900` | 칭량 오차 | open 은 빗나가고 closed 는 트림으로 복구 |
| `rpm:80` | 교반 약함 → 혼합시간 37 s | SETTLE 이 길어지고 카메라 추정이 뒤처짐 |

## 데이터셋 (`--dataset DIR`)

2 s 마다 합성 프레임 PNG + YOLO 라벨(`0 on_target` / `1 off_target`, 액체 ROI 박스)과 `index.jsonl`(진짜 농도, 추정 농도,
RGB, ΔE)을 남깁니다. `dataset.yaml` 은 Ultralytics 형식입니다. 나중에 RealSense 실제 프레임으로 바꿔도 라벨 형식은 그대로
쓰면 됩니다. 단, 색·농도 같은 연속값은 YOLO(탐지)보다 `index.jsonl` 로 회귀 모델을 학습하는 쪽이 맞고, YOLO 는
기포·와류·침전·이물 같은 '사건' 탐지에 쓰는 것이 대화에서 정리한 역할 분담입니다.

## 라즈베리파이에서 실행 (실제 카메라)

### 설치 (AI 노드: Pi 5 + AI HAT+, Raspberry Pi OS 64-bit Bookworm)

```bash
sudo apt install -y python3-numpy python3-opencv python3-zmq python3-picamera2
pip install pyrealsense2        # aarch64 휠이 없으면 librealsense 를 소스 빌드해야 합니다 (아래 링크)
```

RealSense 는 USB 3.0 포트(파란색)에 꽂고 `rs-enumerate-devices` 로 인식을 확인합니다. pyrealsense2 가 Pi 에서 바로
안 깔리면 https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_raspbian.md 를 따라 빌드하거나,
임시로 `--kind opencv` 로 RealSense 를 UVC 웹캠처럼 열어 색만 읽을 수 있습니다. 라즈베리파이 전용 카메라를 사면
`--kind picamera2` 로 바꾸면 됩니다(인터페이스 동일).

I/O 노드(Pi 5 + MCC): `pip install daqhats pyzmq` 후 `python -m cmysim.zmq_bridge io`.
두 Pi 는 이더넷 직결 + 고정 IP(예 I/O 192.168.10.2, AI 192.168.10.3)로 둡니다.

### 카메라 보정 순서 (PDF 8장 절차를 그대로 명령으로)

```bash
cd coprecip_sim
python -m cmysim.camera_tools settings --kind realsense --exposure 120 --gain 16 --wb 4600   # 수동 고정
python -m cmysim.camera_tools preview --save shot.png        # ROI 가 액체 안에 들어가는지 확인
python -m cmysim.camera_tools roi --roi 220,140,200,200       # 또는 --pick (모니터 있을 때 마우스로)
python -m cmysim.camera_tools reference                       # 물만 채운 반응기 → 픽셀별 기준 I0
python -m cmysim.camera_tools sample --dye C --conc 5         # 시안 5 mg/L … 10, 15, 20 (염료마다 4~5점)
python -m cmysim.camera_tools sample --dye M --conc 5
python -m cmysim.camera_tools sample --dye Y --conc 5
python -m cmysim.camera_tools fit                             # E 피팅 → calibration.json (조건수·R² 출력)
python -m cmysim.camera_tools check --cmy 10,5,8              # 보정에 안 쓴 혼합액으로 검증
python -m cmysim.camera_tools target --save target.json       # 목표 시료(기준 색 용액)를 같은 카메라로 촬영
```

카메라가 없는 워크스테이션에서는 `settings --kind fake` 로 위 명령을 전부 돌려 볼 수 있습니다
(`CMYSIM_FAKE_CONC=10,5,8` 환경변수로 가짜 액체 농도를 바꿉니다).

`reference` 에서 I0 가 0.95 를 넘으면 포화이니 노출을 줄이고, `sample` 에서 흡광도가 1 을 넘으면 더 묽게 잡습니다.
조명·카메라 위치·노출을 바꾸면 reference 부터 다시 합니다.

### 실험 실행

```bash
python -m cmysim.camera_tools monitor --target "#5A8F7B"      # 배선 전: 카메라만으로 ĉ, ΔE 확인
python -m cmysim.ai_node_main --io-ip 192.168.10.2 --target-file target.json --mode closed \
       --flow-factor 0.97,0.97,0.97 --log run1.csv --dataset ds_run1/ --preview
```

목표는 `--target '#hex'`, `--cmy`, `--target-file` 중 하나로 줍니다. ΔE 기준으로는 같은 카메라·조명으로 찍은
`target.json` 이 가장 정확합니다(hex 는 모델을 거쳐 환산되므로 비네팅·글레어만큼 어긋날 수 있음).

`ai_node_main` 은 시뮬레이터와 같은 `Controller` 를 쓰고 카메라 입력만 실물입니다. Ctrl+C·예외·완료 어느 경우에도
I/O 노드에 `run_enable OFF` 와 `safe` 를 보내고, I/O 노드는 하트비트가 1 초 끊기면 스스로 SAFE 가 됩니다.
`--dataset` 을 주면 실제 프레임이 2 초마다 YOLO 라벨과 함께 저장됩니다(라벨의 c_true 는 실물에서는 null, 카메라 추정 ĉ 와 ΔE 만 기록).

## 실제 보드로 옮길 때

1. `nodes.DaqHatsHAL` 이 `cfg.channel_map` 대로 daqhats 를 호출합니다(이 저장소에서는 실행 못 했으니 Pi 에서 `mcc152_bench.py` 로
   먼저 핀을 확인한 뒤 OD 핀 번호를 맞추세요).
2. `zmq_bridge.ZmqBus` 가 `Bus` 와 같은 인터페이스로 PUSH/PULL + PUB/SUB 를 제공합니다. I/O 노드: `python -m cmysim.zmq_bridge io`.
3. AI 노드는 `cmysim/ai_node_main.py` 가 완성본입니다. `camera.py` 의 RealSense/Picamera2/OpenCV 백엔드가 ROI 평균 RGB 와
   픽셀별 기준 영상 기반 흡광도를 `Controller.step(..., A=A)` 에 넣습니다.
4. 보정 행렬 E 와 I0 는 `camera_tools` 로 실측해 `calibration.json` 에 저장되고 `ai_node_main` 이 자동으로 읽습니다.
   `config.py` 의 값은 시뮬레이션용 설명값입니다.

## 가정과 출처

| 항목 | 값 | 근거 |
|---|---|---|
| 펌프 스트로크 | 0.19 mL (GMXa 1602), 최대 200 spm, ±1 % | gamma/X 매뉴얼 (대화에서 확인). 실제 모델명은 명판 확인 필요 |
| mA 곡선 | 4.4 mA 시작, 19.6 mA 최고, <3.8 mA 알람 | gamma/X 매뉴얼 |
| Pause 중 저전류 알람 무시 | 가정 | 펌프 메뉴의 신호 이상 처리 설정에 따라 다름 — 확인 항목 |
| MCC 152 | 12 bit 0–5 V, 이득 ±1.5 % | Digilent 전기 사양 |
| XTR111 | 4.016 mA/V (RSET 2.49 kΩ) | 대화의 보드 설계 |
| 반응기 | 5 L, heel 2 L | 설계 가이드에서 5 L 로 확정 |
| 스톡 | 2 L GL45, 1.00 g/L | 대화의 구매 목록·스톡 농도 제안 |
| 혼합시간 | t_m = 3000/rpm s | 가정 (300 rpm 에서 10 s). 실측으로 바꿀 것 |
| E 행렬, I0, 글레어 | 설명용 값 | PDF 보고서의 가상 예와 같은 성격. 조건수 κ = 1.57 |
| 교반기 | 4–20 mA ↔ 0–1000 rpm | 가정. 교반기 외부 입력 사양 확인 필요 |
| 카메라 | 감마 2.2, ROI 4000 픽셀, 픽셀 잡음 2 % | PDF 보고서 가정 + 일반적 값 |

## 파일

```
coprecip_sim/
├── cmysim/            시뮬레이션: config, optics, hardware, process, vision, nodes, control, experiment, __main__
│                      실물(Pi): camera (RealSense/Picamera2/OpenCV), camera_tools (보정 CLI), ai_node_main, zmq_bridge
├── tests/test_sim.py  물질수지·광학 역산·펌프 곡선·DAC 교정·인터록·워치독·폐루프·고장 테스트
├── docs/              예시 그래프
└── README.md
```
