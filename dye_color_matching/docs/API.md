# API 참조

`tools/gen_api_docs.py` 가 독스트링에서 생성. 자세한 설명은 각 모듈 상단 독스트링과 README 참고.

## cmysim.config

```
장비·공정 사양. 숫자 출처는 README의 '가정과 출처' 표 참고.
```

상수: `DYES`, `PUMP_IDS`, `VALVE_IDS`, `PULSE_PUMP_IDS`, `PULSE_VALVES`

### class PumpSpec

| 필드 | 기본 |
|---|---|
| model | `GMXa 1602` |
| stroke_mL | `0.19` |
| max_spm | `200.0` |
| stroke_length | `1.0` |
| i_start_mA | `4.4` |
| i_full_mA | `19.6` |
| i_fault_mA | `3.8` |
| repro | `0.01` |
| input_ohm | `120.0` |
| fb_option_c | `True` |
| relief_bar | `3.0` |

ProMinent gamma/ X (GMXa 1602 기준) 솔레노이드 다이아프램 정량펌프, Analog(4–20 mA) 모드.

- `__init__(self, model: 'str' = 'GMXa 1602', stroke_mL: 'float' = 0.19, max_spm: 'float' = 200.0, stroke_length: 'float' = 1.0, i_start_mA: 'float' = 4.4, i_full_mA: 'float' = 19.6, i_fault_mA: 'float' = 3.8, repro: 'float' = 0.01, input_ohm: 'float' = 120.0, fb_option_c: 'bool' = True, relief_bar: 'float' = 3.0) -> None`

### class PulsePumpSpec

| 필드 | 기본 |
|---|---|
| model | `GMXa 1602 (pulse)` |
| stroke_mL | `0.19` |
| stroke_length | `1.0` |
| max_spm | `200.0` |
| pulse_ms | `20.0` |
| repro | `0.01` |

gamma/X 외부 접점(펄스) 모드: 무전압 접점 1회 = 스트로크 1회. DIO → 포토커플러 → 펌프 접점 입력.

- `__init__(self, model: 'str' = 'GMXa 1602 (pulse)', stroke_mL: 'float' = 0.19, stroke_length: 'float' = 1.0, max_spm: 'float' = 200.0, pulse_ms: 'float' = 20.0, repro: 'float' = 0.01) -> None`

### class DacChainSpec

| 필드 | 기본 |
|---|---|
| v_full | `5.0` |
| bits | `12` |
| gain_err | `0.0` |
| offset_V | `0.0` |
| mA_per_V | `4.016` |
| i_max_mA | `24.0` |
| calibrated | `False` |

MCC 152 AO(0–5 V, 12 bit) → XTR111(RSET 2.49 kΩ, 4.016 mA/V) → 펌프.

- `__init__(self, v_full: 'float' = 5.0, bits: 'int' = 12, gain_err: 'float' = 0.0, offset_V: 'float' = 0.0, mA_per_V: 'float' = 4.016, i_max_mA: 'float' = 24.0, calibrated: 'bool' = False) -> None`

### class AdcSpec

| 필드 | 기본 |
|---|---|
| v_range | `10.0` |
| bits | `12` |
| noise_V | `0.003` |
| shunt_ohm | `250.0` |

MCC 118: 8ch, ±10 V, 12 bit. 4–20 mA 신호는 250 Ω 션트로 1–5 V.

- `__init__(self, v_range: 'float' = 10.0, bits: 'int' = 12, noise_V: 'float' = 0.003, shunt_ohm: 'float' = 250.0) -> None`

### class TankSpec

| 필드 | 기본 |
|---|---|
| volume_mL | `2000.0` |
| conc_mg_L | `1000.0` |
| low_level_mL | `100.0` |
| role | `dye` |
| conc_mol_L | `0.1` |

TankSpec(volume_mL: 'float' = 2000.0, conc_mg_L: 'float' = 1000.0, low_level_mL: 'float' = 100.0, role: 'str' = 'dye', conc_mol_L: 'float' = 0.1)

- `__init__(self, volume_mL: 'float' = 2000.0, conc_mg_L: 'float' = 1000.0, low_level_mL: 'float' = 100.0, role: 'str' = 'dye', conc_mol_L: 'float' = 0.1) -> None`

### class ReactorSpec

| 필드 | 기본 |
|---|---|
| v_max_mL | `5000.0` |
| heel_mL | `2000.0` |
| rpm | `300.0` |
| rpm_max | `1000.0` |
| mix_K | `3000.0` |
| temp_C | `25.0` |
| ph | `7.0` |
| buffers | `((0.005, 6.35),)` |
| probe_tau_s | `8.0` |
| acid_load_mol_min | `0.0` |
| dye_mg_L | `(0.0, 0.0, 0.0)` |

ReactorSpec(v_max_mL: 'float' = 5000.0, heel_mL: 'float' = 2000.0, rpm: 'float' = 300.0, rpm_max: 'float' = 1000.0, mix_K: 'float' = 3000.0, temp_C: 'float' = 25.0, ph: 'float' = 7.0, buffers: 'tuple' = ((0.005, 6.35),), probe_tau_s: 'float' = 8.0, acid_load_mol_min: 'float' = 0.0, dye_mg_L: 'tuple' = (0.0, 0.0, 0.0))

- `__init__(self, v_max_mL: 'float' = 5000.0, heel_mL: 'float' = 2000.0, rpm: 'float' = 300.0, rpm_max: 'float' = 1000.0, mix_K: 'float' = 3000.0, temp_C: 'float' = 25.0, ph: 'float' = 7.0, buffers: 'tuple' = ((0.005, 6.35),), probe_tau_s: 'float' = 8.0, acid_load_mol_min: 'float' = 0.0, dye_mg_L: 'tuple' = (0.0, 0.0, 0.0)) -> None`

### class CameraSpec

| 필드 | 기본 |
|---|---|
| E | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| I0 | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| gamma | `2.2` |
| glare | `0.015` |
| pixel_noise | `0.02` |
| roi_pixels | `4000` |
| exposure_drift | `0.0` |
| turb_K_ntu | `300.0` |
| fps | `10.0` |

흰 배경 반사형 기준. E에는 L_eff가 이미 포함(단위: 흡광도 / (mg/L)).

- `__init__(self, E: 'np.ndarray' = <factory>, I0: 'np.ndarray' = <factory>, gamma: 'float' = 2.2, glare: 'float' = 0.015, pixel_noise: 'float' = 0.02, roi_pixels: 'int' = 4000, exposure_drift: 'float' = 0.0, turb_K_ntu: 'float' = 300.0, fps: 'float' = 10.0) -> None`

### class NetworkSpec

| 필드 | 기본 |
|---|---|
| telemetry_hz | `10.0` |
| heartbeat_timeout_s | `1.0` |

NetworkSpec(telemetry_hz: 'float' = 10.0, heartbeat_timeout_s: 'float' = 1.0)

- `__init__(self, telemetry_hz: 'float' = 10.0, heartbeat_timeout_s: 'float' = 1.0) -> None`

### class SystemConfig

| 필드 | 기본 |
|---|---|
| pump | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| pulse_pump | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| dac | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| adc | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| tanks | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| reactor | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| camera | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| net | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| dt | `0.1` |
| seed | `0` |
| channel_map | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |

SystemConfig(pump: 'PumpSpec' = <factory>, pulse_pump: 'PulsePumpSpec' = <factory>, dac: 'DacChainSpec' = <factory>, adc: 'AdcSpec' = <factory>, tanks: 'tuple' = <factory>, reactor: 'ReactorSpec' = <factory>, camera: 'CameraSpec' = <factory>, net: 'NetworkSpec' = <factory>, dt: 'float' = 0.1, seed: 'int' = 0, channel_map: 'dict' = <factory>)

- `__init__(self, pump: 'PumpSpec' = <factory>, pulse_pump: 'PulsePumpSpec' = <factory>, dac: 'DacChainSpec' = <factory>, adc: 'AdcSpec' = <factory>, tanks: 'tuple' = <factory>, reactor: 'ReactorSpec' = <factory>, camera: 'CameraSpec' = <factory>, net: 'NetworkSpec' = <factory>, dt: 'float' = 0.1, seed: 'int' = 0, channel_map: 'dict' = <factory>) -> None`

- `pump_max_rate_mL_min(cfg: 'SystemConfig') -> 'float'`

## cmysim.optics

```
RGB 영상 ↔ CMY 농도 (PDF 'CMY 염료 농도의 RGB 영상 기반 정량 보고서' 7장 절차) + 색차.
```

- `conc_to_absorbance(E: 'np.ndarray', c: 'np.ndarray') -> 'np.ndarray'`
- `absorbance_to_linear(A: 'np.ndarray', I0: 'np.ndarray', glare: 'float' = 0.0) -> 'np.ndarray'`
- `linear_to_code(I: 'np.ndarray', gamma: 'float' = 2.2) -> 'np.ndarray'` — 선형 세기(0~1) → 8비트 코드값 (감마 인코딩).
- `code_to_linear(V: 'np.ndarray', gamma: 'float' = 2.2) -> 'np.ndarray'`
- `conc_to_rgb8(E, I0, c, gamma=2.2, glare=0.0) -> 'np.ndarray'`
- `nnls3(E: 'np.ndarray', A: 'np.ndarray') -> 'np.ndarray'` — 3변수 비음수 최소제곱. 지지집합 8개를 전부 시험해 잔차 최소인 비음수 해를 고른다.
- `rgb8_to_conc(E, I0, rgb8, gamma=2.2, glare=0.0) -> 'np.ndarray'` — 단계 1 감마 제거 → 단계 2 흡광도 → 단계 5 비음수 최소제곱.
- `condition_number(E) -> 'float'`
- `srgb8_to_lab(rgb8) -> 'np.ndarray'`
- `delta_e76(rgb_a, rgb_b) -> 'float'`
- `delta_e2000(rgb_a, rgb_b, kL=1.0, kC=1.0, kH=1.0) -> 'float'` — CIEDE2000 (Sharma 2005 구현식).
- `hex_to_rgb8(s: 'str') -> 'np.ndarray'`
- `rgb8_to_hex(rgb8) -> 'str'`

