# dye_color_matching — 식용색소(CMY) 색 매칭 자동화 (전구체 공침 반응기 1단계)

ProMinent CHEMICAL FEEDER 패널(gamma/X 펌프 3대)에 **시안·마젠타·옐로 식용색소**를 물려, 목표색을 자동으로 만들고
카메라로 얼마나 가까운지(ΔE2000) 판정하는 실험의 소프트웨어입니다. 하드웨어가 오기 전에는 시뮬레이터로 제어를 검증하고,
도착하면 같은 코드를 Raspberry Pi 두 대에서 돌립니다.

## 지금 단계의 네 가지 핵심

| # | 항목 | 모듈 | 상태 |
|---|---|---|---|
| 1 | **시뮬레이터 + 색 매칭 제어** — 펌프·탱크·반응기·카메라 모델, 목표색 → 투입량 계산 → 피드포워드 → 카메라 트림, 유량 스윕, 고장 주입, **브라우저 UI** | `config optics hardware process vision nodes control experiment ui` | ✅ 실행·테스트 완료 |
| 2 | **RealSense 카메라** — 수동 노출 고정, ROI, 물 기준 영상, 염료별 보정 행렬 E 피팅, 목표 시료 촬영 | `camera camera_tools ai_node_main` | 코드 완료, 실물 미검증 |
|   | **색역 분석** — E·κ(E)·교차 흡수, 목표색 부호 검사(색역 안/밖), 최근접 색, 보정 농도 범위, 색역 지도, 염료 후보 비교, 이상적 CMY 비교 | `gamut` | 실행·테스트 완료 |
| 3 | **I/O 보드(Pi 5 + MCC 152/118/134)** — 펌프 펄스(접점) 또는 4–20 mA 구동, 솔레노이드 밸브, 압력 입력, 인터록·워치독, 빵판 벤치 명령 | `daqhats_hal io_node_main nodes` | 코드 완료, 가짜 보드로 검증 |
| 4 | **YOLO 카메라 학습** — 프레임·라벨 자동 생성, 학습·추론·ONNX, Hailo 래퍼, 기포/액체 상태 | `yolo_train yolo_infer vision` | CPU 학습·추론 확인 |

그 밖의 모듈(pH 제어 `ph_control`, 산 펌프, 침전 모델 `precip`, 로드셀 `loadcell`, 이상탐지 `anomaly`, 레시피 실행기 `recipe`,
Tier C 통합 시험 `integration_test`)은 **공침 단계용**으로 저장소에 남겨 두었고 지금 실험에는 쓰지 않습니다.
전체 참조는 [docs/REFERENCE_ALL.md](docs/REFERENCE_ALL.md) 와 [docs/](docs/) 에 있습니다.

## 1. 시뮬레이션 바로 해 보기

```bash
cd dye_color_matching
pip install numpy matplotlib          # UI 는 numpy 만 있으면 됨
python -m cmysim.ui                   # → 브라우저에서 http://localhost:8050
```

브라우저 화면에서 목표색을 고르고 **시작**을 누르면 펌프 3대가 색소를 넣고, 카메라가 색을 읽어 부족분을 트림합니다.
글꼴은 Pretendard(인터넷이 되면 CDN, 아니면 시스템 글꼴)입니다. 화면 오른쪽 위 **사용 안내** 버튼에 아래 내용이 들어 있습니다.

