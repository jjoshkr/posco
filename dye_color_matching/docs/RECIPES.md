# 레시피 스키마

파일: YAML(또는 JSON). 검증: `python -m cmysim.recipe_cli validate my.yaml`. 템플릿: `python -m cmysim.recipe_cli example`.

```yaml
name: 문자열                      # 결과 폴더·로그 이름
description: 문자열
reactor:
  heel_mL: 2000                   # 초기 물
  rpm: 300
  temp_C: 25
  dye_mg_L: [10, 0, 0]            # heel 에 미리 녹인 염료 (선택)
stocks:                           # 둘 중 한 형식, 섞어도 됨
  C: 1000                         # 염료 스톡 mg/L (C, M, Y)
  P-101: {role: cacl2, mol_L: 0.2, volume_mL: 1000}    # 펌프별 역할: dye | naoh | acid | cacl2 | na2co3 | citrate
ph:                               # pH 관련 (선택)
  initial: 7.0
  buffers: [[0.005, 6.35]]        # [농도 mol/L, pKa] …  Tier B 구연산: [[0.01, 4.8]]
  naoh_pump: P-103
  naoh_mol_L: 0.1
  acid_pump: P-104                # P-104(펄스) 또는 P-10x(아날로그)
  acid_mol_L: 0.1
target: {hex: "#5A8F7B"}          # 또는 {cmy: [30, 10, 25]} 또는 {file: target.json}
match: {de: 1.5, max_trims: 3, tol_mg_L: 0.4}
steps: [...]
matrix: {"reactor.rpm": [150, 300], "steps[2].minutes": [1, 2]}   # 선택: 점 표기 경로의 카르테시안 곱
```

## 스텝

| step | 인자 | 동작 | 끝나는 조건 |
|---|---|---|---|
| `stir` | rpm | 교반기 지령 | 즉시 |
| `wait` | seconds | 대기 | 시간 |
| `hold` | seconds, label | 대기 후 측정 기록 | 시간 |
| `valve` | id, open | 밸브 수동 조작 | 즉시 |
| `dose` | pump 또는 pumps, volume_mL / strokes / total_mL(+ratio), rate_mL_min / minutes / mA, on_abort(continue|stop), label | 밸브 열기 → 스트로크 계수 도징 → 밸브 닫기 | 모든 펌프 도징 완료, 또는 계획 시간 ×1.5+10 s 타임아웃 |
| `dose_to_target` | minutes, flow_factor | 목표 농도에서 투입량 계산 → 세 펌프 동시 | 〃 |
| `settle` | seconds 또는 factor | 혼합시간 × factor 대기 | 시간 |
| `measure` | seconds, label | 카메라 평균 → RGB·ĉ·ΔE·pH·탁도·온도 기록 | 시간(기본 2 s) |
| `trim_to_target` | max_trims, tol_mg_L, de, settle_factor | 측정 → 부족분 투입 → 정착 반복 | ΔE < de, 또는 횟수, 또는 추가 투입 불필요 |
| `ph_control` | pump, acid_pump, setpoint, seconds, Kp, Ki, Kd, deadband, out_max, ff_gain, ph_max, ph_min, max_total_mL, max_acid_mL, min_switch_s, mode(pid|relay|titrate), relay_d, start/end/rate_pH_per_min, period_s, label | 블로킹 pH 제어 | 시간, 또는 제어기 고장(abort) |
| `ph_hold_start` | ph_control 과 같은 인자 (seconds 불필요) | 백그라운드 pH 유지 시작 — 이후 스텝과 동시에 진행 | 즉시 |
| `ph_hold_stop` | label | 백그라운드 pH 유지 종료, 지표 기록 | 즉시 |
| `acid_load` | mol_min | (시뮬레이션) 산 부하 시작 | 즉시 |
| `inject_fault` | kind, arg, seconds | (시뮬레이션) 고장 주입 + 라벨. 실물: 사람이 할 일을 출력하고 대기 | seconds |
| `log` | note | 메모 | 즉시 |
| `stop` | – | 운전 허가 OFF + SAFE, 결과 확정 | – |

## 기록

- `log.json`: `log` = [(t, kind, detail)] — kind: step, measure, trim, fault, fault_manual, acid_load, ph_hold, ph_done, autotune, abort, done.
  `measurements` = 측정·pH 지표 목록 (label, rgb, hex, c_hat, dE2000, ph, turbidity_ntu, temp_C, V_est_mL; pH 스텝은 IAE, overshoot, settle_s, final_err, naoh_mL, acid_mL, beta_est, autotune).
- `result.json`, `timeseries.csv`, `plot.png` (시뮬레이션), `summary.csv` (matrix 묶음).

## 중단 규칙

- `dose`: 실제 스트로크가 계획의 절반 미만이면 `DOSE short`, 타임아웃이면 `DOSE timeout`. `on_abort: stop` 이면 레시피 종료, 기본은 다음 스텝 계속.
- pH 제어기 고장(PH_LIMIT, 부피 한계, STUCK): `PH …` 로 중단.
- I/O 노드가 스스로 SAFE(워치독·부피 한계): `IO node SAFE` 로 중단.

## 예시 (recipes/)

| 파일 | 내용 |
|---|---|
| target_match.yaml | 목표색 피드포워드 + 트림 |
| tierA_ratio_sweep.yaml | 비율 × rpm 매트릭스 9회 |
| fault_injection.yaml | 탱크 고갈 주입 라벨 |
| tierB_ph_step.yaml | 구연산 완충 pH 5 → 10.5, 산 부하 유지 |
| tierC_ph_autotune.yaml | 산 부하 + 릴레이 동조 |
| tierB_ph_bidirectional.yaml | NaOH + HCl 상승·하강·대칭 동조 |
| tierC_coprecip.yaml | CaCl₂ + Na₂CO₃ 공침, 백그라운드 pH 10 |
| tierC_coprecip_fault.yaml | 공침 중 Na₂CO₃ 탱크 고갈 |