## cmysim.hardware

```
I/O 노드 쪽 장비 모델: MCC 152 → XTR111 → gamma/X 펌프, NC 솔레노이드 밸브, MCC 118/134, 교반기.

실제 보드로 옮길 때는 nodes.HAL 인터페이스(ao_write/dio_write/ai_read/tc_read)만 daqhats로 바꾸면 된다.
```

### class Mcc152AO(spec: 'DacChainSpec', gain_err: 'float | None' = None)

MCC 152 아날로그 출력 1채널: 0–5 V, 12 bit, 이득/오프셋 오차, 전원 투입 시 0 V.

- `__init__(self, spec: 'DacChainSpec', gain_err: 'float | None' = None)`
- `write_volts(self, v: 'float') -> 'float'`

### class Xtr111(spec: 'DacChainSpec')

전압→전류 변환기. OD(output disable) High면 0 mA (페일세이프).

- `__init__(self, spec: 'DacChainSpec')`
- `convert(self, v: 'float') -> 'float'`

### class PumpChannel(spec: 'DacChainSpec', gain_err: 'float' = 0.0)

AO 채널 + XTR111 + 2점 교정값. 코드가 '원하는 mA'를 쓰면 실제 펌프에 걸리는 mA를 돌려준다.

- `__init__(self, spec: 'DacChainSpec', gain_err: 'float' = 0.0)`
- `calibrate_two_point(self, measure_mA, lo=5.0, hi=19.0)` — 실측값(measure_mA: 함수)으로 2점 교정. MCC 152 이득 오차(±1.5 %)를 흡수한다.
- `enable(self, on: 'bool')`
- `set_mA(self, mA: 'float') -> 'float'`

### class PumpState

| 필드 | 기본 |
|---|---|
| spm_actual | `0.0` |
| strokes_total | `0` |
| volume_total_mL | `0.0` |
| fault | `` |
| paused | `True` |
| pressure_bar | `0.0` |
| relief_active | `False` |
| phase | `0.0` |

PumpState(spm_actual: 'float' = 0.0, strokes_total: 'int' = 0, volume_total_mL: 'float' = 0.0, fault: 'str' = '', paused: 'bool' = True, pressure_bar: 'float' = 0.0, relief_active: 'bool' = False, phase: 'float' = 0.0)

- `__init__(self, spm_actual: 'float' = 0.0, strokes_total: 'int' = 0, volume_total_mL: 'float' = 0.0, fault: 'str' = '', paused: 'bool' = True, pressure_bar: 'float' = 0.0, relief_active: 'bool' = False, phase: 'float' = 0.0) -> None`

### class GammaXPump(spec: 'PumpSpec', rng: 'np.random.Generator', pump_id: 'str')

gamma/X Analog 모드. 전류 → 스트로크/분, 1 스트로크 = 고정 부피 슬러그.

- `__init__(self, spec: 'PumpSpec', rng: 'np.random.Generator', pump_id: 'str')`
- `feedback_mA(self) -> 'float'` — 옵션 C: 실제 스트로크 속도를 4–20 mA로 (정지·알람 시 4 mA).
- `reset_fault(self)`
- `spm_from_mA(self, mA: 'float') -> 'float'`
- `step(self, mA: 'float', dt: 'float', outlet_open: 'bool', deliver) -> 'None'` — deliver(volume_mL)는 밸브가 열렸을 때 반응기로 들어가는 부피를 받는 콜백.

### class SolenoidValveNC(valve_id: 'str', open_time_s: 'float' = 0.05)

2-way 상시닫힘. 전기가 끊기면 닫힘. 고장 주입: stuck_closed.

- `__init__(self, valve_id: 'str', open_time_s: 'float' = 0.05)`
- `energize(self, on: 'bool')`

### class Mcc118(spec: 'AdcSpec', rng: 'np.random.Generator')

±10 V 12 bit ADC. 4–20 mA는 250 Ω 션트로 1–5 V.

- `__init__(self, spec: 'AdcSpec', rng: 'np.random.Generator')`
- `read_mA_via_shunt(self, mA_true: 'float') -> 'float'`
- `read_volts(self, v_true: 'float') -> 'float'`

### class Mcc134(rng: 'np.random.Generator', noise_C: 'float' = 0.2)

- `__init__(self, rng: 'np.random.Generator', noise_C: 'float' = 0.2)`
- `read_C(self, t_true: 'float') -> 'float'`

### class Stirrer(rpm_max: 'float', tau_s: 'float' = 2.0)

교반기 외부 입력 4–20 mA ↔ 0–rpm_max (모델 확인 전 가정). 1차 지연 τ = 2 s.

- `__init__(self, rpm_max: 'float', tau_s: 'float' = 2.0)`
- `step(self, mA: 'float', dt: 'float')`

### class PulsePump(spec: 'PulsePumpSpec', rng: 'np.random.Generator', pump_id: 'str')

접점(펄스) 모드 펌프: pulse() 한 번 = 스트로크 한 번 (운전 허가·수위 OK 일 때).

- `__init__(self, spec: 'PulsePumpSpec', rng: 'np.random.Generator', pump_id: 'str')`
- `pulse(self, t: 'float', outlet_open: 'bool', deliver) -> 'bool'`

## cmysim.process

```
공정 모델: 스톡 탱크, 반응기 물질수지, 교반 혼합 지연.
```

상수: `DYES`

### class StockTank(spec: 'TankSpec', dye: 'str')

- `__init__(self, spec: 'TankSpec', dye: 'str')`
- `draw(self, vol_mL: 'float') -> 'float'` — 빨아낸 부피를 돌려준다 (탱크가 비면 0).

### class Reactor(spec: 'ReactorSpec', rng=None)

완전혼합 반투입(semi-batch) 반응기.

- `__init__(self, spec: 'ReactorSpec', rng=None)`
- `add(self, dye_idx: 'int', vol_mL: 'float', conc_mg_L: 'float')`
- `add_acid_solution(self, vol_mL: 'float', conc_mol_L: 'float')` — 산(HCl 등) 투입 (양방향 pH 제어의 산 펌프).
- `add_base(self, vol_mL: 'float', conc_mol_L: 'float')` — NaOH 투입 (pH 제어용 펌프). 염료 질량은 그대로, 부피만 늘고 염기가 더해진다.
- `add_feed(self, role: 'str', vol_mL: 'float', conc_mol_L: 'float')` — 공침 피드: cacl2 | na2co3 | citrate (각 펌프는 별도 투입구 — 프리믹싱 금지).
- `final_volume_for(self, c_target: 'np.ndarray', c_stock: 'np.ndarray') -> 'float'` — 목표 농도 c_target 을 heel 에 스톡으로 맞출 때의 최종 부피. V_f = V_heel / (1 − Σ c_j/c_s,j).
- `mixing_time_s(self) -> 'float'`
- `step(self, dt: 'float')`

- `dose_volumes(V_heel_mL: 'float', c_target: 'np.ndarray', c_stock: 'np.ndarray') -> 'np.ndarray'` — 세 염료를 동시에 넣을 때 각 투입 부피 V_j = c_j · V_f / c_s,j (대화의 V_dose 식을 3성분으로 확장).

## cmysim.precip

```
Tier C 공침 아날로그: CaCl₂ + Na₂CO₃ → CaCO₃ (+염료 공동 담지) 의 단순 모델 (통합 시험용, 정량 모델 아님).

- 화학종: Ca²⁺, 총 탄산(C_T), 고체 CaCO₃, 구연산(착화제, 침전 억제)
- 탄산 평형: pKa1 6.35, pKa2 10.33 → 유리 CO₃²⁻ 분율 α₂(pH)
- 과포화도 S = [Ca²⁺][CO₃²⁻] / Ksp (Ksp 3.3e-9, 칼사이트). S > 1 이면 침전 r = k·V·(√S − 1)² [mol/s], 구연산은 k 를 줄임
- 탁도 NTU ≈ k_turb × 고체 농도[g/L]. 입경 d50 은 자리표시자 proxy (실제 답은 현미경 + YOLO)
- pH 결합: Na₂CO₃ 투입 = 강양이온 2n + 탄산 완충 n (두 pKa 를 독립 단양성자산으로 근사), CaCl₂ 투입 = 중성(강양이온 2n + 강음이온 2n),
  CaCO₃ 침전 = Ca²⁺ 2m 제거 + 탄산 m 제거 → pH 가 내려간다 (실제 거동과 정성적으로 같음)
```

상수: `KSP`, `PKA1`, `PKA2`, `MW_CACO3`

### class PrecipSpec

| 필드 | 기본 |
|---|---|
| k_precip | `2e-06` |
| k_turb_ntu_per_g_L | `400.0` |
| citrate_inhibit | `50.0` |

