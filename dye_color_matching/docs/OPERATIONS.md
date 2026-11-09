# 운영 절차와 문제 해결

## 1. 워크스테이션에서 (보드·카메라 없이)

```bash
cd dye_color_matching
python -m pytest -q tests                                   # 37 테스트
python -m cmysim run --target "#5A8F7B" --mode closed --plot run.png
python -m cmysim.recipe_cli run recipes/target_match.yaml --out results --plot
python -m cmysim.integration_test --out it_results          # Tier C 통합 A/B/C
python -m cmysim.camera_tools --config camera.json settings --kind fake   # 카메라 CLI 흐름 연습
```

## 2. I/O 노드 빵판 단계 (24 V 없이)

1. `io_node_main list` 로 주소 0~3 확인.
2. `bench ramp 0`(AO 0→5 V 멀티미터), `bench dio 4 1`, `bench blink 5`, `bench read`(EF·AI·온도).
3. 재부팅 중 PC817 이 꺼져 있는지 확인.

## 3. 펌프 인터페이스 보드 + 24 V

1. Pi/보드 전원 → 24 V 순서.
2. `bench pump P-101 12` 로 12 mA 와 옵션 C 피드백·EF 확인 (펌프는 Pause).
3. `bench calib P-10x` 로 채널마다 2점 교정 → `io_node.json`.
4. 밸브 `bench dio 4 1` 로 XV-101 클릭 확인. 릴리프 설정 3 bar 이하 확인.

## 4. AI 노드

1. `camera_tools settings/preview/roi`, `reference`(물만), `sample`×(3 염료 × 4~5 농도), `fit`, `check`(혼합 검증), `target`.
2. `camera_tools monitor --target ...` 로 ĉ, ΔE 확인.
3. 로드셀: I/O 노드에서 `loadcell read/tare/calib/flow`.

## 5. 연동 시험 (보드 없이 두 Pi)

I/O 노드: `python -m cmysim.io_node_main run --sim --sim-camera --recipe recipes/target_match.yaml`
AI 노드: `python -m cmysim.ai_node_main --io-ip <io-ip> --camera camera.json --recipe recipes/target_match.yaml` (camera.json kind=telemetry)

## 6. 실제 운전

I/O 노드: `python -m cmysim.io_node_main run -v`
AI 노드: `python -m cmysim.ai_node_main --io-ip <io-ip> --recipe my.yaml --target-file target.json --log run1.csv --dataset ds_run1/ --anomaly ad_model --yolo best.pt`

시작 전 점검: 탱크 수위·로드셀 tare, 볼밸브 열림, 비상정지 해제, 펌프 모드(Analog/Contact), 릴리프 설정, pH 프로브 교정, 카메라 노출 고정.

## 7. 문제 해결

| 증상 | 확인 | 조치 |
|---|---|---|
| AI 노드 "텔레메트리가 오지 않습니다" | I/O 노드 실행 중? IP·포트? 방화벽? | `io_node_main run` 먼저, `--io-ip` 확인 |
| 펌프가 안 돎, `INTERLOCK` | 밸브 열었나, run_enable 보냈나 | 레시피/명령 순서: valve → run_enable → pump |
| `REJECT not armed` | arm 전 명령, 또는 SAFE 전이 후 | 워치독·부피 한계 사유 확인 후 재시작 |
| `NO_STROKE` | 펌프 Pause? 수위? mA 케이블? 펌프 신호 알람? | `bench pump`, 펌프 화면 알람 확인 |
| `RELIEF` | 밸브 고착/막힘, 릴리프 설정 과소 | 라인·체크밸브 점검 |
| `FLOW_LOW` + `VOLUME_MISMATCH` | 튜브 공기, 마모, 역류 | 프라이밍, 튜브 교체 |
| `FLOW_HIGH` | 사이펀·누설, 병 건드림 | 배관 높이, 병 고정 |
| `EF` | XTR111 부하 단선/과열 | 펌프 mA 케이블, 보드 발열 |
| 카메라 ΔE 가 실제와 다름 | 자동 노출 켜짐, 조명 변화, 기준 영상 오래됨 | `settings` 수동 고정, `reference` 재촬영 |
| 폐루프가 덜 넣거나 트림 못 함 | 보정 행렬 오차, 과투입 | `check` 로 혼합 검증, flow_factor 0.97 |
| pH 오버슈트 | 이득 과대, 프로브 지연 과소 | 릴레이 동조, `probe_tau_s`·lag_s 실측값 |
| pH `STUCK` | 프로브 고장, 펌프 정지, 탱크 비움 | 프로브·NaOH 탱크 확인 |
| 이상탐지 오경보 많음 | 정상 데이터 부족·조건 변화 | 실제 정상 로그로 재학습, 분위수 상향 |
| 루프 지연 초과 n회 | Pi 부하, 로드셀 시리얼 지연 | hz 낮추기, 다른 프로세스 정리 |