| 영역 | 무엇을 하나 | 언제 쓰나 |
|---|---|---|
| 실험 설정 (왼쪽) | 목표색(도달 가능한 가장 가까운 색과 잔차 ΔE 표시, **적용** 버튼으로 운전 중에도 즉시 변경), 초기 물·rpm, 제어(closed/open), 펌프 구동(펄스/아날로그), 도징 시간, 피드포워드 배율, 카메라 잡음, 시드, 속도 | 시작 전 |
| 색역(gamut) 분석 (왼쪽) | 목표색을 넣으면 c = E⁻¹A 의 부호로 **색역 안/밖**을 판정하고 이유를 보여줌(어느 염료가 음수여야 하는지, 물보다 밝은지), κ(E)·교차 흡수·보정 농도 범위 검사, 도달 가능 색 점구름(a*b*) 위에 목표 × 와 최근접 ○. "이상적 CMY(대각 E)로 보기" 로 교차 흡수가 없는 가상 염료와 비교 | 항상 |
| 카메라 보정 (왼쪽) | `camera_tools fit` 이 만든 `calibration.json` 을 파일 선택이나 서버 경로로 불러오면, 시뮬레이터의 색↔농도 변환과 제어기 역산이 **실제 카메라 기준**으로 바뀜(E, I0, γ, 글레어, 조건수 표시). "기본으로" 되돌리기 가능 | 보정 후 |
| 진행 버튼 | **준비(0 s)**: 계획만 세우고 멈춘 상태(PLAN 확인) · **시작/재시작** · **일시정지/계속** · **▶ 다음 단계**: 다음 단계 전이에서 자동 정지 · **+1 s / +10 s / +60 s**: 멈춘 채 그만큼만 진행 · "단계마다 멈춤" 체크 | 언제든 |
| 단계 칩 클릭 | 그 단계 설명 표시. 운전 중이면 그 단계에 도달할 때 자동 정지 | 언제든 |
| **실시간 제어** (왼쪽) | 펌프별 속도 배율 0~150 %·보류/재개·밸브 열고 닫기·정지, 교반 rpm, 지금 트림, **전체 정지(SAFE)**: 운전 허가 OFF → 펌프 0 → 밸브 닫힘 → 제어기 중단(DONE). 일시정지 중에도 즉시. SAFE 중에는 밸브 열기도 거부되며 '지금 트림'(재무장) 또는 시작/재시작으로 재개. 목표색은 위 설정 칸에서 '적용' | **운전 중** |
| 고장 주입 | 탱크 고갈, 밸브 고착, 카메라 노출, 스톡 농도 오차, 교반 저하, AI 노드 사망 | 운전 중 (시뮬레이션 전용) |
| 수동 모드 | 제어기 없이 밸브를 열고 스트로크 수를 정해 투입. 밸브를 안 열면 I/O 노드가 거부(인터록) | 설정에서 체크 후 시작 |
| 단계 표시줄 (오른쪽) | PLAN 계획 → PRIME 준비 → DOSE 투입 → SETTLE 정착 → MEASURE 측정 → TRIM 보정 → DONE 완료. 현재 단계 설명과 경과 시간 | 항상 |
| 장비 모식도 (P&ID) | 실제 패널 배치대로 라인 3개: 스톡병 → gamma/X 펌프(다기능 밸브) → 튜브 → 수직관 → 티(수동 볼밸브 분기) → 압력계/트랜스미터 → 맥동 댐퍼 → DHV-U 배압 밸브 → 솔레노이드 XV(신설) → 체크밸브 → 반응기(실제 색·수위, 교반기, 카메라). 펌프는 돌 때 깜빡임, 밸브는 초록/회색 | 항상 |
| 색 견본·상태 | 목표/카메라/실제 색, **매칭 게이지**(ΔE2000 위치와 등급: 1 거의 동일 · 1.5 매칭 · 2~4 구분 · 6+ 다른 색), 염료별 ĉ−c* 오차 막대(부족→트림 / 과잉은 못 뺌), 농도, 반응기, 밸브, I/O RUN/SAFE | 항상 |
| 그래프 | 농도(실선 실제·점선 추정·가는 점선 목표), ΔE2000(매칭 기준 1.5), 펌프 spm. **마우스를 올리면** 그 시각의 단계와 각 값(실제 c·추정 ĉ·목표 c*·ΔE·spm)이 상자로 표시 | 항상 |
| 이벤트·알람 | AI 노드 상태 전이, I/O 알람(INTERLOCK, NO_STROKE, SAFE…), 고장 주입, UI 조작 | 항상 |

목표색 변경은 즉시 반영됩니다. 투입 전이면 새 계획으로 진행하고, 정착·측정·완료 상태면 바로 측정→트림 사이클을 돌리며, 투입 중이면 다음 측정부터 씁니다(이미 들어간 염료는 뺄 수 없음).
실시간 제어의 버튼 하나는 I/O 노드 명령 JSON 하나와 같습니다(`rate_scale`, `hold`, `valve`, `stop`, `stirrer_rpm`, `safe` — [docs/PROTOCOL.md](docs/PROTOCOL.md)).
속도 배율과 보류는 도징 목표(남은 스트로크)를 바꾸지 않고 속도만 바꾸므로, 실제 장비에서 펌프가 너무 빠르다 싶을 때 그대로 쓰는 조작입니다.

