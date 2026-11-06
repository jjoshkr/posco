# 노드 간 프로토콜 (AI 노드 ↔ I/O 노드)

전송: ZeroMQ. AI → I/O 는 PUSH/PULL(기본 tcp://<io-ip>:5555), I/O → AI 는 PUB/SUB(기본 :5556, SUB 는 CONFLATE 로 최신만).
메시지는 JSON 객체 하나. 시뮬레이션에서는 `nodes.Bus` 가 같은 dict 를 메모리로 넘깁니다.

## 명령 (AI → I/O)

| cmd | 필드 | 동작 | 거부 조건 |
|---|---|---|---|
| `heartbeat` | t | 워치독 갱신. 0.2 s 마다 보냄. 1 s(설정값) 끊기면 I/O 노드 SAFE | – |
| `arm` | – | 노드를 RUN 으로. 하트비트 기준시각 갱신 | – |
| `safe` | – | 즉시 SAFE (운전 허가 OFF → 0 mA → OD High → 밸브 OFF) | – |
| `run_enable` | on | 펌프 공통 Pause 접점 | – |
| `valve` | id (XV-101~104), open | 솔레노이드 밸브 | – |
| `stirrer_rpm` | rpm | 교반기 4–20 mA 지령 (0–rpm_max) | – |
| `pump` | id (P-101~103), mA | 아날로그 펌프 연속 운전 | 미무장, 밸브 닫힘, 운전 허가 OFF → `REJECT`/`INTERLOCK` 알람 |
| `dose` | id, mA, strokes | 스트로크 계수 도징. 피드백으로 세어 I/O 노드가 멈춤 | 〃 |
| `pulse_rate` | id (P-104), spm | 펄스 펌프 연속 (최대 max_spm) | 〃, HAL 에 펄스 출력 없음 |
| `pulse_dose` | id, strokes, spm | 펄스 펌프 계수 도징 | 〃 |
| `stop` | id | 아날로그/펄스 펌프 정지 (도징 취소) | – |
| `batch_reset` | – | 스트로크 누적·로드셀 누적 기준을 지금으로 | – |
| `reset_faults` | – | 시뮬레이션 펌프 알람 리셋 (실물은 펌프 본체에서 확인) | – |

명령은 수신 순서대로 한 틱(0.1 s) 안에 적용됩니다. 밸브를 연 뒤 같은 틱에 펌프 명령을 보내도 됩니다(순서 보장).

## 텔레메트리 (I/O → AI, 10 Hz)

```json
{
  "t": 123.4, "mode": "RUN", "run_enable": true,
  "pumps": {"P-101": {"cmd_mA": 12.0, "fb_mA": 12.1, "spm": 100.0, "strokes": 412.3, "dosed_mL": 78.3, "dosing": true}, "...": {}},
  "pulse_pumps": {"P-104": {"spm": 30.0, "strokes": 55, "dosed_mL": 10.45, "dosing": false}},
  "valves": {"XV-101": true, "XV-102": false, "XV-103": false, "XV-104": false},
  "ph": 9.98, "pressure_bar": 0.8, "temp_C": 25.1, "turbidity_ntu": 120.5,
  "tanks": {"P-101": {"mass_g": 1875.2, "flow_mL_min": 2.98, "delivered_mL": 78.1, "valid": true, "low": false, "status": "OK", "ratio": 0.99}},
  "est_volume_mL": 2140.3, "alarms": 2,
  "sim_camera": {"rgb": [90, 143, 123]}
}
```

- `mode`: `SAFE` | `RUN`. `alarms` 는 누적 개수(내용은 I/O 노드 로그/표준출력).
- `tanks` 는 로드셀이 있을 때만, `sim_camera` 는 `io_node_main run --sim --sim-camera` 일 때만.
- `turbidity_ntu` 는 HAL 에 탁도 입력이 있을 때만(없으면 null).

## 알람 (I/O 노드 표준출력·`io_log.csv` 의 alarms 개수)

| 알람 | 뜻 | 자동 조치 |
|---|---|---|
| `REJECT <pump>: node not armed` | arm 전에 펌프 명령 | 무시 |
| `INTERLOCK <pump>: valve closed` / `run_enable off` | 밸브·운전 허가 조건 미충족 | 무시 |
| `NO_STROKE <pump>` | 지령은 있는데 피드백 스트로크 0 (수위·신호·알람) | 없음 (AI 노드 DOSE 타임아웃이 잡음) |
| `RELIEF: discharge pressure` | 토출 막힘(밸브 고착) → 릴리프 순환 | 도징 펌프 전부 정지 |
| `SAFE: watchdog` / `reactor volume limit` / `commanded` | SAFE 전이 사유 | 전체 안전 상태 |
| `EF <pump>` | XTR111 고장 핀 (부하 단선/과열) | 없음 |
| `FLOW_LOW` / `FLOW_HIGH <pump>` | 로드셀 유량이 지령의 60 % 미만 / 150 % 초과가 6 s 이상 | 없음 (알람) |
| `VOLUME_MISMATCH <pump>` | 스트로크 누적 대비 로드셀 누적 70 % 미만 | 없음 |
| `TANK_LOW <pump>` | 로드셀 질량 기준 이하 | 없음 (펌프 수위 입력이 멈춤) |
| `LOADCELL read error` | 리더 예외 | 유량 상태 NO_DATA |
| `PULSE_IGNORED <pump>` | 펄스 펌프가 펄스를 무시 (정지/수위/너무 빠름) | 없음 |

## AI 노드 쪽 상태

`Controller.state`: PLAN → PRIME → DOSE → SETTLE → MEASURE → TRIM → DONE.
`RecipeExecutor.state`: INIT → ARMED → `S<i>:<step>` … → DONE. 중단 사유는 `aborted` 문자열(DOSE short/timeout, PH …, IO node SAFE).
