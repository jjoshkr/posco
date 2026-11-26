# 설정 파일과 SystemConfig

## `camera.json` (AI 노드, `camera_tools settings`)

| 키 | 기본 | 뜻 |
|---|---|---|
| kind | realsense | realsense · picamera2 · opencv · fake · telemetry |
| width, height, fps | 640, 480, 30 | 스트림 |
| exposure, gain, white_balance | 100, 16, 4600 | 수동 고정값 (백엔드 단위) |
| device | "" | 시리얼/장치 번호. fake 는 'C,M,Y' 농도 |
| roi | [220,140,200,200] | x, y, w, h |
| gamma | 2.2 | 코드값→선형. 0 이면 정식 sRGB |
| ref_path, calib_path | camera_ref.npy, calibration.json | 기준 영상, 보정 |

## `calibration.json` (`camera_tools fit`)
E(3×3, 흡광도/(mg/L)), I0(3), gamma, glare, cond(조건수), samples(보정 시료), note.

## `target.json` (`camera_tools target`)
rgb, hex, A, c (같은 카메라로 찍은 목표 시료).

## `io_node.json` (I/O 노드, `io_node_main init-config`)

| 키 | 뜻 |
|---|---|
| addresses | 보드 이름 → 주소 |
| ao, od_pin, ef_pin | 펌프/교반기 → [보드, 채널] |
| dio | 밸브, RUN_ENABLE, 펄스 펌프 → [보드, DIO] |
| ai | 아날로그 입력 {ch, shunt_ohm, eu_lo, eu_hi} (PH, FB-101~103, PRESSURE, TURB) |
| tc | 열전대 {ch, type} |
| mA_per_V, ao_max_V, od_disable_level, valve_active_high, run_enable_active_high | 전기적 극성·환산 |
| ai_average | ADC 평균 횟수 |
| cal | 펌프 채널 2점 교정 {gain, offset} (`bench calib`) |
| loadcell | {"config": "loadcell.json"} 이면 리더 부착 |
| pulse_ms | 펄스 펌프 접점 닫힘 시간 |

## `loadcell.json` (`loadcell tare/calib`)
backend(serial·gpio·sim), port, baud, gpio_pins, channels, tare[], counts_per_g[], density_g_mL[], rate_hz, window_s, jump_g, settle_s, low_mass_g.

## `recipe.yaml` → `docs/RECIPES.md`

## `SystemConfig` (`cmysim/config.py`, 시뮬레이션·계획 공용)

| 필드 | 내용 |
|---|---|
| pump | gamma/X 사양(stroke_mL, max_spm, i_start/full/fault, repro, relief_bar, fb_option_c) |
| pulse_pump | 펄스 펌프 사양(stroke_mL, max_spm, pulse_ms) |
| dac | MCC 152 → XTR111 체인(bits, gain_err, mA_per_V, calibrated) |
| adc | MCC 118(bits, noise_V, shunt_ohm) |
| tanks | 4개 TankSpec(volume_mL, conc_mg_L, low_level_mL, role, conc_mol_L) |
| reactor | v_max_mL, heel_mL, rpm, rpm_max, mix_K, temp_C, ph, buffers, probe_tau_s, acid_load_mol_min, dye_mg_L |
| camera | E, I0, gamma, glare, pixel_noise, roi_pixels, exposure_drift, turb_K_ntu, fps |
| net | telemetry_hz, heartbeat_timeout_s |
| dt, seed, channel_map | 시뮬레이션 간격, 난수, 핀 배정 참고표 |

실측값이 들어오는 곳: `Calibration.apply_to(cfg)` 가 camera.E/I0/gamma/glare 를, 레시피가 reactor/tanks/ph 를 덮어씁니다.

## 이상탐지 모델 폴더 (`anomaly train --out`)
meta.json(kind, features, mu, sd, thr, W, dt, heel_mL, c_stock, cusum_k/h, s_mu/s_sd) + pca.npz 또는 conv.npz(+conv.pt), eval.json.
