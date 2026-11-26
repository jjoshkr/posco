# 변경 이력

브랜치 `claude/wonderful-dirac-1zfw8d`, 커밋 순서.

1. **시뮬레이터** — Beer–Lambert 3×3 역산, CIEDE2000, 펌프·DAC·ADC·밸브·탱크·반응기 모델, 두 노드 구조와 인터록·워치독, 피드포워드+트림 제어기, 고장 주입·유량 스윕·그래프·데이터셋.
2. **실제 카메라** — RealSense/Picamera2/OpenCV 백엔드, 픽셀별 기준 영상, E 피팅 CLI, AI 노드 실행 스크립트.
3. **I/O 노드 실물** — daqhats HAL(핀 배정, 페일세이프, 교정), 벤치 명령, 10 Hz 운전 루프, 가짜 daqhats 테스트.
4. **YOLO** — 3 클래스 자동 라벨, gen/prepare/train/export/infer/regress, Hailo 래퍼, AI 노드 연동.
5. **레시피 실행기** — YAML 스텝, matrix, CLI, AI 노드 `--recipe`.
6. **이상탐지** — 특징 빌더, PCA/1D-CNN 오토인코더, CUSUM, gen/train/eval/score, 온라인 Detector.
7. **로드셀** — HX711 serial/gpio/sim, 유량 추정·판정, I/O 노드 알람, 이상탐지 유량 특징, Arduino 스케치.
8. **pH 제어** — 산·염기 모델, 프로브, 한쪽 PID + 완충용량 상한 + 속도 제한기 + 안전, 릴레이 동조, 적정, 레시피 스텝.
9. **양방향 pH** — 펄스 구동 산 펌프 P-104, 부호 출력 제어기, 대칭 릴레이, 로드셀 판정 창 평균.
10. **Tier C 통합 시험** — 침전·탁도 모델, 백그라운드 pH 유지, 시간 가속 2프로세스 시험, 보고서.
11. **문서화** — docs/ (아키텍처, 프로토콜, 하드웨어, 레시피, 설정, 운영, API), CHANGELOG.
12. **펄스 모드·실제 장비 프리셋** — P-101~103 접점 펄스 구동(XTR111 없이), `rig_prominent_feeder()`.
13. **브라우저 UI·README 재구성** — `cmysim.ui` 시뮬레이션 인터페이스(목표색, 그래프, 고장 주입, 수동 모드), README 를 색소 실험 네 핵심 중심으로 다시 씀(이전 README 는 docs/REFERENCE_ALL.md).
14. **UI 2차** — Pretendard, 단계 표시줄·사용 안내, 장비 모식도, 운전 중 실시간 제어(펌프 속도 배율·보류·밸브·교반·목표 변경·지금 트림), I/O 노드 `rate_scale`/`hold` 명령.
