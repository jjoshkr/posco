# 카메라 보정 파일(calibration.json) 만드는 법

`realsense-viewer` 에서 내려받는 것이 아닙니다. realsense-viewer 는 카메라가 인식되는지 보고 노출을 눈으로 맞출 때만 쓰고,
보정은 이 저장소의 `python -m cmysim.camera_tools` 명령으로 **직접 찍어서** 만듭니다. 원리는 PDF 보고서 7~8장 그대로입니다.

## 왜 필요한가

카메라 RGB 를 염료 농도로 바꾸려면 "이 카메라·이 조명·이 반응기·이 염료" 에서 **염료 1 mg/L 가 R, G, B 를 각각 얼마나 어둡게 하는지**(3×3 행렬 E)와
**물만 있을 때의 밝기**(I0)를 알아야 합니다. 이 둘은 장비마다 다르므로 실측해야 하고, 그 결과가 `calibration.json` 입니다.

## 준비물

- AI 노드(또는 RealSense 를 꽂은 리눅스 PC)에 `pyrealsense2`, `numpy`, 이 저장소. (pyrealsense2 가 안 깔리면 `--kind opencv` 로 RealSense 를 웹캠처럼 열어도 됨)
- 반응기에 물(실험과 같은 부피), 교반 켜 둠, 조명 고정(백색 LED 패널이면 투과형, 흰 판이면 반사형). 창문 빛·형광등 깜빡임 차단.
- 염료 스톡 3종(1 g/L)과 피펫. 염료마다 농도 4~5점(예 5, 10, 15, 20 mg/L)을 만들 수 있어야 함. 반응기 2 L 기준 1 g/L 스톡 10 mL = 5 mg/L.
- 카메라는 삼각대 등으로 고정. 보정 뒤 위치·노출을 바꾸면 처음부터 다시.

## 순서 (모두 `coprecip_sim` 폴더에서)

```bash
python -m cmysim.camera_tools settings --kind realsense --exposure 120 --gain 16 --wb 4600 --width 640 --height 480
```
자동 노출·자동 화이트밸런스를 끄고 고정합니다. 노출은 다음 단계에서 포화되지 않게 조정합니다.

```bash
python -m cmysim.camera_tools preview --save shot.png
```
사진을 열어 액체가 보이는 영역을 확인하고 ROI(x, y, 폭, 높이)를 정합니다. 기포·교반축·반사가 없는 액체 안쪽을 고릅니다.

```bash
python -m cmysim.camera_tools roi --roi 220,140,200,200
```

```bash
python -m cmysim.camera_tools reference
```
**물만** 있는 상태에서 30프레임을 평균해 픽셀별 기준 밝기 I0 를 저장합니다(`camera_ref.npy`). 출력된 I0 가 0.95 를 넘으면 포화이니 노출을 줄이고 다시, 0.5 아래면 노출을 올립니다. 목표는 0.6~0.85.

```bash
python -m cmysim.camera_tools sample --dye C --conc 5
```
시안 스톡 10 mL 를 넣고 섞인 뒤(혼합시간 × 3, 300 rpm 이면 30 s) 실행합니다. 이어서 10 mL 씩 더 넣으며 `--conc 10`, `--conc 15`, `--conc 20` 을 반복합니다.
한 염료가 끝나면 반응기를 비우고 물을 다시 채운 뒤 **마젠타(M), 옐로(Y)** 를 같은 식으로 4~5점씩 찍습니다. 각 측정은 `calib_samples.json` 에 쌓입니다.
흡광도가 1 을 넘는다는 경고가 나오면 더 묽은 범위로 잡으세요.

```bash
python -m cmysim.camera_tools fit
```
염료별로 "농도 ↔ 흡광도" 기울기를 구해 E 를 만들고 `calibration.json` 에 저장합니다. 출력에서 확인할 것:
- **조건수 κ**: 3 이하면 좋음. 크면 두 염료가 카메라에 비슷하게 보여 역산이 불안정(염료 선택 재검토).
- **R²**: 염료마다 주로 흡수하는 채널(C→R, M→G, Y→B)에서 0.98 이상.

```bash
python -m cmysim.camera_tools check --cmy 10,5,8
```
보정에 쓰지 않은 혼합액(예 C 10, M 5, Y 8 mg/L)을 만들어 역산이 맞는지 확인합니다. 오차 ±1 mg/L 안이면 성공.

```bash
python -m cmysim.camera_tools target --save target.json
```
실험에서 맞추려는 목표 시료(기준 색 용액)를 같은 카메라로 찍어 목표 RGB 와 목표 농도를 저장합니다. hex 로 주는 것보다 정확합니다.

## 만들어진 파일

| 파일 | 내용 | 쓰는 곳 |
|---|---|---|
| `camera.json` | 카메라 종류, 노출·게인·WB, ROI | camera_tools, ai_node_main |
| `camera_ref.npy` | ROI 픽셀별 기준 밝기 I0 | 흡광도 계산(광원 불균일 보정) |
| `calib_samples.json` | 보정 시료 측정값 | fit 입력 |
| **`calibration.json`** | E(3×3), I0, γ, 글레어, κ, 시료 목록 | **ai_node_main, 시뮬레이터 UI 의 '카메라 보정' 카드** |
| `target.json` | 목표 시료 RGB·농도 | ai_node_main --target-file |

`calibration.json` 을 워크스테이션으로 복사해 UI 의 **카메라 보정 → 파일 선택 → 불러오기** 로 올리면 시뮬레이터가 실제 카메라 기준으로 색을 계산합니다.

## 자주 하는 실수

- 자동 노출을 켠 채 찍음 → 농도마다 밝기 기준이 달라져 E 가 틀어짐. 반드시 수동 고정.
- 기준 영상을 찍은 뒤 조명·카메라 위치를 바꿈 → reference 부터 다시.
- 염료를 넣고 바로 찍음 → 섞이기 전이라 농도가 고르지 않음. 혼합시간 × 3 대기.
- 기포가 ROI 에 들어감 → 교반을 잠시 낮추거나 ROI 를 옮김.
- 흡광도 1 이상(짙은 농도) 까지 보정 → 선형 가정이 깨짐. 실험 농도 범위 안에서만.
