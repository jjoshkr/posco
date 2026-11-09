"""레시피 실행기: YAML 레시피 → 도징 순서 (AI 노드에서 Controller 자리에 끼워 쓴다).

레시피 예 (recipes/ 폴더 참고)

  name: tierA_target_match
  reactor: {heel_mL: 2000, rpm: 300}
  stocks: {C: 1000, M: 1000, Y: 1000}          # mg/L (생략 시 config)
  target: {hex: "#5A8F7B"}                       # 또는 {cmy: [30, 10, 25]} / {file: target.json}
  match:  {de: 1.5}
  steps:
    - {step: stir, rpm: 300}
    - {step: wait, seconds: 5}
    - {step: dose_to_target, minutes: 2, flow_factor: [0.97, 0.97, 0.97]}
    - {step: settle, factor: 3}
    - {step: measure, seconds: 2, label: feedforward}
    - {step: trim_to_target, max_trims: 3, tol_mg_L: 0.4}
    - {step: hold, seconds: 30}
    - {step: stop}
  matrix: {"reactor.rpm": [150, 300, 500]}      # 선택: 실행 묶음 생성 (카르테시안 곱)

스텝 종류
  stir(rpm) · wait(seconds) · valve(id, open) · dose(pump|pumps, volume_mL|strokes, rate_mL_min|minutes|mA, ratio, total_mL)
  ph_control(pump, acid_pump, setpoint, seconds, Kp, Ki, mode) · acid_load(mol_min)
  dose_to_target(minutes, flow_factor) · settle(factor|seconds) · measure(seconds, label)
  trim_to_target(max_trims, tol_mg_L, de) · hold(seconds) · log(note) · inject_fault(kind, arg, seconds)  · stop

인터록은 I/O 노드가 지킨다 (밸브 닫힌 채 펌프 거부 등). 실행기는 밸브를 먼저 열고 펌프를 보내며, 끝나면 닫는다.
모든 스텝 전이·측정·고장 주입은 self.log 에 시간과 함께 남아 이상탐지 라벨이 된다.
"""
from __future__ import annotations
import copy, itertools, json, pathlib
import numpy as np
from .config import SystemConfig, PUMP_IDS, VALVE_IDS, DYES, PULSE_PUMP_IDS, PULSE_VALVES, pump_max_rate_mL_min
from .control import Controller, Recipe, plan_doses, mA_for_rate, target_from_hex, target_from_cmy
from .ph_control import PHController, PHGains, PHSafety, flow_to_mA
from . import optics

STEP_KINDS = ("stir", "wait", "valve", "dose", "dose_to_target", "settle", "measure", "trim_to_target",
              "hold", "log", "inject_fault", "ph_control", "ph_hold_start", "ph_hold_stop", "acid_load", "stop")


# ------------------------------------------------------------------ 로드 · 검증 · 매트릭스 전개
def load_recipe(path) -> dict:
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return json.loads(text)
    import yaml
    return yaml.safe_load(text)


