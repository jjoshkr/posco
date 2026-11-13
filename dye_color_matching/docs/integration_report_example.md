# 통합 시험 보고서 — Tier C 공침 레시피

생성: 2026-11-05 17:31:13

## A. 단일 프로세스 (시뮬레이션): PASS

| 항목 | 결과 | 비고 |
|---|---|---|
| 4 펌프 모두 사용 | ✅ | {'P-101': 59.94, 'P-102': 59.87, 'P-103': 5.51} pulse {'P-104': 3.42} |
| 인터록/거부 알람 없음 | ✅ |  |
| pH 유지: 설정값 ±0.3 안 비율 ≥ 0.9 | ✅ | 96.29% (sp 10.0, 구간 1~1523 s) |
| 피드 후 탁도 > 50 NTU | ✅ | 757.9 NTU, 고체 1.191 g, d50 proxy 20.1 µm |
| DOSE short/timeout 없음 | ✅ |  |
| 로드셀 유량 판정 정상 | ✅ |  |
| 종료 시 I/O 노드 SAFE | ✅ | SAFE |
| 측정 라벨 전부 기록 | ✅ | ['baseline', 'end_of_feed', 'ageing', 'ph_hold', 'final'] |
| 탁도 상승 순서 baseline < end_of_feed | ✅ | {'baseline': 0.2, 'end_of_feed': 749.8, 'ageing': 757.1, 'final': 757.1} |
| 데이터셋 프레임·라벨 생성 | ✅ | 764 frames |

## B. ZeroMQ 2프로세스 (I/O 노드 --sim + AI 노드): PASS

| 항목 | 결과 | 비고 |
|---|---|---|
| AI 노드 정상 종료 (exit 0) | ✅ | exit 0, 78 s |
| 텔레메트리 수신·레시피 로드 | ✅ |  |
| 레시피 완료 (DONE) | ✅ |  |
| I/O 노드 모드 RUN → SAFE | ✅ | 799 rows |
| 피드 펌프 2줄 동작 (I/O 로그 스트로크) | ✅ | 315.9/315.8 |
| AI 로그에 pH·탁도·로드셀 열 | ✅ | 765 rows |
| 피드 후 탁도 > 50 NTU (I/O 로그) | ✅ | 759.5 NTU |
| pH 유지 (후반 2/3 구간 ±0.3 비율 ≥ 0.85) | ✅ | 100.00% |

## C. 고장 변형 (Na₂CO₃ 탱크 고갈): PASS

| 항목 | 결과 | 비고 |
|---|---|---|
| NO_STROKE 또는 TANK_LOW 알람 | ✅ | FAULT_INJECTED tank_empty P-102; NO_STROKE P-102: commanded 5.6 mA, feedback 4.0 mA; TANK_LOW P-102: 99.98 g; NO_STROKE P-102: commanded 5.6 mA, feedback 4.0 mA; TANK_LOW P-102: 100.0 g; NO_STROKE P-1 |
| DOSE 중단 라벨 | ✅ | DOSE timeout |
| pH 유지 계속 (after_fault 측정에 pH) | ✅ |  |
| 종료 시 I/O 노드 SAFE | ✅ | SAFE |

**전체: PASS**