"""두 노드 구조.

  AI 노드 (Pi 5 + AI HAT+, RealSense)      I/O 노드 (Pi 5 + MCC 118 + MCC 134 + MCC 152 ×2)
  ───────────────────────────────            ─────────────────────────────────────────────
  카메라 → 농도 추정 → 레시피/제어   ──cmd──▶  명령 수신, 인터록, 펌프/밸브 구동, 스트로크 계수
  하트비트 0.2 s                     ◀─tele──  10 Hz 텔레메트리 (펌프 피드백, pH, 압력, 온도)
                                               하트비트 1 s 끊기면 SAFE

시뮬레이션에서는 Bus 가 ZeroMQ 를 대신한다. 메시지는 전부 JSON 직렬화 가능한 dict 라서
zmq_bridge.py 처럼 PUB/SUB + PUSH/PULL 로 그대로 옮길 수 있다.
HAL 은 '엔지니어링 단위' 인터페이스다. SimHAL 은 모델에, daqhats_hal.DaqHatsHAL 은 실제 보드에 붙는다.
"""
from __future__ import annotations
from collections import deque
import json
import numpy as np
from .config import SystemConfig, PUMP_IDS, VALVE_IDS, PULSE_PUMP_IDS, PULSE_VALVES, pump_control_mode
from .hardware import PumpChannel, GammaXPump, SolenoidValveNC, Mcc118, Mcc134, Stirrer, PulsePump
from .process import StockTank, Reactor
from .vision import SyntheticCamera
from .loadcell import LoadCellConfig, SimLoadCell, FlowEstimator, FlowCheck


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
    def read_turbidity_ntu(self) -> float: ...
    def pulse(self, pid: str) -> bool: ...
    def step(self, dt: float): ...