def validate(r: dict) -> list[str]:
    errs = []
    if not isinstance(r, dict):
        return ["레시피는 매핑이어야 합니다"]
    if "steps" not in r or not isinstance(r["steps"], list) or not r["steps"]:
        errs.append("steps 가 비어 있습니다")
    tgt = r.get("target") or {}
    if not any(k in tgt for k in ("hex", "cmy", "file")) and any(s.get("step") in ("dose_to_target", "trim_to_target") for s in r.get("steps", []) if isinstance(s, dict)):
        errs.append("dose_to_target/trim_to_target 를 쓰려면 target (hex|cmy|file) 이 필요합니다")
    for i, s in enumerate(r.get("steps", [])):
        if not isinstance(s, dict) or "step" not in s:
            errs.append(f"steps[{i}]: {{step: ...}} 형식이어야 합니다"); continue
        k = s["step"]
        if k not in STEP_KINDS:
            errs.append(f"steps[{i}]: 모르는 스텝 '{k}' (가능: {', '.join(STEP_KINDS)})")
        if k == "dose":
            pumps = s.get("pumps") or ([s["pump"]] if "pump" in s else [])
            if not pumps:
                errs.append(f"steps[{i}] dose: pump 또는 pumps 필요")
            for pid in pumps:
                if pid not in PUMP_IDS:
                    errs.append(f"steps[{i}] dose: 모르는 펌프 {pid}")
            if not any(x in s for x in ("volume_mL", "strokes", "total_mL")):
                errs.append(f"steps[{i}] dose: volume_mL | strokes | total_mL 중 하나 필요")
            if "ratio" in s and len(s["ratio"]) != len(pumps):
                errs.append(f"steps[{i}] dose: ratio 길이가 pumps 와 다릅니다")
        if k == "valve" and s.get("id") not in VALVE_IDS:
            errs.append(f"steps[{i}] valve: 모르는 밸브 {s.get('id')}")
        if k == "stir" and not (0 <= float(s.get("rpm", 0)) <= 2000):
            errs.append(f"steps[{i}] stir: rpm 범위 밖")
        if k in ("ph_control", "ph_hold_start"):
            if s.get("pump", "P-103") not in PUMP_IDS:
                errs.append(f"steps[{i}] ph_control: 모르는 펌프 {s.get('pump')}")
            if "acid_pump" in s and s["acid_pump"] not in PUMP_IDS + PULSE_PUMP_IDS:
                errs.append(f"steps[{i}] ph_control: 모르는 산 펌프 {s['acid_pump']}")
            if "setpoint" not in s and s.get("mode", "pid") != "titrate":
                errs.append(f"steps[{i}] ph_control: setpoint 필요")
            if k == "ph_control" and not (0 < float(s.get("seconds", 0))):
                errs.append(f"steps[{i}] ph_control: seconds > 0 필요")
    return errs


def _set_path(d: dict, dotted: str, value):
    """'reactor.rpm' 또는 'steps[2].minutes' 를 d 에 설정."""
    cur = d
    parts = []
    for tok in dotted.split("."):
        while "[" in tok:
            head, rest = tok.split("[", 1)
            if head:
                parts.append(head)
            idx, tok = rest.split("]", 1)
            parts.append(int(idx))
        if tok:
            parts.append(tok)
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value


def expand_matrix(r: dict) -> list[dict]:
    m = r.get("matrix")
    if not m:
        return [r]
    keys = list(m.keys())
    out = []
    for combo in itertools.product(*[m[k] for k in keys]):
        rr = copy.deepcopy(r); rr.pop("matrix", None)
        tag = []
        for k, v in zip(keys, combo):
            _set_path(rr, k, v); tag.append(f"{k.split('.')[-1]}={v}")
        rr["name"] = f"{r.get('name', 'recipe')}__" + "_".join(tag)
        rr["matrix_point"] = dict(zip(keys, combo))
        out.append(rr)
    return out


def apply_recipe_to_config(r: dict, cfg: SystemConfig) -> SystemConfig:
    rx = r.get("reactor") or {}
    cfg.reactor.heel_mL = float(rx.get("heel_mL", cfg.reactor.heel_mL))
    cfg.reactor.rpm = float(rx.get("rpm", cfg.reactor.rpm))
    cfg.reactor.temp_C = float(rx.get("temp_C", cfg.reactor.temp_C))
    for j, d in enumerate(DYES):
        if d in (r.get("stocks") or {}):
            cfg.tanks[j].conc_mg_L = float(r["stocks"][d])
    # 펌프별 역할 지정: stocks: {P-101: {role: cacl2, mol_L: 0.2}, P-102: {role: na2co3, mol_L: 0.2}, P-104: {role: acid, mol_L: 0.1}}
    for pid, spec in (r.get("stocks") or {}).items():
        if isinstance(spec, dict) and pid in PUMP_IDS + PULSE_PUMP_IDS:
            j = PUMP_IDS.index(pid) if pid in PUMP_IDS else 3 + list(PULSE_PUMP_IDS).index(pid)
            cfg.tanks[j].role = spec.get("role", "dye")
            if "mol_L" in spec:
                cfg.tanks[j].conc_mol_L = float(spec["mol_L"])
            if "mg_L" in spec:
                cfg.tanks[j].conc_mg_L = float(spec["mg_L"])
            if "volume_mL" in spec:
                cfg.tanks[j].volume_mL = float(spec["volume_mL"])
    if "dye_mg_L" in rx:
        cfg.reactor.dye_mg_L = tuple(float(v) for v in rx["dye_mg_L"])
    # pH: 초기 pH, 완충계, NaOH 탱크 역할 (예: ph: {initial: 7, buffers: [[0.01, 4.8]], naoh_pump: P-103, naoh_mol_L: 0.1})
    ph = r.get("ph") or {}
    if "initial" in ph:
        cfg.reactor.ph = float(ph["initial"])
    if "buffers" in ph:
        cfg.reactor.buffers = tuple((float(c), float(pk)) for c, pk in ph["buffers"])
    if "naoh_pump" in ph:
        j = PUMP_IDS.index(ph["naoh_pump"])
        cfg.tanks[j].role = "naoh"; cfg.tanks[j].conc_mol_L = float(ph.get("naoh_mol_L", 0.1))
    if "acid_pump" in ph:                                   # 산 펌프: P-104(펄스) 또는 P-10x(아날로그)
        pid = ph["acid_pump"]
        j = PUMP_IDS.index(pid) if pid in PUMP_IDS else 3 + list(PULSE_PUMP_IDS).index(pid)
        cfg.tanks[j].role = "acid"; cfg.tanks[j].conc_mol_L = float(ph.get("acid_mol_L", 0.1))
    return cfg


