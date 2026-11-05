"""레시피 계획과 제어기 (AI 노드에서 실행).

흐름
  PLAN  : 목표색(hex 또는 CMY mg/L) → 목표 농도 c* → 투입 부피 V_j → 펌프 유량/스트로크 수
  PRIME : 교반 rpm 지령, 밸브 열기, 운전 허가
  DOSE  : 피드포워드. I/O 노드에 dose(id, mA, strokes) 명령 → 끝나면 밸브 닫기
  SETTLE: 혼합시간 3·t_m 대기
  TRIM  : (closed 모드) 카메라 추정 ĉ 와 c* 의 차이로 추가 투입량 계산 → DOSE 반복 (최대 n회)
  DONE  : 운전 허가 OFF
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .config import SystemConfig, PUMP_IDS, VALVE_IDS, pump_max_rate_mL_min
from .process import dose_volumes
from . import optics


@dataclass
class Recipe:
    target_rgb8: np.ndarray            # 목표색 (sRGB 8bit)
    c_target: np.ndarray               # 목표 농도 [mg/L] (C, M, Y)
    mode: str = "closed"               # "open" | "closed"
    dose_minutes: float = 2.0          # 피드포워드 도징 시간 (가장 많이 넣는 펌프 기준)
    flow_factor: np.ndarray = field(default_factory=lambda: np.ones(3))  # 유량 스윕용 배율 (1 = 계획대로)
    de_match: float = 1.5              # 이 ΔE2000 아래면 '매칭'
    trim_tol_mg_L: float = 0.4
    max_trims: int = 4
    settle_factor: float = 3.0         # 혼합시간의 몇 배를 기다리나
    rpm: float | None = None


def target_from_hex(cfg: SystemConfig, hex_color: str) -> tuple[np.ndarray, np.ndarray, float]:
    """목표 hex → (목표 RGB, 목표 농도, 도달 가능 잔차 ΔE). 스톡·광학 모델에서 못 내는 색이면 가장 가까운 색으로."""
    rgb = optics.hex_to_rgb8(hex_color)
    cam = cfg.camera
    c = optics.rgb8_to_conc(cam.E, cam.I0, rgb, cam.gamma, cam.glare)
    reach = optics.conc_to_rgb8(cam.E, cam.I0, c, cam.gamma, cam.glare)
    return reach, c, optics.delta_e2000(rgb, reach)


def target_from_cmy(cfg: SystemConfig, c_target) -> tuple[np.ndarray, np.ndarray]:
    cam = cfg.camera
    c = np.asarray(c_target, float)
    return optics.conc_to_rgb8(cam.E, cam.I0, c, cam.gamma, cam.glare), c


def mA_for_rate(cfg: SystemConfig, rate_mL_min: float) -> float:
    p = cfg.pump
    spm = rate_mL_min / (p.stroke_mL * p.stroke_length)
    if spm <= 0:
        return 0.0
    return float(p.i_start_mA + (p.i_full_mA - p.i_start_mA) * np.clip(spm / p.max_spm, 0, 1))


def plan_doses(cfg: SystemConfig, V_heel_mL: float, c_target: np.ndarray, dose_minutes: float,
               flow_factor=np.ones(3)) -> list[dict]:
    """각 펌프의 투입 부피·스트로크 수·유량·mA 계획."""
    c_stock = np.array([t.conc_mg_L for t in cfg.tanks])
    V = dose_volumes(V_heel_mL, c_target, c_stock) * np.asarray(flow_factor, float)
    rmax = pump_max_rate_mL_min(cfg)
    T = max(dose_minutes, float(np.max(V)) / rmax)         # 가장 많이 넣는 펌프가 최대 유량을 넘지 않게
    out = []
    for j, pid in enumerate(PUMP_IDS):
        rate = V[j] / T
        strokes = V[j] / (cfg.pump.stroke_mL * cfg.pump.stroke_length)
        out.append(dict(id=pid, valve=VALVE_IDS[j], volume_mL=float(V[j]), strokes=float(strokes),
                        rate_mL_min=float(rate), mA=mA_for_rate(cfg, rate), minutes=T))
    return out


class Controller:
    def __init__(self, cfg: SystemConfig, recipe: Recipe, E_cal: np.ndarray | None = None, I0_cal=None):
        self.cfg, self.r = cfg, recipe
        cam = cfg.camera
        self.E, self.I0 = (cam.E if E_cal is None else E_cal), (cam.I0 if I0_cal is None else I0_cal)
        self.state = "PLAN"
        self.t_state = 0.0
        self.trims = 0
        self.plan: list[dict] = []
        self.c_hat = np.zeros(3)
        self.rgb = np.zeros(3)
        self.de = np.nan
        self.V_est = cfg.reactor.heel_mL
        self.events: list = []
        self.result: dict | None = None
        self.aborted: str = ""
        self._rgb_buf: list = []
        self._strokes0: dict = {}
        self._A_buf: list = []

    # ---- 보조
    def _go(self, t, s):
        self.events.append((round(t, 2), f"{self.state} → {s}"))
        self.state, self.t_state = s, t

    def estimate(self, rgb8, A=None):
        """rgb8: ROI 평균 코드값 (ΔE 용). A: 실제 카메라가 픽셀별 기준 영상으로 구한 흡광도 (있으면 농도 역산에 우선)."""
        n = int(self.cfg.camera.fps * 2)                                   # 최근 2 s 평균
        self._rgb_buf.append(np.asarray(rgb8, float)); self._rgb_buf = self._rgb_buf[-n:]
        self.rgb = np.mean(self._rgb_buf, axis=0)
        if A is not None:
            self._A_buf.append(np.asarray(A, float)); self._A_buf = self._A_buf[-n:]
            self.c_hat = optics.nnls3(self.E, np.mean(self._A_buf, axis=0))
        else:
            self.c_hat = optics.rgb8_to_conc(self.E, self.I0, self.rgb, self.cfg.camera.gamma, self.cfg.camera.glare)
        self.de = optics.delta_e2000(self.rgb, self.r.target_rgb8)

    def _send_doses(self, bus, plan):
        tele = bus.latest()
        self._strokes0 = {d["id"]: (tele["pumps"][d["id"]]["strokes"] if tele else 0.0) for d in plan}
        for d in plan:
            if d["strokes"] >= 1.0:
                bus.send_cmd(dict(cmd="valve", id=d["valve"], open=True))
        for d in plan:
            if d["strokes"] >= 1.0:
                bus.send_cmd(dict(cmd="dose", id=d["id"], mA=d["mA"], strokes=d["strokes"]))
        self.V_est += sum(d["volume_mL"] for d in plan)

    def mixing_time(self):
        rpm = self.r.rpm or self.cfg.reactor.rpm
        return self.cfg.reactor.mix_K / max(rpm, 1.0)

    # ---- 주기 실행 (AI 노드에서 호출)
    def step(self, t, tele, rgb8, bus, A=None):
        self.estimate(rgb8, A)
        r = self.r
        if self.state == "PLAN":
            self.plan = plan_doses(self.cfg, self.cfg.reactor.heel_mL, r.c_target, r.dose_minutes, r.flow_factor)
            bus.send_cmd(dict(cmd="arm"))
            bus.send_cmd(dict(cmd="stirrer_rpm", rpm=r.rpm or self.cfg.reactor.rpm))
            bus.send_cmd(dict(cmd="run_enable", on=True))
            self._go(t, "PRIME")
        elif self.state == "PRIME":
            if t - self.t_state >= 0.5:                         # 밸브 응답 + 교반 안정
                self._send_doses(bus, self.plan)
                self._go(t, "DOSE")
        elif self.state == "DOSE":
            finished = tele and t - self.t_state > 0.5 and not any(p["dosing"] for p in tele["pumps"].values())
            timeout = t - self.t_state > max(d["minutes"] for d in self.plan) * 60.0 * 1.5 + 10.0
            if timeout and not finished:                        # 펌프가 끝내지 못함 (수위/신호/밸브 고장)
                self.aborted = "DOSE timeout: " + ", ".join(
                    f"{pid} {p['strokes']:.0f} str" for pid, p in tele["pumps"].items() if p["dosing"])
                self.events.append((round(t, 2), self.aborted))
                for d in self.plan:
                    bus.send_cmd(dict(cmd="stop", id=d["id"]))
            if finished and not self.aborted:                   # 실제 스트로크가 계획의 절반도 안 되면 중단
                short = [f"{d['id']} {tele['pumps'][d['id']]['strokes'] - self._strokes0.get(d['id'], 0):.0f}/{d['strokes']:.0f} str"
                         for d in self.plan if d["strokes"] >= 1.0
                         and tele["pumps"][d["id"]]["strokes"] - self._strokes0.get(d["id"], 0) < 0.5 * d["strokes"]]
                if short:
                    self.aborted = "DOSE short (relief/valve/pump stop?): " + ", ".join(short)
                    self.events.append((round(t, 2), self.aborted))
            if finished or timeout:
                for d in self.plan:
                    bus.send_cmd(dict(cmd="valve", id=d["valve"], open=False))
                self._go(t, "SETTLE")
        elif self.state == "SETTLE":
            if t - self.t_state >= r.settle_factor * self.mixing_time():
                self._go(t, "MEASURE")
        elif self.state == "MEASURE":
            if t - self.t_state >= 2.0:                         # 2 s 평균이 차도록
                if r.mode == "open" or self.aborted or self.de < r.de_match or self.trims >= r.max_trims:
                    self._go(t, "DONE")
                else:
                    self._go(t, "TRIM")
        elif self.state == "TRIM":
            err = r.c_target - self.c_hat
            c_stock = np.array([tk.conc_mg_L for tk in self.cfg.tanks])
            extra = np.where(err > r.trim_tol_mg_L, err * self.V_est / (c_stock - r.c_target), 0.0)
            plan = []
            for j, pid in enumerate(PUMP_IDS):
                strokes = extra[j] / (self.cfg.pump.stroke_mL * self.cfg.pump.stroke_length)
                rate = min(extra[j] / 0.5, pump_max_rate_mL_min(self.cfg))   # 트림은 30 s 안에
                plan.append(dict(id=pid, valve=VALVE_IDS[j], volume_mL=float(extra[j]), strokes=float(strokes),
                                 rate_mL_min=rate, mA=mA_for_rate(self.cfg, rate), minutes=0.5))
            self.trims += 1
            if any(d["strokes"] >= 1.0 for d in plan):
                self.events.append((round(t, 2), f"trim#{self.trims} extra mL=" + ", ".join(f"{d['volume_mL']:.2f}" for d in plan)))
                self.plan = plan
                self._send_doses(bus, plan)
                self._go(t, "DOSE")
            else:
                self.events.append((round(t, 2), f"trim#{self.trims}: 추가 투입 불필요 (오버슈트는 물 없이 보정 불가)"))
                self._go(t, "DONE")
        elif self.state == "DONE":
            if self.result is None:
                bus.send_cmd(dict(cmd="run_enable", on=False))
                bus.send_cmd(dict(cmd="safe"))
                self.result = dict(t_done=t, dE2000=self.de, c_hat=self.c_hat.copy(), rgb=self.rgb.copy(), trims=self.trims)
        return dict(t=t, state=self.state, rgb=self.rgb.copy(), c_hat=self.c_hat.copy(), dE=self.de)

    @property
    def done(self):
        return self.state == "DONE" and self.result is not None