PrecipSpec(k_precip: 'float' = 2e-06, k_turb_ntu_per_g_L: 'float' = 400.0, citrate_inhibit: 'float' = 50.0)

- `__init__(self, k_precip: 'float' = 2e-06, k_turb_ntu_per_g_L: 'float' = 400.0, citrate_inhibit: 'float' = 50.0) -> None`

### class PrecipModel(ph_model, spec: 'PrecipSpec | None' = None)

- `__init__(self, ph_model, spec: 'PrecipSpec | None' = None)`
- `add_cacl2(self, vol_mL: 'float', conc_mol_L: 'float')`
- `add_citrate(self, vol_mL: 'float', conc_mol_L: 'float')`
- `add_na2co3(self, vol_mL: 'float', conc_mol_L: 'float')`
- `step(self, dt: 'float', pH: 'float')`

## cmysim.ph_control

```
pH 제어기 (NaOH 도징) — Tier B(pH 유도 침전) · Tier C(공침, pH 9~11 유지) 용.

구성
  PHModel      : 반응기 산·염기 평형 (강염기 − 강산 + 약산 완충계) 으로 pH 계산. 금속염 피드 등 '산 부하' 를 넣을 수 있다.
  PHProbe      : 혼합 지연 + 프로브 1차 지연(τ≈8 s) + 잡음 + 드리프트. 4–20 mA 트랜스미터는 SimHAL 쪽에서 양자화.
  PHController : 한쪽(염기만) PID. 미분은 측정값에 필터, 적분 안티와인드업(백캘큘레이션), 불감대, 피드포워드(산 부하 × 화학량론),
                 안전(상한/하한 pH, 배치 최대 NaOH 부피, 프로브 고착 감지). 출력 = NaOH 유량 [mL/min] → 펌프 mA.
  relay 자동동조: Åström–Hägglund 릴레이 → Ku, Tu → Tyreus–Luyben PI (완충 용량을 모르는 새 배치에서 첫 동조).
  titrate      : 설정값 램프 (pH 10 → 3 스윕, Tier B 침전 개시 pH 찾기).

하드웨어 매핑
  NaOH 는 펌프 3대 중 하나(기본 P-103)에 배정한다. 스톡 탱크 역할을 TankSpec.role = "naoh", conc_mol_L 로 둔다.
  pH 는 I/O 노드 텔레메트리 'ph' (MCC 118 CH0, 절연형 트랜스미터 4–20 mA ↔ pH 0–14) 로 들어온다.
  제어기는 AI 노드(레시피 스텝 ph_control) 에서 돌고 I/O 노드에 'pump' 명령(연속 mA)을 보낸다. 인터록은 I/O 노드가 지킨다.

  python -m cmysim.ph_control sim      --setpoint 10.5 --load 0.001 --plot ph.png     단독 폐루프 시뮬레이션
  python -m cmysim.ph_control autotune --setpoint 10.5 --load 0.001                   릴레이 동조 → Kp, Ki 추천
  레시피:  - {step: ph_control, pump: P-103, setpoint: 10.5, seconds: 300, Kp: 6, Ki: 0.15}
```

상수: `KW`

### class BufferSpecies

| 필드 | 기본 |
|---|---|
| conc_mol_L | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| pKa | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |

BufferSpecies(conc_mol_L: 'float', pKa: 'float')

- `__init__(self, conc_mol_L: 'float', pKa: 'float') -> None`

### class PHModel(V_L: 'float', pH0: 'float' = 7.0, buffers=None)

전하 균형: (B − A)/V + [H+] = Kw/[H+] + Σ C_i·Ka_i/(Ka_i + [H+])  → [H+] 이분법.

- `__init__(self, V_L: 'float', pH0: 'float' = 7.0, buffers=None)`
- `add_acid(self, mol: 'float')`
- `add_base(self, vol_mL: 'float', conc_mol_L: 'float')`
- `add_water(self, vol_mL: 'float')`
- `buffer_capacity(self) -> 'float'` — β = dB/dpH [mol/L/pH] 수치 미분.
- `pH(self, B=None) -> 'float'`

### class PHProbe(tau_s=8.0, noise=0.01, drift_per_h=0.0, rng=None)

- `__init__(self, tau_s=8.0, noise=0.01, drift_per_h=0.0, rng=None)`
- `step(self, ph_true: 'float', dt: 'float') -> 'float'`

### class PHGains

| 필드 | 기본 |
|---|---|
| Kp | `10.0` |
| Ki | `0.02` |
| Kd | `0.0` |
| d_filter_s | `5.0` |
| deadband | `0.02` |
| out_max | `38.0` |
| out_min | `0.0` |
| ff_gain | `0.0` |
| beta0_mol_L_pH | `0.0005` |
| lag_s | `20.0` |
| horizon_s | `30.0` |
| cap_enabled | `True` |
| i_band | `0.5` |
| rate_governor | `True` |

PHGains(Kp: 'float' = 10.0, Ki: 'float' = 0.02, Kd: 'float' = 0.0, d_filter_s: 'float' = 5.0, deadband: 'float' = 0.02, out_max: 'float' = 38.0, out_min: 'float' = 0.0, ff_gain: 'float' = 0.0, beta0_mol_L_pH: 'float' = 0.0005, lag_s: 'float' = 20.0, horizon_s: 'float' = 30.0, cap_enabled: 'bool' = True, i_band: 'float' = 0.5, rate_governor: 'bool' = True)

- `__init__(self, Kp: 'float' = 10.0, Ki: 'float' = 0.02, Kd: 'float' = 0.0, d_filter_s: 'float' = 5.0, deadband: 'float' = 0.02, out_max: 'float' = 38.0, out_min: 'float' = 0.0, ff_gain: 'float' = 0.0, beta0_mol_L_pH: 'float' = 0.0005, lag_s: 'float' = 20.0, horizon_s: 'float' = 30.0, cap_enabled: 'bool' = True, i_band: 'float' = 0.5, rate_governor: 'bool' = True) -> None`

### class PHSafety

| 필드 | 기본 |
|---|---|
| ph_max | `12.0` |
| ph_min | `2.0` |
| max_total_mL | `500.0` |
| max_acid_mL | `500.0` |
| min_switch_s | `10.0` |
| stuck_s | `60.0` |
| stuck_dpH | `0.05` |

PHSafety(ph_max: 'float' = 12.0, ph_min: 'float' = 2.0, max_total_mL: 'float' = 500.0, max_acid_mL: 'float' = 500.0, min_switch_s: 'float' = 10.0, stuck_s: 'float' = 60.0, stuck_dpH: 'float' = 0.05)

- `__init__(self, ph_max: 'float' = 12.0, ph_min: 'float' = 2.0, max_total_mL: 'float' = 500.0, max_acid_mL: 'float' = 500.0, min_switch_s: 'float' = 10.0, stuck_s: 'float' = 60.0, stuck_dpH: 'float' = 0.05) -> None`

### class PHController(setpoint: 'float', gains: 'PHGains | None' = None, safety: 'PHSafety | None' = None, naoh_mol_L: 'float' = 0.1, mode: 'str' = 'pid', V_L: 'float' = 2.0, acid_mol_L: 'float | None' = None)

- `__init__(self, setpoint: 'float', gains: 'PHGains | None' = None, safety: 'PHSafety | None' = None, naoh_mol_L: 'float' = 0.1, mode: 'str' = 'pid', V_L: 'float' = 2.0, acid_mol_L: 'float | None' = None)` — acid_mol_L 을 주면 양방향: update() 가 음수(산 유량 mL/min)도 낸다.
- `metrics(self) -> 'dict'`
- `relay_result(self) -> 'dict | None'` — 릴레이 진동 2주기 이상이면 Ku, Tu, 추천 PI (Tyreus–Luyben) 를 돌려준다.
- `set_titration(self, start_pH, end_pH, rate_pH_per_min)`
- `update(self, t: 'float', meas: 'float') -> 'float'` — 측정 pH → NaOH 유량 [mL/min] (한쪽 제어: 0 이상).

- `flow_to_mA(flow_mL_min: 'float', stroke_mL=0.19, stroke_len=1.0, max_spm=200.0, i_start=4.4, i_full=19.6) -> 'float'`
- `simulate(setpoint=10.5, pH0=7.0, V_L=2.0, naoh_mol_L=0.1, load_mol_min=0.0, load_start_s=0.0, duration=600.0, dt=0.5, gains=None, mode='pid', rpm=300.0, probe_tau=8.0, buffers=None, seed=0, titrate=None, relay_d=2.0, acid_mol_L=None, sp_steps=(), base_load_mol_min=0.0, base_load_start_s=0.0)` — acid_mol_L 을 주면 양방향. sp_steps=((t, sp), ...) 로 설정값 변경, base_load 는 염기성 외란(pH 를 올리는 피드).
- `main(argv=None)`

## cmysim.vision

```
AI 노드 쪽 카메라 모델 (RealSense D4xx RGB 대역) + 데이터셋 기록기.

- 프레임: 반응기 ROI를 합성. 색은 optics 모델, 여기에 픽셀 잡음·비네팅·기포 반점을 얹는다.
- 라벨: 프레임마다 JSON(진짜 농도, 추정 농도, ΔE, 목표) + YOLO txt(클래스 0=on_target, 1=off_target, 액체 ROI 박스).
  나중에 진짜 RealSense 프레임으로 바꿔 끼워도 라벨 형식은 같다.
```