명령행으로도 같은 것을 돌립니다.

```bash
python -m cmysim run   --target "#5A8F7B" --mode closed --plot run.png --csv run.csv --dataset ds/
python -m cmysim sweep --target "#5A8F7B" --factors 0.7,0.85,1,1.15,1.3     # 유량(투입량) 비율별 ΔE 표
python -m cmysim plan  --target "#5A8F7B"                                   # 투입량·스트로크·mA 계획만
python -m pytest -q tests                                                   # 테스트 39개
```

### 색 매칭이 돌아가는 원리

1. 목표색(hex)을 카메라 모델로 역산해 목표 농도 c*(C, M, Y) mg/L 를 구합니다. Beer–Lambert: RGB → 흡광도 → 3×3 행렬 → 농도.
2. 스톡 1 g/L 기준으로 투입 부피 V_j = c_j·V_f / c_stock, 펌프별 스트로크 수(0.19 mL/스트로크)와 속도를 정합니다.
3. I/O 노드가 밸브를 열고 스트로크를 세며 투입합니다(피드포워드, 기본 97 %).
4. 혼합시간만큼 기다린 뒤 카메라가 ĉ 를 읽고, 모자란 염료만 추가 투입(트림)합니다. 과투입은 되돌릴 수 없으니 일부러 조금 적게 넣습니다.
5. ΔE2000 < 1.5 면 매칭. 유량을 15 % 틀리면 ΔE 2~4 로 육안 식별 수준이 됩니다(`sweep`).

## 2. 실제 장비 계획 (사진 기준)

