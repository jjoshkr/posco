# Pi ↔ 워크스테이션 연결 처음부터 — 순서, LED 로 보는 상태, 릴레이 HAT 만으로 자동제어

대상: Raspberry Pi 5 (호스트 `powerxlab`, 사용자 `powerx`) + Relay_module_v1 HAT + 32CH 릴레이 보드, 워크스테이션 Ubuntu. MCC 보드는 아직 없음.

## 1. 준비물 체크

| 항목 | 기준 |
|---|---|
| Pi 전원 | **5 V 5 A (27 W) 공식 어댑터**. 65 W PD 충전기는 Pi 혼자일 때만(5 V 3 A). 18 W·PC USB 는 불가 |
| SD 카드 | 이미저로 구운 것. 설정 확인: 호스트 `powerxlab`, 사용자 `powerx`, **Wi-Fi 입력**, **SSH 사용** |
| 네트워크 선 | LAN 케이블 1개 (Pi ↔ 워크스테이션 직결 권장, 가장 확실) |
| HAT 전원 | 전원 박스 5 V → HAT J3 (빨강 +5V, 검정 GND, 멀티미터로 극성 확인 완료) |
| 하지 말 것 | Pi USB-A 와 PC 를 USB 케이블로 잇기(역전압). 릴레이 보드 J34 에 220 V 넣기 |

## 2. 연결 순서 (처음부터)

**A. Pi 혼자 켜기** — HAT 빼고, 전원 박스 꺼 두고
1. SD 카드를 끝까지 꽂는다.
2. LAN 케이블을 Pi 와 워크스테이션 이더넷 포트에 직결한다.
3. 27 W 어댑터를 꽂는다. LED 를 본다 (3절).
4. 워크스테이션에서 유선 연결을 **공유 모드**로 (한 번만):

```bash
nmcli dev status
nmcli con mod "Wired connection 1" ipv4.method shared && nmcli con up "Wired connection 1"
```

   연결 이름이 다르면 `nmcli dev status` 의 CONNECTION 열 이름을 쓴다. Pi 의 LAN 선을 뽑았다 꽂는다.
5. 2~3분 뒤 (첫 부팅은 중간에 한 번 재부팅):

```bash
ping -c 3 powerxlab.local
```

   안 되면 IP 로:

```bash
ip neigh show | grep 10.42
ssh powerx@10.42.0.X
```

6. 접속되면 Pi 안에서 고정 IP 와 I2C, 코드:

```bash
sudo nmcli con add type ethernet ifname eth0 con-name lab ipv4.method manual ipv4.addresses 192.168.10.2/24 ipv4.gateway 10.42.0.1 ipv4.dns 8.8.8.8
sudo raspi-config nonint do_i2c 0
sudo apt update && sudo apt install -y i2c-tools git python3-pip
sudo usermod -aG i2c $USER
git clone https://github.com/jjoshkr/posco -b claude/wonderful-dirac-1zfw8d && cd posco/dye_color_matching
pip install --break-system-packages smbus2 pyzmq numpy
sudo reboot
```

   재부팅 뒤 워크스테이션 유선 어댑터를 수동 192.168.10.1/24 로 바꾸면 `ssh powerx@192.168.10.2` 로 들어간다. (공유 모드를 유지하려면 고정 IP 줄을 생략하고 10.42.0.X 로 계속 써도 된다.)

**B. HAT 올리기** — Pi 전원 뺀 뒤
1. HAT 를 40핀에 끝까지 꽂는다. 점퍼: U1 쪽 JP1~3 비움(0x20), U2 쪽 JP4 꽂음(0x24).
2. J3 에 전원 박스 5 V (아직 AC 는 끔). 릴레이 보드 리본은 아직 안 꽂아도 됨.
3. Pi 켜고 → 접속 → 전원 박스 AC 켬 → J3 5.0~5.1 V 확인.

```bash
i2cdetect -y 1
cd ~/posco/dye_color_matching && python -m cmysim.relay_ctl scan
```

   `20` 과 `24` 가 보여야 한다.

**C. 릴레이 보드** — 모두 끈 뒤 리본(1번 핀 방향) → J34 비운 채 → 켜고 4절.

## 3. LED 로 보는 상태 (Pi 5 는 LED 하나가 빨강/초록으로 바뀜)