상수: `CLASSES`

### class SyntheticCamera(spec: 'CameraSpec', rng: 'np.random.Generator', size=(96, 128))

- `__init__(self, spec: 'CameraSpec', rng: 'np.random.Generator', size=(96, 128))`
- `frame(self, c_obs: 'np.ndarray', bubbles: 'int' = 0) -> 'np.ndarray'` — H×W×3 uint8 합성 프레임. 기포(밝은 원) 위치는 self.last_bubbles 에 (x, y, r) 로 남겨 YOLO 라벨에 쓴다.
- `linear_mean(self, c_obs: 'np.ndarray') -> 'np.ndarray'`
- `roi_rgb8(self, c_obs: 'np.ndarray') -> 'np.ndarray'` — ROI 평균 RGB 코드값 (픽셀 잡음은 √N 으로 줄어든다).

### class DatasetRecorder(out_dir, cam, every_s: 'float' = 2.0, de_match: 'float' = 2.0, roi=None)

YOLO 학습용 프레임/라벨 기록.

- `__init__(self, out_dir, cam, every_s: 'float' = 2.0, de_match: 'float' = 2.0, roi=None)`
- `close(self)`
- `maybe_record(self, t: 'float', c_true, c_hat, c_obs, rgb8, target_rgb8, de, run_id='run', image=None)` — image 를 주면(실제 카메라 프레임) 그대로 저장하고, 없으면 합성 프레임을 만든다. c_true 는 실물에서는 None.

- `write_png(path, img: 'np.ndarray')` — 외부 라이브러리 없이 8비트 RGB PNG 저장.

## cmysim.camera

```
실제 카메라 (AI 노드, Raspberry Pi 5).

세 가지 백엔드가 같은 인터페이스를 가진다.
  RealSenseCamera : Intel RealSense D4xx 컬러 스트림 (pyrealsense2)
  Picamera2Camera : 라즈베리파이 전용 카메라 (picamera2)
  OpenCVCamera    : /dev/videoN (USB 웹캠, 또는 RealSense 를 UVC 로 열 때)

공통
  read()            → H×W×3 uint8 RGB 프레임
  roi_rgb8(frame)   → ROI 평균 RGB 코드값 (3,)            … ΔE 계산·표시용
  roi_absorbance()  → ROI 평균 흡광도 A (3,)              … 농도 역산용
                      기준 영상(물만) 이 있으면 픽셀별 A 를 구해 평균 (PDF 8장: 광원 불균일 대책)
노출·게인·화이트밸런스는 반드시 수동 고정 (PDF 8장). 설정은 camera.json 에 둔다.
```

### class CameraSettings

| 필드 | 기본 |
|---|---|
| kind | `realsense` |
| width | `640` |
| height | `480` |
| fps | `30` |
| exposure | `100.0` |
| gain | `16.0` |
| white_balance | `4600.0` |
| device | `` |
| roi | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| gamma | `2.2` |
| warmup_frames | `15` |
| ref_path | `camera_ref.npy` |
| calib_path | `calibration.json` |

CameraSettings(kind: 'str' = 'realsense', width: 'int' = 640, height: 'int' = 480, fps: 'int' = 30, exposure: 'float' = 100.0, gain: 'float' = 16.0, white_balance: 'float' = 4600.0, device: 'str' = '', roi: 'list' = <factory>, gamma: 'float' = 2.2, warmup_frames: 'int' = 15, ref_path: 'str' = 'camera_ref.npy', calib_path: 'str' = 'calibration.json')

- `__init__(self, kind: 'str' = 'realsense', width: 'int' = 640, height: 'int' = 480, fps: 'int' = 30, exposure: 'float' = 100.0, gain: 'float' = 16.0, white_balance: 'float' = 4600.0, device: 'str' = '', roi: 'list' = <factory>, gamma: 'float' = 2.2, warmup_frames: 'int' = 15, ref_path: 'str' = 'camera_ref.npy', calib_path: 'str' = 'calibration.json') -> None`
- `save(self, path='camera.json')`

### class CameraBase(s: 'CameraSettings')

- `__init__(self, s: 'CameraSettings')`
- `average(self, n=10, delay=0.03)` — n 프레임의 (ROI 평균 RGB, 흡광도) 평균.
- `capture_reference(self, n=30, delay=0.05) -> 'np.ndarray'` — 물만 채운 상태에서 n 프레임 평균 → 픽셀별 기준 선형 세기 저장.
- `frame(self, *_a, **_k) -> 'np.ndarray'`
- `read(self) -> 'np.ndarray'`
- `roi_absorbance(self, frame=None, I0_vec=None) -> 'np.ndarray'` — 픽셀별 기준 영상이 있으면 A = mean(−log10(I/I_ref)), 없으면 ROI 평균과 I0 벡터로.
- `roi_crop(self, frame=None) -> 'np.ndarray'`
- `roi_linear(self, frame=None) -> 'np.ndarray'`
- `roi_rgb8(self, frame=None) -> 'np.ndarray'`
- `start(self)`
- `stop(self)`

### class RealSenseCamera(s: 'CameraSettings')

- `info(self) -> 'dict'`
- `start(self)`
- `stop(self)`

### class Picamera2Camera(s: 'CameraSettings')

- `start(self)`
- `stop(self)`

### class OpenCVCamera(s: 'CameraSettings')

- `start(self)`
- `stop(self)`

### class FakeCamera(s: 'CameraSettings')

카메라 없이 camera_tools / ai_node_main 흐름을 돌려 보기 위한 백엔드.
device 필드에 'C,M,Y' mg/L 를 적으면 그 농도의 액체를 보는 것처럼 프레임을 만든다 (기본 0,0,0 = 물).
환경변수 CMYSIM_FAKE_CONC 가 있으면 그 값이 우선한다 (실행 중 바꿔 가며 시험).

- `start(self)`
- `stop(self)`

### class TelemetryCamera(s: 'CameraSettings')

카메라 대신 I/O 노드(--sim --sim-camera) 텔레메트리의 'sim_camera' 관측을 쓴다. 2프로세스 통합시험용.
AI 노드가 start() 뒤에 .bus 를 붙여 준다.

- `roi_absorbance(self, frame=None, I0_vec=None)`
- `roi_rgb8(self, frame=None)`
- `start(self)`
- `stop(self)`

### class Calibration

| 필드 | 기본 |
|---|---|
| E | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| I0 | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| gamma | `2.2` |
| glare | `0.0` |
| cond | `0.0` |
| samples | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| note | `` |

Calibration(E: 'list', I0: 'list', gamma: 'float' = 2.2, glare: 'float' = 0.0, cond: 'float' = 0.0, samples: 'list' = <factory>, note: 'str' = '')

- `__init__(self, E: 'list', I0: 'list', gamma: 'float' = 2.2, glare: 'float' = 0.0, cond: 'float' = 0.0, samples: 'list' = <factory>, note: 'str' = '') -> None`
- `apply_to(self, cfg)` — SystemConfig.camera 에 실측값 주입 → Controller/계획이 그대로 쓴다.
- `save(self, path)`

- `code_to_linear(V, gamma)`
- `open_camera(s: 'CameraSettings') -> 'CameraBase'`
- `fit_E(samples: 'list', dyes=('C', 'M', 'Y')) -> 'tuple[np.ndarray, dict]'` — 단일 염료 시료들로 E 의 열을 구한다 (PDF 7장 단계 4): 염료 j 만 있을 때 A_k = E_kj · c_j → 원점 통과 기울기.

## cmysim.loadcell

```
로드셀(HX711) 중량 유량 계측 — 스톡병마다 로드셀을 두고 무게 감소율로 실제 유량을 잰다.

왜: 정량펌프는 개루프라 튜브 마모·공기 유입·체크밸브 역류가 생기면 스트로크는 세는데 액은 안 나간다.
    질량유량(로드셀) 과 지령 유량·스트로크 계수를 비교하면 그 차이가 곧 고장 신호이자 이상탐지의 정답 라벨이 된다.

연결 (권장 → 차선)
  serial : Arduino/ESP32 가 HX711 여러 개를 읽어 USB 시리얼로 "ms,raw0,raw1,raw2" 를 보낸다 (firmware/hx711_bridge.ino).
           HX711 은 비트뱅 타이밍이 까다롭고 I/O 노드의 GPIO 는 MCC HAT 아래에 묻혀 있어 이 방식이 가장 안정적이다.
  gpio   : Pi GPIO 에 직접 (lgpio, Pi 5). HAT 이 안 쓰는 GPIO(5, 6, 22~25, 27) 를 스태킹 헤더로 빼야 한다.
  sim    : 시뮬레이터 탱크에서 가짜 raw 값 생성.

처리
  raw → (raw − tare) / counts_per_g = 질량[g] → 밀도로 mL → 이동창 최소제곱 기울기 = 유량[mL/min]
  병을 건드리면(급격한 점프) 그 창은 무효 처리하고 다시 쌓는다.
  FlowCheck: 지령 유량·스트로크 부피와 비교해 FLOW_LOW(공기/마모/정지), TANK_LOW, DISTURBED 판정.

  python -m cmysim.loadcell read   --backend serial --port /dev/ttyUSB0
  python -m cmysim.loadcell tare   --ch 0                      빈 병(또는 현재 상태)을 0 으로
  python -m cmysim.loadcell calib  --ch 0 --mass 500           기준 분동 500 g 올리고 실행 → counts_per_g
  python -m cmysim.loadcell flow   --backend serial            질량·유량 실시간 표시
  python -m cmysim.loadcell demo                               시뮬레이션 데모 (펌프 20 mL/min, 50 s 에 공기 유입)
```

