"""daqhats 라이브러리 흉내 (PC 에서 DaqHatsHAL 을 시험하기 위한 최소 구현). API 이름·의미는 mccdaq/daqhats 와 같게."""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum


class HatIDs(IntEnum):
    ANY = 0; MCC_118 = 0x0142; MCC_134 = 0x0143; MCC_152 = 0x0144


class DIOConfigItem(IntEnum):
    DIRECTION = 0; PULL_CONFIG = 1; PULL_ENABLE = 2; INPUT_INVERT = 3; INPUT_LATCH = 4; OUTPUT_TYPE = 5; INT_MASK = 6


class TcTypes(IntEnum):
    TYPE_J = 0; TYPE_K = 1; TYPE_T = 2; TYPE_E = 3; TYPE_R = 4; TYPE_S = 5; TYPE_B = 6; TYPE_N = 7; DISABLED = 255


class OptionFlags(IntEnum):
    DEFAULT = 0


@dataclass
class HatInfo:
    address: int; id: int; version: int; product_name: str


BOARDS = {0: HatInfo(0, HatIDs.MCC_152, 1, "MCC 152"), 1: HatInfo(1, HatIDs.MCC_152, 1, "MCC 152"),
          2: HatInfo(2, HatIDs.MCC_118, 1, "MCC 118"), 3: HatInfo(3, HatIDs.MCC_134, 1, "MCC 134")}
LOG: list = []          # (board, op, args) 호출 순서 기록


def hat_list(filter_by_id=HatIDs.ANY):
    return [b for b in BOARDS.values() if filter_by_id == HatIDs.ANY or b.id == filter_by_id]


class mcc152:
    def __init__(self, address):
        self.address = address
        self.ao = [0.0, 0.0]
        self.direction = [1] * 8          # 부팅: 전부 입력
        self.pull_enable = [1] * 8
        self.out_latch = [1] * 8          # 출력 래치 기본 High
        self.inputs = [1] * 8             # 외부에서 읽히는 입력 값 (테스트가 바꿈)

    def a_out_write(self, ch, v, options=OptionFlags.DEFAULT):
        assert 0.0 <= v <= 5.0, v
        self.ao[ch] = v; LOG.append((self.address, "ao", ch, v))

    def a_out_write_all(self, vals, options=OptionFlags.DEFAULT):
        self.ao = list(vals); LOG.append((self.address, "ao_all", tuple(vals)))

    def dio_reset(self):
        self.direction = [1] * 8; self.pull_enable = [1] * 8; self.out_latch = [1] * 8; LOG.append((self.address, "dio_reset"))

    def dio_config_write_bit(self, ch, item, val):
        if item == DIOConfigItem.DIRECTION:
            self.direction[ch] = val
        elif item == DIOConfigItem.PULL_ENABLE:
            self.pull_enable[ch] = val
        LOG.append((self.address, "cfg", ch, int(item), val))

    def dio_output_write_bit(self, ch, val):
        self.out_latch[ch] = val; LOG.append((self.address, "dio", ch, val))

    def dio_input_read_bit(self, ch):
        return self.out_latch[ch] if self.direction[ch] == 0 else self.inputs[ch]

    def pin_level(self, ch):
        """실제 핀 전압 레벨: 출력이면 래치, 입력이면 풀업(1) 또는 외부 구동값."""
        return self.out_latch[ch] if self.direction[ch] == 0 else self.inputs[ch]


class mcc118:
    def __init__(self, address):
        self.address = address
        self.volts = [0.0] * 8

    def a_in_read(self, ch, options=OptionFlags.DEFAULT):
        return self.volts[ch]


class mcc134:
    OPEN_TC_VALUE = -9999.0; OVERRANGE_TC_VALUE = -8888.0; COMMON_MODE_TC_VALUE = -7777.0

    def __init__(self, address):
        self.address = address; self.types = {}; self.temps = [25.0] * 4

    def tc_type_write(self, ch, t):
        self.types[ch] = t

    def t_in_read(self, ch):
        return self.temps[ch]
