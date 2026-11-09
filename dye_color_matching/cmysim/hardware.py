"""I/O 노드 쪽 장비 모델: MCC 152 → XTR111 → gamma/X 펌프, NC 솔레노이드 밸브, MCC 118/134, 교반기.

실제 보드로 옮길 때는 nodes.HAL 인터페이스(ao_write/dio_write/ai_read/tc_read)만 daqhats로 바꾸면 된다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .config import PumpSpec, DacChainSpec, AdcSpec, PulsePumpSpec


class Mcc152AO:
    """MCC 152 아날로그 출력 1채널: 0–5 V, 12 bit, 이득/오프셋 오차, 전원 투입 시 0 V."""

    def __init__(self, spec: DacChainSpec, gain_err: float | None = None):
        self.spec = spec
        self.gain_err = spec.gain_err if gain_err is None else gain_err
        self.code = 0
        self.lsb = spec.v_full / (2 ** spec.bits - 1)

    def write_volts(self, v: float) -> float:
        self.code = int(np.clip(round(v / self.lsb), 0, 2 ** self.spec.bits - 1))
        return self.actual_volts

    @property
    def actual_volts(self) -> float:
        return self.code * self.lsb * (1 + self.gain_err) + self.spec.offset_V


class Xtr111:
    """전압→전류 변환기. OD(output disable) High면 0 mA (페일세이프)."""

    def __init__(self, spec: DacChainSpec):
        self.spec = spec
        self.od_high = True          # Pi 부팅 직후 DIO는 입력(풀업) → OD High → 출력 꺼짐

    def convert(self, v: float) -> float:
        if self.od_high:
            return 0.0
        return float(np.clip(v * self.spec.mA_per_V, 0.0, self.spec.i_max_mA))


class PumpChannel:
    """AO 채널 + XTR111 + 2점 교정값. 코드가 '원하는 mA'를 쓰면 실제 펌프에 걸리는 mA를 돌려준다."""

    def __init__(self, spec: DacChainSpec, gain_err: float = 0.0):
        self.ao = Mcc152AO(spec, gain_err)
        self.xtr = Xtr111(spec)
        self.cal_gain, self.cal_offset = 1.0, 0.0   # 교정 전: 이상 모델 가정
        self.cmd_mA = 0.0

    def set_mA(self, mA: float) -> float:
        self.cmd_mA = mA
        v = (mA * self.cal_gain + self.cal_offset) / self.ao.spec.mA_per_V
        return self.xtr.convert(self.ao.write_volts(v))

    @property
    def actual_mA(self) -> float:
        return self.xtr.convert(self.ao.actual_volts)

    def enable(self, on: bool):
        self.xtr.od_high = not on

    def calibrate_two_point(self, measure_mA, lo=5.0, hi=19.0):
        """실측값(measure_mA: 함수)으로 2점 교정. MCC 152 이득 오차(±1.5 %)를 흡수한다."""
        self.cal_gain, self.cal_offset = 1.0, 0.0
        self.set_mA(lo); m_lo = measure_mA()
        self.set_mA(hi); m_hi = measure_mA()
        slope = (m_hi - m_lo) / (hi - lo)          # 실제/지령
        self.cal_gain = 1.0 / slope
        self.cal_offset = -(m_lo - lo * slope) / slope
        self.set_mA(0.0)
        return slope


@dataclass
class PumpState:
    spm_actual: float = 0.0
    strokes_total: int = 0
    volume_total_mL: float = 0.0
    fault: str = ""                 # "", "SIGNAL<3.8mA", "LEVEL"
    paused: bool = True             # 운전 허가(Pause) 접점. True면 정지
    pressure_bar: float = 0.0
    relief_active: bool = False
    phase: float = 0.0


class GammaXPump:
    """gamma/X Analog 모드. 전류 → 스트로크/분, 1 스트로크 = 고정 부피 슬러그."""

    def __init__(self, spec: PumpSpec, rng: np.random.Generator, pump_id: str):
        self.spec, self.rng, self.id = spec, rng, pump_id
        self.s = PumpState()
        self.level_ok = True

    def reset_fault(self):
        self.s.fault = ""

    def spm_from_mA(self, mA: float) -> float:
        p = self.spec
        if mA < p.i_start_mA:
            return 0.0
        return float(np.clip(p.max_spm * (mA - p.i_start_mA) / (p.i_full_mA - p.i_start_mA), 0, p.max_spm))

    def step(self, mA: float, dt: float, outlet_open: bool, deliver) -> None:
        """deliver(volume_mL)는 밸브가 열렸을 때 반응기로 들어가는 부피를 받는 콜백."""
        p, s = self.spec, self.s
        if not self.level_ok:
            s.fault = "LEVEL"
        if (not s.paused) and 0.0 < mA < p.i_fault_mA:
            s.fault = "SIGNAL<3.8mA"          # 신호 이상 → 알람 정지 (운전 허가 OFF면 무시: 가정)
        running = (not s.paused) and (s.fault == "") and self.level_ok
        s.spm_actual = self.spm_from_mA(mA) if running else 0.0
        s.phase += s.spm_actual / 60.0 * dt
        n = int(s.phase)
        s.phase -= n
        for _ in range(n):
            vol = p.stroke_mL * p.stroke_length * (1 + self.rng.normal(0, p.repro))
            s.strokes_total += 1
            if outlet_open:
                s.volume_total_mL += vol
                deliver(vol)
            # 밸브 닫힘: 릴리프 밸브를 통해 탱크로 복귀 (반응기에는 안 들어감)
        if s.spm_actual > 0 and not outlet_open:
            s.pressure_bar, s.relief_active = p.relief_bar, True
        elif s.spm_actual > 0:
            s.pressure_bar, s.relief_active = 0.8, False   # 주입 밸브 개방압 + 라인 손실 (가정)
        else:
            s.pressure_bar, s.relief_active = 0.0, False

    def feedback_mA(self) -> float:
        """옵션 C: 실제 스트로크 속도를 4–20 mA로 (정지·알람 시 4 mA)."""
        if not self.spec.fb_option_c:
            return 0.0
        return 4.0 + 16.0 * self.s.spm_actual / self.spec.max_spm


class SolenoidValveNC:
    """2-way 상시닫힘. 전기가 끊기면 닫힘. 고장 주입: stuck_closed."""

    def __init__(self, valve_id: str, open_time_s: float = 0.05):
        self.id, self.coil, self.stuck_closed = valve_id, False, False
        self.open_time_s = open_time_s

    def energize(self, on: bool):
        self.coil = on

    @property
    def is_open(self) -> bool:
        return self.coil and not self.stuck_closed


class Mcc118:
    """±10 V 12 bit ADC. 4–20 mA는 250 Ω 션트로 1–5 V."""

    def __init__(self, spec: AdcSpec, rng: np.random.Generator):
        self.spec, self.rng = spec, rng
        self.lsb = 2 * spec.v_range / (2 ** spec.bits)

    def read_volts(self, v_true: float) -> float:
        v = v_true + self.rng.normal(0, self.spec.noise_V)
        v = np.clip(v, -self.spec.v_range, self.spec.v_range)
        return float(round(v / self.lsb) * self.lsb)

    def read_mA_via_shunt(self, mA_true: float) -> float:
        return self.read_volts(mA_true * self.spec.shunt_ohm / 1000.0) * 1000.0 / self.spec.shunt_ohm


class Mcc134:
    def __init__(self, rng: np.random.Generator, noise_C: float = 0.2):
        self.rng, self.noise = rng, noise_C

    def read_C(self, t_true: float) -> float:
        return float(t_true + self.rng.normal(0, self.noise))


class Stirrer:
    """교반기 외부 입력 4–20 mA ↔ 0–rpm_max (모델 확인 전 가정). 1차 지연 τ = 2 s."""

    def __init__(self, rpm_max: float, tau_s: float = 2.0):
        self.rpm_max, self.tau, self.rpm = rpm_max, tau_s, 0.0

    def step(self, mA: float, dt: float):
        target = 0.0 if mA < 4.0 else self.rpm_max * np.clip((mA - 4.0) / 16.0, 0, 1)
        self.rpm += (target - self.rpm) * min(1.0, dt / self.tau)
        return self.rpm


class PulsePump:
    """접점(펄스) 모드 펌프: pulse() 한 번 = 스트로크 한 번 (운전 허가·수위 OK 일 때)."""

    def __init__(self, spec: PulsePumpSpec, rng: np.random.Generator, pump_id: str):
        self.spec, self.rng, self.id = spec, rng, pump_id
        self.paused, self.level_ok = True, True
        self.strokes_total, self.volume_total_mL, self.pulses_ignored = 0, 0.0, 0
        self.last_pulse_t = -1e9

    def pulse(self, t: float, outlet_open: bool, deliver) -> bool:
        p = self.spec
        if self.paused or not self.level_ok or (t - self.last_pulse_t) < 60.0 / p.max_spm * 0.9:
            self.pulses_ignored += 1                    # 너무 빠른 펄스·정지 상태: 펌프가 무시
            self.last_ignore_reason = "paused" if self.paused else ("level" if not self.level_ok else "too fast")
            return False
        self.last_pulse_t = t
        self.strokes_total += 1
        vol = p.stroke_mL * p.stroke_length * (1 + self.rng.normal(0, p.repro))
        if outlet_open:
            self.volume_total_mL += vol
            deliver(vol)
        return True