### class LoadCellConfig

| 필드 | 기본 |
|---|---|
| backend | `serial` |
| port | `/dev/ttyUSB0` |
| baud | `115200` |
| gpio_pins | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| channels | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| tare | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| counts_per_g | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| density_g_mL | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| rate_hz | `10.0` |
| window_s | `10.0` |
| jump_g | `3.0` |
| settle_s | `3.0` |
| low_mass_g | `100.0` |

LoadCellConfig(backend: 'str' = 'serial', port: 'str' = '/dev/ttyUSB0', baud: 'int' = 115200, gpio_pins: 'list' = <factory>, channels: 'list' = <factory>, tare: 'list' = <factory>, counts_per_g: 'list' = <factory>, density_g_mL: 'list' = <factory>, rate_hz: 'float' = 10.0, window_s: 'float' = 10.0, jump_g: 'float' = 3.0, settle_s: 'float' = 3.0, low_mass_g: 'float' = 100.0)

- `__init__(self, backend: 'str' = 'serial', port: 'str' = '/dev/ttyUSB0', baud: 'int' = 115200, gpio_pins: 'list' = <factory>, channels: 'list' = <factory>, tare: 'list' = <factory>, counts_per_g: 'list' = <factory>, density_g_mL: 'list' = <factory>, rate_hz: 'float' = 10.0, window_s: 'float' = 10.0, jump_g: 'float' = 3.0, settle_s: 'float' = 3.0, low_mass_g: 'float' = 100.0) -> None`
- `save(self, path='loadcell.json')`

### class ReaderBase(cfg: 'LoadCellConfig')

- `__init__(self, cfg: 'LoadCellConfig')`
- `average_raw(self, n=20, delay=None) -> 'list[float]'`
- `read_g(self) -> 'list[float | None]'`
- `read_raw(self) -> 'list[float | None]'`
- `start(self)`
- `stop(self)`

### class SerialHX711(cfg: 'LoadCellConfig')

firmware/hx711_bridge.ino 가 보내는 'ms,raw0,raw1,...' 줄을 읽는다. 마지막 값을 보관.

- `read_raw(self)`
- `start(self)`
- `stop(self)`

### class HX711GPIO(cfg: 'LoadCellConfig')

Pi 5 GPIO 직결 (lgpio). 채널 A, 128 배. SCK High 가 60 µs 를 넘으면 칩이 슬립하므로 가능한 한 짧게.

- `read_raw(self)`
- `start(self)`
- `stop(self)`

### class SimLoadCell(cfg: 'LoadCellConfig', tanks, rng, noise_g=0.05, drift_g_per_h=2.0, bottle_g=(350.0, 350.0, 350.0))

시뮬레이터 탱크 질량 → raw counts. 잡음·느린 드리프트·병 건드림 주입 가능.

- `__init__(self, cfg: 'LoadCellConfig', tanks, rng, noise_g=0.05, drift_g_per_h=2.0, bottle_g=(350.0, 350.0, 350.0))`
- `read_raw(self)`
- `step(self, dt)`

### class FlowEstimator(cfg: 'LoadCellConfig', i: 'int')

채널 하나: (t, g) 이동창 → 기울기(유량), 누적 투입, 무효(건드림) 판정.

- `__init__(self, cfg: 'LoadCellConfig', i: 'int')`
- `push(self, t: 'float', g: 'float | None') -> 'dict'`
- `reset_batch(self)`
- `state(self, t)`

### class FlowCheck(ratio_low=0.6, ratio_high=1.5, min_expected_mL_min=2.0, hold_s=6.0)

펌프 지령(기대 유량)·스트로크 부피 vs 로드셀. 상태: OK / FLOW_LOW / FLOW_HIGH / TANK_LOW / DISTURBED / NO_DATA.

- `__init__(self, ratio_low=0.6, ratio_high=1.5, min_expected_mL_min=2.0, hold_s=6.0)`
- `check(self, t, pid, expected_mL_min, est_state: 'dict', stroke_mL=None) -> 'tuple[str, float]'`

- `open_reader(cfg: 'LoadCellConfig', **kw) -> 'ReaderBase'`
- `main(argv=None)`
- `demo()` — 시뮬레이션: 펌프 20 mL/min 으로 투입, 50 s 에 공기 유입(토출 절반), 80 s 에 병을 건드림.

## cmysim.nodes

```
두 노드 구조.

  AI 노드 (Pi 5 + AI HAT+, RealSense)      I/O 노드 (Pi 5 + MCC 118 + MCC 134 + MCC 152 ×2)
  ───────────────────────────────            ─────────────────────────────────────────────
  카메라 → 농도 추정 → 레시피/제어   ──cmd──▶  명령 수신, 인터록, 펌프/밸브 구동, 스트로크 계수
  하트비트 0.2 s                     ◀─tele──  10 Hz 텔레메트리 (펌프 피드백, pH, 압력, 온도)
                                               하트비트 1 s 끊기면 SAFE

시뮬레이션에서는 Bus 가 ZeroMQ 를 대신한다. 메시지는 전부 JSON 직렬화 가능한 dict 라서
zmq_bridge.py 처럼 PUB/SUB + PUSH/PULL 로 그대로 옮길 수 있다.
HAL 은 '엔지니어링 단위' 인터페이스다. SimHAL 은 모델에, daqhats_hal.DaqHatsHAL 은 실제 보드에 붙는다.
```

상수: `PUMP_IDS`, `VALVE_IDS`, `PULSE_PUMP_IDS`, `PULSE_VALVES`

### class Bus()

- `__init__(self)`
- `drain_cmds(self)`
- `latest(self)`
- `publish(self, msg: 'dict')`
- `send_cmd(self, msg: 'dict')`

### class HAL()

I/O 노드가 쓰는 하드웨어 추상층. 실제 보드에서는 DaqHatsHAL 로 교체.

- `pulse(self, pid: 'str') -> 'bool'`
- `pump_enable(self, pid: 'str', on: 'bool')`
- `pump_set_mA(self, pid: 'str', mA: 'float')`
- `read_feedback_mA(self, pid: 'str') -> 'float'`
- `read_ph(self) -> 'float'`
- `read_pressure_bar(self) -> 'float'`
- `read_temp_C(self) -> 'float'`
- `read_turbidity_ntu(self) -> 'float'`
- `run_enable(self, on: 'bool')`
- `step(self, dt: 'float')`
- `stirrer_set_mA(self, mA: 'float')`
- `valve(self, vid: 'str', on: 'bool')`

### class SimPlant(cfg: 'SystemConfig')

공정 + 장비 모델 전체 (시뮬레이션 전용). AI 노드의 카메라도 여기 반응기를 본다.

- `__init__(self, cfg: 'SystemConfig')`
- `step(self, dt: 'float')`

### class SimHAL(plant: 'SimPlant')

- `__init__(self, plant: 'SimPlant')`
- `pulse(self, pid)` — 접점 펄스 1회 → 펌프 스트로크 1회 (밸브 열림·운전 허가·수위 OK 일 때 반응기로).
- `pump_enable(self, pid, on)`
- `pump_set_mA(self, pid, mA)`
- `read_feedback_mA(self, pid)`
- `read_ph(self)`
- `read_pressure_bar(self)`
- `read_tank_mass_g(self)`
- `read_temp_C(self)`
- `read_turbidity_ntu(self)`
- `run_enable(self, on)`
- `step(self, dt)`
- `stirrer_set_mA(self, mA)`
- `valve(self, vid, on)`

### class IONode(cfg: 'SystemConfig', hal: 'HAL', bus: 'Bus')

실시간 책임: 명령 적용, 인터록, 스트로크 계수 도징, 워치독, 텔레메트리.

- `__init__(self, cfg: 'SystemConfig', hal: 'HAL', bus: 'Bus')`
- `alarm(self, msg)`
- `handle(self, m: 'dict')`
- `safe(self, why: 'str')`
- `tick(self, t: 'float')`

### class AINode(cfg: 'SystemConfig', bus: 'Bus', camera: 'SyntheticCamera', controller, heartbeat_s=0.2)

비전(카메라 → 농도) + 제어기. 실시간 구동은 안 하고 I/O 노드에 명령만 보낸다.

- `__init__(self, cfg: 'SystemConfig', bus: 'Bus', camera: 'SyntheticCamera', controller, heartbeat_s=0.2)`
- `tick(self, t: 'float', c_obs_true_for_camera: 'np.ndarray')` — c_obs_true_for_camera 는 시뮬레이션에서만 넘긴다 (실제는 RealSense 프레임).

## cmysim.daqhats_hal

