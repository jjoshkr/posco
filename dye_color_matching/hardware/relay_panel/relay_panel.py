#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
32채널 릴레이 보드 테스트 패널
(Raspberry Pi 5 + Relay_module_v1 HAT + Relay_40pin_32CH 릴레이 보드)

■ 실행
    python3 relay_panel.py                  제어패널 (GUI)
    python3 relay_panel.py --cli            모니터 없이 SSH에서 쓰는 텍스트 모드
    python3 relay_panel.py --sim            보드 없이 화면만 확인 (PC에서도 실행됨)
    python3 relay_panel.py --addr 0x24 0x25 --installed all

■ 필요한 것
    파이썬 표준 라이브러리만 씁니다. I2C는 리눅스의 /dev/i2c-N 장치 파일을 직접 다루므로
    smbus 같은 패키지를 설치할 필요가 없습니다.
    GPIO27(RST) 제어에만 Raspberry Pi OS에 기본으로 들어 있는 gpiozero를 쓰고,
    gpiozero가 없으면 RST 시험만 건너뛰고 나머지는 그대로 동작합니다.

■ 하드웨어 (두 KiCad 프로젝트의 넷리스트에서 확인한 내용)
    1) I/O 확장 칩은 MCP23017 2개. 둘 다 Pi의 I2C-1 버스(GPIO2 = SDA, GPIO3 = SCL)에 연결.
       "시리얼 통신"은 이 I2C 버스를 뜻합니다.

    2) I2C 주소 = 0x20 + A2×4 + A1×2 + A0
       점퍼를 꽂으면 그 비트가 1 (3.3 V에 연결), 빼면 0 (10 kΩ 풀다운).
           모듈 1 = HAT의 U1 = 릴레이  1~16 :  JP3 = A0,  JP2 = A1,  JP1 = A2
           모듈 2 = HAT의 U2 = 릴레이 17~32 :  JP6 = A0,  JP5 = A1,  JP4 = A2
       ※ 점퍼를 모두 뺀 상태면 두 칩이 똑같이 0x20이 되어 충돌합니다.
          한쪽은 반드시 다르게 설정해야 합니다 (기본값: 모듈 1 = 0x20, 모듈 2 = 0x21 → JP6만 꽂음).

    3) 칩 하나 안에서 "포트 B"가 앞 번호입니다 (포트 A가 아님).
           릴레이  1~ 8 = U1 GPB0~7 → ULN2803A U3 → 40핀 헤더  1, 2, 3, 4, 6, 7, 8, 9번
           릴레이  9~16 = U1 GPA0~7 → ULN2803A U4 → 40핀 헤더 11,12,13,14,16,17,18,19번
           릴레이 17~24 = U2 GPB0~7 → ULN2803A U5 → 40핀 헤더 21,22,23,24,26,27,28,29번
           릴레이 25~32 = U2 GPA0~7 → ULN2803A U6 → 40핀 헤더 31,32,33,34,36,37,38,39번
       (40핀 헤더의 5, 10, 15, ... 40번은 릴레이 코일용 +5 V)

    4) 극성: MCP 출력 1 → ULN2803A가 코일 전류를 GND로 흘림 → 릴레이 ON.
       전원을 켠 직후 MCP 핀은 입력(하이 임피던스)이므로 릴레이는 모두 꺼져 있습니다.

    5) 릴레이 코일 5 V는 HAT의 J3 단자로만 들어옵니다 (Pi의 5 V 핀과 연결되어 있지 않음).
       J3에 5 V가 없으면 통신은 되지만 릴레이는 붙지 않습니다.

    6) MCP23017 RESET = Pi GPIO27 (HAT에 10 kΩ 풀업). Low = 리셋.

■ 코드 구성 (위에서 아래로)
    보드 정의          주소·핀 대응 등 하드웨어 상수와 channel_info()
    I2C 버스           LinuxI2C (실제 버스) / SimBus (가짜 버스)
    RST 라인           GpioResetLine (GPIO27) / SimResetLine
    RelayBoard         연결·자가진단, 릴레이 ON/OFF, 되읽기 검사  ← 다른 프로그램에서 가져다 쓸 수 있는 부분
    제어패널 (GUI)      build_panel() 안의 Panel 클래스 (tkinter)
    텍스트 모드         run_cli()
    시작               main()
