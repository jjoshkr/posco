"""I/O 노드 실제 하드웨어 층: Raspberry Pi 5 + MCC 152 ×2 + MCC 118 + MCC 134 (daqhats 라이브러리).

보드와 핀 배정 (대화에서 확정한 것, io_node.json 으로 바꿀 수 있음)

  MCC 152 #1 (주소 0)                       MCC 152 #2 (주소 1)
    AO0 → XTR111 A → P-101 (4–20 mA)          AO0 → XTR111 A → P-103
    AO1 → XTR111 B → P-102                    AO1 → XTR111 B → 교반기 지령
    DIO0 OD(A)  출력 차단, High=꺼짐          DIO0 OD(A)
    DIO1 EF(A)  고장 감지 입력, Low=고장      DIO1 EF(A)
    DIO2 OD(B)                                DIO2 OD(B)
    DIO3 EF(B)                                DIO3 EF(B)
    DIO4 XV-101 솔레노이드 (포토커플러)       DIO4 XV-103
    DIO5 XV-102                               DIO5 RUN_ENABLE (펌프 3대 Pause 접점 공통)
    DIO6, DIO7 예비                           DIO6 P-104 펄스(접점, 산 펌프)  DIO7 XV-104
  MCC 118 (주소 2)  CH0 pH(4–20 mA, 250 Ω)  CH1~3 펌프 옵션 C 피드백  CH4 압력 트랜스미터
  MCC 134 (주소 3)  CH0 열전대 K (반응기 온도)

안전 원칙
  - 부팅 직후 MCC 152 DIO 는 입력(풀업) → OD High → XTR111 출력 0 mA. 이 코드는 그 상태를 유지한 채 시작하고
    AO 를 0 V 로 쓴 뒤에만 OD 를 제어 출력으로 바꾼다.
  - safe(): RUN_ENABLE OFF → AO 0 V → OD High → 밸브 OFF 순서. 종료(예외 포함) 시 항상 호출.
  - 24 V 전원은 Pi 와 보드가 켜진 뒤에 넣는다 (데이터시트 검토 결과).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json, math, pathlib, time
import numpy as np
from .nodes import HAL


@dataclass
class IOConfig:
    addresses: dict = field(default_factory=lambda: {"mcc152#1": 0, "mcc152#2": 1, "mcc118": 2, "mcc134": 3})
    ao: dict = field(default_factory=lambda: {"P-101": ["mcc152#1", 0], "P-102": ["mcc152#1", 1],
                                             "P-103": ["mcc152#2", 0], "STIRRER": ["mcc152#2", 1]})
    od_pin: dict = field(default_factory=lambda: {"P-101": ["mcc152#1", 0], "P-102": ["mcc152#1", 2],
                                                 "P-103": ["mcc152#2", 0], "STIRRER": ["mcc152#2", 2]})
    ef_pin: dict = field(default_factory=lambda: {"P-101": ["mcc152#1", 1], "P-102": ["mcc152#1", 3],
                                                 "P-103": ["mcc152#2", 1], "STIRRER": ["mcc152#2", 3]})
    dio: dict = field(default_factory=lambda: {"XV-101": ["mcc152#1", 4], "XV-102": ["mcc152#1", 5],
                                              "XV-103": ["mcc152#2", 4], "RUN_ENABLE": ["mcc152#2", 5],
                                              "P-104": ["mcc152#2", 6], "XV-104": ["mcc152#2", 7]})   # 펄스 펌프(산) + 밸브
    pulse_ms: float = 20.0
    # 아날로그 입력: 4–20 mA → 션트 → V → 공학단위 (eu_lo @ 4 mA, eu_hi @ 20 mA)
    ai: dict = field(default_factory=lambda: {
        "PH": {"ch": 0, "shunt_ohm": 250.0, "eu_lo": 0.0, "eu_hi": 14.0},
        "FB-101": {"ch": 1, "shunt_ohm": 250.0}, "FB-102": {"ch": 2, "shunt_ohm": 250.0}, "FB-103": {"ch": 3, "shunt_ohm": 250.0},
        "PRESSURE": {"ch": 4, "shunt_ohm": 250.0, "eu_lo": 0.0, "eu_hi": 10.0}})
    tc: dict = field(default_factory=lambda: {"TEMP": {"ch": 0, "type": "K"}})
    mA_per_V: float = 4.016          # XTR111 RSET 2.49 kΩ
    ao_max_V: float = 5.0
    od_disable_level: int = 1        # OD High = 출력 꺼짐
    valve_active_high: bool = True   # DIO High = 포토커플러 ON = 밸브 열림
    run_enable_active_high: bool = True
    ai_average: int = 4              # 잡음 줄이려고 a_in_read 평균 횟수
    cal: dict = field(default_factory=dict)   # 2점 교정 {"P-101": {"gain": 1.0, "offset": 0.0}}
    loadcell: dict = field(default_factory=dict)  # {"config": "loadcell.json"} 이 있으면 HX711 리더를 붙인다 (serial/gpio)

    @classmethod
    def load(cls, path="io_node.json"):
        p = pathlib.Path(path)
        return cls(**json.loads(p.read_text())) if p.exists() else cls()

    def save(self, path="io_node.json"):
        pathlib.Path(path).write_text(json.dumps(asdict(self), indent=1, ensure_ascii=False))


class DaqHatsHAL(HAL):
    """nodes.HAL 구현. daqhats 가 없는 PC 에서는 fake 모듈을 주입해 시험한다 (tests 참고)."""

    def __init__(self, io: IOConfig | None = None, daqhats_module=None, open_boards=True):
        self.io = io or IOConfig()
        self.dh = daqhats_module or __import__("daqhats")
        self.b: dict = {}
        self.ao_cache: dict = {}
        self.dio_cache: dict = {}
        self.last_ef: dict = {}
        self.lc = None; self.lc_cfg = None
        if self.io.loadcell:
            from .loadcell import LoadCellConfig, open_reader
            self.lc_cfg = LoadCellConfig.load(self.io.loadcell.get("config", "loadcell.json"))
            self.lc = open_reader(self.lc_cfg)
        if open_boards:
            self.open()

    # ---------------- 보드 열기 / 초기화
    def open(self):
        dh = self.dh
        found = {h.address: h for h in dh.hat_list(dh.HatIDs.ANY)}
        for name, addr in self.io.addresses.items():
            if addr not in found:
                raise RuntimeError(f"{name}: 주소 {addr} 에 보드가 없습니다. 발견된 보드: "
                                   + ", ".join(f"{h.address}:{h.product_name}" for h in found.values()) + "  (주소 점퍼 A0~A2 확인)")
            kind = name.split("#")[0]
            cls = {"mcc152": dh.mcc152, "mcc118": dh.mcc118, "mcc134": dh.mcc134}[kind]
            self.b[name] = cls(addr)
        # MCC 152: AO 0 V 먼저, 그다음 DIO 방향 설정
        for name, brd in self.b.items():
            if name.startswith("mcc152"):
                brd.a_out_write_all([0.0, 0.0])
                brd.dio_reset()                                  # 전부 입력 + 풀업 (OD High 유지)
        for key, (bname, ch) in self.io.ef_pin.items():          # EF: 입력, 풀업
            brd = self.b[bname]
            brd.dio_config_write_bit(ch, self.dh.DIOConfigItem.DIRECTION, 1)
            brd.dio_config_write_bit(ch, self.dh.DIOConfigItem.PULL_ENABLE, 1)
        for key, (bname, ch) in self.io.od_pin.items():          # OD: 출력, 먼저 High(꺼짐) 로 쓴 뒤 방향 전환
            self._dio_out(bname, ch, self.io.od_disable_level)
        for key, (bname, ch) in self.io.dio.items():             # 밸브·운전허가: 출력, OFF
            self._dio_out(bname, ch, 0 if self.io.valve_active_high else 1)
        for key, spec in self.io.tc.items():                     # 열전대 타입
            tct = getattr(self.dh.TcTypes, "TYPE_" + spec.get("type", "K"))
            self.b["mcc134"].tc_type_write(spec["ch"], tct)
        return self

    def _dio_out(self, bname, ch, level):
        brd = self.b[bname]
        brd.dio_output_write_bit(ch, int(level))                 # 출력 래치 값 먼저
        brd.dio_config_write_bit(ch, self.dh.DIOConfigItem.DIRECTION, 0)
        self.dio_cache[(bname, ch)] = int(level)

    # ---------------- HAL 구현
    def _ao_volts(self, key, mA):
        c = self.io.cal.get(key, {})
        v = (mA * c.get("gain", 1.0) + c.get("offset", 0.0)) / self.io.mA_per_V
        return float(np.clip(v, 0.0, self.io.ao_max_V))

    def pump_set_mA(self, pid, mA):
        bname, ch = self.io.ao[pid]
        v = self._ao_volts(pid, mA)
        self.b[bname].a_out_write(ch, v)
        self.ao_cache[pid] = v

    def pump_enable(self, pid, on):
        bname, ch = self.io.od_pin[pid]
        lvl = (1 - self.io.od_disable_level) if on else self.io.od_disable_level
        self.b[bname].dio_output_write_bit(ch, lvl)
        self.dio_cache[(bname, ch)] = lvl

    def valve(self, vid, on):
        bname, ch = self.io.dio[vid]
        lvl = int(on) if self.io.valve_active_high else int(not on)
        self.b[bname].dio_output_write_bit(ch, lvl)
        self.dio_cache[(bname, ch)] = lvl

    def run_enable(self, on):
        bname, ch = self.io.dio["RUN_ENABLE"]
        lvl = int(on) if self.io.run_enable_active_high else int(not on)
        self.b[bname].dio_output_write_bit(ch, lvl)
        self.dio_cache[(bname, ch)] = lvl

    def stirrer_set_mA(self, mA):
        bname, ch = self.io.ao["STIRRER"]
        self.b[bname].a_out_write(ch, self._ao_volts("STIRRER", mA))
        # 교반기 지령은 OD 를 켜야 나간다
        self.pump_enable("STIRRER", mA > 0)

    def _ai_V(self, ch):
        n = max(1, self.io.ai_average)
        return sum(self.b["mcc118"].a_in_read(ch) for _ in range(n)) / n

    def _ai_mA(self, key):
        spec = self.io.ai[key]
        return self._ai_V(spec["ch"]) * 1000.0 / spec.get("shunt_ohm", 250.0)

    def _ai_eu(self, key):
        spec = self.io.ai[key]
        mA = self._ai_mA(key)
        return spec["eu_lo"] + (spec["eu_hi"] - spec["eu_lo"]) * (mA - 4.0) / 16.0

    def read_feedback_mA(self, pid):
        return self._ai_mA("FB-" + pid[-3:])

    def read_ph(self):
        return self._ai_eu("PH") if "PH" in self.io.ai else float("nan")

    def read_pressure_bar(self):
        return self._ai_eu("PRESSURE") if "PRESSURE" in self.io.ai else 0.0

    def read_temp_C(self):
        spec = self.io.tc.get("TEMP")
        if not spec:
            return float("nan")
        v = self.b["mcc134"].t_in_read(spec["ch"])
        bad = {getattr(self.dh.mcc134, "OPEN_TC_VALUE", -9999.0), getattr(self.dh.mcc134, "OVERRANGE_TC_VALUE", -8888.0),
               getattr(self.dh.mcc134, "COMMON_MODE_TC_VALUE", -7777.0)}
        return float("nan") if v in bad else float(v)

    def read_tank_mass_g(self):
        if self.lc is None:
            raise AttributeError("loadcell not configured")
        return self.lc.read_g()

    def pulse(self, pid) -> bool:
        """접점 펄스: DIO High(포토커플러 ON = 접점 닫힘) pulse_ms 유지 후 Low. 펌프 최소 펄스폭(매뉴얼) 이상으로 둘 것."""
        if pid not in self.io.dio:
            return False
        bname, ch = self.io.dio[pid]
        self.b[bname].dio_output_write_bit(ch, 1)
        time.sleep(self.io.pulse_ms / 1000.0)
        self.b[bname].dio_output_write_bit(ch, 0)
        return True

    def read_ef_faults(self) -> dict:
        """XTR111 EF 핀: Low = 부하 단선/과열. {'P-101': True(고장), ...}"""
        out = {}
        for key, (bname, ch) in self.io.ef_pin.items():
            out[key] = self.b[bname].dio_input_read_bit(ch) == 0
        self.last_ef = out
        return out

    def step(self, dt):
        pass

    def close(self):
        """모든 출력을 안전 상태로 (safe 와 같은 순서)."""
        if self.lc is not None:
            try:
                self.lc.stop()
            except Exception:
                pass
        try:
            self.run_enable(False)
            for pid in self.io.ao:
                self.b[self.io.ao[pid][0]].a_out_write(self.io.ao[pid][1], 0.0)
                self.pump_enable(pid, False)
            for vid in self.io.dio:
                if vid != "RUN_ENABLE":
                    self.valve(vid, False)
        except Exception:
            pass

    # ---------------- 교정·벤치
    def calibrate_pump_channel(self, pid, measure_mA, lo=5.0, hi=19.0, settle=0.5):
        """2점 교정. measure_mA(): 멀티미터 값을 입력받거나, 피드백 루프백을 읽는 함수."""
        self.io.cal.pop(pid, None)
        self.pump_enable(pid, True)
        self.pump_set_mA(pid, lo); time.sleep(settle); m_lo = measure_mA()
        self.pump_set_mA(pid, hi); time.sleep(settle); m_hi = measure_mA()
        self.pump_set_mA(pid, 0.0); self.pump_enable(pid, False)
        slope = (m_hi - m_lo) / (hi - lo)
        gain = 1.0 / slope
        offset = -(m_lo - lo * slope) / slope
        self.io.cal[pid] = {"gain": gain, "offset": offset}
        return slope, gain, offset

    def snapshot(self) -> dict:
        """벤치용: 현재 출력 래치·입력을 한 번에."""
        d = dict(ao_V=dict(self.ao_cache), dio={f"{b}/DIO{c}": v for (b, c), v in self.dio_cache.items()},
                 ef_fault=self.read_ef_faults())
        d["ai_mA"] = {k: round(self._ai_mA(k), 3) for k in self.io.ai}
        d["temp_C"] = self.read_temp_C()
        return d