```
I/O 노드 실제 하드웨어 층: Raspberry Pi 5 + MCC 152 ×2 + MCC 118 + MCC 134 (daqhats 라이브러리).

보드와 핀 배정 (대화에서 확정한 것, io_node.json 으로 바꿀 수 있음)

  MCC 152 #1 (주소 0)                       MCC 152 #2 (주소 1)
    AO0 → XTR111 A → P-101 (4–20 mA)          AO0 → XTR111 A → P-103
    AO1 → XTR111 B → P-102                    AO1 → XTR111 B → 교반기 지령
    DIO0 OD(A)  출력 차단, High=꺼짐          DIO0 OD(A)
    DIO1 EF(A)  고장 감지 입력, Low=고장      DIO1 EF(A)
    DIO2 OD(B)                                DIO2 OD(B)
    DIO3 EF(B)                                DIO3 EF(B)
    DIO4 XV-101 솔레노이드 (포토커플러)       DIO4 XV-103
    DIO5 XV-102                               DIO5 RUN_ENABLE (펌프 3대 Pause 접점 공통)
    DIO6, DIO7 예비                           DIO6 P-104 펄스(접점, 산 펌프)  DIO7 XV-104
  MCC 118 (주소 2)  CH0 pH(4–20 mA, 250 Ω)  CH1~3 펌프 옵션 C 피드백  CH4 압력 트랜스미터
  MCC 134 (주소 3)  CH0 열전대 K (반응기 온도)

안전 원칙
  - 부팅 직후 MCC 152 DIO 는 입력(풀업) → OD High → XTR111 출력 0 mA. 이 코드는 그 상태를 유지한 채 시작하고
    AO 를 0 V 로 쓴 뒤에만 OD 를 제어 출력으로 바꾼다.
  - safe(): RUN_ENABLE OFF → AO 0 V → OD High → 밸브 OFF 순서. 종료(예외 포함) 시 항상 호출.
  - 24 V 전원은 Pi 와 보드가 켜진 뒤에 넣는다 (데이터시트 검토 결과).
```

### class IOConfig

| 필드 | 기본 |
|---|---|
| addresses | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| ao | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| od_pin | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| ef_pin | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| dio | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| pulse_ms | `20.0` |
| ai | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| tc | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| mA_per_V | `4.016` |
| ao_max_V | `5.0` |
| od_disable_level | `1` |
| valve_active_high | `True` |
| run_enable_active_high | `True` |
| ai_average | `4` |
| cal | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| loadcell | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |

IOConfig(addresses: 'dict' = <factory>, ao: 'dict' = <factory>, od_pin: 'dict' = <factory>, ef_pin: 'dict' = <factory>, dio: 'dict' = <factory>, pulse_ms: 'float' = 20.0, ai: 'dict' = <factory>, tc: 'dict' = <factory>, mA_per_V: 'float' = 4.016, ao_max_V: 'float' = 5.0, od_disable_level: 'int' = 1, valve_active_high: 'bool' = True, run_enable_active_high: 'bool' = True, ai_average: 'int' = 4, cal: 'dict' = <factory>, loadcell: 'dict' = <factory>)

- `__init__(self, addresses: 'dict' = <factory>, ao: 'dict' = <factory>, od_pin: 'dict' = <factory>, ef_pin: 'dict' = <factory>, dio: 'dict' = <factory>, pulse_ms: 'float' = 20.0, ai: 'dict' = <factory>, tc: 'dict' = <factory>, mA_per_V: 'float' = 4.016, ao_max_V: 'float' = 5.0, od_disable_level: 'int' = 1, valve_active_high: 'bool' = True, run_enable_active_high: 'bool' = True, ai_average: 'int' = 4, cal: 'dict' = <factory>, loadcell: 'dict' = <factory>) -> None`
- `save(self, path='io_node.json')`

### class DaqHatsHAL(io: 'IOConfig | None' = None, daqhats_module=None, open_boards=True)

nodes.HAL 구현. daqhats 가 없는 PC 에서는 fake 모듈을 주입해 시험한다 (tests 참고).

- `__init__(self, io: 'IOConfig | None' = None, daqhats_module=None, open_boards=True)`
- `calibrate_pump_channel(self, pid, measure_mA, lo=5.0, hi=19.0, settle=0.5)` — 2점 교정. measure_mA(): 멀티미터 값을 입력받거나, 피드백 루프백을 읽는 함수.
- `close(self)` — 모든 출력을 안전 상태로 (safe 와 같은 순서).
- `open(self)`
- `pulse(self, pid) -> 'bool'` — 접점 펄스: DIO High(포토커플러 ON = 접점 닫힘) pulse_ms 유지 후 Low. 펌프 최소 펄스폭(매뉴얼) 이상으로 둘 것.
- `pump_enable(self, pid, on)`
- `pump_set_mA(self, pid, mA)`
- `read_ef_faults(self) -> 'dict'` — XTR111 EF 핀: Low = 부하 단선/과열. {'P-101': True(고장), ...}
- `read_feedback_mA(self, pid)`
- `read_ph(self)`
- `read_pressure_bar(self)`
- `read_tank_mass_g(self)`
- `read_temp_C(self)`
- `read_turbidity_ntu(self)`
- `run_enable(self, on)`
- `snapshot(self) -> 'dict'` — 벤치용: 현재 출력 래치·입력을 한 번에.
- `step(self, dt)`
- `stirrer_set_mA(self, mA)`
- `valve(self, vid, on)`

## cmysim.control

```
레시피 계획과 제어기 (AI 노드에서 실행).

흐름
  PLAN  : 목표색(hex 또는 CMY mg/L) → 목표 농도 c* → 투입 부피 V_j → 펌프 유량/스트로크 수
  PRIME : 교반 rpm 지령, 밸브 열기, 운전 허가
  DOSE  : 피드포워드. I/O 노드에 dose(id, mA, strokes) 명령 → 끝나면 밸브 닫기
  SETTLE: 혼합시간 3·t_m 대기
  TRIM  : (closed 모드) 카메라 추정 ĉ 와 c* 의 차이로 추가 투입량 계산 → DOSE 반복 (최대 n회)
  DONE  : 운전 허가 OFF
```

상수: `PUMP_IDS`, `VALVE_IDS`

### class Recipe

| 필드 | 기본 |
|---|---|
| target_rgb8 | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| c_target | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| mode | `closed` |
| dose_minutes | `2.0` |
| flow_factor | `<dataclasses._MISSING_TYPE object at 0x7fb813eb02f0>` |
| de_match | `1.5` |
| trim_tol_mg_L | `0.4` |
| max_trims | `4` |
| settle_factor | `3.0` |
| rpm | `None` |

Recipe(target_rgb8: 'np.ndarray', c_target: 'np.ndarray', mode: 'str' = 'closed', dose_minutes: 'float' = 2.0, flow_factor: 'np.ndarray' = <factory>, de_match: 'float' = 1.5, trim_tol_mg_L: 'float' = 0.4, max_trims: 'int' = 4, settle_factor: 'float' = 3.0, rpm: 'float | None' = None)

- `__init__(self, target_rgb8: 'np.ndarray', c_target: 'np.ndarray', mode: 'str' = 'closed', dose_minutes: 'float' = 2.0, flow_factor: 'np.ndarray' = <factory>, de_match: 'float' = 1.5, trim_tol_mg_L: 'float' = 0.4, max_trims: 'int' = 4, settle_factor: 'float' = 3.0, rpm: 'float | None' = None) -> None`

### class Controller(cfg: 'SystemConfig', recipe: 'Recipe', E_cal: 'np.ndarray | None' = None, I0_cal=None)

- `__init__(self, cfg: 'SystemConfig', recipe: 'Recipe', E_cal: 'np.ndarray | None' = None, I0_cal=None)`
- `estimate(self, rgb8, A=None)` — rgb8: ROI 평균 코드값 (ΔE 용). A: 실제 카메라가 픽셀별 기준 영상으로 구한 흡광도 (있으면 농도 역산에 우선).
- `mixing_time(self)`
- `step(self, t, tele, rgb8, bus, A=None)`

- `target_from_hex(cfg: 'SystemConfig', hex_color: 'str') -> 'tuple[np.ndarray, np.ndarray, float]'` — 목표 hex → (목표 RGB, 목표 농도, 도달 가능 잔차 ΔE). 스톡·광학 모델에서 못 내는 색이면 가장 가까운 색으로.
- `target_from_cmy(cfg: 'SystemConfig', c_target) -> 'tuple[np.ndarray, np.ndarray]'`
- `mA_for_rate(cfg: 'SystemConfig', rate_mL_min: 'float') -> 'float'`
- `plan_doses(cfg: 'SystemConfig', V_heel_mL: 'float', c_target: 'np.ndarray', dose_minutes: 'float', flow_factor=array([1., 1., 1.])) -> 'list[dict]'` — 각 펌프의 투입 부피·스트로크 수·유량·mA 계획.

## cmysim.recipe

```
레시피 실행기: YAML 레시피 → 도징 순서 (AI 노드에서 Controller 자리에 끼워 쓴다).

레시피 예 (recipes/ 폴더 참고)

  name: tierA_target_match
  reactor: {heel_mL: 2000, rpm: 300}
  stocks: {C: 1000, M: 1000, Y: 1000}          # mg/L (생략 시 config)
  target: {hex: "#5A8F7B"}                       # 또는 {cmy: [30, 10, 25]} / {file: target.json}
  match:  {de: 1.5}
  steps:
    - {step: stir, rpm: 300}
    - {step: wait, seconds: 5}
    - {step: dose_to_target, minutes: 2, flow_factor: [0.97, 0.97, 0.97]}
    - {step: settle, factor: 3}
    - {step: measure, seconds: 2, label: feedforward}
    - {step: trim_to_target, max_trims: 3, tol_mg_L: 0.4}
    - {step: hold, seconds: 30}
    - {step: stop}
  matrix: {"reactor.rpm": [150, 300, 500]}      # 선택: 실행 묶음 생성 (카르테시안 곱)

스텝 종류
  stir(rpm) · wait(seconds) · valve(id, open) · dose(pump|pumps, volume_mL|strokes, rate_mL_min|minutes|mA, ratio, total_mL)
  ph_control(pump, acid_pump, setpoint, seconds, Kp, Ki, mode) · acid_load(mol_min)
  dose_to_target(minutes, flow_factor) · settle(factor|seconds) · measure(seconds, label)
  trim_to_target(max_trims, tol_mg_L, de) · hold(seconds) · log(note) · inject_fault(kind, arg, seconds)  · stop

인터록은 I/O 노드가 지킨다 (밸브 닫힌 채 펌프 거부 등). 실행기는 밸브를 먼저 열고 펌프를 보내며, 끝나면 닫는다.
모든 스텝 전이·측정·고장 주입은 self.log 에 시간과 함께 남아 이상탐지 라벨이 된다.
```

