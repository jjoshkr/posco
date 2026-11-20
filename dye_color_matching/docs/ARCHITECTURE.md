# 아키텍처

## 목적

전구체 공침 반응기 자동화의 1단계(식용색소 CMY 색 매칭)부터 Tier B(pH 유도 침전), Tier C(CaCO₃ 공침)까지를
**같은 코드**로 시뮬레이션하고 실제 장치에서 돌리기 위한 소프트웨어입니다. 시뮬레이터에서 검증한 제어기·레시피·이상탐지가
하드웨어 추상층(HAL)과 카메라 백엔드만 바꿔 실제 Raspberry Pi 두 대에서 그대로 동작합니다.

## 두 노드 구조

```
┌──────────────────────────── AI 노드 (Pi 5 + AI HAT+) ────────────────────────────┐
│ camera.py      RealSense / Picamera2 / OpenCV / fake / telemetry → ROI RGB, 흡광도  │
│ optics.py      RGB → 흡광도 → 3×3 NNLS → ĉ(C,M,Y), CIEDE2000                       │
│ control.py     목표색 → 투입 계획, 피드포워드 + 카메라 트림 (Controller)            │
│ recipe.py      YAML 스텝 실행기 (RecipeExecutor, Controller 와 같은 step() 인터페이스)│
│ ph_control.py  양방향 pH PID + 완충용량 상한 + 속도 제한기 + 릴레이 동조             │
│ yolo_infer.py  기포·액체 상태 (ultralytics / Hailo)                                 │
│ anomaly.py     시계열 오토인코더 + CUSUM (Detector.push)                              │
│ ai_node_main.py  10 Hz 루프: 카메라 → 제어기 → 명령, 하트비트 0.2 s, CSV·데이터셋    │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                     ZeroMQ  PUSH cmd(JSON) ↓   ↑ PUB telemetry(JSON) 10 Hz
┌──────────────────────────── I/O 노드 (Pi 5 + MCC 152×2 + MCC 118 + MCC 134) ──────┐
│ nodes.IONode   명령 적용, 인터록, 스트로크 계수 도징, 펄스 펌프, 워치독 1 s, 알람   │
│ loadcell.py    HX711 질량 → 유량, FlowCheck (FLOW_LOW/HIGH, TANK_LOW, DISTURBED)     │
│ daqhats_hal.py MCC 보드 구동 (AO → XTR111 → 4–20 mA, DIO 밸브/OD/EF/펄스, AI/TC)    │
│ io_node_main.py  10 Hz 루프, 벤치 명령, --sim (SimHAL)                              │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                                    │ 4–20 mA / 접점 / 24 V
   gamma/X P-101~103 (아날로그) · P-104 (펄스) · XV-101~104 · 교반기 · pH/압력/탁도 트랜스미터 · 열전대 · 로드셀
```

- **AI 노드는 실시간 책임이 없습니다.** 명령만 보내고, 끊기면 I/O 노드가 1 s 안에 SAFE 가 됩니다.
- **I/O 노드는 명령을 검증합니다.** 밸브 닫힌 채 펌프, 운전 허가 없이 펌프, 노드 미무장(arm) 상태의 펌프 명령은 거부하고 알람을 냅니다.
- 두 노드 사이 메시지는 전부 JSON dict 입니다(`docs/PROTOCOL.md`). 시뮬레이션에서는 `nodes.Bus` 가 ZeroMQ 를 대신합니다.

## 시뮬레이터

`nodes.SimPlant` 가 공정과 장비 모델 전체를 담습니다.

| 모델 | 모듈 | 요점 |
|---|---|---|
| 펌프 체인 | hardware.py | MCC 152 12 bit DAC(이득오차 ±1.5 %) → XTR111 4.016 mA/V → gamma/X(4.4 mA 시작, 19.6 mA 200 spm, <3.8 mA 알람, 0.19 mL/스트로크 ±1 %, 옵션 C 피드백, 릴리프 3 bar), 펄스 펌프 |
| 공정 | process.py | 스톡 탱크(수위 스위치), 반응기 물질수지, 교반 혼합 지연 t_m=3000/rpm, pH 모델·프로브, 침전·탁도 |
| pH | ph_control.py | 강염기−강산+약산 완충계 전하 균형(이분법) |
| 침전 | precip.py | 탄산 평형, 과포화도 S, 침전 속도 k(√S−1)², 구연산 억제, 탁도 = k×고체 농도 |
| 카메라 | vision.py | Beer–Lambert + 글레어 + 비네팅 + 잡음 + 기포 + 탁도 백색 혼입, YOLO 라벨 자동 생성 |
| 로드셀 | loadcell.py | 질량 raw(잡음·드리프트·병 건드림) |
| 계측 | hardware.py | MCC 118 12 bit ±10 V + 250 Ω 션트, MCC 134 열전대 잡음 |

고장 주입(`experiment.apply_fault`): tank_empty, valve_stuck, signal_loss, ai_crash, camera_drift, rpm, stock_conc, ph_drift, pump_air,
temp_step, acid_load.

## 안전 체인

1. 부팅: MCC 152 DIO 는 입력(풀업) → XTR111 OD High → 0 mA. 코드는 AO 0 V 를 쓴 뒤에야 OD 를 출력으로 바꿉니다.
2. 운전 중: I/O 노드 인터록(밸브·운전 허가·무장), 릴리프 압력 시 펌프 정지, 부피 한계 시 SAFE, 하트비트 1 s 워치독.
3. 종료: `safe()` = 운전 허가 OFF → AO 0 V → OD High → 밸브 OFF. 프로세스 예외/신호에서도 `finally` 로 보장.
4. 제어기 수준: pH 상·하한, 배치 최대 시약 부피, 프로브 고착 감지, 완충용량·상승률 기반 과투입 방지.
5. 하드웨어 수준(코드 밖): 비상정지 버튼(24 V 차단), 배압·릴리프 밸브, 체크밸브, 펌프 수위 입력.

## 데이터 흐름과 산출물

| 산출물 | 생성 | 소비 |
|---|---|---|
| `timeseries.csv` (시뮬레이션) / `ai_node_log.csv`, `io_log.csv` (실물) | experiment / 노드 스크립트 | anomaly(gen/train/score), 분석 |
| 데이터셋 `images/`, `labels/`, `index.jsonl` | DatasetRecorder | yolo_train(prepare/train), regress |
| `log.json` (스텝·측정·고장 라벨) | RecipeExecutor | 이상탐지 라벨, 보고 |
| `calibration.json`, `camera_ref.npy` | camera_tools | ai_node_main, Controller |
| `loadcell.json`, `io_node.json`, `camera.json` | CLI | 노드 스크립트 |
| `ad_model/` (meta.json + pca.npz/conv.npz) | anomaly train | ai_node_main --anomaly |
| `best.pt` / `.onnx` / `.hef` | yolo_train | ai_node_main --yolo |

## 모듈 의존 관계 (위가 아래를 쓴다)

```
integration_test ─┬─ recipe_cli ── recipe ──┬─ control ── optics
                  │                         ├─ ph_control
                  └─ experiment ── nodes ───┼─ hardware, process(precip, ph_control), vision, loadcell
ai_node_main ── camera, control/recipe, yolo_infer, anomaly, zmq_bridge
io_node_main ── nodes(IONode), daqhats_hal(loadcell), zmq_bridge
yolo_train ── vision(CLASSES), experiment(gen)
anomaly ── experiment(gen)
```
