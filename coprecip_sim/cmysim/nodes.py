"""두 노드 구조.

  AI 노드 (Pi 5 + AI HAT+, RealSense)      I/O 노드 (Pi 5 + MCC 118 + MCC 134 + MCC 152 ×2)
  ───────────────────────────────            ─────────────────────────────────────────────
  카메라 → 농도 추정 → 레시피/제어   ──cmd──▶  명령 수신, 인터록, 펌프/밸브 구동, 스트로크 계수
  하트비트 0.2 s                     ◀─tele──  10 Hz 텔레메트리 (펌프 피드백, pH, 압력, 온도)
                                               하트비트 1 s 끊기면 SAFE

시뮬레이션에서는 Bus 가 ZeroMQ 를 대신한다. 메시지는 전부 JSON 직렬화 가능한 dict 라서
zmq_bridge.py 처럼 PUB/SUB + PUSH/PULL 로 그대로 옮길 수 있다.
HAL 은 '엔지니어링 단위' 인터페이스다. SimHAL 은 모델에, DaqHatsHAL 은 실제 보드에 붙는다.
"""
from __future__ import annotations
from collections import deque
import json
import numpy as np
from .config import SystemConfig, PUMP_IDS, VALVE_IDS
from .hardware import PumpChannel, GammaXPump, SolenoidValveNC, Mcc118, Mcc134, Stirrer
from .process import StockTank, Reactor
from .vision import SyntheticCamera


# ------------------------------------------------------------------ 메시지 버스
class Bus:
    def __init__(self):
        self.cmd_q: deque = deque()
        self.tele_q: deque = deque(maxlen=1000)
        self.log: list = []

    def send_cmd(self, msg: dict):
        self.cmd_q.append(json.loads(json.dumps(msg)))   # 직렬화 가능성 검사 겸 복사
        self.log.append(("cmd", msg))

    def drain_cmds(self):
        out = list(self.cmd_q)
        self.cmd_q.clear()
        return out

    def publish(self, msg: dict):
        self.tele_q.append(json.loads(json.dumps(msg)))

    def latest(self):
        return self.tele_q[-1] if self.tele_q else None


# ------------------------------------------------------------------ HAL
class HAL:
    """I/O 노드가 쓰는 하드웨어 추상층. 실제 보드에서는 DaqHatsHAL 로 교체."""
    def pump_set_mA(self, pid: str, mA: float): ...
    def pump_enable(self, pid: str, on: bool): ...
    def valve(self, vid: str, on: bool): ...
    def run_enable(self, on: bool): ...
    def stirrer_set_mA(self, mA: float): ...
    def read_feedback_mA(self, pid: str) -> float: ...
    def read_ph(self) -> float: ...
    def read_pressure_bar(self) -> float: ...
    def read_temp_C(self) -> float: ...
    def step(self, dt: float): ...