| 부품 | 현재 | 자동화 |
|---|---|---|
| gamma/X 펌프 × 3 | 제어함과 연결 (확인 필요) | **펄스(접점) 모드 권장**: MCC 152 DIO → PC817 → 펌프 접점 입력, 1 펄스 = 1 스트로크. XTR111 보드 없이 빵판으로 시작. 4–20 mA 는 옵션 |
| S-LOK 볼밸브 | 수동 | 항상 열어 둠 (정비용) |
| DHV-U 배압 밸브 (PVDF/EPDM, 0.5~10 bar) | 수동 설정 | **2 bar** 로 설정. 출구가 막히면 릴리프 역할 |
| HIDRACAR 맥동 댐퍼 0.09 L (Po 0) | 예압 없음 | 배압의 60~80 % 로 질소 예압 (예 1.4 bar) |
| Autonics 압력계 0~1 MPa | 눈으로 확인 | 티로 **4–20 mA 압력 트랜스미터** 추가 → MCC 118 CH4 |
| 라인 출구 | 없음 | **내화학 솔레노이드 밸브 HTV 04L2-C DC24V × 3** (테프론 몸체·시트, 직동식 NC, 0~3 bar, PT 1/4", 12 W) + 체크밸브. 대안 HDC042(SUS316+PTFE 다이아프램, 0~2.5 bar) |

핀 배정(펄스 모드): P-101 → MCC 152 #1 DIO6, P-102 → #1 DIO7, P-103 → #2 DIO0, XV-101/102 → #1 DIO4/5, XV-103 → #2 DIO4,
운전 허가(펌프 Pause 공통) → #2 DIO5, 압력 → MCC 118 CH4. 배선 상세는 [docs/HARDWARE.md](docs/HARDWARE.md), 보드 스택·인터페이스 보드(KiCad)·납땜·점검 순서는 [docs/ASSEMBLY.md](docs/ASSEMBLY.md).
도면: [P&ID](docs/P_AND_ID.svg) · [시스템 아키텍처](docs/ARCHITECTURE.svg) · [반응기 뚜껑 포트 배치·염료 주입 구조](docs/REACTOR_PORTS.svg) · [인터페이스 보드 KiCad 회로도](hardware/kicad/) (미리보기 `hardware/kicad/io_interface_preview.svg`, BOM 포함).

## 3. Raspberry Pi 에서

카메라 보정 파일을 만드는 자세한 순서는 [docs/CAMERA_CALIBRATION.md](docs/CAMERA_CALIBRATION.md) 에 있습니다.
염료 고르기 → 색역 확인 → 목표색 정하기의 실험 절차는 [docs/DYE_EXPERIMENT.md](docs/DYE_EXPERIMENT.md) 에 있습니다.

```bash
python -m cmysim.gamut check --calib calibration.json --target "#53F3B6"   # 색역 안/밖 판정, 이유, 최근접 색, 보정 범위
python -m cmysim.gamut map   --calib calibration.json --out gamut.png      # 도달 가능 색 지도 (a*b*, a*L*)
python -m cmysim.gamut compare blue1.json blue2.json --ideal               # 염료 후보 세트 비교 (κ, 교차 흡수, 색역 면적)
```

### AI 노드 (Pi 5 + AI HAT+ + RealSense)

```bash
sudo apt install -y python3-numpy python3-opencv python3-zmq && pip install pyrealsense2
python -m cmysim.camera_tools settings --kind realsense --exposure 120 --gain 16 --wb 4600
python -m cmysim.camera_tools roi --roi 220,140,200,200
python -m cmysim.camera_tools reference                 # 물만 채운 반응기
python -m cmysim.camera_tools sample --dye C --conc 5   # 염료마다 4~5 농도
python -m cmysim.camera_tools fit && python -m cmysim.camera_tools check --cmy 10,5,8
python -m cmysim.camera_tools target --save target.json # 목표 시료를 같은 카메라로
python -m cmysim.ai_node_main --io-ip 192.168.10.2 --target-file target.json --mode closed --log run1.csv --dataset ds_run1/
```

### I/O 노드 (Pi 5 + MCC 152 ×2 + MCC 118 + MCC 134)

```bash
git clone https://github.com/mccdaq/daqhats && cd daqhats && sudo ./install.sh && pip install pyzmq
python -m cmysim.io_node_main list
python -m cmysim.io_node_main bench dio 6 1            # 펄스 핀 LED 확인 (빵판, 24 V 없이)
python -m cmysim.io_node_main bench blink 6
python -m cmysim.io_node_main run --pump-mode pulse -v
```

두 Pi 는 이더넷 직결(예 I/O 192.168.10.2, AI 192.168.10.3). 보드 없이 연동만 시험하려면 I/O 쪽을 `run --sim --sim-camera` 로.

### YOLO

```bash
python -m cmysim.yolo_train gen --out ds_sim --runs 12                    # 시뮬레이션 프레임 (기포 라벨 자동)
python -m cmysim.yolo_train prepare --src ds_sim/* ds_run1 --out yolo_ds   # 실제 프레임과 섞어 분할
python -m cmysim.yolo_train train --data yolo_ds/data.yaml --model yolo11n.pt --epochs 50 --imgsz 320 --device 0
python -m cmysim.yolo_train export --weights runs/detect/cmy/weights/best.pt   # ONNX → Hailo
```

## 4. 검증된 것 / 안 된 것

- 이 저장소에서 실행·확인: 시뮬레이터 전체, 두 프로세스 ZeroMQ 통신, UI, YOLO 학습·내보내기(CPU), 테스트 39개.
- 실물로는 미확인: MCC 보드, RealSense, 펌프 접점 입력, 솔레노이드 구동. 핀 배정과 안전 순서는 가짜 보드 모듈로만 검증했습니다.
- 실측으로 바꿔야 하는 값: 카메라 보정 행렬 E·기준 영상, 혼합시간(300 rpm 에서 10 s 가정), 펌프 스트로크 토출량(명판).

## 문서

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 구조 · [docs/PROTOCOL.md](docs/PROTOCOL.md) 노드 간 명령/텔레메트리 · [docs/HARDWARE.md](docs/HARDWARE.md) 배선·교정 ·
[docs/CONFIG.md](docs/CONFIG.md) 설정 파일 · [docs/OPERATIONS.md](docs/OPERATIONS.md) 절차·문제 해결 · [docs/API.md](docs/API.md) API ·
[docs/REFERENCE_ALL.md](docs/REFERENCE_ALL.md) 전체 참조(공침 단계 모듈 포함) · [CHANGELOG.md](CHANGELOG.md)