def build_target(r: dict, cfg: SystemConfig) -> Recipe:
    tgt = r.get("target") or {}
    m = r.get("match") or {}
    kw = dict(mode="closed", de_match=float(m.get("de", 1.5)), trim_tol_mg_L=float(m.get("tol_mg_L", 0.4)),
              max_trims=int(m.get("max_trims", 4)))
    if "file" in tgt:
        tf = json.loads(pathlib.Path(tgt["file"]).read_text())
        return Recipe(target_rgb8=np.array(tf["rgb"], float), c_target=np.array(tf["c"], float), **kw)
    if "cmy" in tgt:
        rgb, c = target_from_cmy(cfg, tgt["cmy"]); return Recipe(target_rgb8=rgb, c_target=c, **kw)
    if "hex" in tgt:
        rgb, c, _ = target_from_hex(cfg, tgt["hex"]); return Recipe(target_rgb8=rgb, c_target=c, **kw)
    # 목표 없음: 흰색(물) 을 기준으로 두고 측정만
    return Recipe(target_rgb8=optics.conc_to_rgb8(cfg.camera.E, cfg.camera.I0, np.zeros(3), cfg.camera.gamma, cfg.camera.glare),
                  c_target=np.zeros(3), **kw)


# ------------------------------------------------------------------ 실행기
class RecipeExecutor(Controller):
    """Controller 와 같은 step(t, tele, rgb8, bus, A) 인터페이스. 상태 대신 레시피 스텝 인덱스로 진행한다."""

    def __init__(self, cfg: SystemConfig, recipe: dict, E_cal=None, I0_cal=None, fault_hook=None, sim=True):
        errs = validate(recipe)
        if errs:
            raise ValueError("레시피 오류: " + "; ".join(errs))
        self.recipe = recipe
        apply_recipe_to_config(recipe, cfg)
        super().__init__(cfg, build_target(recipe, cfg), E_cal=E_cal, I0_cal=I0_cal)
        self.steps = recipe["steps"]
        self.i = -1                       # 현재 스텝
        self.state = "INIT"
        self.phase = ""                   # 스텝 내부 단계 (dose: DOSE / trim: DOSE·SETTLE·MEASURE)
        self.fault_hook, self.sim = fault_hook, sim
        self.measurements: list = []
        self.log: list = []               # (t, kind, detail)
        self.name = recipe.get("name", "recipe")
        self._trim_n = 0
        self._active_plan: list = []
        self.bg_ph = None
        self._last_tele = None

    # ---- 보조
    def _note(self, t, kind, detail=""):
        self.log.append((round(t, 2), kind, detail))
        self.events.append((round(t, 2), f"{kind} {detail}".strip()))

    def _next(self, t, bus):
        self.i += 1
        self.phase, self.t_state = "", t
        if self.i >= len(self.steps):
            self._finish(t, bus); return
        s = self.steps[self.i]
        self.state = f"S{self.i}:{s['step']}"
        self._note(t, "step", f"{self.i} {s['step']} " + " ".join(f"{k}={v}" for k, v in s.items() if k != "step"))
        self._enter(t, s, bus)

    def _finish(self, t, bus):
        if self.result is None:
            if getattr(self, "bg_ph", None):
                self._ph_finish(t, self.bg_ph["step"], bus, label="ph_hold"); self.bg_ph = None
            bus.send_cmd(dict(cmd="run_enable", on=False)); bus.send_cmd(dict(cmd="safe"))
            self.state = "DONE"
            self.result = dict(t_done=t, dE2000=self.de, c_hat=self.c_hat.copy(), rgb=self.rgb.copy(), trims=self.trims,
                               measurements=self.measurements, log=self.log, name=self.name, aborted=self.aborted)
            self._note(t, "done", f"ΔE={self.de:.2f}")

    def _plan_explicit(self, s) -> list[dict]:
        pumps = s.get("pumps") or [s["pump"]]
        p = self.cfg.pump
        vol_per_stroke = p.stroke_mL * p.stroke_length
        if "total_mL" in s:
            ratio = np.asarray(s.get("ratio", [1] * len(pumps)), float)
            vols = float(s["total_mL"]) * ratio / ratio.sum()
        elif "strokes" in s:
            vols = np.full(len(pumps), float(s["strokes"]) * vol_per_stroke)
        else:
            vols = np.full(len(pumps), float(s["volume_mL"]))
        rmax = pump_max_rate_mL_min(self.cfg)
        plan = []
        for pid, v in zip(pumps, vols):
            if "mA" in s:
                mA = float(s["mA"]); rate = max(0.0, (mA - p.i_start_mA) / (p.i_full_mA - p.i_start_mA)) * rmax
            elif "rate_mL_min" in s:
                rate = min(float(s["rate_mL_min"]), rmax); mA = mA_for_rate(self.cfg, rate)
            else:
                minutes = float(s.get("minutes", 1.0)); rate = min(v / max(minutes, 1e-6), rmax); mA = mA_for_rate(self.cfg, rate)
            plan.append(dict(id=pid, valve=VALVE_IDS[PUMP_IDS.index(pid)], volume_mL=float(v), strokes=float(v / vol_per_stroke),
                             rate_mL_min=float(rate), mA=float(mA), minutes=float(v / rate) if rate > 0 else 0.0))
        return plan

    def _start_dose(self, t, plan, bus):
        self._active_plan = plan
        self.plan = plan
        self._send_doses(bus, plan)
        self.phase, self.t_state = "DOSE", t

    def _dose_running(self, t, tele, bus) -> bool:
        """DOSE 진행; 끝나면 밸브 닫고 True."""
        finished = tele and t - self.t_state > 0.5 and not any(tele["pumps"][d["id"]]["dosing"] for d in self._active_plan)
        timeout = self._dose_stalled(t, tele)
        if finished:
            short = [d["id"] for d in self._active_plan if d["strokes"] >= 1.0
                     and tele["pumps"][d["id"]]["strokes"] - self._strokes0.get(d["id"], 0) < 0.5 * d["strokes"]]
            if short:
                self.aborted = f"DOSE short: {short}"; self._note(t, "abort", self.aborted)
        if timeout and not finished:
            self.aborted = "DOSE timeout"; self._note(t, "abort", self.aborted)
            for d in self._active_plan:
                bus.send_cmd(dict(cmd="stop", id=d["id"]))
        if finished or timeout:
            for d in self._active_plan:
                bus.send_cmd(dict(cmd="valve", id=d["valve"], open=False))
            return True
        return False

    def _record_measurement(self, t, label):
        tele = getattr(self, "_last_tele", None) or {}
        m = dict(t=round(t, 2), label=label, rgb=[int(v) for v in self.rgb], hex=optics.rgb8_to_hex(self.rgb),
                 c_hat=[round(float(v), 3) for v in self.c_hat], dE2000=round(float(self.de), 3), V_est_mL=round(self.V_est, 1),
                 ph=tele.get("ph"), turbidity_ntu=tele.get("turbidity_ntu"), temp_C=tele.get("temp_C"))
        self.measurements.append(m)
        self._note(t, "measure", f"{label} ΔE={m['dE2000']} ĉ={m['c_hat']}")
        return m

    # ---- 스텝 진입
    def _enter(self, t, s, bus):
        k = s["step"]
        if k == "stir":
            bus.send_cmd(dict(cmd="stirrer_rpm", rpm=float(s["rpm"]))); self.r.rpm = float(s["rpm"])
        elif k == "valve":
            bus.send_cmd(dict(cmd="valve", id=s["id"], open=bool(s.get("open", True))))
        elif k == "dose":
            self._start_dose(t, self._plan_explicit(s), bus)
        elif k == "dose_to_target":
            ff = np.asarray(s.get("flow_factor", [1, 1, 1]), float)
            plan = plan_doses(self.cfg, self.V_est, self.r.c_target, float(s.get("minutes", 2.0)), ff)
            self._start_dose(t, plan, bus)
        elif k == "trim_to_target":
            self._trim_n = 0
            self.phase = "MEASURE"; self.t_state = t
        elif k == "inject_fault":
            if self.sim and self.fault_hook:
                self.fault_hook(s["kind"], str(s.get("arg", "")))
                self._note(t, "fault", f"{s['kind']} {s.get('arg', '')}")
            else:
                self._note(t, "fault_manual", f"사람이 지금 수행: {s['kind']} {s.get('arg', '')}")
        elif k == "log":
            self._note(t, "log", str(s.get("note", "")))
        elif k == "acid_load":                                   # 시뮬레이션: 산 부하 시작 (실물: 피드 펌프가 하는 일)
            if self.sim and self.fault_hook:
                self.fault_hook("acid_load", str(s.get("mol_min", 0.0002)))
            self._note(t, "acid_load", f"{s.get('mol_min', 0.0002)} mol/min")
        elif k == "ph_hold_start":                              # 백그라운드 pH 유지 시작 (다음 스텝들과 동시에 진행)
            self._ph_setup(t, s, bus)
            self.bg_ph = dict(step=s, next=t, last_mA=-1.0, last_acid=-1.0, t0=t)
            self._note(t, "ph_hold", f"start sp={self.ph_ctl.sp}")
        elif k == "ph_hold_stop":
            if getattr(self, "bg_ph", None):
                self._ph_finish(t, self.bg_ph["step"], bus, label=s.get("label", "ph_hold"))
                self.bg_ph = None
        elif k == "ph_control":
            self._ph_setup(t, s, bus)
            self._ph_last_mA, self._ph_next, self._acid_last = -1.0, t, -1.0
            self.phase = "PH"
        elif k == "stop":
            self._finish(t, bus)

    def _ph_setup(self, t, s, bus):
        if True:
            pid = s.get("pump", "P-103")
            j = PUMP_IDS.index(pid)
            gains = PHGains(**{k2: float(s[k2]) for k2 in ("Kp", "Ki", "Kd", "deadband", "out_max", "ff_gain") if k2 in s})
            safety = PHSafety(**{k2: float(s[k2]) for k2 in ("ph_max", "ph_min", "max_total_mL", "max_acid_mL", "min_switch_s") if k2 in s})
            acid_pid = s.get("acid_pump", (self.recipe.get("ph") or {}).get("acid_pump"))
            acid_conc = None
            if acid_pid:
                ja = PUMP_IDS.index(acid_pid) if acid_pid in PUMP_IDS else 3 + list(PULSE_PUMP_IDS).index(acid_pid)
                acid_conc = self.cfg.tanks[ja].conc_mol_L
            self.ph_ctl = PHController(float(s.get("setpoint", 7.0)), gains, safety, naoh_mol_L=self.cfg.tanks[j].conc_mol_L,
                                       mode=s.get("mode", "pid"), V_L=self.V_est / 1000.0, acid_mol_L=acid_conc)
            if s.get("mode") == "titrate":
                self.ph_ctl.set_titration(float(s["start"]), float(s["end"]), float(s.get("rate_pH_per_min", 0.5)))
            if "relay_d" in s:
                self.ph_ctl.relay_d = float(s["relay_d"])
            self._ph_pump, self._ph_valve = pid, VALVE_IDS[j]
            self._acid_pump = acid_pid
            self._acid_valve = (PULSE_VALVES[acid_pid] if acid_pid in PULSE_PUMP_IDS else VALVE_IDS[PUMP_IDS.index(acid_pid)]) if acid_pid else None
            bus.send_cmd(dict(cmd="valve", id=self._ph_valve, open=True))
            if self._acid_valve:
                bus.send_cmd(dict(cmd="valve", id=self._acid_valve, open=True))

    def _ph_apply(self, t, tele, bus, state: dict, done=False):
        """텔레메트리 pH → 제어기 → 펌프 명령. state 는 last_mA/last_acid 를 보관하는 dict."""
        ph = tele.get("ph")
        flow = 0.0 if done or ph is None else self.ph_ctl.update(t, float(ph))
        base, acid = max(flow, 0.0), max(-flow, 0.0)
        mA = flow_to_mA(base, self.cfg.pump.stroke_mL, self.cfg.pump.stroke_length, self.cfg.pump.max_spm,
                        self.cfg.pump.i_start_mA, self.cfg.pump.i_full_mA)
        if abs(mA - state["last_mA"]) > 0.02 or done:
            bus.send_cmd(dict(cmd="pump", id=self._ph_pump, mA=round(mA, 3)) if mA > 0 else dict(cmd="stop", id=self._ph_pump))
            state["last_mA"] = mA
        if self._acid_pump and (abs(acid - state["last_acid"]) > 0.02 or done):
            if self._acid_pump in PULSE_PUMP_IDS:
                spm = acid / (self.cfg.pulse_pump.stroke_mL * self.cfg.pulse_pump.stroke_length)
                bus.send_cmd(dict(cmd="pulse_rate", id=self._acid_pump, spm=round(spm, 3)) if spm > 0 else dict(cmd="stop", id=self._acid_pump))
            else:
                mA_a = flow_to_mA(acid, self.cfg.pump.stroke_mL, self.cfg.pump.stroke_length, self.cfg.pump.max_spm,
                                  self.cfg.pump.i_start_mA, self.cfg.pump.i_full_mA)
                bus.send_cmd(dict(cmd="pump", id=self._acid_pump, mA=round(mA_a, 3)) if mA_a > 0 else dict(cmd="stop", id=self._acid_pump))
            state["last_acid"] = acid
        if self.ph_ctl.fault and not self.aborted:
            self.aborted = "PH " + self.ph_ctl.fault; self._note(t, "abort", self.aborted)
            return True
        return False

    def _ph_finish(self, t, s, bus, label=None):
        bus.send_cmd(dict(cmd="stop", id=self._ph_pump)); bus.send_cmd(dict(cmd="valve", id=self._ph_valve, open=False))
        if self._acid_pump:
            bus.send_cmd(dict(cmd="stop", id=self._acid_pump)); bus.send_cmd(dict(cmd="valve", id=self._acid_valve, open=False))
        m = self.ph_ctl.metrics(); m.update(label=label or s.get("label", f"ph{self.i}"), setpoint=self.ph_ctl.sp, t=round(t, 2),
                                             beta_est_mmol_L_pH=round(self.ph_ctl.beta * 1000, 3))
        if self.ph_ctl.mode == "relay":
            m["autotune"] = self.ph_ctl.relay_result()
        self.measurements.append(m); self.V_est += self.ph_ctl.total_mL + self.ph_ctl.acid_mL
        self._note(t, "ph_done", f"sp={self.ph_ctl.sp:.2f} final_err={m.get('final_err')} NaOH={m.get('naoh_mL')} 산={m.get('acid_mL')} mL settle={m.get('settle_s')}")
        self.ph_log = getattr(self, "ph_log", []) + self.ph_ctl.log

    # ---- 주기 실행
    def step(self, t, tele, rgb8, bus, A=None):
        self.estimate(rgb8, A)
        self._last_tele = tele
        if tele is not None and tele.get("mode") == "SAFE" and self.state not in ("INIT", "ARMED", "DONE") and t - self.t_state > 1.0:
            # I/O 노드가 스스로 SAFE 가 됨 (워치독·부피 한계 등): 레시피를 중단하고 결과를 남긴다
            self.aborted = self.aborted or f"IO node SAFE (alarms={tele.get('alarms')})"
            self._note(t, "abort", self.aborted); self.bg_ph = None
            self._finish(t, bus)
            return dict(t=t, state=self.state, rgb=self.rgb.copy(), c_hat=self.c_hat.copy(), dE=self.de)
        if getattr(self, "bg_ph", None) and self.state not in ("INIT", "ARMED", "DONE"):
            self._bg_ph_tick(t, tele, bus)
        if self.state == "INIT":
            bus.send_cmd(dict(cmd="arm"))
            bus.send_cmd(dict(cmd="stirrer_rpm", rpm=self.r.rpm or self.cfg.reactor.rpm))
            bus.send_cmd(dict(cmd="run_enable", on=True))
            self.state = "ARMED"; self.t_state = t
        elif self.state == "ARMED":
            if t - self.t_state >= 0.5:
                self._next(t, bus)
        elif self.state == "DONE":
            pass
        else:
            s = self.steps[self.i]; k = s["step"]
            if k in ("stir", "valve", "log", "stop", "ph_hold_start", "ph_hold_stop") or (k == "inject_fault" and not s.get("seconds")):
                if t - self.t_state >= 0.2:
                    self._next(t, bus)
            elif k in ("wait", "hold", "inject_fault"):
                if t - self.t_state >= float(s.get("seconds", 0)):
                    if k == "hold":
                        self._record_measurement(t, s.get("label", f"hold{self.i}"))
                    self._next(t, bus)
            elif k in ("dose", "dose_to_target"):
                if self._dose_running(t, tele, bus):
                    if self.aborted and s.get("on_abort", "continue") == "stop":
                        self._finish(t, bus)
                    else:
                        self._next(t, bus)
            elif k == "settle":
                dur = float(s["seconds"]) if "seconds" in s else float(s.get("factor", 3.0)) * self.mixing_time()
                if t - self.t_state >= dur:
                    self._next(t, bus)
            elif k == "measure":
                if t - self.t_state >= float(s.get("seconds", 2.0)):
                    self._record_measurement(t, s.get("label", f"m{self.i}"))
                    self._next(t, bus)
            elif k == "trim_to_target":
                self._trim_step(t, tele, s, bus)
            elif k == "acid_load":
                if t - self.t_state >= 0.2:
                    self._next(t, bus)
            elif k == "ph_control":
                self._ph_step(t, tele, s, bus)
        return dict(t=t, state=self.state, rgb=self.rgb.copy(), c_hat=self.c_hat.copy(), dE=self.de)

    def _ph_step(self, t, tele, s, bus):
        """ph_control 스텝 (블로킹): 매 period_s 제어, seconds 지나면 종료."""
        done = t - self.t_state >= float(s["seconds"])
        if tele is not None and (t >= self._ph_next or done):
            self._ph_next = t + float(s.get("period_s", 1.0))
            state = dict(last_mA=self._ph_last_mA, last_acid=self._acid_last)
            if self._ph_apply(t, tele, bus, state, done):
                done = True
            self._ph_last_mA, self._acid_last = state["last_mA"], state["last_acid"]
            if self.ph_ctl.mode == "relay" and self.ph_ctl.relay_result() and not getattr(self, "_relay_logged", False):
                self._relay_logged = True; self._note(t, "autotune", str({k: round(v, 4) for k, v in self.ph_ctl.relay_result().items()}))
        if done:
            self._ph_finish(t, s, bus)
            self._next(t, bus)

    def _bg_ph_tick(self, t, tele, bus):
        bg = self.bg_ph
        if tele is None or t < bg["next"]:
            return
        bg["next"] = t + float(bg["step"].get("period_s", 1.0))
        if self._ph_apply(t, tele, bus, bg, False):
            self._note(t, "ph_hold", "abort → hold stopped"); self.bg_ph = None

    @property
    def done(self):
        return self.state == "DONE" and self.result is not None


# ------------------------------------------------------------------ 템플릿
EXAMPLE = """# 공침 반응기 1단계(식용색소) 레시피 예시
name: target_match_closed
description: 목표색을 피드포워드로 넣고 카메라로 트림
reactor: {heel_mL: 2000, rpm: 300}
stocks: {C: 1000, M: 1000, Y: 1000}
target: {hex: "#5A8F7B"}
match: {de: 1.5, max_trims: 3, tol_mg_L: 0.4}
steps:
  - {step: stir, rpm: 300}
  - {step: wait, seconds: 5}
  - {step: dose_to_target, minutes: 2, flow_factor: [0.97, 0.97, 0.97]}
  - {step: settle, factor: 3}
  - {step: measure, seconds: 2, label: feedforward}
  - {step: trim_to_target, max_trims: 3}
  - {step: hold, seconds: 30, label: final}
  - {step: stop}
"""