상수: `PUMP_IDS`, `VALVE_IDS`, `DYES`, `PULSE_PUMP_IDS`, `PULSE_VALVES`, `STEP_KINDS`, `EXAMPLE`

### class RecipeExecutor(cfg: 'SystemConfig', recipe: 'dict', E_cal=None, I0_cal=None, fault_hook=None, sim=True)

Controller 와 같은 step(t, tele, rgb8, bus, A) 인터페이스. 상태 대신 레시피 스텝 인덱스로 진행한다.

- `__init__(self, cfg: 'SystemConfig', recipe: 'dict', E_cal=None, I0_cal=None, fault_hook=None, sim=True)`
- `step(self, t, tele, rgb8, bus, A=None)`

- `load_recipe(path) -> 'dict'`
- `validate(r: 'dict') -> 'list[str]'`
- `expand_matrix(r: 'dict') -> 'list[dict]'`
- `apply_recipe_to_config(r: 'dict', cfg: 'SystemConfig') -> 'SystemConfig'`
- `build_target(r: 'dict', cfg: 'SystemConfig') -> 'Recipe'`

## cmysim.recipe_cli

```
레시피 CLI.

python -m cmysim.recipe_cli example  > my.yaml                       템플릿 출력
python -m cmysim.recipe_cli validate my.yaml
python -m cmysim.recipe_cli expand   my.yaml                          matrix 전개 결과 (실행 목록)
python -m cmysim.recipe_cli run      my.yaml --sim --out results/     시뮬레이션 실행 (matrix 면 전부) + 요약 CSV/JSON/그래프
실제 장치:  python -m cmysim.ai_node_main --recipe my.yaml ...
```

상수: `EXAMPLE`

- `main(argv=None)`

## cmysim.experiment

```
실험 실행기: 한 번 실행(run), 유량 스윕(sweep), 고장 주입, 그래프, 데이터셋 기록.
```

상수: `PUMP_IDS`, `VALVE_IDS`, `DYES`, `PULSE_PUMP_IDS`

- `parse_fault(spec: 'str')` — 'tank_empty:P-102@30' → (30.0, 'tank_empty', 'P-102'). '@' 없으면 t=0.
- `apply_fault(kind: 'str', arg: 'str', plant: 'SimPlant', ai: 'AINode', io: 'IONode')`
- `run_once(cfg: 'SystemConfig', recipe: 'Recipe', duration_s: 'float' = 600.0, faults=(), dataset_dir=None, E_cal_err: 'float' = 0.0, run_id='run', verbose=False, controller=None) -> 'dict'`
- `make_recipe(cfg: 'SystemConfig', target_hex=None, target_cmy=None, **kw) -> 'tuple[Recipe, float]'`
- `print_result(res: 'dict')`
- `save_timeseries_csv(res: 'dict', path)`
- `plot_result(res: 'dict', path)`
- `sweep(cfg: 'SystemConfig', base: 'Recipe', factors, which=('C', 'M', 'Y'), duration_s=400.0, csv_path=None, mode='open') -> 'list[dict]'` — 펌프별 유량(=투입량) 배율을 바꿔 가며 최종 ΔE 를 본다. 같은 시간에 더/덜 흘리면 색이 어떻게 비껴가는가.
- `print_sweep(rows)`
- `dump_json(res: 'dict', path)`

## cmysim.anomaly

```
다변량 시계열 이상탐지 (오토인코더) — 대화의 '4. AI 설계' 세 번째 갈래.

입력 특징 (0.5 s 간격, 정상 실행으로 표준화)
  펌프 3대: 지령 mA, 피드백 spm, 스트로크 잔차(지령으로 기대되는 spm − 실제 spm)
  물질수지 잔차: 스트로크 계수로 기대되는 농도 − 카메라 추정 농도 (염료 3개)
  카메라: ĉ(C,M,Y), ΔE2000, dΔE/dt
  공정: 토출 압력, pH, 온도, rpm (있는 것만)
모델 (같은 인터페이스 fit / score / save / load)
  PCAAutoencoder : numpy 만. 창을 펼쳐 PCA 로 압축·복원. Pi 에서 추론 기본값
  ConvAutoencoder: PyTorch 1D-CNN. 워크스테이션에서 학습, 가중치는 numpy 로도 저장해 Pi 에서 torch 없이 추론 가능
점수 = 창 복원오차(MSE). 임계값 = 정상 검증 점수의 분위수. CUSUM 으로 느린 드리프트 누적.
융합 점수 S = Σ w_i·z_i  (ΔE, AE 점수, pH 오차, 유량 잔차, YOLO 확률) 는 fusion_score().

  python -m cmysim.anomaly gen   --out ad_ds --normal 24 --faults 16
  python -m cmysim.anomaly train --data ad_ds --model pca  --out ad_pca
  python -m cmysim.anomaly train --data ad_ds --model conv --out ad_conv --epochs 40
  python -m cmysim.anomaly eval  --data ad_ds --model-dir ad_conv
  python -m cmysim.anomaly score --csv run_timeseries.csv --model-dir ad_conv --plot score.png
  실시간: ai_node_main --anomaly ad_conv
```

상수: `STROKE_ML`, `I_START`, `I_FULL`, `MAX_SPM`, `FEATURES_BASE`, `FEATURES_OPT`, `MODELS`, `FAULT_POOL`

### class FeatureBuilder(dt=0.5, heel_mL=2000.0, c_stock=(1000.0, 1000.0, 1000.0), features=None)

오프라인(행 목록)과 온라인(한 행씩) 이 같은 코드로 같은 특징을 만든다.

- `__init__(self, dt=0.5, heel_mL=2000.0, c_stock=(1000.0, 1000.0, 1000.0), features=None)`
- `available_features(self, rows)`
- `matrix(self, rows: 'list[dict]', features: 'list[str]') -> 'np.ndarray'`
- `push(self, r: 'dict') -> 'dict'` — 한 행 → 특징 dict (상태: 누적 투입량, 이전 ΔE).
- `reset(self)`

### class PCAAutoencoder(W, n_feat, var_keep=0.95)

- `__init__(self, W, n_feat, var_keep=0.95)`
- `fit(self, Xw: 'np.ndarray', epochs=None, verbose=False)`
- `reconstruct(self, Xw)`
- `save(self, d)`
- `score(self, Xw)`

### class ConvAutoencoder(W, n_feat, latent=8, hidden=32)

1D-CNN 오토인코더 (torch). 추론은 numpy 로도 가능하도록 가중치를 npz 로 함께 저장한다.

- `__init__(self, W, n_feat, latent=8, hidden=32)`
- `fit(self, Xw, epochs=40, lr=0.002, batch=64, verbose=False, seed=0)`
- `reconstruct(self, Xw)`
- `save(self, d)`
- `score(self, Xw)`

### class Detector(model, features, mu, sd, thr, W, dt=0.5, heel_mL=2000.0, c_stock=(1000, 1000, 1000), cusum_k=0.5, cusum_h=30.0, s_mu=0.0, s_sd=1.0)

- `__init__(self, model, features, mu, sd, thr, W, dt=0.5, heel_mL=2000.0, c_stock=(1000, 1000, 1000), cusum_k=0.5, cusum_h=30.0, s_mu=0.0, s_sd=1.0)`
- `calibrate_cusum(self, normal_scores_per_run: 'list', k=0.5, margin=1.5)` — 정상 실행들의 점수로 s_mu/s_sd 를 정하고, 정상에서 한 번도 안 울리도록 h 를 최대 CUSUM × margin 으로.
- `push(self, row: 'dict') -> 'dict | None'`
- `reset(self)`
- `save(self, d)`
- `score_rows(self, rows)`
- `standardize(self, X)`

- `spm_expected(mA)`
- `canonical_rows(path) -> 'list[dict]'` — 시뮬레이션 timeseries.csv / AI 노드 ai_node_log.csv 어느 쪽이든 공통 키로 바꾼다.
- `resample(rows: 'list[dict]', dt=0.5) -> 'list[dict]'` — 불규칙/고속 로그를 dt 간격 평균으로.
- `windows(X: 'np.ndarray', W: 'int', stride: 'int' = 1) -> 'np.ndarray'`
- `cusum_seq(s: 'np.ndarray', mu: 'float', sd: 'float', k: 'float' = 0.5) -> 'np.ndarray'` — z = (점수 − 정상 평균)/정상 표준편차; (z − k) 의 양의 누적합. 느린 드리프트(스톡 농도 오차, 공기 유입, 교반 저하)를 잡는다.
- `fusion_score(dE=None, ae_ratio=None, ph_err=None, flow_resid=None, p_yolo=None, w=(1.0, 1.5, 1.0, 1.0, 1.0), z_scale=(2.0, 1.0, 0.2, 10.0, 1.0))` — S = Σ w_i · z_i. z 는 각 항을 '정상 범위 폭' 으로 나눈 값. 1 을 넘으면 그 항이 정상 범위를 벗어난 것.
- `cmd_gen(a)`
- `load_runs(data_dir, sub, dt=0.5)`
- `cmd_train(a)`
- `evaluate(det: 'Detector', data_dir, dt=0.5, verbose=True)`
- `cmd_eval(a)`
- `cmd_score(a)`
- `main(argv=None)`