class SimPlant:
    """공정 + 장비 모델 전체 (시뮬레이션 전용). AI 노드의 카메라도 여기 반응기를 본다."""

    def __init__(self, cfg: SystemConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        gain_errs = self.rng.uniform(-0.015, 0.015, 3) if cfg.dac.gain_err == 0 else [cfg.dac.gain_err] * 3
        self.channels = {pid: PumpChannel(cfg.dac, float(g)) for pid, g in zip(PUMP_IDS, gain_errs)}
        self.pumps = {pid: GammaXPump(cfg.pump, self.rng, pid) for pid in PUMP_IDS}
        self.valves = {vid: SolenoidValveNC(vid) for vid in VALVE_IDS}
        self.tanks = [StockTank(ts, d) for ts, d in zip(cfg.tanks, ("C", "M", "Y"))]
        self.reactor = Reactor(cfg.reactor)
        self.stirrer = Stirrer(cfg.reactor.rpm_max)
        self.stirrer_mA = 4.0 + 16.0 * cfg.reactor.rpm / cfg.reactor.rpm_max
        self.stirrer.rpm = cfg.reactor.rpm
        self.adc = Mcc118(cfg.adc, self.rng)
        self.tc = Mcc134(self.rng)
        self.camera = SyntheticCamera(cfg.camera, self.rng)
        self.run_enabled = False
        self.t = 0.0

    def step(self, dt: float):
        for j, pid in enumerate(PUMP_IDS):
            pump, ch, valve, tank = self.pumps[pid], self.channels[pid], self.valves[VALVE_IDS[j]], self.tanks[j]
            pump.s.paused = not self.run_enabled
            pump.level_ok = tank.level_ok

            def deliver(v, j=j, tank=tank):
                self.reactor.add(j, tank.draw(v), tank.conc_mg_L)

            pump.step(ch.actual_mA, dt, valve.is_open, deliver)
        self.reactor.rpm = self.stirrer.step(self.stirrer_mA, dt)
        self.reactor.step(dt)
        self.t += dt


class SimHAL(HAL):
    def __init__(self, plant: SimPlant):
        self.p = plant

    def pump_set_mA(self, pid, mA):
        self.p.channels[pid].set_mA(mA)

    def pump_enable(self, pid, on):
        self.p.channels[pid].enable(on)

    def valve(self, vid, on):
        self.p.valves[vid].energize(on)

    def run_enable(self, on):
        self.p.run_enabled = on

    def stirrer_set_mA(self, mA):
        self.p.stirrer_mA = mA

    def read_feedback_mA(self, pid):
        return self.p.adc.read_mA_via_shunt(self.p.pumps[pid].feedback_mA())

    def read_ph(self):      # pH 트랜스미터 4–20 mA ↔ pH 0–14
        return 14.0 * (self.p.adc.read_mA_via_shunt(4.0 + 16.0 * self.p.reactor.ph / 14.0) - 4.0) / 16.0

    def read_pressure_bar(self):  # 압력 트랜스미터 4–20 mA ↔ 0–10 bar
        pmax = max(pp.s.pressure_bar for pp in self.p.pumps.values())
        return 10.0 * (self.p.adc.read_mA_via_shunt(4.0 + 1.6 * pmax) - 4.0) / 16.0

    def read_temp_C(self):
        return self.p.tc.read_C(self.p.reactor.temp_C)

    def step(self, dt):
        self.p.step(dt)


class DaqHatsHAL(HAL):
    """실제 보드용 (Pi 5 + daqhats). 이 저장소에서는 실행하지 않았다. 채널 배정은 cfg.channel_map."""

    def __init__(self, cfg: SystemConfig, addr=(0, 1, 2, 3)):
        from daqhats import mcc152, mcc118, mcc134, DIOConfigItem  # noqa: F401  (Pi 에서만)
        self.cfg = cfg
        self.b = {"mcc152#1": mcc152(addr[0]), "mcc152#2": mcc152(addr[1]),
                  "mcc118": mcc118(addr[2]), "mcc134": mcc134(addr[3])}
        for k in ("mcc152#1", "mcc152#2"):
            for ch in range(8):
                self.b[k].dio_config_write_bit(ch, DIOConfigItem.DIRECTION, 0)  # 출력
                self.b[k].dio_output_write_bit(ch, 1 if ch < 4 else 0)         # OD High(출력 꺼짐), 밸브 OFF
        self.mA_per_V = cfg.dac.mA_per_V

    def _ao(self, key):
        board, ch = self.cfg.channel_map[key]
        return self.b[board], int(ch[2:])

    def _dio(self, key):
        board, ch = self.cfg.channel_map[key]
        return self.b[board], int(ch[3:])

    def pump_set_mA(self, pid, mA):
        b, ch = self._ao(pid)
        b.a_out_write(ch, float(np.clip(mA / self.mA_per_V, 0, 5)))

    def pump_enable(self, pid, on):
        b, ch = self._ao(pid)             # OD 핀 = 같은 보드 DIO(2·ch): AO0→DIO0, AO1→DIO2 (보드 설계와 일치시킬 것)
        b.dio_output_write_bit(2 * ch, 0 if on else 1)

    def valve(self, vid, on):
        b, ch = self._dio(vid)
        b.dio_output_write_bit(ch, 1 if on else 0)

    def run_enable(self, on):
        b, ch = self._dio("RUN_ENABLE")
        b.dio_output_write_bit(ch, 1 if on else 0)

    def stirrer_set_mA(self, mA):
        b, ch = self._ao("STIRRER")
        b.a_out_write(ch, float(np.clip(mA / self.mA_per_V, 0, 5)))

    def _ai_mA(self, key):
        board, ch = self.cfg.channel_map[key]
        return self.b[board].a_in_read(int(ch[2:])) * 1000.0 / self.cfg.adc.shunt_ohm

    def read_feedback_mA(self, pid):
        return self._ai_mA("FB-" + pid[-3:])

    def read_ph(self):
        return 14.0 * (self._ai_mA("PH") - 4.0) / 16.0

    def read_pressure_bar(self):
        return 10.0 * (self._ai_mA("PRESSURE") - 4.0) / 16.0

    def read_temp_C(self):
        board, ch = self.cfg.channel_map["TEMP"]
        return self.b[board].t_in_read(int(ch[2:]))

    def step(self, dt):
        pass


# ------------------------------------------------------------------ I/O 노드
class IONode:
    """실시간 책임: 명령 적용, 인터록, 스트로크 계수 도징, 워치독, 텔레메트리."""

    def __init__(self, cfg: SystemConfig, hal: HAL, bus: Bus):
        self.cfg, self.hal, self.bus = cfg, hal, bus
        self.mode = "SAFE"
        self.cmd_mA = {pid: 0.0 for pid in PUMP_IDS}
        self.valve_on = {vid: False for vid in VALVE_IDS}
        self.run_en = False
        self.dose_target = {pid: None for pid in PUMP_IDS}   # 남은 스트로크 수 (도징 모드)
        self.strokes = {pid: 0.0 for pid in PUMP_IDS}
        self.dosed_mL = {pid: 0.0 for pid in PUMP_IDS}
        self.alarms: list = []
        self.last_hb = 0.0
        self._last_tele = -1e9
        self.t = 0.0
        self.stirrer_mA = 4.0 + 16.0 * cfg.reactor.rpm / cfg.reactor.rpm_max
        self._cmd_t: dict = {}
        self.safe("boot")

    # ---- 안전
    def safe(self, why: str):
        self.hal.run_enable(False)              # 1) Pause 먼저 (0 mA 알람 회피)
        for pid in PUMP_IDS:
            self.cmd_mA[pid] = 0.0
            self.hal.pump_set_mA(pid, 0.0)
            self.hal.pump_enable(pid, False)    # 2) XTR111 OD High → 0 mA
            self.dose_target[pid] = None
        for vid in VALVE_IDS:                   # 3) 밸브 닫힘 (NC)
            self.valve_on[vid] = False
            self.hal.valve(vid, False)
        self.run_en = False
        if self.mode != "SAFE":
            self.alarms.append((self.t, f"SAFE: {why}"))
        self.mode = "SAFE"

    def alarm(self, msg):
        if not self.alarms or self.alarms[-1][1] != msg:
            self.alarms.append((self.t, msg))

    # ---- 명령
    def handle(self, m: dict):
        c = m.get("cmd")
        if c == "heartbeat":
            self.last_hb = self.t
        elif c == "arm":
            self.mode = "RUN"
            self.last_hb = self.t
        elif c == "safe":
            self.safe("commanded")
        elif c == "run_enable":
            self.run_en = bool(m["on"])
            self.hal.run_enable(self.run_en)
        elif c == "valve":
            self.valve_on[m["id"]] = bool(m["open"])
            self.hal.valve(m["id"], self.valve_on[m["id"]])
        elif c == "stirrer_rpm":
            self.stirrer_mA = 4.0 + 16.0 * float(np.clip(m["rpm"] / self.cfg.reactor.rpm_max, 0, 1))
            self.hal.stirrer_set_mA(self.stirrer_mA)
        elif c == "pump":                       # 연속 운전 (mA 직접)
            self._set_pump(m["id"], float(m["mA"]))
        elif c == "dose":                       # 스트로크 계수 도징: I/O 노드가 끝까지 책임
            pid = m["id"]
            self.dose_target[pid] = float(m["strokes"])
            self._set_pump(pid, float(m["mA"]))
        elif c == "stop":
            self._set_pump(m["id"], 0.0)
            self.dose_target[m["id"]] = None
        elif c == "reset_faults":
            if hasattr(self.hal, "p"):
                for pp in self.hal.p.pumps.values():
                    pp.reset_fault()

    def _set_pump(self, pid, mA):
        if self.mode != "RUN":
            self.alarm(f"REJECT {pid}: node not armed")
            return
        vid = VALVE_IDS[PUMP_IDS.index(pid)]
        if mA > 0 and not self.valve_on[vid]:   # 인터록: 밸브 닫힌 채 펌프 금지 (데드헤드 → 릴리프)
            self.alarm(f"INTERLOCK {pid}: valve {vid} closed")
            return
        if mA > 0 and not self.run_en:
            self.alarm(f"INTERLOCK {pid}: run_enable off")
            return
        self.cmd_mA[pid] = mA
        self.hal.pump_enable(pid, mA > 0)
        self.hal.pump_set_mA(pid, mA)

    # ---- 주기 실행
    def tick(self, t: float):
        dt, self.t = t - self.t if t > self.t else self.cfg.dt, t
        for m in self.bus.drain_cmds():
            self.handle(m)
        if self.mode == "RUN" and t - self.last_hb > self.cfg.net.heartbeat_timeout_s:
            self.safe(f"watchdog: no heartbeat for {t - self.last_hb:.1f}s")

        fb = {}
        for pid in PUMP_IDS:
            mA_fb = self.hal.read_feedback_mA(pid)
            spm = max(0.0, (mA_fb - 4.0) / 16.0 * self.cfg.pump.max_spm) if mA_fb > 3.0 else 0.0
            if spm < 2.0:
                spm = 0.0                        # ADC 잡음 바닥
            fb[pid] = (mA_fb, spm)
            if self.cmd_mA[pid] > 0:
                ds = spm / 60.0 * dt
                self.strokes[pid] += ds
                self.dosed_mL[pid] += ds * self.cfg.pump.stroke_mL * self.cfg.pump.stroke_length
                tgt = self.dose_target[pid]
                if tgt is not None:
                    self.dose_target[pid] = tgt - ds
                    if self.dose_target[pid] <= 0:
                        self._set_pump(pid, 0.0)
                        self.dose_target[pid] = None
                # 지령은 있는데 스트로크가 없음 → 펌프 알람/수위/신호 문제
                if self.cmd_mA[pid] >= self.cfg.pump.i_start_mA + 0.5 and spm == 0.0 and t - self._cmd_t.get(pid, t) > 1.0:
                    self.alarm(f"NO_STROKE {pid}: commanded {self.cmd_mA[pid]:.1f} mA, feedback {mA_fb:.1f} mA")
                self._cmd_t.setdefault(pid, t)
            else:
                self._cmd_t.pop(pid, None)

        est_V = self.cfg.reactor.heel_mL + sum(self.dosed_mL.values())
        if est_V > self.cfg.reactor.v_max_mL * 0.98 and self.mode == "RUN":
            self.safe("reactor volume limit (stroke-count estimate)")
        p_bar = self.hal.read_pressure_bar()
        if p_bar > self.cfg.pump.relief_bar * 0.9 and self.mode == "RUN" and any(v > 0 for v in self.cmd_mA.values()):
            # 데드헤드(밸브 고착 등): 릴리프로 탱크 순환만 하므로 도징 중인 펌프를 모두 멈춘다
            self.alarm(f"RELIEF: discharge pressure {p_bar:.1f} bar -> pumps stopped")
            for pid in PUMP_IDS:
                if self.cmd_mA[pid] > 0:
                    self._set_pump(pid, 0.0)
                    self.dose_target[pid] = None

        if t - self._last_tele >= 1.0 / self.cfg.net.telemetry_hz - 1e-9:
            self._last_tele = t
            self.bus.publish(dict(
                t=round(t, 3), mode=self.mode, run_enable=self.run_en,
                pumps={pid: dict(cmd_mA=round(self.cmd_mA[pid], 3), fb_mA=round(fb[pid][0], 3),
                                 spm=round(fb[pid][1], 1), strokes=round(self.strokes[pid], 2),
                                 dosed_mL=round(self.dosed_mL[pid], 3),
                                 dosing=self.dose_target[pid] is not None) for pid in PUMP_IDS},
                valves=dict(self.valve_on), ph=round(self.hal.read_ph(), 3),
                pressure_bar=round(p_bar, 3), temp_C=round(self.hal.read_temp_C(), 2),
                est_volume_mL=round(est_V, 1), alarms=len(self.alarms)))



# ------------------------------------------------------------------ AI 노드
class AINode:
    """비전(카메라 → 농도) + 제어기. 실시간 구동은 안 하고 I/O 노드에 명령만 보낸다."""

    def __init__(self, cfg: SystemConfig, bus: Bus, camera: SyntheticCamera, controller, heartbeat_s=0.2):
        self.cfg, self.bus, self.camera, self.ctl = cfg, bus, camera, controller
        self.hb_period, self._last_hb, self.alive = heartbeat_s, -1e9, True
        self.rows: list = []

    def tick(self, t: float, c_obs_true_for_camera: np.ndarray):
        """c_obs_true_for_camera 는 시뮬레이션에서만 넘긴다 (실제는 RealSense 프레임)."""
        if not self.alive:
            return
        if t - self._last_hb >= self.hb_period:
            self.bus.send_cmd(dict(cmd="heartbeat", t=t))
            self._last_hb = t
        tele = self.bus.latest()
        rgb = self.camera.roi_rgb8(c_obs_true_for_camera)
        row = self.ctl.step(t, tele, rgb, self.bus)
        if row is not None:
            self.rows.append(row)
