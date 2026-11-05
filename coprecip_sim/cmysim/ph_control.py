"""pH 제어기 (NaOH 도징) — Tier B(pH 유도 침전) · Tier C(공침, pH 9~11 유지) 용.

구성
  PHModel      : 반응기 산·염기 평형 (강염기 − 강산 + 약산 완충계) 으로 pH 계산. 금속염 피드 등 '산 부하' 를 넣을 수 있다.
  PHProbe      : 혼합 지연 + 프로브 1차 지연(τ≈8 s) + 잡음 + 드리프트. 4–20 mA 트랜스미터는 SimHAL 쪽에서 양자화.
  PHController : 한쪽(염기만) PID. 미분은 측정값에 필터, 적분 안티와인드업(백캘큘레이션), 불감대, 피드포워드(산 부하 × 화학량론),
                 안전(상한/하한 pH, 배치 최대 NaOH 부피, 프로브 고착 감지). 출력 = NaOH 유량 [mL/min] → 펌프 mA.
  relay 자동동조: Åström–Hägglund 릴레이 → Ku, Tu → Tyreus–Luyben PI (완충 용량을 모르는 새 배치에서 첫 동조).
  titrate      : 설정값 램프 (pH 10 → 3 스윕, Tier B 침전 개시 pH 찾기).

하드웨어 매핑
  NaOH 는 펌프 3대 중 하나(기본 P-103)에 배정한다. 스톡 탱크 역할을 TankSpec.role = "naoh", conc_mol_L 로 둔다.
  pH 는 I/O 노드 텔레메트리 'ph' (MCC 118 CH0, 절연형 트랜스미터 4–20 mA ↔ pH 0–14) 로 들어온다.
  제어기는 AI 노드(레시피 스텝 ph_control) 에서 돌고 I/O 노드에 'pump' 명령(연속 mA)을 보낸다. 인터록은 I/O 노드가 지킨다.

  python -m cmysim.ph_control sim      --setpoint 10.5 --load 0.001 --plot ph.png     단독 폐루프 시뮬레이션
  python -m cmysim.ph_control autotune --setpoint 10.5 --load 0.001                   릴레이 동조 → Kp, Ki 추천
  레시피:  - {step: ph_control, pump: P-103, setpoint: 10.5, seconds: 300, Kp: 6, Ki: 0.15}
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import numpy as np

KW = 1e-14


# ------------------------------------------------------------------ 공정 모델
@dataclass
class BufferSpecies:
    conc_mol_L: float       # 총 농도
    pKa: float


class PHModel:
    """전하 균형: (B − A)/V + [H+] = Kw/[H+] + Σ C_i·Ka_i/(Ka_i + [H+])  → [H+] 이분법.

    B: 강염기(NaOH) 몰, A: 강산 몰, 완충종 i (약산 HA ⇌ H+ + A−). 체적 V [L].
    """

    def __init__(self, V_L: float, pH0: float = 7.0, buffers=None):
        self.V = V_L
        self.buffers = buffers if buffers is not None else [BufferSpecies(0.005, 6.35)]   # 용존 CO2 수준의 약한 완충
        self.A = 0.0
        self.B = 0.0
        self.B = self._base_for_pH(pH0)

    def _charge_residual(self, h, B=None):
        B = self.B if B is None else B
        acid_side = KW / h + sum(b.conc_mol_L * self.V / self.V * 10 ** (-b.pKa) / (10 ** (-b.pKa) + h) for b in self.buffers)
        return (B - self.A) / self.V + h - acid_side

    def pH(self, B=None) -> float:
        lo, hi = 0.0, 14.0
        for _ in range(60):
            mid = 0.5 * (lo + hi); h = 10 ** (-mid)
            if self._charge_residual(h, B) > 0:      # 양이온 과잉 → pH 가 더 높아야
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def _base_for_pH(self, target):
        lo, hi = -1.0 * self.V, 1.0 * self.V
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if self.pH(mid) < target:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def add_base(self, vol_mL: float, conc_mol_L: float):
        self.B += vol_mL / 1000.0 * conc_mol_L
        self.V += vol_mL / 1000.0
        for b in self.buffers:                      # 희석
            b.conc_mol_L *= (self.V - vol_mL / 1000.0) / self.V

    def add_acid(self, mol: float):
        self.A += mol

    def add_water(self, vol_mL: float):
        V0 = self.V; self.V += vol_mL / 1000.0
        for b in self.buffers:
            b.conc_mol_L *= V0 / self.V

    def buffer_capacity(self) -> float:
        """β = dB/dpH [mol/L/pH] 수치 미분."""
        p = self.pH(); dB = 1e-5 * self.V
        return dB / self.V / max(self.pH(self.B + dB) - p, 1e-9)


class PHProbe:
    def __init__(self, tau_s=8.0, noise=0.01, drift_per_h=0.0, rng=None):
        self.tau, self.noise, self.drift, self.rng = tau_s, noise, drift_per_h / 3600.0, rng or np.random.default_rng(0)
        self.y = None; self.t = 0.0; self.offset = 0.0

    def step(self, ph_true: float, dt: float) -> float:
        self.t += dt
        if self.y is None:
            self.y = ph_true
        self.y += (ph_true - self.y) * (1 - math.exp(-dt / self.tau))
        self.offset += self.drift * dt
        return self.y + self.offset + self.rng.normal(0, self.noise)


# ------------------------------------------------------------------ 제어기
@dataclass
class PHGains:
    Kp: float = 10.0           # mL/min per pH  (0.1 M NaOH, 2 L 기준; 과투입은 속도 제한기·완충용량 상한이 막는다)
    Ki: float = 0.02           # mL/min per pH·s
    Kd: float = 0.0
    d_filter_s: float = 5.0
    deadband: float = 0.02
    out_max: float = 38.0      # 펌프 최대 mL/min (gamma/X 200 spm × 0.19 mL)
    out_min: float = 0.0
    ff_gain: float = 0.0       # 피드포워드: 산 부하 [mol/min] → NaOH mL/min = load / conc × 1000 × ff_gain
    # 완충용량 기반 투입 상한: '설정값까지 필요한 염기량 − 아직 반영 안 된 양' 을 horizon 안에 넣는 속도 이상은 내지 않는다
    beta0_mol_L_pH: float = 0.5e-3   # 완충용량 사전값 (작게 → 안전쪽: 모자라면 적분이 채움)
    lag_s: float = 20.0               # 혼합 + 프로브 지연 (이 시간 안에 넣은 염기는 아직 측정에 안 보임)
    horizon_s: float = 30.0
    cap_enabled: bool = True
    i_band: float = 0.5               # |e| 가 이 안일 때만 적분 (큰 오차 접근 중 와인드업 방지)
    rate_governor: bool = True        # 관측된 dpH/dt 가 e/(2·lag) 를 넘으면 P 항을 줄인다 (완충용량과 무관한 과투입 방지)


@dataclass
class PHSafety:
    ph_max: float = 12.0
    ph_min: float = 2.0
    max_total_mL: float = 500.0
    stuck_s: float = 60.0      # 이 시간 동안 최대 출력인데 pH 변화 < stuck_dpH 면 프로브/펌프 고장
    stuck_dpH: float = 0.05


class PHController:
    def __init__(self, setpoint: float, gains: PHGains | None = None, safety: PHSafety | None = None,
                 naoh_mol_L: float = 0.1, mode: str = "pid", V_L: float = 2.0):
        self.sp, self.g, self.s = setpoint, gains or PHGains(), safety or PHSafety()
        self.naoh, self.V = naoh_mol_L, V_L
        self.beta = self.g.beta0_mol_L_pH          # 완충용량 추정 [mol/L/pH]
        self._dose_hist: list = []                 # (t, mmol) 최근 투입
        self._beta_obs: list = []                  # (pH, 누적 mmol) 관측 → 기울기
        self.mode = mode                     # pid | relay | titrate | off
        self.i_term = 0.0; self.d_state = None; self.prev_t = None; self.prev_meas = None
        self.total_mL = 0.0; self.out = 0.0
        self.fault = ""; self._stuck_t0 = None; self._stuck_ph0 = None
        self.load_mol_min = 0.0
        # relay
        self.relay_d, self.relay_h = 2.0, 0.05
        self.relay_state = 1; self._relay_switch_t = []; self._relay_peaks = []; self._relay_min = math.inf; self._relay_max = -math.inf
        # titrate
        self.titrate_rate = 0.0; self.titrate_end = None
        self.log: list = []

    # ---- 보조
    def set_titration(self, start_pH, end_pH, rate_pH_per_min):
        self.mode, self.sp, self.titrate_end = "titrate", start_pH, end_pH
        self.titrate_rate = abs(rate_pH_per_min) / 60.0 * (1 if end_pH > start_pH else -1)

    def update(self, t: float, meas: float) -> float:
        """측정 pH → NaOH 유량 [mL/min] (한쪽 제어: 0 이상)."""
        if self.fault or self.mode == "off":
            self.out = 0.0; return 0.0
        dt = 0.0 if self.prev_t is None else max(t - self.prev_t, 1e-3)
        if self.mode == "titrate" and dt > 0:
            self.sp += self.titrate_rate * dt
            if (self.titrate_rate > 0 and self.sp >= self.titrate_end) or (self.titrate_rate < 0 and self.sp <= self.titrate_end):
                self.sp = self.titrate_end
        # 안전
        if meas > self.s.ph_max or meas < self.s.ph_min:
            self.fault = f"PH_LIMIT {meas:.2f}"; self.out = 0.0; return 0.0
        if self.total_mL >= self.s.max_total_mL:
            self.fault = f"NAOH_VOLUME_LIMIT {self.total_mL:.0f} mL"; self.out = 0.0; return 0.0
        if self.mode == "relay":
            out = self._relay(t, meas)
            if dt > 0:
                self._record_dose(t, out / 60.0 * dt * self.naoh, meas)
        else:
            out = self._pid(t, meas, dt)
        # 프로브/펌프 고착: 최대 출력인데 pH 가 안 움직임
        if out >= self.g.out_max * 0.95:
            if self._stuck_t0 is None:
                self._stuck_t0, self._stuck_ph0 = t, meas
            elif t - self._stuck_t0 > self.s.stuck_s and abs(meas - self._stuck_ph0) < self.s.stuck_dpH:
                self.fault = "STUCK: full dosing, pH not moving (probe/pump/empty tank?)"; out = 0.0
        else:
            self._stuck_t0 = None
        self.total_mL += out / 60.0 * dt
        self.out = out
        self.prev_t, self.prev_meas = t, meas
        self.log.append((round(t, 2), round(meas, 3), round(self.sp, 3), round(out, 3)))
        return out

    def _pid(self, t, meas, dt):
        e = self.sp - meas
        if abs(e) < self.g.deadband:
            e = 0.0
        ff = 0.0
        if self.g.ff_gain and self.load_mol_min > 0:
            ff = self.load_mol_min / self.naoh * 1000.0 * self.g.ff_gain
        # 미분 (측정값, 1차 필터)
        d = 0.0
        if dt > 0 and self.prev_meas is not None and self.g.Kd:
            raw = -(meas - self.prev_meas) / dt
            a = dt / (self.g.d_filter_s + dt)
            self.d_state = raw if self.d_state is None else self.d_state + a * (raw - self.d_state)
            d = self.g.Kd * self.d_state
        p_term = self.g.Kp * e + d
        governed = False
        if e > 0:
            if self.g.cap_enabled:
                p_term = min(p_term, self._cap_mL_min(t, e))  # 접근 속도 상한 1: 완충용량 추정
            if self.g.rate_governor:
                slope = self._ph_slope(t)                      # 접근 속도 상한 2: 관측된 상승률. 지연 동안 올라갈 양이 남은 오차의 절반을 넘지 않게
                slope_max = max(e, 0.05) / (2.0 * self.g.lag_s) + max(self.titrate_rate, 0.0)   # 램프 중엔 램프 속도만큼 허용
                if slope is not None and slope > slope_max:
                    p_term *= slope_max / slope; governed = True
        u_unsat = p_term + self.i_term + ff
        u = float(np.clip(u_unsat, self.g.out_min, self.g.out_max))
        if dt > 0:
            # 조건부 적분: 오차가 적분대 안이고, 포화/속도제한으로 묶여 있지 않을 때만
            saturated_hi = u_unsat > self.g.out_max and e > 0
            saturated_lo = u_unsat < self.g.out_min and e < 0
            if abs(e) < self.g.i_band and not (saturated_hi or saturated_lo or governed):
                self.i_term += self.g.Ki * e * dt
            self.i_term = float(np.clip(self.i_term, 0.0, self.g.out_max))
            self._record_dose(t, u / 60.0 * dt * self.naoh, meas)
        return u

    def _ph_slope(self, t, W=10.0):
        obs = [(o[0], o[1]) for o in self._beta_obs if t - o[0] <= W]
        if len(obs) < 4:
            return None
        ts = np.array([o[0] for o in obs]); ph = np.array([o[1] for o in obs])
        return float(np.polyfit(ts - ts[0], ph, 1)[0])

    # ---- 완충용량 추정과 투입 상한
    def _record_dose(self, t, mmol, meas):
        """mmol = mL × mol/L. 누적 투입과 pH 이력으로 완충용량을 추정한다 (지연 lag_s 만큼 어긋나게 비교)."""
        if mmol > 0:
            self._dose_hist.append((t, mmol))
        self._dose_hist = [(tt, m) for tt, m in self._dose_hist if t - tt <= 2 * self.g.lag_s]
        self._cum_mmol = getattr(self, "_cum_mmol", 0.0) + mmol
        self._beta_obs.append((t, meas, self._cum_mmol))
        W = 1.5 * self.g.lag_s
        self._beta_obs = [o for o in self._beta_obs if t - o[0] <= W + self.g.lag_s + 1.0]

        def at(tq, idx):
            cand = [o for o in self._beta_obs if o[0] <= tq]
            return cand[-1][idx] if cand else None
        ph_now, ph_old = meas, at(t - W, 1)
        b_now, b_old = at(t - self.g.lag_s, 2), at(t - self.g.lag_s - W, 2)
        if None not in (ph_old, b_now, b_old):
            dph, db = ph_now - ph_old, b_now - b_old
            if dph > 0.1 and db > 0.02:                            # 염기를 넣어 pH 가 올라간 구간에서만
                beta_hat = db / 1000.0 / self.V / dph
                self.beta = 0.8 * self.beta + 0.2 * float(np.clip(beta_hat, 0.2 * self.g.beta0_mol_L_pH, 200 * self.g.beta0_mol_L_pH))

    def _cap_mL_min(self, t, e):
        need_mmol = self.beta * self.V * e * 1000.0
        in_transit = sum(m for tt, m in self._dose_hist if t - tt <= self.g.lag_s)
        remaining = max(need_mmol - in_transit, 0.0)
        cap = remaining / self.naoh / (self.g.horizon_s / 60.0)
        cap += self.beta * self.V * max(self.titrate_rate, 0.0) * 60.0 / self.naoh * 1000.0   # 램프를 따라가는 데 필요한 유량
        return max(cap, 0.1 * self.g.Kp * e, 0.05)              # 바닥: 완충용량을 과소추정해도 P 항의 10 % 는 남긴다

    def _relay(self, t, meas):
        if self.relay_state == 1 and meas > self.sp + self.relay_h:
            self.relay_state = 0; self._relay_switch_t.append(t)
            self._relay_peaks.append((self._relay_min, self._relay_max)); self._relay_min, self._relay_max = math.inf, -math.inf
        elif self.relay_state == 0 and meas < self.sp - self.relay_h:
            self.relay_state = 1; self._relay_switch_t.append(t)
        self._relay_min, self._relay_max = min(self._relay_min, meas), max(self._relay_max, meas)
        return self.relay_d if self.relay_state == 1 else 0.0

    def relay_result(self) -> dict | None:
        """릴레이 진동 2주기 이상이면 Ku, Tu, 추천 PI (Tyreus–Luyben) 를 돌려준다."""
        sw = self._relay_switch_t
        if len(sw) < 5:
            return None
        periods = np.diff(sw[-5:])[::2] * 2 if len(sw) >= 5 else []
        Tu = float(np.mean(np.diff(sw[-5:])) * 2)
        amps = [(mx - mn) / 2 for mn, mx in self._relay_peaks[-2:] if math.isfinite(mn) and math.isfinite(mx)]
        if not amps:
            return None
        a = float(np.mean(amps))
        d = self.relay_d / 2                                   # 0 ↔ d 릴레이의 등가 진폭
        Ku = 4 * d / (math.pi * a)
        Kp, Ti = Ku / 3.2, 2.2 * Tu
        return dict(Ku=Ku, Tu=Tu, a=a, Kp=Kp, Ki=Kp / Ti, Ti=Ti)

    def metrics(self) -> dict:
        if not self.log:
            return {}
        t = np.array([l[0] for l in self.log]); y = np.array([l[1] for l in self.log]); sp = np.array([l[2] for l in self.log])
        e = sp - y
        inband = np.abs(e) < 0.1
        settle = None
        for i in range(len(t)):
            if inband[i:].all():
                settle = float(t[i] - t[0]); break
        return dict(IAE=float(np.trapezoid(np.abs(e), t)) if hasattr(np, "trapezoid") else float(np.trapz(np.abs(e), t)),
                    overshoot=float(max(0.0, (y - sp).max())), settle_s=settle, final_err=float(e[-1]),
                    naoh_mL=round(self.total_mL, 2), fault=self.fault)


def flow_to_mA(flow_mL_min: float, stroke_mL=0.19, stroke_len=1.0, max_spm=200.0, i_start=4.4, i_full=19.6) -> float:
    if flow_mL_min <= 0:
        return 0.0
    spm = min(flow_mL_min / (stroke_mL * stroke_len), max_spm)
    return i_start + (i_full - i_start) * spm / max_spm


# ------------------------------------------------------------------ 단독 시뮬레이션 (노드 없이, 동조용)
def simulate(setpoint=10.5, pH0=7.0, V_L=2.0, naoh_mol_L=0.1, load_mol_min=0.0, load_start_s=0.0, duration=600.0,
             dt=0.5, gains=None, mode="pid", rpm=300.0, probe_tau=8.0, buffers=None, seed=0, titrate=None, relay_d=2.0):
    rng = np.random.default_rng(seed)
    model = PHModel(V_L, pH0, buffers); probe = PHProbe(probe_tau, rng=rng)
    ctl = PHController(setpoint, gains, naoh_mol_L=naoh_mol_L, mode=mode, V_L=V_L)
    if titrate:
        ctl.set_titration(*titrate)
    ctl.relay_d = relay_d
    tm = 3000.0 / rpm; mixed = pH0
    hist = dict(t=[], ph_true=[], ph_meas=[], sp=[], flow=[], naoh_mL=[], beta=[])
    t = 0.0; flow = 0.0
    while t < duration:
        if t >= load_start_s and load_mol_min > 0:
            model.add_acid(load_mol_min / 60.0 * dt); ctl.load_mol_min = load_mol_min
        model.add_base(flow / 60.0 * dt, naoh_mol_L)
        ph_true = model.pH()
        mixed += (ph_true - mixed) * (1 - math.exp(-dt / (tm / 3)))
        meas = probe.step(mixed, dt)
        flow = ctl.update(t, meas)
        hist["t"].append(t); hist["ph_true"].append(ph_true); hist["ph_meas"].append(meas); hist["sp"].append(ctl.sp)
        hist["flow"].append(flow); hist["naoh_mL"].append(ctl.total_mL)
        t += dt
    hist = {k: np.array(v) for k, v in hist.items()}
    return hist, ctl, model


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ph_control", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("sim", "autotune"):
        p = sp.add_parser(name)
        p.add_argument("--setpoint", type=float, default=10.5); p.add_argument("--ph0", type=float, default=7.0)
        p.add_argument("--volume", type=float, default=2.0, help="L"); p.add_argument("--naoh", type=float, default=0.1, help="mol/L")
        p.add_argument("--load", type=float, default=0.0, help="산 부하 mol/min (금속염 피드 등)"); p.add_argument("--load-start", type=float, default=0.0)
        p.add_argument("--buffer", default="0.005@6.35", help="완충종 'conc@pKa[,conc@pKa]' (Tier B 구연산: 0.01@4.8)")
        p.add_argument("--duration", type=float, default=600.0); p.add_argument("--rpm", type=float, default=300.0)
        p.add_argument("--Kp", type=float, default=10.0); p.add_argument("--Ki", type=float, default=0.02); p.add_argument("--Kd", type=float, default=0.0)
        p.add_argument("--no-cap", action="store_true", help="완충용량 상한·속도 제한기 끄기 (비교용)"); p.add_argument("--relay-d", type=float, default=0.0, help="릴레이 진폭 mL/min (0 = 부하 등가의 2 배)")
        p.add_argument("--ff", type=float, default=0.0, help="피드포워드 이득 (1.0 = 화학량론)")
        p.add_argument("--titrate", help="'start,end,rate_pH_per_min' 램프 (예 10,3,0.5)")
        p.add_argument("--plot")
    a = ap.parse_args(argv)
    buffers = [BufferSpecies(float(x.split("@")[0]), float(x.split("@")[1])) for x in a.buffer.split(",")]
    gains = PHGains(Kp=a.Kp, Ki=a.Ki, Kd=a.Kd, ff_gain=a.ff, cap_enabled=not a.no_cap, rate_governor=not a.no_cap)
    titr = tuple(float(v) for v in a.titrate.split(",")) if a.titrate else None
    if a.cmd == "autotune":
        if a.load <= 0:
            a.load = 0.0002
            print("주의: 염기만 넣는 제어라 산 부하가 없으면 릴레이 진동이 생기지 않습니다. 기본 부하 0.2 mmol/min 을 가정합니다.")
        relay_d = a.relay_d if a.relay_d > 0 else 2.0 * a.load / a.naoh * 1000.0
        hist, ctl, model = simulate(a.setpoint, a.ph0, a.volume, a.naoh, a.load, a.load_start, a.duration, gains=gains, mode="relay",
                                    rpm=a.rpm, buffers=buffers, relay_d=relay_d)
        r = ctl.relay_result()
        print(f"릴레이 진폭 {relay_d:.2f} mL/min, 결과:", {k: round(v, 4) for k, v in r.items()} if r else "진동 부족 (duration 을 늘리거나 relay-d 를 키우세요)")
        if r:
            print(f"추천: --Kp {r['Kp']:.2f} --Ki {r['Ki']:.4f}   (Tyreus–Luyben PI, 완충용량 β≈{model.buffer_capacity()*1000:.2f} mmol/L/pH)")
    else:
        hist, ctl, model = simulate(a.setpoint, a.ph0, a.volume, a.naoh, a.load, a.load_start, a.duration, gains=gains,
                                    rpm=a.rpm, buffers=buffers, titrate=titr)
        m = ctl.metrics()
        print(f"최종 pH {hist['ph_meas'][-1]:.2f} (설정 {ctl.sp:.2f})  정착 {m['settle_s']} s  오버슈트 {m['overshoot']:.2f}  IAE {m['IAE']:.1f}  "
              f"NaOH {m['naoh_mL']} mL  β 실제 {model.buffer_capacity()*1000:.2f} / 추정 {ctl.beta*1000:.2f} mmol/L/pH  {m['fault']}")
    if a.plot:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        ax[0].plot(hist["t"], hist["ph_true"], "k", lw=1, label="pH true"); ax[0].plot(hist["t"], hist["ph_meas"], "b", lw=0.8, label="pH probe")
        ax[0].plot(hist["t"], hist["sp"], "r--", label="setpoint"); ax[0].set_ylabel("pH"); ax[0].legend()
        ax[1].plot(hist["t"], hist["flow"], "g", label="NaOH mL/min"); ax[1].set_ylabel("NaOH [mL/min]"); ax[1].set_xlabel("t [s]")
        ax1b = ax[1].twinx(); ax1b.plot(hist["t"], hist["naoh_mL"], "gray", lw=0.8); ax1b.set_ylabel("total mL")
        fig.tight_layout(); fig.savefig(a.plot, dpi=120); print("그래프:", a.plot)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