| LED | 뜻 | 할 일 |
|---|---|---|
| **빨강 고정, 초록 전혀 없음** | 전원은 오는데 프로세서가 시작을 못 함. 거의 항상 **전압 부족**(18 W·PC USB·긴 케이블). 드물게 SD 없음/EEPROM | 27 W 어댑터로 교체. HAT·USB 장치 빼고 Pi 혼자 재시도. 그래도면 SD 다시 굽기 |
| **빨강 ↔ 초록 번갈아, 불규칙** | 부팅을 시작했다가 전압이 떨어져 멈추기를 반복 | 전원 교체(위와 같음). HAT 의 J3 가 Pi 5 V 와 섞여 있지 않은지 확인 |
| **빨강 + 초록이 일정한 패턴으로 반복** (예: 길게 4번 짧게 4번) | 부트 파일을 못 찾음(SD 안 읽힘, 이미지 불량) | SD 뺐다 끝까지 다시 꽂기. 이미저로 다시 굽기(쓰기 완료 메시지 확인) |
| **초록 불규칙하게 깜빡** | 정상 부팅 중 / 디스크 접근 | 2~3분 기다렸다가 `ping powerxlab.local` |
| **초록 고정 (깜빡임 없음)** | 부팅 끝나고 유휴 | 접속 시도. 안 되면 네트워크 쪽(4·5번) |
| **불이 전혀 안 들어옴** | 전원 없음 | 케이블·어댑터·멀티탭 스위치 |

HDMI 모니터가 있으면 붙여 두면 가장 빠르다. 부팅 실패 시 Pi 5 가 화면에 원인(진단 페이지)을 띄운다.

## 4. 릴레이 HAT 만으로 터미널 자동제어

### 4-1. 수동·순차 (relay_ctl)

```bash
cd ~/posco/dye_color_matching
cp hardware/io_node_rev_b.json io_node.json          # 밸브 ↔ 릴레이 번호 매핑 (XV-101 → 릴레이 1 …)
python -m cmysim.relay_ctl scan                      # 0x20, 0x24
python -m cmysim.relay_ctl status
python -m cmysim.relay_ctl on 1                      # 릴레이 1 ON (Enter 로 끄고 종료)
python -m cmysim.relay_ctl valve XV-102 open         # 이름으로
python -m cmysim.relay_ctl hold 1 3                  # 3 초 켰다 끔
python -m cmysim.relay_ctl walk 1 1 9 17 25          # 네 ULN 확인
python -m cmysim.relay_ctl seq "XV-101:5,XV-102:5,XV-103:5" --repeat 2   # 밸브 세 개를 5 초씩 차례로, 2회
python -m cmysim.relay_ctl shell                     # 대화형
```

매 조작 뒤 칩을 되읽어 명령과 다르면 `⚠` 로 알려 준다(칩 리셋, 납땜 브리지). 종료·Ctrl+C 때 전부 OFF. 주소가 다르면 `--addr 0x20 0x21`.

### 4-2. 제어 루프 전체를 돌리되 밸브만 실제로 (relay-only)

공정·펌프·센서는 시뮬레이션이고, 제어기가 내는 **밸브 열림/닫힘과 운전 허가만 진짜 릴레이**로 나간다. AI 노드(또는 UI 대신 ai_node_main)가 PLAN→PRIME 에서 밸브를 열고 DOSE 끝에 닫는 것을 릴레이 소리로 확인할 수 있다.

Pi 터미널 1 (I/O 노드):

```bash
python -m cmysim.io_node_main run --sim --sim-camera --relay-only -v
```

Pi 터미널 2 (AI 노드 역할, 같은 Pi 에서). 카메라는 I/O 노드가 보내는 시뮬레이션 영상(telemetry)을 쓴다:

```bash
echo '{"kind": "telemetry"}' > camera.json
python -m cmysim.ai_node_main --io-ip 127.0.0.1 --camera camera.json --target "#5A8F7B" --mode closed --log run_relay.csv
```

PRIME 에서 릴레이 1·2·3 이 "딸깍" 켜지고, DOSE 가 끝나면 꺼지고, DONE 에서 SAFE 로 전부 OFF 된다. 터미널 1 에서 Ctrl+C 하면 SAFE 순서로 끈다.

### 4-3. MCC 보드가 오면
`io_node.json` 은 그대로 두고 `--sim --relay-only` 를 `--pump-mode pulse` 로 바꾸면 된다. 주소(118=0, 152a=2, 152b=3, 134=4)와 I2C 주소 충돌(0x22·0x23 은 MCC 152) 은 [BOARDS.md](BOARDS.md) 참고.

## 5. 접속이 안 될 때 (초록인데 ping 실패)

| 증상 | 확인 |
|---|---|
| `Name or service not known` | 워크스테이션과 Pi 가 다른 망. 2-A 4번(공유 모드) 또는 같은 Wi-Fi 로 |
| ping 은 되는데 ssh 거부 | 이미저에서 SSH 를 안 켠 것. 다시 굽기 |
| `Connection timed out` (192.168.10.2) | 아직 고정 IP 안 넣음. `.local` 또는 10.42.0.X 로 |
| 두 Pi 를 같이 켬 | 둘 다 `powerxlab` 이면 충돌. 하나만 켜고, 두 번째는 접속해서 `sudo hostnamectl set-hostname ainode` |