"""
import argparse
import atexit
import errno
import os
import signal
import sys
import time

# ══════════════════════════════════════════════════════════════════════════
#  보드 정의  ―  하드웨어가 바뀌면 이 구역만 고치면 됩니다
# ══════════════════════════════════════════════════════════════════════════

# MCP23017이 가질 수 있는 주소 범위. 상위 4비트는 0100으로 고정이고 하위 3비트가 A2 A1 A0.
ADDR_MIN, ADDR_MAX = 0x20, 0x27

# 프로그램을 옵션 없이 실행했을 때 쓰는 주소 (모듈 1, 모듈 2).
DEFAULT_ADDRS = (0x20, 0x21)

# 지금 릴레이를 납땜해 둔 채널. 패널에서 파란 테두리로 표시되고 순차 테스트의 기본 대상이 됩니다.
# 1, 9, 17, 25는 ULN2803A 4개(U3~U6)의 첫 번째 출력이라, 드라이버 칩 4개를 하나씩 확인하게 됩니다.
DEFAULT_INSTALLED = (1, 9, 17, 25)

# MCP23017 두 개의 RESET 핀이 함께 연결된 Pi의 GPIO 번호 (40핀 헤더 13번 핀).
RST_GPIO = 27

# 모듈(= MCP23017 한 개) 정의.
#   first   : 이 모듈이 맡는 첫 릴레이 번호 (16개를 맡음)
#   jumpers : 주소 핀 (A0, A1, A2) 순서로, 각각에 연결된 점퍼 이름
MODULES = (
    {"name": "모듈 1", "chip": "U1", "first": 1, "jumpers": ("JP3", "JP2", "JP1")},
    {"name": "모듈 2", "chip": "U2", "first": 17, "jumpers": ("JP6", "JP5", "JP4")},
)

# 릴레이 8개 묶음(1~8, 9~16, 17~24, 25~32)마다 ULN2803A 드라이버가 하나씩 있습니다.
ULN_OF_GROUP = ("U3", "U4", "U5", "U6")

# 한 묶음 안에서 8개 출력이 나가는 40핀 헤더 핀 번호 (묶음마다 +10).
# 5번째, 10번째 자리는 +5 V라서 건너뜁니다.
HEADER_PINS = (1, 2, 3, 4, 6, 7, 8, 9)

# ── MCP23017 레지스터 주소 (IOCON.BANK = 0, 전원 투입 시 기본 배치) ──
# 이 배치에서는 A포트 레지스터 바로 다음 주소가 같은 기능의 B포트 레지스터입니다.
# 그래서 A 주소에 2바이트를 연달아 쓰면 A, B가 한 번의 전송으로 함께 써집니다.
IODIRA = 0x00    # 방향. 비트 1 = 입력, 0 = 출력. 리셋 후 0xFF (전부 입력)
IPOLA = 0x02     # 입력 극성 반전. 출력에는 영향이 없어 "쓰기/읽기 시험용"으로 씁니다
GPINTENA = 0x04  # 핀 변화 인터럽트 허용. 쓰지 않으므로 0
IOCON = 0x0A     # 칩 설정. 0x0A와 0x0B가 같은 레지스터
GPPUA = 0x0C     # 입력 풀업. 쓰지 않으므로 0
GPIOA = 0x12     # 읽으면 "핀의 실제 전압 레벨"
OLATA = 0x14     # 출력 래치. 여기에 쓴 값이 출력 핀으로 나갑니다

# IOCON의 ODR 비트: INT 출력을 오픈드레인으로 바꿉니다.
# HAT에서 두 칩의 INTA끼리, INTB끼리 한 선으로 묶여 Pi(GPIO22, GPIO23)로 갑니다.
# 기본값(푸시풀)이면 한 칩이 Low, 다른 칩이 High를 낼 때 서로 밀게 되므로 오픈드레인으로 해 둡니다.
# (이 프로그램은 인터럽트 자체를 쓰지 않습니다.)
IOCON_ODR = 0x04


def channel_info(n):
    """릴레이 번호(1~32)가 어느 칩의 어느 핀으로 나가는지 계산해 dict로 돌려준다.

    돌려주는 값
        module      0 = 모듈 1(U1), 1 = 모듈 2(U2)
        bit         모듈 안에서의 비트 번호 0~15. 0~7 = 포트 B, 8~15 = 포트 A
        port, pin   MCP23017 핀 이름 (예: 'B', 0 → GPB0)
        uln         이 채널을 구동하는 ULN2803A (U3~U6)
        uln_out     그 ULN2803A의 몇 번째 출력인지 (1~8)
        header_pin  HAT의 J2 / 릴레이 보드의 J33 (40핀 헤더) 핀 번호
    """
    if not 1 <= n <= 32:
        raise ValueError("릴레이 번호는 1~32입니다: %r" % (n,))
    # 16개씩 나누면 모듈 번호와 모듈 안의 비트 번호가 나온다. 예) 릴레이 18 → 모듈 1(두 번째), 비트 1
    module, bit = divmod(n - 1, 16)
    # 8개씩 나누면 ULN2803A 묶음 번호와 묶음 안의 위치가 나온다.
    group, pos = divmod(n - 1, 8)
    return {"relay": n, "module": module, "bit": bit,
            "port": "B" if bit < 8 else "A",       # 앞 8개가 포트 B (보드 배선이 그렇게 되어 있음)
            "pin": bit % 8,
            "uln": ULN_OF_GROUP[group], "uln_out": pos + 1,
            "header_pin": group * 10 + HEADER_PINS[pos]}


def describe(n, addrs):
    """릴레이 n의 신호 경로를 한 줄 문장으로 만든다 (멀티미터로 따라가며 확인할 때 사용)."""
    c = channel_info(n)
    mod = MODULES[c["module"]]
    return ("릴레이 %d:  %s(0x%02X) HAT %s GP%s%d → HAT %s O%d → 40핀 헤더 %d번 → 릴레이 보드 U%d → 단자 J%d"
            % (n, mod["name"], addrs[c["module"]], mod["chip"], c["port"], c["pin"],
               c["uln"], c["uln_out"], c["header_pin"], n, n))


def jumper_text(module, addr):
    """주소를 만들려면 점퍼를 어떻게 해야 하는지 문자열로 돌려준다.  ● = 꽂음, ○ = 뺌.

    예) jumper_text(1, 0x21) → 'JP4 ○   JP5 ○   JP6 ●'
    """
    bits = addr - ADDR_MIN                 # 0~7. 비트0 = A0, 비트1 = A1, 비트2 = A2
    a0, a1, a2 = MODULES[module]["jumpers"]
    marks = {a0: bits & 1, a1: bits & 2, a2: bits & 4}
    # 보드 실크의 번호 순서(JP1, JP2, JP3 ...)대로 보여 준다.
    return "   ".join("%s %s" % (name, "●" if marks[name] else "○") for name in sorted(marks))


class RelayError(Exception):
    """릴레이 조작이 실패했을 때 내는 예외 (미연결, I2C 오류, 잘못된 주소 설정)."""


# ══════════════════════════════════════════════════════════════════════════
#  I2C 버스
#  두 클래스 모두 write(주소, 바이트들) / read(주소, 개수) / probe(주소) / close() 를 제공합니다.
#  RelayBoard는 어느 쪽인지 모른 채 이 네 가지만 씁니다.
# ══════════════════════════════════════════════════════════════════════════
class LinuxI2C:
    """리눅스 i2c-dev 장치 파일(/dev/i2c-N)을 직접 쓰는 I2C 버스.

    동작 원리: 장치 파일을 연 다음 ioctl(I2C_SLAVE, 주소)로 상대 칩을 고르면,
    그 뒤의 write()는 I2C 쓰기 전송 한 번, read()는 I2C 읽기 전송 한 번이 됩니다.
    """
    I2C_SLAVE = 0x0703                     # <linux/i2c-dev.h>의 ioctl 번호: "다음 전송의 상대 주소 지정"

    def __init__(self, busnum):
        import fcntl                       # 리눅스 전용 모듈. --sim으로 윈도우에서 돌릴 때를 위해 여기서 불러온다
        self._ioctl = fcntl.ioctl
        self.name = "/dev/i2c-%d" % busnum
        try:
            self.fd = os.open(self.name, os.O_RDWR)
        except FileNotFoundError:
            # 장치 파일이 없다 = I2C 인터페이스가 꺼져 있다
            raise SystemExit("%s 가 없습니다. I2C를 켜세요:  sudo raspi-config nonint do_i2c 0  (필요하면 재부팅)"
                             % self.name)
        except PermissionError:
            raise SystemExit("%s 권한이 없습니다:  sudo usermod -aG i2c $USER  후 다시 로그인" % self.name)

    def write(self, addr, data):
        """addr 칩에 data를 쓴다. MCP23017에서는 첫 바이트가 레지스터 주소, 나머지가 값이다.
        칩이 응답(ACK)하지 않으면 OSError가 난다."""
        self._ioctl(self.fd, self.I2C_SLAVE, addr)
        os.write(self.fd, bytes(data))

    def read(self, addr, n):
        """addr 칩에서 n바이트를 읽는다. MCP23017은 직전에 지정한 레지스터부터 차례로 내보낸다."""
        self._ioctl(self.fd, self.I2C_SLAVE, addr)
        return os.read(self.fd, n)

    def probe(self, addr):
        """그 주소에 칩이 있는지 확인한다 (1바이트 읽기를 시도해 응답이 오면 True).
        읽기만 하므로 어떤 칩이든 상태를 바꾸지 않는다."""
        try:
            self.read(addr, 1)
            return True
        except OSError:
            return False

    def close(self):
        os.close(self.fd)


class SimBus:
    """보드 없이 동작을 흉내 내는 가짜 버스. 주어진 주소마다 MCP23017 하나가 있는 것처럼 행동한다.

    --sim 옵션으로 화면을 미리 볼 때와, 코드 검증(레지스터에 맞는 값이 써지는지)에 쓴다.
    실제 칩의 동작 중 이 프로그램이 의존하는 부분만 구현했다:
      · 레지스터 22개와 "주소 포인터 자동 증가" (연속 읽기/쓰기)
      · GPIO 레지스터를 읽으면 핀 레벨이 나옴 (출력 핀 = 래치 값, 입력 핀 = 0)
      · 리셋하면 IODIR = 0xFF, 나머지 0
    """
    name = "시뮬레이션"
    NREG = 0x16                            # 레지스터 개수 (0x00 ~ 0x15)

    def __init__(self, addrs):
        self.chips = {a: self._fresh() for a in addrs}   # 주소 → 레지스터 값 목록
        self.ptr = {a: 0 for a in addrs}                 # 주소 → 현재 레지스터 포인터
        self.stuck_low = {}                # 고장 흉내용: {주소: 16비트 마스크} → 그 핀은 항상 Low로 읽힘

    def _fresh(self):
        """리셋 직후의 레지스터 값."""
        r = [0] * self.NREG
        r[0] = r[1] = 0xFF                 # IODIRA, IODIRB = 전부 입력
        return r

    def reset_all(self):
        """RESET 핀에 Low 펄스가 들어온 것처럼 모든 칩을 초기화한다."""
        for a in self.chips:
            self.chips[a] = self._fresh()

    def _chip(self, addr):
        if addr not in self.chips:         # 없는 주소 → 실제 버스처럼 "응답 없음" 오류
            raise OSError(errno.EREMOTEIO, "Remote I/O error (no ACK)")
        return self.chips[addr]

    def probe(self, addr):
        return addr in self.chips

    def write(self, addr, data):
        r = self._chip(addr)
        p = data[0] % self.NREG            # 첫 바이트 = 레지스터 주소
        for v in data[1:]:                 # 나머지 = 값. 쓸 때마다 포인터가 1씩 증가
            if p in (0x0A, 0x0B):
                r[0x0A] = r[0x0B] = v & 0xFE          # IOCON은 두 주소가 한 레지스터, 비트0은 항상 0
            elif p in (0x12, 0x13):
                r[p + 2] = v & 0xFF                   # GPIO에 쓰면 실제로는 OLAT가 바뀐다
            else:
                r[p] = v & 0xFF
            p = (p + 1) % self.NREG
        self.ptr[addr] = p

    def read(self, addr, n):
        r = self._chip(addr)
        p = self.ptr[addr]
        out = []
        for _ in range(n):
            if p in (0x12, 0x13):          # GPIOA / GPIOB = 핀 레벨
                port = p - 0x12                       # 0 = A, 1 = B
                # 출력으로 설정된 핀(IODIR 비트 0)은 래치 값이 그대로 나오고,
                # 입력 핀은 ULN2803A 입력 쪽 저항 때문에 Low로 읽힌다.
                v = r[0x14 + port] & ~r[port] & 0xFF
                stuck = self.stuck_low.get(addr, 0)
                v &= ~((stuck >> 8) if port == 0 else stuck) & 0xFF
                v ^= r[0x02 + port]                   # IPOL 비트가 1이면 읽은 값이 뒤집힌다
            else:
                v = r[p]
            out.append(v)
            p = (p + 1) % self.NREG
        self.ptr[addr] = p
        return bytes(out)

    def close(self):
        pass


# ══════════════════════════════════════════════════════════════════════════
#  RST 라인
# ══════════════════════════════════════════════════════════════════════════
class GpioResetLine:
    """MCP23017 RESET 핀 (Pi GPIO27).  High = 정상 동작, Low = 리셋.

    HAT에는 10 kΩ 풀업 저항만 있습니다. Pi의 GPIO27을 입력으로 내버려 두면 Pi 내부 풀다운과
    전압이 나뉘어 High 레벨의 여유가 줄어들 수 있으므로, 프로그램이 도는 동안에는 Pi가
    출력 High로 확실하게 잡아 줍니다.
    """

    def __init__(self, gpio):
        # gpiozero는 Pi 5의 GPIO 칩(RP1)을 알아서 찾아 준다. 없거나 Pi가 아니면 여기서 예외가 난다.
        from gpiozero import DigitalOutputDevice
        self.dev = DigitalOutputDevice(gpio, initial_value=True)   # 처음부터 High (리셋 해제 상태)

    def release(self):
        """리셋 해제 상태(High)로 둔다."""
        self.dev.on()

    def pulse(self):
        """Low 펄스를 한 번 준다 → 두 칩이 전원 투입 직후 상태로 돌아가고 릴레이는 모두 꺼진다.
        칩이 요구하는 최소 펄스 폭은 1 µs라서 5 ms면 충분하다."""
        self.dev.off()
        time.sleep(0.005)
        self.dev.on()
        time.sleep(0.005)

    def close(self):
        self.dev.close()


class SimResetLine:
    """SimBus용 가짜 RST 라인."""

    def __init__(self, bus):
        self.bus = bus

    def release(self):
        pass

    def pulse(self):
        self.bus.reset_all()

    def close(self):
        pass


# ══════════════════════════════════════════════════════════════════════════
#  RelayBoard  ―  MCP23017 2개 = 릴레이 32개
#
#  다른 프로그램에서 쓰는 예:
#      board = RelayBoard(LinuxI2C(1), (0x20, 0x21))
#      board.connect()          # 자가진단 + 초기화 (모두 OFF)
#      board.set(9, True)       # 릴레이 9 ON
#      board.all_off()
# ══════════════════════════════════════════════════════════════════════════
class RelayBoard:
    """릴레이 32개의 상태를 관리하고 MCP23017 두 개에 써 넣는다.

    state[m]  모듈 m에 "명령한" 16비트 값. 비트 0~7 = GPB0~7, 비트 8~15 = GPA0~7. 1 = 릴레이 ON
    online[m] 모듈 m이 초기화되어 지금 제어 가능한지
    seen[m]   현재 주소에서 모듈 m이 한 번이라도 초기화된 적이 있는지.
              all_off()는 seen인 모듈에만 쓴다 (MCP23017임을 확인한 적 없는 주소에는 쓰지 않기 위해).
    """

    def __init__(self, bus, addrs=DEFAULT_ADDRS, rst=None):
        self.bus = bus
        self.addrs = list(addrs)           # [모듈 1 주소, 모듈 2 주소]
        self.rst = rst                     # RST 라인 객체. None이면 리셋 기능 없이 동작
        self.state = [0, 0]
        self.online = [False, False]
        self.seen = [False, False]

    # ───────── 레지스터 접근 ─────────
    def _wr(self, m, reg, *vals):
        """모듈 m의 레지스터 reg부터 vals를 차례로 쓴다. I2C로 [reg, 값, 값 ...]이 한 번에 나간다."""
        self.bus.write(self.addrs[m], bytes((reg,) + vals))

    def _rd(self, m, reg, n=1):
        """모듈 m의 레지스터 reg부터 n바이트를 읽는다.
        먼저 레지스터 주소만 써서 칩 안의 포인터를 옮기고, 이어서 읽는다."""
        self.bus.write(self.addrs[m], bytes((reg,)))
        return self.bus.read(self.addrs[m], n)

    def scan(self):
        """0x20~0x27 가운데 응답하는 주소 목록. 읽기만 하므로 안전하다."""
        return [a for a in range(ADDR_MIN, ADDR_MAX + 1) if self.bus.probe(a)]

    def set_addrs(self, addrs):
        """두 모듈의 주소를 바꾼다. 바꾸기 전에 옛 주소의 릴레이를 모두 끄고, 연결 상태를 초기화한다.
        바꾼 뒤에는 connect()를 다시 불러야 한다."""
        self.all_off()
        self.addrs[:] = list(addrs)
        self.online = [False, False]
        self.seen = [False, False]

    # ───────── 연결 + 자가진단 ─────────
    def connect(self):
        """두 칩을 찾아 시험하고 16핀을 모두 출력으로 설정한다. 릴레이는 모두 꺼진 상태로 시작한다.

        하는 일 (순서대로)
          1. 각 주소에 응답이 있는지 확인
          2. 읽기만으로 MCP23017이 맞는지 확인 (엉뚱한 장치에 쓰지 않기 위해)
          3. RST 라인 시험: 레지스터에 표시를 써 두고 리셋 펄스 후 지워졌는지 확인
          4. 쓰기/읽기 시험: 출력에 영향이 없는 레지스터에 무늬를 썼다가 되읽기
          5. 출력 래치를 0으로 만든 뒤 방향을 출력으로 전환
          6. 되읽기 검사 (verify)

        돌려주는 값: [(수준, 문장), ...]   수준은 'ok' / 'info' / 'warn' / 'err'
        """
        log = []
        self.online = [False, False]
        self.state = [0, 0]
        if self.addrs[0] == self.addrs[1]:
            # 주소가 같으면 두 칩이 같은 명령에 동시에 반응해 릴레이 1~16과 17~32가 함께 움직인다.
            raise RelayError("두 모듈의 주소가 같습니다 (0x%02X). 한쪽 점퍼를 바꿔 서로 다르게 하세요." % self.addrs[0])
        if self.rst:
            self.rst.release()             # 혹시 Low로 남아 있었다면 리셋에서 풀어 준다

        # ── 1, 2단계: 응답 확인 + MCP23017인지 확인 ──
        present = []                       # 통과한 모듈 번호
        for m, mod in enumerate(MODULES):
            tag = "%s (0x%02X)" % (mod["name"], self.addrs[m])
            if not self.bus.probe(self.addrs[m]):
                log.append(("err", "%s: 응답 없음. 점퍼(%s), 납땜, 3.3 V를 확인하세요."
                            % (tag, jumper_text(m, self.addrs[m]))))
                continue
            try:
                # MCP23017은 0x0A와 0x0B가 같은 레지스터(IOCON)라 두 값이 같고, 비트0은 항상 0이다.
                # 레지스터가 8개뿐인 다른 I/O 확장 칩은 이 조건에 맞지 않는 경우가 많다.
                a, b = self._rd(m, IOCON)[0], self._rd(m, IOCON + 1)[0]
            except OSError as e:
                log.append(("err", "%s: 읽기 실패 (%s)" % (tag, e.strerror or e)))
                continue
            if a != b or a & 0x01:
                log.append(("err", "%s: MCP23017의 레지스터 모양이 아닙니다 (0x0A=0x%02X, 0x0B=0x%02X). "
                                   "다른 I2C 장치의 주소일 수 있어 쓰지 않았습니다." % (tag, a, b)))
                continue
            present.append(m)

        # ── 3단계: RST 라인 시험 ──
        # IPOLA에 0xA5를 써 두고 리셋 펄스를 준다. 리셋이 칩에 전달됐다면 0x00으로 지워져 있어야 한다.
        # 이 펄스로 두 칩이 전원 투입 직후 상태가 되므로, 이전 실행에서 켜 둔 릴레이도 여기서 꺼진다.
        if self.rst and present:
            try:
                for m in present:
                    self._wr(m, IPOLA, 0xA5)
                self.rst.pulse()
                for m in present:
                    cleared = self._rd(m, IPOLA)[0] == 0x00
                    log.append(("ok", "%s: RST(GPIO%d) 리셋 동작 확인" % (MODULES[m]["name"], RST_GPIO)) if cleared else
                               ("err", "%s: RST 펄스를 줘도 레지스터가 지워지지 않음 → GPIO%d~칩 18번 핀 배선 확인"
                                % (MODULES[m]["name"], RST_GPIO)))
            except OSError as e:
                log.append(("err", "RST 시험 중 I2C 오류 (%s)" % (e.strerror or e)))
        elif not self.rst:
            log.append(("info", "RST(GPIO%d)를 제어하지 않아 리셋 시험은 건너뜁니다." % RST_GPIO))

        # ── 4, 5, 6단계: 쓰기/읽기 시험 → 출력 설정 → 되읽기 ──
        for m in present:
            tag = "%s (0x%02X)" % (MODULES[m]["name"], self.addrs[m])
            try:
                # 다른 프로그램이 IOCON.BANK를 1로 바꿔 놓았을 경우의 대비.
                # BANK=1이면 0x05가 IOCON이라 0을 쓰면 BANK=0으로 돌아오고,
                # BANK=0이면 0x05는 GPINTENB(인터럽트 허용)라 0을 써도 해가 없다.
                self._wr(m, 0x05, 0x00)
                self._wr(m, IOCON, IOCON_ODR)          # 연속 주소 모드(기본) + INT 오픈드레인

                # 쓰기/읽기 시험. IPOL은 "입력을 읽을 때 뒤집을지"만 정하므로 릴레이에 영향이 없다.
                # 서로 반대 무늬(1010 0101 / 0101 1010)를 써서 모든 데이터 비트가 0과 1 양쪽으로 전달되는지 본다.
                bad = None
                for pat in ((0xA5, 0x5A), (0x5A, 0xA5), (0x00, 0x00)):   # 마지막에 0으로 되돌려 놓는다
                    self._wr(m, IPOLA, *pat)
                    back = tuple(self._rd(m, IPOLA, 2))
                    if back != pat:
                        bad = (pat, back)
                        break
                if bad:
                    log.append(("err", "%s: 쓰기/읽기 불일치 (쓴 값 %s, 읽은 값 %s) → SDA/SCL 납땜 확인"
                                % (tag, _hx(bad[0]), _hx(bad[1]))))
                    continue

                # 출력 설정. 순서가 중요하다:
                # 래치(OLAT)를 먼저 0으로 만들어 놓고 그다음에 방향(IODIR)을 출력으로 바꿔야,
                # 출력으로 바뀌는 순간에 릴레이가 잠깐 켜지는 일이 없다.
                self._wr(m, OLATA, 0x00, 0x00)         # OLATA, OLATB = 0 (모두 OFF)
                self._wr(m, GPINTENA, 0x00, 0x00)      # 인터럽트 사용 안 함
                self._wr(m, GPPUA, 0x00, 0x00)         # 풀업 사용 안 함
                self._wr(m, IODIRA, 0x00, 0x00)        # IODIRA, IODIRB = 0 (16핀 모두 출력)
            except OSError as e:
                log.append(("err", "%s: 초기화 중 I2C 오류 (%s)" % (tag, e.strerror or e)))
                continue
            self.online[m] = True
            self.seen[m] = True
            problems = self.verify(m)
            if problems:
                log.extend(("err", p) for p in problems)
            else:
                first = MODULES[m]["first"]
                log.append(("ok", "%s: 통신·레지스터 정상, 릴레이 %d~%d 제어 준비됨" % (tag, first, first + 15)))
        return log

    # ───────── 출력 ─────────
    def _write_state(self, m, value):
        """모듈 m의 16비트 출력 값을 칩에 쓴다. 성공했을 때만 state를 갱신한다."""
        if not self.online[m]:
            raise RelayError("%s이(가) 연결되어 있지 않습니다. '연결'을 먼저 하세요." % MODULES[m]["name"])
        try:
            # 상위 바이트(비트 8~15)가 포트 A, 하위 바이트(비트 0~7)가 포트 B.
            # OLATA(0x14)부터 2바이트를 쓰면 OLATA, OLATB가 한 번의 전송으로 함께 바뀐다.
            self._wr(m, OLATA, (value >> 8) & 0xFF, value & 0xFF)
        except OSError as e:
            self.online[m] = False         # 칩 상태를 알 수 없으므로 연결 끊김으로 처리
            raise RelayError("%s: I2C 쓰기 실패 (%s)" % (MODULES[m]["name"], e.strerror or e))
        self.state[m] = value

    def set(self, n, on):
        """릴레이 n(1~32)을 켜거나(True) 끈다(False). 같은 모듈의 다른 릴레이는 그대로 둔다."""
        c = channel_info(n)
        m, mask = c["module"], 1 << c["bit"]
        self._write_state(m, (self.state[m] | mask) if on else (self.state[m] & ~mask))

    def get(self, n):
        """릴레이 n에 마지막으로 명령한 상태 (True = ON)."""
        c = channel_info(n)
        return bool(self.state[c["module"]] >> c["bit"] & 1)

    def on_list(self):
        """지금 ON으로 명령된 릴레이 번호 목록."""
        return [n for n in range(1, 33) if self.get(n)]

    def all_off(self):
        """모든 릴레이를 끈다 (전체 OFF 버튼, 주소 변경, 종료 시 사용).

        online 여부와 관계없이, 한 번이라도 초기화한 모듈에는 모두 OFF 쓰기를 시도한다.
        (I2C 오류로 연결이 끊긴 모듈이라도 릴레이가 켜진 채 남아 있을 수 있기 때문)
        쓰기에 실패한 모듈 이름 목록을 돌려준다. 빈 목록이면 전부 성공.
        """
        failed = []
        for m in (0, 1):
            if self.seen[m]:
                try:
                    self._wr(m, OLATA, 0x00, 0x00)
                except OSError:
                    failed.append(MODULES[m]["name"])
            self.state[m] = 0
        return failed

    # ───────── 되읽기 검사 ─────────
    def verify(self, m):
        """모듈 m의 칩에서 실제 값을 읽어 명령과 비교한다. 문제 설명 목록을 돌려준다 (정상이면 빈 목록).

        읽는 값과 잡아내는 고장
          IODIR  방향 레지스터. 0xFFFF로 돌아가 있으면 칩이 리셋된 것 (전원 순간 저하, RST 노이즈)
          OLAT   출력 래치. 명령과 다르면 I2C 데이터가 잘못 전달된 것
          GPIO   핀의 실제 레벨. 래치는 맞는데 핀 레벨이 다르면 그 핀이 다른 곳과 붙은 것 (납땜 브리지 등)
        릴레이 접점이 실제로 붙었는지는 여기서 알 수 없다 (그건 소리나 멀티미터로 확인).
        """
        if not self.online[m]:
            return []
        name = MODULES[m]["name"]
        try:
            gpa, gpb, ola, olb = self._rd(m, GPIOA, 4)      # 0x12~0x15: GPIOA, GPIOB, OLATA, OLATB
            dira, dirb = self._rd(m, IODIRA, 2)             # 0x00~0x01: IODIRA, IODIRB
        except (OSError, ValueError) as e:                  # ValueError = 바이트 수가 모자라게 읽힘
            self.online[m] = False
            return ["%s: I2C 읽기 실패 (%s). 연결이 끊어졌습니다." % (name, getattr(e, "strerror", None) or e)]
        # state와 같은 비트 배치(상위 = 포트 A, 하위 = 포트 B)의 16비트 값으로 합친다.
        iodir, olat, gpio = dira << 8 | dirb, ola << 8 | olb, gpa << 8 | gpb
        want = self.state[m]
        if iodir == 0xFFFF:
            # 16핀이 모두 입력으로 돌아갔다 = 칩이 리셋됐다. 출력이 끊겼으므로 이 모듈의 릴레이는 꺼져 있다.
            self.online[m] = False
            self.state[m] = 0
            return ["%s: 칩이 리셋되었습니다 (모든 핀이 입력으로 돌아감 → 이 모듈의 릴레이는 꺼짐). "
                    "3.3 V 순간 저하나 RST 라인 노이즈를 의심하세요. '연결'을 다시 누르세요." % name]
        problems = []
        if iodir != 0:
            problems.append("%s: 방향 레지스터가 0x%04X입니다 (예상 0x0000)" % (name, iodir))
        if olat != want:
            problems.append("%s: 출력 래치가 명령과 다릅니다 (명령 0x%04X, 칩 0x%04X)" % (name, want, olat))
        # 출력으로 설정된 핀 가운데, 핀 레벨이 명령과 다른 비트를 찾는다.
        diff = (gpio ^ want) & ~iodir & 0xFFFF
        for bit in range(16):
            if diff >> bit & 1:
                n = MODULES[m]["first"] + bit
                c = channel_info(n)
                problems.append("릴레이 %d: 명령은 %s인데 핀(%s GP%s%d)이 %s로 읽힘 → 핀이 다른 곳과 붙었는지(납땜 브리지) 확인"
                                % (n, "ON" if want >> bit & 1 else "OFF", MODULES[m]["chip"], c["port"], c["pin"],
                                   "High" if gpio >> bit & 1 else "Low"))
        return problems

    def shutdown(self):
        """프로그램이 끝날 때 불린다: 릴레이를 모두 끄고 RST 핀을 반납한다."""
        self.all_off()
        if self.rst:
            try:
                self.rst.close()
            except Exception:
                pass
            self.rst = None


def _hx(vals):
    """(0xA5, 0x5A) → '[0xA5 0x5A]'  (오류 문장용)"""
    return "[" + " ".join("0x%02X" % v for v in vals) + "]"


def scan_advice(found, addrs):
    """버스 스캔 결과(found)를 사람이 읽을 설명으로 바꾼다. [(수준, 문장)] 목록."""
    if not found:
        return [("err", "0x20~0x27에서 응답하는 칩이 없습니다. HAT 장착 방향, 3.3 V(칩 9번 핀), SDA/SCL 납땜을 확인하세요.")]
    out = [("info", "응답한 주소: " + ", ".join("0x%02X" % a for a in found))]
    if len(found) == 1:
        out.append(("warn", "주소가 하나만 응답합니다. 두 칩의 점퍼가 같으면(예: 모두 뺌 = 0x20) 한 주소로 겹쳐 보입니다. "
                            "한쪽 점퍼를 바꾸세요. 점퍼가 다른데도 하나뿐이면 다른 칩의 납땜·전원을 보세요."))
    elif len(found) > 2:
        out.append(("warn", "칩이 3개 이상 응답합니다. 같은 주소 범위를 쓰는 다른 I2C 장치(다른 HAT 등)가 있습니다. "
                            "릴레이 모듈의 주소를 정확히 골라야 합니다."))
    missing = [a for a in addrs if a not in found]
    if missing:
        out.append(("warn", "선택한 주소 중 응답이 없는 것: " + ", ".join("0x%02X" % a for a in missing)))
    return out


# ══════════════════════════════════════════════════════════════════════════
#  제어패널 (GUI, tkinter)
#
#  화면 구성
#     [연결]      모듈별 주소 선택 · 점퍼 안내 · 연결 상태, [버스 스캔] [연결 / 자가진단]
#     [릴레이]    4줄 × 8개 버튼 (한 줄 = ULN2803A 한 개)
#     [조작]      전체 OFF, 납땜한 채널 모두 ON, 순차 테스트
#     [경로/기록] 선택한 채널의 신호 경로 한 줄 + 동작 기록
#
#  tkinter는 한 스레드에서 돌아가므로 스레드를 쓰지 않고, 시간이 걸리는 일(순차 테스트, 1초 감시)은
#  root.after(밀리초, 함수)로 "나중에 이 함수를 불러 달라"고 예약하는 방식으로 처리합니다.
# ══════════════════════════════════════════════════════════════════════════
def build_panel(root, board, installed):
    """root 창 안에 제어패널을 만들고 Panel 객체를 돌려준다."""
    # tkinter는 GUI를 쓸 때만 필요하므로 여기서 불러온다 (--cli 모드는 tkinter 없이도 동작).
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText

    ON_BG, OFF_BG, DEAD_BG = "#2e9e4f", "#e4e4e4", "#f3f3f3"     # 버튼 색: ON / OFF / 미연결
    ROW_TITLES = ("1~8\n모듈 1 · 포트 B", "9~16\n모듈 1 · 포트 A", "17~24\n모듈 2 · 포트 B", "25~32\n모듈 2 · 포트 A")
    ADDR_CHOICES = ["0x%02X" % a for a in range(ADDR_MIN, ADDR_MAX + 1)]

    class Panel:
        def __init__(self):
            self.root, self.board, self.installed = root, board, sorted(installed)
            self.buttons = {}                # 릴레이 번호 → 버튼 위젯
            self.walk = None                 # 순차 테스트 중이면 {"targets": 대상 목록, "i": 현재 위치, "after": 예약 ID}
            self.last_problems = [None, None]   # 모듈별로 마지막에 기록한 문제 목록 (같은 내용을 반복 기록하지 않기 위해)
            root.title("32채널 릴레이 테스트 패널")
            self._build()
            root.protocol("WM_DELETE_WINDOW", self.close)        # 창의 X 버튼 → 릴레이를 끄고 닫기
            root.bind("<Escape>", lambda e: self.all_off())      # Esc 키 = 전체 OFF
            self.refresh()
            root.after(200, self.startup)    # 창이 뜬 직후 자동으로 스캔 + 연결
            root.after(1000, self.poll)      # 1초 주기 감시 시작

        # ───────── 화면 구성 ─────────
        def _build(self):
            pad = {"padx": 6, "pady": 3}

            # ── 연결 영역 ──
            top = ttk.LabelFrame(self.root, text="연결  (버스 %s)" % self.board.bus.name)
            top.pack(fill="x", padx=8, pady=(8, 4))
            self.addr_var, self.jumper_lbl, self.status_lbl = [], [], []
            for m, mod in enumerate(MODULES):
                ttk.Label(top, text="%s · 릴레이 %d~%d (HAT %s)" % (mod["name"], mod["first"], mod["first"] + 15,
                                                                 mod["chip"])).grid(row=m, column=0, sticky="w", **pad)
                ttk.Label(top, text="주소").grid(row=m, column=1, sticky="e", **pad)
                var = tk.StringVar(value="0x%02X" % self.board.addrs[m])
                box = ttk.Combobox(top, textvariable=var, values=ADDR_CHOICES, width=6, state="readonly")
                box.grid(row=m, column=2, **pad)
                # 람다의 m=m 은 "지금의 m 값"을 붙잡아 두기 위한 것 (없으면 두 상자 모두 마지막 m을 쓰게 된다)
                box.bind("<<ComboboxSelected>>", lambda e, m=m: self.addr_changed(m))
                jl = ttk.Label(top, text="", width=30)           # 그 주소에 해당하는 점퍼 상태
                jl.grid(row=m, column=3, sticky="w", **pad)
                sl = tk.Label(top, text="", width=14, anchor="w")  # 연결됨 / 연결 안 됨
                sl.grid(row=m, column=4, sticky="w", **pad)
                self.addr_var.append(var)
                self.jumper_lbl.append(jl)
                self.status_lbl.append(sl)
            bar = ttk.Frame(top)
            bar.grid(row=2, column=0, columnspan=5, sticky="w", **pad)
            ttk.Button(bar, text="버스 스캔", command=self.scan).pack(side="left", padx=(0, 6))
            ttk.Button(bar, text="연결 / 자가진단", command=self.connect).pack(side="left", padx=(0, 12))
            ttk.Label(bar, text="점퍼:  ● 꽂음   ○ 뺌").pack(side="left")

            # ── 릴레이 버튼 32개 ──
            grid = ttk.LabelFrame(self.root, text="릴레이  (클릭 = ON/OFF,  Esc = 전체 OFF,  파란 테두리 = 릴레이를 납땜한 채널)")
            grid.pack(fill="x", padx=8, pady=4)
            for r in range(4):
                ttk.Label(grid, text=ROW_TITLES[r], justify="left").grid(row=r, column=0, sticky="w", padx=6, pady=4)
                for col in range(8):
                    n = r * 8 + col + 1
                    mounted = n in self.installed
                    # 색을 자유롭게 바꾸려고 ttk.Button이 아닌 tk.Button을 쓴다.
                    b = tk.Button(grid, width=5, height=2, relief="raised", bd=2,
                                  font=("TkDefaultFont", 10, "bold" if mounted else "normal"),
                                  highlightthickness=3, highlightbackground="#1f6fd0" if mounted else "#d9d9d9",
                                  command=lambda n=n: self.toggle(n))
                    b.grid(row=r, column=col + 1, padx=3, pady=3)
                    # 마우스를 올리면 그 채널의 신호 경로를 아래 줄에 보여 준다.
                    b.bind("<Enter>", lambda e, n=n: self.info.set(describe(n, self.board.addrs)))
                    self.buttons[n] = b

            # ── 조작 영역 ──
            ctl = ttk.Frame(self.root)
            ctl.pack(fill="x", padx=8, pady=4)
            tk.Button(ctl, text="전체 OFF", bg="#c62828", fg="white", activebackground="#a31f1f",
                      activeforeground="white", font=("TkDefaultFont", 10, "bold"), width=10,
                      command=self.all_off).pack(side="left")
            ttk.Button(ctl, text="납땜한 채널 모두 ON", command=self.installed_on).pack(side="left", padx=8)
            ttk.Separator(ctl, orient="vertical").pack(side="left", fill="y", padx=6)
            ttk.Label(ctl, text="순차 테스트").pack(side="left")
            self.walk_scope = tk.StringVar(value="installed")    # 대상: 납땜한 채널 / 32채널 전부
            ttk.Radiobutton(ctl, text="납땜한 채널", variable=self.walk_scope, value="installed").pack(side="left", padx=3)
            ttk.Radiobutton(ctl, text="32채널 전부", variable=self.walk_scope, value="all").pack(side="left", padx=3)
            ttk.Label(ctl, text="ON 시간(초)").pack(side="left", padx=(8, 2))
            self.walk_sec = tk.StringVar(value="1.0")
            ttk.Spinbox(ctl, textvariable=self.walk_sec, from_=0.2, to=10.0, increment=0.2, width=5).pack(side="left")
            self.walk_repeat = tk.BooleanVar(value=False)
            ttk.Checkbutton(ctl, text="반복", variable=self.walk_repeat).pack(side="left", padx=6)
            self.walk_btn = ttk.Button(ctl, text="시작", width=6, command=self.walk_toggle)
            self.walk_btn.pack(side="left")

            # ── 신호 경로 한 줄 + 기록 창 ──
            self.info = tk.StringVar(value="버튼에 마우스를 올리면 그 채널의 신호 경로가 여기에 나옵니다.")
            ttk.Label(self.root, textvariable=self.info, foreground="#444444").pack(fill="x", padx=10, pady=(2, 0))
            self.logbox = ScrolledText(self.root, height=11, width=100, state="disabled", wrap="word")
            self.logbox.pack(fill="both", expand=True, padx=8, pady=(4, 8))
            for tag, color in (("ok", "#1b7a36"), ("err", "#c62828"), ("warn", "#b26a00"), ("info", "#222222")):
                self.logbox.tag_config(tag, foreground=color)    # 수준별 글자색

        # ───────── 공통 ─────────
        def log(self, level, text):
            """기록 창에 시각과 함께 한 줄을 추가한다. level에 따라 글자색이 달라진다."""
            self.logbox.config(state="normal")                   # 평소에는 사용자가 고치지 못하게 잠가 둔다
            self.logbox.insert("end", "%s  %s\n" % (time.strftime("%H:%M:%S"), text), level)
            self.logbox.see("end")
            self.logbox.config(state="disabled")

        def log_all(self, entries):
            for level, text in entries:
                self.log(level, text)

        def refresh(self):
            """board의 현재 상태에 맞춰 점퍼 안내, 연결 표시, 버튼 32개의 모양을 다시 그린다."""
            for m in (0, 1):
                self.jumper_lbl[m].config(text=jumper_text(m, self.board.addrs[m]))
                if self.board.online[m]:
                    self.status_lbl[m].config(text="● 연결됨", fg="#1b7a36")
                else:
                    self.status_lbl[m].config(text="○ 연결 안 됨", fg="#c62828")
            for n, b in self.buttons.items():
                if not self.board.online[channel_info(n)["module"]]:
                    b.config(text="%d\n–" % n, bg=DEAD_BG, fg="#9a9a9a", activebackground=DEAD_BG, relief="raised")
                elif self.board.get(n):
                    b.config(text="%d\nON" % n, bg=ON_BG, fg="white", activebackground="#268643", relief="sunken")
                else:
                    b.config(text="%d\nOFF" % n, bg=OFF_BG, fg="black", activebackground="#d2d2d2", relief="raised")

        def report(self, m, problems):
            """되읽기 결과를 기록한다. 1초마다 검사하므로, 내용이 바뀌었을 때만 적는다."""
            if problems != self.last_problems[m]:
                if problems:
                    self.log_all(("err", p) for p in problems)
                elif self.last_problems[m]:
                    self.log("ok", "%s: 되읽기 값이 다시 정상입니다." % MODULES[m]["name"])
                self.last_problems[m] = problems

        def check(self, modules=(0, 1)):
            """지정한 모듈의 칩 값을 되읽어 검사하고 화면을 갱신한다."""
            for m in modules:
                if self.board.online[m]:
                    self.report(m, self.board.verify(m))
            self.refresh()

        # ───────── 연결 ─────────
        def startup(self):
            """프로그램 시작 직후 한 번: 스캔 결과를 보여 주고 현재 주소로 연결을 시도한다."""
            self.scan(autofill=False)
            self.connect()

        def addr_changed(self, m):
            """주소 선택 상자를 바꿨을 때. 옛 주소의 릴레이를 끄고, 다시 연결하도록 안내한다."""
            self.walk_stop()
            new = list(self.board.addrs)
            new[m] = int(self.addr_var[m].get(), 16)
            self.board.set_addrs(new)
            self.last_problems = [None, None]
            self.refresh()
            self.log("info", "%s 주소를 0x%02X로 바꿨습니다 (점퍼: %s). '연결 / 자가진단'을 누르세요."
                     % (MODULES[m]["name"], new[m], jumper_text(m, new[m])))

        def scan(self, autofill=True):
            """[버스 스캔] 0x20~0x27에서 응답하는 주소를 찾는다.
            정확히 두 개가 응답하고 선택한 주소와 다르면, 낮은 쪽을 모듈 1로 하여 주소 칸을 채워 준다."""
            found = self.board.scan()
            if autofill and len(found) == 2 and set(found) != set(self.board.addrs):
                self.walk_stop()
                self.board.set_addrs(found)
                for m in (0, 1):
                    self.addr_var[m].set("0x%02X" % found[m])
                self.log("info", "응답한 두 주소로 채웠습니다: 모듈 1 = 0x%02X, 모듈 2 = 0x%02X. "
                                 "릴레이 번호가 16칸 어긋나면 두 주소를 서로 바꾸세요. '연결 / 자가진단'을 누르세요."
                         % (found[0], found[1]))
            self.log_all(scan_advice(found, self.board.addrs))
            self.refresh()

        def connect(self):
            """[연결 / 자가진단] RelayBoard.connect()를 실행하고 결과를 기록 창에 적는다."""
            self.walk_stop()
            self.last_problems = [None, None]
            try:
                self.log_all(self.board.connect())
            except RelayError as e:
                self.log("err", str(e))
            self.refresh()

        # ───────── 릴레이 조작 ─────────
        def toggle(self, n):
            """릴레이 버튼을 눌렀을 때: 상태를 뒤집고, 곧바로 칩 값을 되읽어 확인한다."""
            if self.walk:
                self.log("info", "순차 테스트 중입니다. 먼저 '정지'를 누르세요.")
                return
            try:
                self.board.set(n, not self.board.get(n))
            except RelayError as e:
                self.log("err", str(e))
                self.refresh()
                return
            self.log("info", "릴레이 %d %s" % (n, "ON" if self.board.get(n) else "OFF"))
            self.info.set(describe(n, self.board.addrs))
            self.check([channel_info(n)["module"]])

        def all_off(self):
            """[전체 OFF] / Esc. 순차 테스트도 함께 멈춘다."""
            self.walk_stop(quiet=True)
            failed = self.board.all_off()
            self.log("err" if failed else "info",
                     "전체 OFF" + (" (실패: %s — 전원을 직접 차단하세요)" % ", ".join(failed) if failed else ""))
            self.check()

        def installed_on(self):
            """[납땜한 채널 모두 ON] 여러 릴레이가 동시에 붙을 때의 5 V 전원 상태를 볼 때 쓴다."""
            if self.walk:
                self.log("info", "순차 테스트 중입니다. 먼저 '정지'를 누르세요.")
                return
            try:
                for n in self.installed:
                    if self.board.online[channel_info(n)["module"]]:
                        self.board.set(n, True)
            except RelayError as e:
                self.log("err", str(e))
            self.log("info", "ON: " + (", ".join(map(str, self.board.on_list())) or "없음"))
            self.check()

        # ───────── 순차 테스트 ─────────
        # 한 번에 하나씩:  ON → (ON 시간) → OFF → 0.3초 → 다음 채널 ON → ...
        # walk_step_on과 walk_step_off가 root.after()로 서로를 예약하며 번갈아 실행된다.
        def walk_toggle(self):
            """[시작]/[정지] 버튼."""
            if self.walk:
                self.walk_stop()
                return
            scope = self.installed if self.walk_scope.get() == "installed" else range(1, 33)
            targets = [n for n in scope if self.board.online[channel_info(n)["module"]]]   # 연결된 모듈의 채널만
            if not targets:
                self.log("err", "순차 테스트 대상이 없습니다. 먼저 연결하세요.")
                return
            try:
                self.walk_on_ms = int(max(0.2, min(10.0, float(self.walk_sec.get()))) * 1000)   # 0.2~10초로 제한
            except ValueError:
                self.walk_on_ms = 1000
            self.board.all_off()
            self.walk = {"targets": targets, "i": 0, "after": None}
            self.walk_btn.config(text="정지")
            self.log("info", "순차 테스트 시작: " + ", ".join(map(str, targets)))
            self.walk_step_on()

        def walk_step_on(self):
            """현재 차례의 릴레이를 켜고, ON 시간 뒤에 walk_step_off를 예약한다."""
            if not self.walk:
                return
            n = self.walk["targets"][self.walk["i"]]
            try:
                self.board.set(n, True)
            except RelayError as e:
                self.log("err", str(e))
                self.walk_stop()
                return
            self.log("info", "순차: 릴레이 %d ON" % n)
            self.info.set(describe(n, self.board.addrs))
            self.check([channel_info(n)["module"]])
            if self.walk:
                self.walk["after"] = self.root.after(self.walk_on_ms, self.walk_step_off)

        def walk_step_off(self):
            """켜 둔 릴레이를 끄고 다음 차례로 넘어간다. 마지막이면 끝내거나(반복 꺼짐) 처음으로 돌아간다."""
            if not self.walk:
                return
            n = self.walk["targets"][self.walk["i"]]
            try:
                self.board.set(n, False)
            except RelayError as e:
                self.log("err", str(e))
                self.walk_stop()
                return
            self.check([channel_info(n)["module"]])
            if not self.walk:
                return
            self.walk["i"] += 1
            if self.walk["i"] >= len(self.walk["targets"]):
                if not self.walk_repeat.get():
                    self.walk_stop(done=True)
                    return
                self.walk["i"] = 0
            self.walk["after"] = self.root.after(300, self.walk_step_on)

        def walk_stop(self, done=False, quiet=False):
            """순차 테스트를 멈추고 모두 끈다. 진행 중이 아니면 아무 일도 하지 않는다."""
            if not self.walk:
                return
            if self.walk["after"]:
                self.root.after_cancel(self.walk["after"])       # 예약해 둔 다음 단계를 취소
            self.walk = None
            self.walk_btn.config(text="시작")
            self.board.all_off()
            if not quiet:
                self.log("ok" if done else "info", "순차 테스트 완료" if done else "순차 테스트 정지 (전체 OFF)")
            self.refresh()

        # ───────── 주기 감시 / 종료 ─────────
        def poll(self):
            """1초마다 칩 값을 되읽어 리셋·연결 끊김·핀 불일치를 잡아낸다."""
            self.check()
            self.root.after(1000, self.poll)

        def close(self):
            """창을 닫을 때: 릴레이를 모두 끄고 종료한다."""
            self.walk_stop(quiet=True)
            self.board.all_off()
            self.root.destroy()

    return Panel()


def run_gui(board, installed):
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception as e:                   # tkinter가 없거나, 화면이 없는 환경(SSH)
        raise SystemExit("GUI를 열 수 없습니다 (%s).\n모니터가 없으면:  python3 relay_panel.py --cli\n"
                         "tkinter가 없으면:  sudo apt install python3-tk" % e)
    # GUI에서는 터미널의 Ctrl+C도 정상 종료(릴레이 OFF)로 이어지게 한다.
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    build_panel(root, board, installed)
    root.mainloop()


# ══════════════════════════════════════════════════════════════════════════
#  텍스트 모드 (--cli)  ―  모니터 없이 SSH로 접속해 시험할 때
# ══════════════════════════════════════════════════════════════════════════
CLI_HELP = """명령
  scan                    0x20~0x27 스캔
  connect                 연결 + 자가진단 (릴레이 모두 OFF에서 시작)
  on  <대상>              켜기      대상: 번호(1 9 17), 범위(1-8), inst(납땜한 채널), all
  off <대상>              끄기      (대상을 생략하면 전체 OFF)
  t   <번호>              토글
  walk [초] [inst|all]    순차 테스트 (기본 1초, 납땜한 채널). Ctrl+C로 중단
  status                  켜진 채널과 되읽기 결과
  info <번호>             신호 경로
  addr <모듈1> <모듈2>     주소 변경 (예: addr 0x24 0x25) 후 다시 연결
  q                       전체 OFF 후 종료"""

_MARK = {"ok": "[ OK ]", "info": "[    ]", "warn": "[주의]", "err": "[오류]"}   # 수준 → 줄 머리 표시


def parse_targets(tokens, installed):
    """'1', '9-11', 'inst', 'all' 같은 낱말들을 릴레이 번호 목록으로 바꾼다. 범위를 벗어나면 ValueError."""
    out = []
    for tok in tokens:
        if tok == "all":
            out.extend(range(1, 33))
        elif tok == "inst":
            out.extend(installed)
        elif "-" in tok:
            a, b = tok.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(tok))
    for n in out:
        channel_info(n)                      # 1~32 범위 검사
    return out


def run_cli(board, installed):
    def show(entries):
        for level, text in entries:
            print(_MARK[level], text)

    def status():
        """켜진 채널, 연결 상태, 되읽기 결과를 출력한다."""
        print("ON:", ", ".join(map(str, board.on_list())) or "없음",
              "  |  연결:", ", ".join("%s=%s" % (MODULES[m]["name"], "O" if board.online[m] else "X") for m in (0, 1)))
        for m in (0, 1):
            show(("err", p) for p in board.verify(m))

    def do_connect():
        try:
            show(board.connect())
        except RelayError as e:
            print(_MARK["err"], e)

    print("32채널 릴레이 테스트 (텍스트 모드, 버스 %s).  help = 명령 목록" % board.bus.name)
    show(scan_advice(board.scan(), board.addrs))
    do_connect()
    while True:
        try:
            parts = input("relay> ").split()
        except (EOFError, KeyboardInterrupt):    # Ctrl+D, Ctrl+C → 종료
            print()
            break
        if not parts:
            continue
        cmd, args = parts[0].lower(), [a.lower() for a in parts[1:]]
        try:
            if cmd in ("q", "quit", "exit"):
                break
            elif cmd in ("help", "h", "?"):
                print(CLI_HELP)
            elif cmd == "scan":
                show(scan_advice(board.scan(), board.addrs))
            elif cmd == "connect":
                do_connect()
            elif cmd == "addr":
                new = [int(a, 0) for a in args]      # int(문자열, 0): '0x24'도 '36'도 받아들인다
                if len(new) != 2 or not all(ADDR_MIN <= a <= ADDR_MAX for a in new):
                    raise ValueError("addr 0x20 0x21 처럼 0x20~0x27 범위의 주소 두 개를 주세요")
                board.set_addrs(new)
                for m in (0, 1):
                    print("  %s = 0x%02X   점퍼: %s" % (MODULES[m]["name"], new[m], jumper_text(m, new[m])))
                do_connect()
            elif cmd in ("on", "off"):
                if cmd == "off" and not args:
                    failed = board.all_off()
                    if failed:
                        print(_MARK["err"], "OFF 실패:", ", ".join(failed))
                else:
                    for n in parse_targets(args, installed):
                        board.set(n, cmd == "on")
                status()
            elif cmd == "t":
                for n in parse_targets(args, installed):
                    board.set(n, not board.get(n))
                status()
            elif cmd == "walk":
                # 인자 가운데 숫자가 있으면 ON 시간(초)으로, 'all'이 있으면 32채널 전부를 대상으로 한다.
                sec = next((float(a) for a in args if a.replace(".", "", 1).isdigit()), 1.0)
                targets = [n for n in (range(1, 33) if "all" in args else installed)
                           if board.online[channel_info(n)["module"]]]
                board.all_off()
                try:
                    for n in targets:
                        board.set(n, True)
                        print("  릴레이 %2d ON " % n, end="", flush=True)
                        problems = board.verify(channel_info(n)["module"])   # 켠 상태에서 되읽기
                        time.sleep(sec)
                        board.set(n, False)
                        print("→ OFF" + ("" if not problems else "   " + _MARK["err"] + " " + "; ".join(problems)))
                        time.sleep(0.3)
                except KeyboardInterrupt:
                    print("\n  중단")
                finally:
                    board.all_off()              # 끝나든 중단되든 모두 끈다
            elif cmd == "status":
                status()
            elif cmd == "info":
                for n in parse_targets(args, installed):
                    print(" ", describe(n, board.addrs))
            else:
                print("모르는 명령입니다. help를 입력하세요.")
        except (RelayError, ValueError) as e:
            print(_MARK["err"], e)
    board.all_off()
    print("전체 OFF 후 종료")


# ══════════════════════════════════════════════════════════════════════════
#  시작
# ══════════════════════════════════════════════════════════════════════════
def parse_installed(text):
    """--installed 옵션 값('1,9,17,25' / '1-8' / 'all')을 번호 목록으로 바꾼다."""
    if text.strip().lower() == "all":
        return list(range(1, 33))
    return sorted(set(parse_targets(text.replace(",", " ").split(), [])))


def main(argv=None):
    ap = argparse.ArgumentParser(description="32채널 릴레이 보드 테스트 패널 (MCP23017 x2, I2C)")
    ap.add_argument("--bus", type=int, default=1, help="I2C 버스 번호 (기본 1 = GPIO2/3)")
    ap.add_argument("--addr", nargs=2, metavar=("모듈1", "모듈2"), default=["0x%02X" % a for a in DEFAULT_ADDRS],
                    help="두 MCP23017의 주소 (기본 0x20 0x21)")
    ap.add_argument("--installed", default=",".join(map(str, DEFAULT_INSTALLED)),
                    help="릴레이를 납땜한 채널. 예: 1,9,17,25 또는 1-8 또는 all (기본 1,9,17,25)")
    ap.add_argument("--cli", action="store_true", help="GUI 대신 텍스트 모드")
    ap.add_argument("--sim", action="store_true", help="보드 없이 시뮬레이션")
    ap.add_argument("--no-rst", action="store_true", help="GPIO%d(RST)를 건드리지 않음" % RST_GPIO)
    args = ap.parse_args(argv)

    addrs = [int(a, 0) for a in args.addr]
    if not all(ADDR_MIN <= a <= ADDR_MAX for a in addrs):
        ap.error("주소는 0x20~0x27 범위여야 합니다")
    installed = parse_installed(args.installed)

    # 버스와 RST 라인을 준비한다. --sim이면 둘 다 가짜를 쓴다.
    if args.sim:
        bus = SimBus(addrs)
        rst = None if args.no_rst else SimResetLine(bus)
    else:
        bus = LinuxI2C(args.bus)
        rst = None
        if not args.no_rst:
            try:
                rst = GpioResetLine(RST_GPIO)
            except Exception as e:
                # gpiozero가 없거나 GPIO27을 다른 프로그램이 쓰는 경우. 리셋 시험만 빼고 계속 진행한다.
                print("주의: GPIO%d(RST)를 제어할 수 없어 리셋 시험을 건너뜁니다 (%s: %s)"
                      % (RST_GPIO, type(e).__name__, e), file=sys.stderr)

    board = RelayBoard(bus, addrs, rst)
    # 프로그램이 어떤 식으로 끝나든(창 닫기, q, 오류, kill) 릴레이를 끄고 나간다.
    # 단, 전원이 끊기거나 kill -9로 강제 종료되면 이 처리가 실행되지 않고 칩은 마지막 출력을 유지한다.
    atexit.register(board.shutdown)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    if args.cli:
        run_cli(board, installed)
    else:
        run_gui(board, installed)


if __name__ == "__main__":
    main()