## cmysim.yolo_train

```
YOLO 학습 파이프라인 (워크스테이션에서 학습 → ONNX → Hailo HEF → AI HAT+ 추론).

  python -m cmysim.yolo_train gen      --out ds_sim --runs 12                      시뮬레이션으로 라벨 달린 프레임 생성
  python -m cmysim.yolo_train prepare  --src ds_sim/* ds_run1 --out yolo_ds        train/val 분할 + data.yaml + 회귀 CSV
  python -m cmysim.yolo_train train    --data yolo_ds/data.yaml --model yolo11n.pt --epochs 50 --imgsz 320
  python -m cmysim.yolo_train train    --data yolo_ds_cls --task classify --model yolo11n-cls.pt      (프레임 상태 분류)
  python -m cmysim.yolo_train export   --weights runs/detect/cmy/weights/best.pt                   ONNX (Hailo 컴파일용)
  python -m cmysim.yolo_train infer    --weights best.pt --source yolo_ds/images/val                 또는 --source camera.json
  python -m cmysim.yolo_train regress  --csv yolo_ds/regression.csv                                 색→농도 회귀 (YOLO 보조)

역할 분담 (대화에서 정리한 대로)
  - YOLO detect  : 기포·거품·침전·이물 같은 '사건' 과 액체 ROI 의 on/off_target 상태
  - YOLO classify: 프레임 한 장의 on_target / off_target (가장 가벼움, Hailo 에서 수백 fps)
  - 회귀         : 색 → 농도 같은 연속값은 YOLO 가 아니라 optics 역산 또는 작은 회귀 모델
```

상수: `CLASSES`

- `cmd_gen(a)`
- `cmd_prepare(a)`
- `link(src, dst, copy)`
- `cmd_train(a)`
- `cmd_export(a)`
- `cmd_infer(a)`
- `features(R, G, B, I0=(0.9, 0.9, 0.9), gamma=2.2)`
- `cmd_regress(a)`
- `main(argv=None)`

## cmysim.yolo_infer

```
학습된 모델로 프레임에서 '사건' 을 읽는 래퍼 (AI 노드에서 사용).

VisionEvents(weights).detect(rgb_frame) → {"liquid": "liquid_on_target"|"liquid_off_target"|None, "liquid_conf", "bubbles", "boxes", "ms"}

백엔드
  .pt / .onnx : ultralytics (CPU; 워크스테이션 또는 Pi CPU 에서 수 fps)
  .hef        : Hailo-8 (AI HAT+). hailo_platform 이 설치된 Pi 에서만. 후처리는 hailo_model_zoo 의 YOLO NMS 를 쓴다고 가정.
```

상수: `CLASSES`

### class VisionEvents(weights: 'str', conf: 'float' = 0.25, imgsz: 'int' = 320)

- `__init__(self, weights: 'str', conf: 'float' = 0.25, imgsz: 'int' = 320)`
- `detect(self, rgb: 'np.ndarray') -> 'dict'`
- `draw(self, rgb, result)`

## cmysim.ai_node_main

```
AI 노드 실행 스크립트 (Raspberry Pi 5 + AI HAT+ + RealSense).

  python -m cmysim.ai_node_main --io-ip 192.168.10.2 --target "#5A8F7B" --mode closed          --camera camera.json --log run1.csv --dataset ds_run1/

  --monitor    : I/O 노드에 연결하지 않고 카메라 측정만 출력 (배선 전 점검용)
  --no-io      : 명령을 보내지 않고 화면에만 찍음 (제어기 상태기계 점검; 텔레메트리가 없어 DOSE 에서 멈춤)

구조: 카메라 → ROI RGB·흡광도 → Controller.step() → ZeroMQ 로 I/O 노드에 명령, 하트비트 0.2 s.
종료(Ctrl+C, 예외, DONE) 시 반드시 run_enable OFF + safe 를 보낸다. I/O 노드는 하트비트가 1 s 끊겨도 스스로 SAFE 가 된다.
```

### class NullBus()

--no-io: 명령을 기록만 한다.

- `__init__(self)`
- `latest(self)`
- `send_cmd(self, m)`

- `main(argv=None)`

## cmysim.io_node_main

```
I/O 노드 실행 스크립트 (Raspberry Pi 5 + MCC 118 + MCC 134 + MCC 152 ×2).

  python -m cmysim.io_node_main list                         보드 목록·주소 확인 (daqhats_list_boards 와 같음)
  python -m cmysim.io_node_main run   [--config io_node.json] [--log io_log.csv]
  python -m cmysim.io_node_main run   --sim                   보드 없이 SimPlant 로 I/O 노드 흉내 (AI 노드와 이더넷 시험)
  python -m cmysim.io_node_main bench ramp 0                 AO0 를 0→5 V 계단으로 (멀티미터로 확인)
  python -m cmysim.io_node_main bench dio 4 1                DIO4 = 1 (LED/포토커플러)
  python -m cmysim.io_node_main bench blink 5                DIO5 깜빡임
  python -m cmysim.io_node_main bench read                   EF·아날로그 입력·온도 연속 표시
  python -m cmysim.io_node_main bench pump P-101 12          P-101 에 12 mA (OD 켬, RUN_ENABLE 은 켜지 않음)
  python -m cmysim.io_node_main bench calib P-101            2점 교정 (멀티미터 값을 물어봄) → io_node.json 에 저장
  python -m cmysim.io_node_main bench safe                   전부 안전 상태

run 은 10 Hz 로 IONode.tick() 을 돌리며 ZeroMQ(PULL 5555 / PUB 5556)로 AI 노드와 통신한다.
AI 노드 하트비트가 1 s 끊기면 IONode 가 SAFE, 이 프로세스가 죽어도 finally 에서 close() 로 출력을 끈다.
```

상수: `PUMP_IDS`

- `cmd_list()`
- `cmd_bench(a, io: 'IOConfig')`
- `cmd_run(a, io: 'IOConfig')`
- `main(argv=None)`

## cmysim.zmq_bridge

```
실제 두 Pi 사이에서 Bus 를 ZeroMQ 로 대체하는 최소 예시 (이 저장소에서는 실행하지 않음; pyzmq 필요).

I/O 노드:  PULL(tcp://*:5555) 로 명령 수신, PUB(tcp://*:5556) 으로 텔레메트리
AI  노드:  PUSH(tcp://<io-ip>:5555) 로 명령, SUB(tcp://<io-ip>:5556) 으로 텔레메트리

메시지 형식은 nodes.Bus 와 같은 JSON dict 이므로 IONode / AINode / Controller 코드는 그대로 쓴다.
```

### class ZmqBus(role: 'str', io_ip: 'str' = '192.168.10.2', cmd_port=5555, tele_port=5556)

nodes.Bus 와 같은 인터페이스. role='io' 또는 'ai'.

- `__init__(self, role: 'str', io_ip: 'str' = '192.168.10.2', cmd_port=5555, tele_port=5556)`
- `drain_cmds(self)`
- `latest(self)`
- `publish(self, msg: 'dict')`
- `send_cmd(self, msg: 'dict')`

- `io_node_main(io_ip='0.0.0.0')` — 하위 호환: python -m cmysim.io_node_main run 을 쓰세요.

## cmysim.integration_test

```
전체 시스템 통합 시험 — Tier C 공침 레시피.

  python -m cmysim.integration_test            # A: 단일 프로세스, B: ZeroMQ 2프로세스, C: 고장 변형 — 전부 실행 후 보고서
  python -m cmysim.integration_test --only A --out it_results

검증 항목 (각 시나리오)
  A/B 정상: 4 펌프 모두 사용, 인터록/거부 알람 없음, pH 유지 구간의 90 % 이상이 설정값 ±0.3, 피드 후 탁도 > 50 NTU,
           로드셀 유량 상태 OK, DOSE short/timeout 없음, 종료 시 I/O 노드 SAFE, 측정 라벨 전부 기록, 데이터셋 프레임·라벨 생성
  C 고장 : NO_STROKE/TANK_LOW 알람 발생, DOSE 중단 라벨, pH 유지는 계속, 종료 시 SAFE
보고서는 out/report.md 와 report.json. 이 스크립트의 A 와 C 는 pytest 에서도 돈다.
```

상수: `PUMP_IDS`, `HERE`

- `scenario_A(out: 'pathlib.Path', duration=2400.0)`
- `scenario_C(out: 'pathlib.Path', duration=1200.0)`
- `scenario_B(out: 'pathlib.Path', timeout_s=2700, hz=10.0, time_scale=20.0)` — ZeroMQ 2프로세스: io_node_main run --sim (텔레메트리에 카메라 관측 포함) + ai_node_main --camera-kind telemetry --recipe.
- `write_report(out: 'pathlib.Path', results: 'dict')`
- `main(argv=None)`