class SimPlant:
    """공정 + 장비 모델 전체 (시뮬레이션 전용). AI 노드의 카메라도 여기 반응기를 본다."""

    def __init__(self, cfg: SystemConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        gain_errs = self.rng.uniform(-0.015, 0.015, 3) if cfg.dac.gain_err == 0 else [cfg.dac.gain_err] * 3
        self.channels = {pid: PumpChannel(cfg.dac, float(g)) for pid, g in zip(PUMP_IDS, gain_errs)}
        self.adc = Mcc118(cfg.adc, self.rng)
        if cfg.dac.calibrated:                       # 2점 교정 (루프백 션트로 실측) — 실제 bench calib 절차와 동일
            for ch in self.channels.values():
                ch.enable(True); ch.calibrate_two_point(lambda ch=ch: self.adc.read_mA_via_shunt(ch.actual_mA)); ch.enable(False)
        self.pumps = {pid: GammaXPump(cfg.pump, self.rng, pid) for pid in PUMP_IDS}
        # 펄스 모드 펌프: P-104 + pump_mode == "pulse" 인 P-101~103 (스트로크 부피는 아날로그 사양과 같은 펌프)
        self.pulse_pumps = {pid: PulsePump(cfg.pulse_pump, self.rng, pid) for pid in PULSE_PUMP_IDS}
        for pid in PUMP_IDS:
            if pump_control_mode(cfg, pid) == "pulse":
                from dataclasses import replace as _rp
                self.pulse_pumps[pid] = PulsePump(_rp(cfg.pulse_pump, stroke_mL=cfg.pump.stroke_mL, stroke_length=cfg.pump.stroke_length,
                                                      max_spm=cfg.pump.max_spm), self.rng, pid)
        self.valves = {vid: SolenoidValveNC(vid) for vid in list(VALVE_IDS) + list(PULSE_VALVES.values())}
        self.tanks = [StockTank(ts, d) for ts, d in zip(cfg.tanks, ("C", "M", "Y", "A"))]
        self.reactor = Reactor(cfg.reactor, self.rng)
        self.stirrer = Stirrer(cfg.reactor.rpm_max)
        self.stirrer_mA = 4.0 + 16.0 * cfg.reactor.rpm / cfg.reactor.rpm_max
        self.stirrer.rpm = cfg.reactor.rpm
        self.tc = Mcc134(self.rng)
        self.camera = SyntheticCamera(cfg.camera, self.rng)
        self.loadcells = SimLoadCell(LoadCellConfig(backend="sim"), self.tanks, self.rng)
        self.run_enabled = False
        self.t = 0.0

    def step(self, dt: float):
        for j, pid in enumerate(PUMP_IDS):
            pump, ch, valve, tank = self.pumps[pid], self.channels[pid], self.valves[VALVE_IDS[j]], self.tanks[j]
            pump.s.paused = not self.run_enabled
            pump.level_ok = tank.level_ok

            def deliver(v, j=j, tank=tank):
                drawn = tank.draw(v)
                role = tank.spec.role
                if role == "naoh":
                    self.reactor.add_base(drawn, tank.spec.conc_mol_L)
                elif role == "acid":
                    self.reactor.add_acid_solution(drawn, tank.spec.conc_mol_L)
                elif role in ("cacl2", "na2co3", "citrate"):
                    self.reactor.add_feed(role, drawn, tank.spec.conc_mol_L)
                else:
                    self.reactor.add(j, drawn, tank.conc_mg_L)

            pump.step(ch.actual_mA, dt, valve.is_open, deliver)
        self.reactor.rpm = self.stirrer.step(self.stirrer_mA, dt)
        self.reactor.step(dt)
        self.camera.turbidity_ntu = self.reactor.turbidity_ntu
        self.loadcells.step(dt)
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

    def read_turbidity_ntu(self):   # 탁도계 4–20 mA ↔ 0–1000 NTU
        return 1000.0 * (self.p.adc.read_mA_via_shunt(4.0 + 16.0 * min(self.p.reactor.turbidity_ntu, 1000.0) / 1000.0) - 4.0) / 16.0

    def read_tank_mass_g(self):
        return self.p.loadcells.read_g()

    def pulse(self, pid):
        """접점 펄스 1회 → 펌프 스트로크 1회 (밸브 열림·운전 허가·수위 OK 일 때 반응기로)."""
        p = self.p
        j = PUMP_IDS.index(pid) if pid in PUMP_IDS else 3 + list(PULSE_PUMP_IDS).index(pid)
        tank = p.tanks[j]; valve_id = VALVE_IDS[j] if pid in PUMP_IDS else PULSE_VALVES[pid]
        pump = p.pulse_pumps[pid]; pump.paused = not p.run_enabled; pump.level_ok = tank.level_ok

        def deliver(v):
            drawn = tank.draw(v)
            if tank.spec.role == "acid":
                p.reactor.add_acid_solution(drawn, tank.spec.conc_mol_L)
            elif tank.spec.role == "naoh":
                p.reactor.add_base(drawn, tank.spec.conc_mol_L)
            elif tank.spec.role in ("cacl2", "na2co3", "citrate"):
                p.reactor.add_feed(tank.spec.role, drawn, tank.spec.conc_mol_L)
            else:
                p.reactor.add(min(j, 2), drawn, tank.conc_mg_L)
        return pump.pulse(p.t, p.valves[valve_id].is_open, deliver)

    def step(self, dt):
        self.p.step(dt)


# 실제 보드용 HAL 은 daqhats_hal.DaqHatsHAL (MCC 152/118/134)


# ------------------------------------------------------------------ I/O 노드
class IONode:
    """실시간 책임: 명령 적용, 인터록, 스트로크 계수 도징, 워치독, 텔레메트리."""

    def __init__(self, cfg: SystemConfig, hal: HAL, bus: Bus):
        self.cfg, self.hal, self.bus = cfg, hal, bus
        self.mode = "SAFE"
        self.cmd_mA = {pid: 0.0 for pid in PUMP_IDS}
        self.valve_on = {vid: False for vid in list(VALVE_IDS) + list(PULSE_VALVES.values())}
        self.run_en = False
        self.dose_target = {pid: None for pid in PUMP_IDS}   # 남은 스트로크 수 (도징 모드)
        self.strokes = {pid: 0.0 for pid in PUMP_IDS}
        self.dosed_mL = {pid: 0.0 for pid in PUMP_IDS}
        # 펄스 펌프 (P-104 …): 지령 spm, 남은 스트로크, 위상 누적, 계수
        self.pulse_ids = tuple(PULSE_PUMP_IDS) + tuple(pid for pid in PUMP_IDS if pump_control_mode(cfg, pid) == "pulse")
        self.pulse_spm = {pid: 0.0 for pid in self.pulse_ids}
        self.pulse_target = {pid: None for pid in self.pulse_ids}
        self.pulse_phase = {pid: 0.0 for pid in self.pulse_ids}
        self.pulse_strokes = {pid: 0 for pid in self.pulse_ids}
        self.pulse_dosed_mL = {pid: 0.0 for pid in self.pulse_ids}
        self.pulse_last_t = {pid: -1e9 for pid in self.pulse_ids}
        self.has_pulse = hasattr(hal, "pulse")
        # 실시간 오버라이드: 운전 중 펌프 속도 배율(0~1.5) 과 일시 보류. 도징 목표(스트로크 수)는 그대로 둔다
        all_ids = tuple(PUMP_IDS) + tuple(PULSE_PUMP_IDS)
        self.rate_scale = {pid: 1.0 for pid in all_ids}
        self.hold = {pid: False for pid in all_ids}
        self.base_spm = {pid: 0.0 for pid in all_ids}      # 명령 원본 (배율 적용 전)
        self.base_mA = {pid: 0.0 for pid in all_ids}
        self.publish_sim_camera = False          # io_node_main run --sim 에서 켠다
        self.alarms: list = []
        self.last_hb = 0.0
        self._last_tele = -1e9
        self.t = 0.0
        self.stirrer_mA = 4.0 + 16.0 * cfg.reactor.rpm / cfg.reactor.rpm_max
        self._cmd_t: dict = {}
        # 로드셀 유량 감시 (HAL 이 read_tank_mass_g 를 주면 켜짐)
        self.has_loadcell = hasattr(hal, "read_tank_mass_g")
        self.lc_cfg = getattr(hal, "lc_cfg", None) or LoadCellConfig(backend="sim")
        self.flow_est = {pid: FlowEstimator(self.lc_cfg, j) for j, pid in enumerate(PUMP_IDS)}
        self.flow_chk = FlowCheck()
        self._exp_hist = {pid: [] for pid in PUMP_IDS}     # (t, 기대 유량) — 로드셀 창과 같은 길이로 평균해 비교 (지령이 매초 바뀌는 pH 제어 등)
        self.flow_state = {pid: dict(mass_g=None, flow_mL_min=0.0, delivered_mL=0.0, valid=False, low=False, status="NO_DATA", ratio=float("nan"))
                           for pid in PUMP_IDS}
        self._next_lc = 0.0
        self.safe("boot")

    # ---- 안전
    def safe(self, why: str):
        self.hal.run_enable(False)              # 1) Pause 먼저 (0 mA 알람 회피)
        for pid in PUMP_IDS:
            self.cmd_mA[pid] = 0.0
            self.hal.pump_set_mA(pid, 0.0)
            self.hal.pump_enable(pid, False)    # 2) XTR111 OD High → 0 mA
            self.dose_target[pid] = None
        for pid in self.pulse_ids:
            self.pulse_spm[pid] = 0.0; self.pulse_target[pid] = None
        for vid in list(VALVE_IDS) + list(PULSE_VALVES.values()):   # 3) 밸브 닫힘 (NC)
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
        elif c == "pump":                       # 연속 운전 (mA 직접). 펄스 모드 펌프면 같은 유량의 spm 으로
            pid = m["id"]
            if pid in self.pulse_ids:
                self._set_pulse(pid, self._spm_from_mA(float(m["mA"])))
            else:
                self._set_pump(pid, float(m["mA"]))
        elif c == "dose":                       # 스트로크 계수 도징: I/O 노드가 끝까지 책임
            pid = m["id"]
            if pid in self.pulse_ids:
                self.pulse_target[pid] = int(round(float(m["strokes"])))
                self._set_pulse(pid, self._spm_from_mA(float(m["mA"])))
            else:
                self.dose_target[pid] = float(m["strokes"])
                self._set_pump(pid, float(m["mA"]))
        elif c == "pulse_rate":                 # 펄스 펌프 연속 운전: spm
            self._set_pulse(m["id"], float(m["spm"]))
        elif c == "pulse_dose":                 # 펄스 펌프 스트로크 계수 도징
            pid = m["id"]
            self.pulse_target[pid] = int(m["strokes"])
            self._set_pulse(pid, float(m.get("spm", self.cfg.pulse_pump.max_spm)))
        elif c == "rate_scale":                 # 실시간: 펌프 속도 배율 (0 = 정지, 1 = 지령대로, 최대 1.5)
            pid = m["id"]; self.rate_scale[pid] = float(np.clip(float(m["factor"]), 0.0, 1.5)); self._reapply(pid)
        elif c == "hold":                       # 실시간: 펌프 일시 보류/재개 (도징 목표 유지)
            pid = m["id"]; self.hold[pid] = bool(m["on"]); self._reapply(pid)
        elif c == "batch_reset":                # 스트로크 누적·로드셀 누적 기준을 지금으로
            for pid in PUMP_IDS:
                self.dosed_mL[pid] = 0.0; self.strokes[pid] = 0.0; self.flow_est[pid].reset_batch()
        elif c == "stop":
            self.base_spm[m["id"]] = 0.0; self.base_mA[m["id"]] = 0.0
            if m["id"] in self.pulse_ids:
                self.pulse_spm[m["id"]] = 0.0; self.pulse_target[m["id"]] = None
            else:
                self._set_pump(m["id"], 0.0)
                self.dose_target[m["id"]] = None
        elif c == "reset_faults":
            if hasattr(self.hal, "p"):
                for pp in self.hal.p.pumps.values():
                    pp.reset_fault()

    def _effective(self, pid, value):
        return 0.0 if self.hold.get(pid) else value * self.rate_scale.get(pid, 1.0)

    def _mA_from_spm(self, spm):
        p = self.cfg.pump
        return 0.0 if spm <= 0 else float(p.i_start_mA + (p.i_full_mA - p.i_start_mA) * min(spm, p.max_spm) / p.max_spm)

    def _reapply(self, pid):
        """배율/보류가 바뀌면 현재 명령을 다시 적용한다."""
        if pid in self.pulse_ids:
            if self.base_spm[pid] > 0 or self.pulse_spm[pid] > 0:
                self._set_pulse(pid, self.base_spm[pid], _raw=True)
        else:
            if self.base_mA[pid] > 0 or self.cmd_mA[pid] > 0:
                self._set_pump(pid, self.base_mA[pid], _raw=True)

    def _spm_from_mA(self, mA):
        p = self.cfg.pump
        return 0.0 if mA < p.i_start_mA else float(min(p.max_spm, p.max_spm * (mA - p.i_start_mA) / (p.i_full_mA - p.i_start_mA)))

    def _set_pulse(self, pid, spm, _raw=False):
        if self.mode != "RUN":
            self.alarm(f"REJECT {pid}: node not armed"); return
        vid = PULSE_VALVES[pid] if pid in PULSE_VALVES else VALVE_IDS[PUMP_IDS.index(pid)]
        if spm > 0 and not self.valve_on[vid]:
            self.alarm(f"INTERLOCK {pid}: valve {vid} closed"); return
        if spm > 0 and not self.run_en:
            self.alarm(f"INTERLOCK {pid}: run_enable off"); return
        if not self.has_pulse:
            self.alarm(f"REJECT {pid}: HAL has no pulse output"); return
        self.base_spm[pid] = float(spm)
        spec = self.cfg.pump if pid in PUMP_IDS else self.cfg.pulse_pump
        self.pulse_spm[pid] = float(min(self._effective(pid, spm), spec.max_spm))

    def _set_pump(self, pid, mA, _raw=False):
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
        self.base_mA[pid] = float(mA)
        mA = self._mA_from_spm(self._effective(pid, self._spm_from_mA(mA))) if mA > 0 else 0.0
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

        if self.has_loadcell and t >= self._next_lc:
            self._next_lc = t + 1.0 / self.lc_cfg.rate_hz
            try:
                masses = self.hal.read_tank_mass_g()
            except Exception as e:
                masses = [None] * 3; self.alarm(f"LOADCELL read error: {e!r}")
            for j, pid in enumerate(PUMP_IDS):
                st = self.flow_est[pid].push(t, masses[j] if j < len(masses) else None)
                exp_spm = self.pulse_spm[pid] if pid in self.pulse_ids else self._spm_from_mA(self.cmd_mA[pid])
                exp_now = min(exp_spm, self.cfg.pump.max_spm) * self.cfg.pump.stroke_mL * self.cfg.pump.stroke_length
                hist_e = self._exp_hist[pid]; hist_e.append((t, exp_now))
                self._exp_hist[pid] = hist_e = [(tt, v) for tt, v in hist_e if t - tt <= self.lc_cfg.window_s]
                exp_flow = sum(v for _, v in hist_e) / len(hist_e)          # 로드셀 기울기 창과 같은 창의 평균 지령 유량
                status, ratio = self.flow_chk.check(t, pid, exp_flow, st)
                st.update(status=status, ratio=None if ratio != ratio else round(ratio, 3))
                self.flow_state[pid] = st
                if status == "FLOW_LOW":
                    self.alarm(f"FLOW_LOW {pid}: loadcell {st['flow_mL_min']:.1f} vs expected {exp_flow:.1f} mL/min (air/tube wear/stall?)")
                elif status == "FLOW_HIGH":
                    self.alarm(f"FLOW_HIGH {pid}: loadcell {st['flow_mL_min']:.1f} vs expected {exp_flow:.1f} mL/min (siphon/leak?)")
                elif status == "TANK_LOW":
                    self.alarm(f"TANK_LOW {pid}: {st['mass_g']} g")
                # 스트로크 계수 vs 로드셀 누적 (배치 기준)
                if self.dosed_mL[pid] > 10.0 and st["valid"] and st["delivered_mL"] < 0.7 * self.dosed_mL[pid]:
                    self.alarm(f"VOLUME_MISMATCH {pid}: strokes say {self.dosed_mL[pid]:.1f} mL, loadcell {st['delivered_mL']:.1f} mL")

        # 펄스 펌프: 위상 누적 → 펄스 출력 (틱당 최대 2회)
        for pid in self.pulse_ids:
            if self.pulse_spm[pid] > 0 and self.mode == "RUN":
                spec = self.cfg.pump if pid in PUMP_IDS else self.cfg.pulse_pump
                self.pulse_phase[pid] = min(self.pulse_phase[pid] + self.pulse_spm[pid] / 60.0 * dt, 2.0)
                min_gap = 60.0 / spec.max_spm * 0.95            # 펌프 최대 스트로크 속도보다 빠른 펄스는 내지 않는다 (펌프가 무시함)
                n = 1 if (self.pulse_phase[pid] >= 1.0 and t - self.pulse_last_t[pid] >= min_gap) else 0
                for _ in range(n):
                    self.pulse_phase[pid] -= 1.0
                    self.pulse_last_t[pid] = t
                    if self.hal.pulse(pid):
                        self.pulse_strokes[pid] += 1
                        self.pulse_dosed_mL[pid] += spec.stroke_mL * spec.stroke_length
                        if pid in PUMP_IDS:                 # 아날로그 펌프와 같은 집계에 반영 (AI 노드는 pumps[...] 만 본다)
                            self.strokes[pid] += 1; self.dosed_mL[pid] += spec.stroke_mL * spec.stroke_length
                        if self.pulse_target[pid] is not None:
                            self.pulse_target[pid] -= 1
                            if self.pulse_target[pid] <= 0:
                                self.pulse_spm[pid] = 0.0; self.pulse_target[pid] = None; break
                    else:
                        self.alarm(f"PULSE_IGNORED {pid}: pump paused/level/too fast")
            else:
                self.pulse_phase[pid] = 0.0

        est_V = self.cfg.reactor.heel_mL + sum(self.dosed_mL.values()) + sum(v for k, v in self.pulse_dosed_mL.items() if k not in PUMP_IDS)
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
                pumps={pid: (dict(cmd_mA=0.0, fb_mA=None, spm=round(self.pulse_spm[pid], 1), strokes=round(self.strokes[pid], 2),
                                  dosed_mL=round(self.dosed_mL[pid], 3), dosing=self.pulse_target[pid] is not None, mode="pulse",
                                  scale=self.rate_scale[pid], hold=self.hold[pid], remaining=self.pulse_target[pid])
                             if pid in self.pulse_ids else
                             dict(cmd_mA=round(self.cmd_mA[pid], 3), fb_mA=round(fb[pid][0], 3),
                                  spm=round(fb[pid][1], 1), strokes=round(self.strokes[pid], 2),
                                  dosed_mL=round(self.dosed_mL[pid], 3),
                                  dosing=self.dose_target[pid] is not None, mode="analog",
                                  scale=self.rate_scale[pid], hold=self.hold[pid],
                                  remaining=(None if self.dose_target[pid] is None else round(self.dose_target[pid])))) for pid in PUMP_IDS},
                valves=dict(self.valve_on), ph=round(self.hal.read_ph(), 3),
                pressure_bar=round(p_bar, 3), temp_C=round(self.hal.read_temp_C(), 2),
                turbidity_ntu=round(self.hal.read_turbidity_ntu(), 1) if hasattr(self.hal, "read_turbidity_ntu") else None,
                est_volume_mL=round(est_V, 1), alarms=len(self.alarms),
                tanks={pid: dict(self.flow_state[pid]) for pid in PUMP_IDS} if self.has_loadcell else {},
                pulse_pumps={pid: dict(spm=round(self.pulse_spm[pid], 2), strokes=self.pulse_strokes[pid],
                                       dosed_mL=round(self.pulse_dosed_mL[pid], 3), dosing=self.pulse_target[pid] is not None)
                             for pid in self.pulse_ids},
                sim_camera=(dict(rgb=[int(v) for v in self.hal.p.camera.roi_rgb8(self.hal.p.reactor.c_obs)])
                            if hasattr(self.hal, "p") and self.publish_sim_camera else None)))



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
