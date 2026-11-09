# coprecip_sim — 식용색소 색 매칭 자동화 (전구체 공침 반응기 1단계)

ProMinent CHEMICAL FEEDER 패널(gamma/X 펌프 3대)에 **시안·마젠타·옐로 식용색소**를 물려, 목표색을 자동으로 만들고
카메라로 얼마나 가까운지(ΔE2000) 판정하는 실험의 소프트웨어입니다. 하드웨어가 오기 전에는 시뮬레이터로 제어를 검증하고,
도착하면 같은 코드를 Raspberry Pi 두 대에서 돌립니다.

## 지금 단계의 네 가지 핵심

| # | 항목 | 모듈 | 상태 |
|---|---|---|---|
| 1 | **시뮬레이터 + 색 매칭 제어** — 펌프·탱크·반응기·카메라 모델, 목표색 → 투입량 계산 → 피드포워드 → 카메라 트림, 유량 스윕, 고장 주입, **브라우저 UI** | `config optics hardware process vision nodes control experiment ui` | ✅ 실행·테스트 완료 |
| 2 | **RealSense 카메라** — 수동 노출 고정, ROI, 물 기준 영상, 염료별 보정 행렬 E 피팅, 목표 시료 촬영 | `camera camera_tools ai_node_main` | 코드 완료, 실물 미검증 |
| 3 | **I/O 보드(Pi 5 + MCC 152/118/134)** — 펌프 펄스(접점) 또는 4–20 mA 구동, 솔레노이드 밸브, 압력 입력, 인터록·워치독, 빵판 벤치 명령 | `daqhats_hal io_node_main nodes` | 코드 완료, 가짜 보드로 검증 |
| 4 | **YOLO 카메라 학습** — 프레임·라벨 자동 생성, 학습·추론·ONNX, Hailo 래퍼, 기포/액체 상태 | `yolo_train yolo_infer vision` | CPU 학습·추론 확인 |

그 밖의 모듈(pH 제어 `ph_control`, 산 펌프, 침전 모델 `precip`, 로드셀 `loadcell`, 이상탐지 `anomaly`, 레시피 실행기 `recipe`,
Tier C 통합 시험 `integration_test`)은 **공침 단계용**으로 저장소에 남겨 두었고 지금 실험에는 쓰지 않습니다.
전체 참조는 [docs/REFERENCE_ALL.md](docs/REFERENCE_ALL.md) 와 [docs/](docs/) 에 있습니다.

## 1. 시뮬레이션 바로 해 보기

```bash
cd coprecip_sim
pip install numpy matplotlib          # UI 는 numpy 만 있으면 됨
python -m cmysim.ui                   # → 브라우저에서 http://localhost:8050
```

브라우저 화면에서 목표색을 고르고 **시작**을 누르면 펌프 3대가 색소를 넣고, 카메라가 색을 읽어 부족분을 트림합니다.

- 목표/카메라/실제 색 견본, 농도·ΔE·펌프 spm 그래프, I/O 노드 상태(RUN/SAFE, 밸브, 스트로크), 이벤트·알람 로그
- 속도 1~60배, 일시정지, SAFE
- 고장 주입 버튼: 탱크 고갈, 밸브 고착, 카메라 노출 변화, 스톡 농도 오차, 교반 저하, AI 노드 사망(워치독 동작 확인)
- **수동 모드**: 제어기 없이 밸브를 열고 스트로크 수를 정해 직접 투입. 밸브를 안 열고 투입하면 I/O 노드가 거부하는 인터록을 볼 수 있음

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
| 라인 출구 | 없음 | **내화학 솔레노이드 밸브 HDC042 DC24V × 3** (SUS316 + 테프론 다이아프램, 0~2.5 bar, PT 1/4") + 체크밸브 |

핀 배정(펄스 모드): P-101 → MCC 152 #1 DIO6, P-102 → #1 DIO7, P-103 → #2 DIO0, XV-101/102 → #1 DIO4/5, XV-103 → #2 DIO4,
운전 허가(펌프 Pause 공통) → #2 DIO5, 압력 → MCC 118 CH4. 배선 상세는 [docs/HARDWARE.md](docs/HARDWARE.md).

## 3. Raspberry Pi 에서

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
