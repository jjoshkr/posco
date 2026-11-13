# io_interface — 인터페이스 보드 KiCad 프로젝트

I/O 노드(Pi 5 + MCC 152/118) 와 현장(펌프 접점, 24 V 솔레노이드, 압력 트랜스미터) 사이의 보드. 회로 설명과 조립 순서는 [../../docs/ASSEMBLY.md](../../docs/ASSEMBLY.md).

| 파일 | 내용 |
|---|---|
| `io_interface.kicad_pro` / `io_interface.kicad_sch` | KiCad 프로젝트와 회로도 (KiCad 7 형식, KiCad 7/8/9 에서 열림). 심볼은 파일 안에 포함되어 외부 라이브러리가 없어도 열림 |
| `io_interface_preview.svg` | 회로도 간이 미리보기 (KiCad 없이 보는 용도) |
| `BOM.md` | 부품표 (참조·값·풋프린트) |

## 여는 법
1. KiCad 실행 → File → Open Project → `io_interface.kicad_pro`.
2. 회로도 편집기에서 **Inspect → Electrical Rules Checker** 실행. 글로벌 라벨로만 연결되어 있어 "라벨이 한 번만 쓰임" 경고는 없어야 하고, 전원 네트(+24V, +5V, GND_*)에 `PWR_FLAG` 를 붙이라는 경고가 나오면 Place → Power Symbol → PWR_FLAG 를 해당 라벨 옆에 두고 선으로 잇는다.
3. **Tools → Update PCB from Schematic (F8)** → PCB 편집기로 부품을 넘긴다. 풋프린트는 모두 KiCad 표준 라이브러리 이름이라 바로 배치된다.

## 회로 블록
- **[A] 입력** J1: MCC 152 DIO 8선 (P-101/102/103 펄스, XV-101/102/103, RUN_ENABLE, GND). J2: Pi 5 V.
- **[B] 펌프 펄스 ×3**: DIO → 470 Ω → PC817 → 펌프 External contact. 상태 LED.
- **[C] 운전 허가**: DIO_RUN → 2N7000 → PC817 ×3 (5 V, 330 Ω) → 각 펌프 Pause. 펌프 설정은 "닫힘 = 운전".
- **[D] 솔레노이드 ×3**: DIO → 100 Ω → IRLZ44N (10 kΩ 풀다운) → 24 V 코일, 1N4007 플라이백. 상태 LED.
- **[E] 24 V 전원**: 퓨즈 2 A, 100 nF, 24 V 표시 LED, GND_PI–GND_24 한 점 결합(R30 0 Ω).
- **[F] 압력 트랜스미터**: +24V → PT → PT_LOOP → 250 Ω 0.1 % → GND_24. PT_LOOP 를 MCC 118 CH4 로 (1–5 V). 100 nF + 5.1 V 제너 보호. PT 3개면 [F] 를 복제해 CH5/CH6.

## PCB 배치 원칙
왼쪽 Pi 쪽(3.3/5 V), 오른쪽 24 V 쪽. PC817 열이 경계. 24 V 트랙 1.0 mm, 신호 0.3 mm, GND 는 양면 영역(zone)으로 GND_PI 와 GND_24 를 따로 두고 R30 에서만 만남. 외곽 80×90 mm, M3 구멍 4개.

## 다시 생성
이 회로도는 스크립트로 만들어졌다. 채널 수나 핀을 바꾸려면 KiCad 에서 직접 고치면 된다 (이후에는 KiCad 파일이 원본).
