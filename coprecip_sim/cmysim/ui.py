"""브라우저 시뮬레이션 인터페이스 — 색소 색 매칭 실험을 직접 돌려 본다.

  python -m cmysim.ui                 → http://localhost:8050
  python -m cmysim.ui --port 8060 --host 0.0.0.0

표준 라이브러리만 사용(http.server + threading). 페이지는 인라인 HTML/JS(외부 CDN 없음, 오프라인 OK).
한 화면에서: 목표색 선택 → 시작 → 농도·ΔE·펌프 그래프, 목표/카메라 색 견본, I/O 노드 상태·알람, 고장 주입, 속도 조절,
수동 모드(밸브 열기, 스트로크 투입)까지 할 수 있다. 내부는 experiment.run_once 와 같은 SimPlant / IONode / AINode / Controller.
"""
from __future__ import annotations
import argparse, json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import numpy as np
from .config import SystemConfig, PUMP_IDS, VALVE_IDS, rig_prominent_feeder
from .nodes import Bus, SimPlant, SimHAL, IONode, AINode
from .control import Controller, plan_doses
from .experiment import make_recipe, apply_fault
from .camera import Calibration
import pathlib
from . import optics


class SimSession:
    """한 번의 실험. 백그라운드 스레드가 speed 배속으로 시뮬레이션을 진행한다."""

    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.running = False
        self.paused = False
        self.speed = 10.0
        self.params = {}
        self.step_mode = False            # 단계가 바뀔 때마다 자동 일시정지
        self.calib: Calibration | None = None   # 실제 카메라 보정 (camera_tools fit → calibration.json)
        self.calib_name = "기본(설명용 행렬)"
        self.run_until = None             # 이 단계에 도달하면 일시정지
        self._last_stage = None
        self.reset()

    # ---- 구성
    def reset(self, params: dict | None = None):
        p = dict(target="#5A8F7B", heel_mL=2000, rpm=300, mode="closed", dose_min=1.5, flow_factor=0.97,
                 pump_mode="pulse", pixel_noise=0.02, seed=0, manual=False, de_match=1.5)
        p.update(params or {})
        self.params = p
        cfg = rig_prominent_feeder(p["pump_mode"])
        cfg.seed = int(p["seed"]); cfg.dac.calibrated = True
        cfg.reactor.heel_mL = float(p["heel_mL"]); cfg.reactor.rpm = float(p["rpm"])
        cfg.camera.pixel_noise = float(p["pixel_noise"])
        if self.calib is not None:
            self.calib.apply_to(cfg)          # 실측 E, I0, gamma, glare → 시뮬레이터 카메라 모델과 제어기 역산이 같은 보정을 쓴다
        self.cfg = cfg
        if str(p["target"]).startswith("#"):
            rec, resid = make_recipe(cfg, p["target"], None, mode=p["mode"], dose_minutes=float(p["dose_min"]),
                                     de_match=float(p["de_match"]), flow_factor=np.array([float(p["flow_factor"])] * 3))
        else:
            cmy = [float(v) for v in str(p["target"]).split(",")]
            rec, resid = make_recipe(cfg, None, cmy, mode=p["mode"], dose_minutes=float(p["dose_min"]),
                                     de_match=float(p["de_match"]), flow_factor=np.array([float(p["flow_factor"])] * 3))
        self.recipe, self.target_resid = rec, resid
        self.plant = SimPlant(cfg); self.bus = Bus(); self.io = IONode(cfg, SimHAL(self.plant), self.bus)
        self.ctl = Controller(cfg, rec)
        self.ai = AINode(cfg, self.bus, self.plant.camera, self.ctl)
        self.ai.alive = not p["manual"]
        self.t = 0.0
        self.hist = {k: [] for k in ("t", "c_true", "c_hat", "dE", "dE_true", "spm", "strokes", "V", "tank", "valves", "state", "mode", "rgb", "rgb_true")}
        self.events = []
        self.plan = plan_doses(cfg, cfg.reactor.heel_mL, rec.c_target, rec.dose_minutes, rec.flow_factor)
        self._n_alarm = 0
        self._last_stage = self.ctl.state
        self.run_until = None
        self.ctl.estimate(self.plant.camera.roi_rgb8(self.plant.reactor.c_obs))   # 시작 전에도 카메라 견본이 물 색을 보이게
        cam = cfg.camera
        self.reachable_hex = optics.rgb8_to_hex(rec.target_rgb8)     # 모델이 낼 수 있는 가장 가까운 색
        if p["manual"]:                                    # 수동 모드: 노드 무장 + 운전 허가만 해 둔다
            self.bus.send_cmd(dict(cmd="arm")); self.bus.send_cmd(dict(cmd="run_enable", on=True))

    # ---- 진행
    def step(self):
        cfg, dt = self.cfg, self.cfg.dt
        self.t += dt
        if self.params["manual"]:
            self.bus.send_cmd(dict(cmd="heartbeat"))
        self.io.tick(self.t)
        self.ai.tick(self.t, self.plant.reactor.c_obs)
        self.plant.step(dt)
        if len(self.io.alarms) > self._n_alarm:
            for a in self.io.alarms[self._n_alarm:]:
                self.events.append((round(a[0], 1), "IO", a[1]))
            self._n_alarm = len(self.io.alarms)
        if int(round(self.t / dt)) % 5 == 0:                 # 0.5 s 마다 기록
            cam = cfg.camera
            rgb_true = optics.conc_to_rgb8(cam.E, cam.I0, self.plant.reactor.c_true, cam.gamma, cam.glare)
            tele = self.bus.latest() or {}
            pm = tele.get("pumps", {})
            h = self.hist
            h["t"].append(round(self.t, 1))
            h["c_true"].append([round(float(v), 2) for v in self.plant.reactor.c_true])
            h["c_hat"].append([round(float(v), 2) for v in self.ctl.c_hat])
            h["dE"].append(round(float(self.ctl.de), 2) if self.ctl.de == self.ctl.de else None)
            h["dE_true"].append(round(optics.delta_e2000(rgb_true, self.recipe.target_rgb8), 2))
            h["spm"].append([round(pm.get(p, {}).get("spm", 0.0), 1) for p in PUMP_IDS])
            h["strokes"].append([round(self.io.strokes[p]) for p in PUMP_IDS])
            h["V"].append(round(self.plant.reactor.V_mL, 1))
            h["tank"].append([round(tk.volume_mL, 1) for tk in self.plant.tanks[:3]])
            h["valves"].append([int(self.io.valve_on[v]) for v in VALVE_IDS])
            h["state"].append(self.ctl.state); h["mode"].append(self.io.mode)
            h["rgb"].append([int(v) for v in self.ctl.rgb]); h["rgb_true"].append([int(v) for v in rgb_true])
            for k in h:                                        # 메모리 상한 (최근 2시간)
                if len(h[k]) > 14400:
                    del h[k][:len(h[k]) - 14400]
        if self.ctl.events and (not self.events or self.events[-1][2] != self.ctl.events[-1][1] or self.events[-1][1] != "AI"):
            last = self.ctl.events[-1]
            if not any(e[1] == "AI" and e[2] == last[1] and e[0] == round(last[0], 1) for e in self.events[-10:]):
                self.events.append((round(last[0], 1), "AI", last[1]))
        # 단계 모드 / 특정 단계까지 진행: 단계가 바뀌면 멈춘다
        if self.ctl.state != self._last_stage:
            self._last_stage = self.ctl.state
            if self.step_mode or (self.run_until and self.ctl.state == self.run_until):
                self.paused = True
                if self.run_until == self.ctl.state:
                    self.run_until = None

    def _loop(self):
        acc = 0.0; last = time.monotonic()
        while self.running:
            now = time.monotonic(); wall = now - last; last = now
            if not self.paused:
                acc += wall * self.speed
                n = int(acc / self.cfg.dt); acc -= n * self.cfg.dt
                with self.lock:
                    for _ in range(min(n, 200)):
                        self.step()
                        if self.paused:                      # 단계 모드/run_until 로 멈추면 그 틱에서 바로 선다
                            acc = 0.0; break
            time.sleep(0.02)

    def start(self, paused=False):
        if self.thread and self.thread.is_alive():
            self.running = False; self.thread.join(1.0)
        self.running, self.paused = True, paused
        self.thread = threading.Thread(target=self._loop, daemon=True); self.thread.start()

    def advance(self, seconds: float):
        """일시정지 상태에서 시뮬레이션을 seconds 만큼만 진행 (한 틱씩 보기)."""
        n = int(round(seconds / self.cfg.dt))
        with self.lock:
            for _ in range(max(1, min(n, 6000))):
                self.step()

    # ---- 상태 (JSON)
    def state(self, since: int = 0) -> dict:
        with self.lock:
            tele = self.bus.latest() or {}
            h = self.hist
            n = len(h["t"])
            sl = slice(max(0, since), n)
            cam = self.cfg.camera
            return dict(
                t=round(self.t, 1), running=self.running, paused=self.paused, speed=self.speed, params=self.params,
                step_mode=self.step_mode, run_until=self.run_until, requested_target=self.params.get("target"),
                target_hex=optics.rgb8_to_hex(self.recipe.target_rgb8), target_resid=round(float(self.target_resid), 2),
                pressure_bar=tele.get("pressure_bar"),
                c_target=[round(float(v), 2) for v in self.recipe.c_target],
                camera_hex=optics.rgb8_to_hex(self.ctl.rgb), true_hex=(h["rgb_true"][-1] if n else None),
                ctl_state=self.ctl.state, done=self.ctl.done, dE=(None if self.ctl.de != self.ctl.de else round(float(self.ctl.de), 2)),
                trims=self.ctl.trims, aborted=self.ctl.aborted,
                io=dict(mode=self.io.mode, run_enable=self.io.run_en, valves=dict(self.io.valve_on),
                        pumps={p: dict(spm=round((tele.get("pumps", {}).get(p, {}) or {}).get("spm", 0.0), 1),
                                       strokes=round(self.io.strokes[p]), dosed_mL=round(self.io.dosed_mL[p], 2),
                                       mode=(tele.get("pumps", {}).get(p, {}) or {}).get("mode", "")) for p in PUMP_IDS},
                        est_V=round(self.cfg.reactor.heel_mL + sum(self.io.dosed_mL.values()), 1), alarms=len(self.io.alarms)),
                reactor=dict(V_mL=round(self.plant.reactor.V_mL, 1), rpm=round(self.plant.reactor.rpm),
                             c_true=[round(float(v), 2) for v in self.plant.reactor.c_true],
                             tanks=[round(tk.volume_mL, 1) for tk in self.plant.tanks[:3]]),
                pumps_live={p: (tele.get("pumps", {}).get(p, {}) or {}) for p in PUMP_IDS},
                calib=self.calib_info(),
                stage=self._stage_info(),
                plan=[dict(id=d["id"], volume_mL=round(d["volume_mL"], 2), strokes=round(d["strokes"]), rate=round(d["rate_mL_min"], 2),
                           mA=round(d["mA"], 2)) for d in self.plan],
                events=self.events[-60:], n=n,
                hist={k: h[k][sl] for k in ("t", "c_true", "c_hat", "dE", "dE_true", "spm", "strokes", "V", "tank", "valves", "rgb", "rgb_true")},
            )

    STAGES = [("PLAN", "계획", "목표색을 농도 c*(C,M,Y)로 역산하고 펌프별 투입 부피·스트로크·속도를 정한다"),
              ("PRIME", "준비", "I/O 노드 무장(arm), 교반기 지령, 운전 허가, 밸브 열기"),
              ("DOSE", "투입", "세 펌프가 스트로크를 세며 동시에 색소를 넣는다. 끝나면 밸브를 닫는다"),
              ("SETTLE", "정착", "혼합시간 × 3 만큼 기다린다 (교반 rpm 이 낮으면 길어짐)"),
              ("MEASURE", "측정", "카메라 2 s 평균 → ĉ 와 ΔE2000"),
              ("TRIM", "보정", "ĉ 가 목표보다 모자란 염료만 추가 투입 (과투입은 되돌릴 수 없음)"),
              ("DONE", "완료", "운전 허가 OFF, SAFE. '지금 트림' 으로 한 사이클 더 할 수 있음")]

    def _stage_info(self):
        st = self.ctl.state
        idx = next((i for i, (k, _, _) in enumerate(self.STAGES) if k == st), -1)
        return dict(index=idx, key=st, names=[n for _, n, _ in self.STAGES], keys=[k for k, _, _ in self.STAGES],
                    desc=(self.STAGES[idx][2] if idx >= 0 else ("수동 모드: 밸브·펌프를 직접 조작" if self.params["manual"] else st)),
                    elapsed=round(self.t - self.ctl.t_state, 1))

    # ---- 조작
    def inject(self, kind: str, arg: str):
        with self.lock:
            apply_fault(kind, arg, self.plant, self.ai, self.io)
            self.io.alarms.append((self.t, f"FAULT_INJECTED {kind} {arg}"))
            self.events.append((round(self.t, 1), "IO", f"FAULT_INJECTED {kind} {arg}"))
            self._n_alarm = len(self.io.alarms)

    def manual(self, cmd: dict):
        with self.lock:
            self.bus.send_cmd(cmd)

    def load_calibration(self, data: dict | None = None, path: str | None = None, name: str = ""):
        """calibration.json 내용(dict) 또는 서버 경로를 읽어 다음 준비/시작부터 적용. None 이면 기본으로 되돌림."""
        with self.lock:
            if data is None and path is None:
                self.calib, self.calib_name = None, "기본(설명용 행렬)"
            else:
                if data is None:
                    data = json.loads(pathlib.Path(path).read_text())
                cal = Calibration(**{k: data[k] for k in ("E", "I0", "gamma", "glare", "cond", "samples", "note") if k in data})
                E = np.array(cal.E, float)
                if E.shape != (3, 3) or len(cal.I0) != 3:
                    raise ValueError("E 는 3×3, I0 는 3개여야 합니다")
                self.calib, self.calib_name = cal, (name or path or "업로드")
        p = dict(self.params); self.reset(p); self.running = False
        return self.calib_info()

    def calib_info(self):
        c = self.calib
        return dict(name=self.calib_name, custom=c is not None,
                    E=(np.round(np.array(c.E), 5).tolist() if c else np.round(self.cfg.camera.E, 5).tolist()),
                    I0=(np.round(np.array(c.I0), 4).tolist() if c else np.round(self.cfg.camera.I0, 4).tolist()),
                    cond=round(float(np.linalg.cond(np.array(c.E if c else self.cfg.camera.E))), 3),
                    gamma=(c.gamma if c else self.cfg.camera.gamma), glare=(c.glare if c else self.cfg.camera.glare),
                    samples=(len(c.samples) if c else 0), note=(c.note if c else "config.py 의 설명용 값. camera_tools fit 결과를 올리면 실제 카메라 기준이 된다"))

    def set_rpm(self, rpm: float):
        with self.lock:
            self.bus.send_cmd(dict(cmd="stirrer_rpm", rpm=float(rpm))); self.ctl.r.rpm = float(rpm)

    def change_target(self, target: str):
        """운전 중 목표색 변경: 다음 MEASURE/TRIM 부터 새 목표를 쓴다 (이미 들어간 염료는 뺄 수 없음)."""
        with self.lock:
            p = dict(self.params); p["target"] = target
            if str(target).startswith("#"):
                rec, resid = make_recipe(self.cfg, target, None, mode=p["mode"], dose_minutes=float(p["dose_min"]),
                                         de_match=float(p["de_match"]), flow_factor=np.array([float(p["flow_factor"])] * 3))
            else:
                rec, resid = make_recipe(self.cfg, None, [float(v) for v in str(target).split(",")], mode=p["mode"],
                                         dose_minutes=float(p["dose_min"]), de_match=float(p["de_match"]), flow_factor=np.array([float(p["flow_factor"])] * 3))
            self.params = p; self.recipe.target_rgb8 = rec.target_rgb8; self.recipe.c_target = rec.c_target; self.target_resid = resid
            self.ctl.r = self.recipe; self.reachable_hex = optics.rgb8_to_hex(rec.target_rgb8)
            self.ctl.estimate(self.ctl.rgb)                                  # ΔE 를 새 목표로 즉시 다시 계산
            self.plan = plan_doses(self.cfg, self.cfg.reactor.heel_mL, rec.c_target, rec.dose_minutes, rec.flow_factor)
            self.events.append((round(self.t, 1), "UI", f"목표 변경 → {optics.rgb8_to_hex(rec.target_rgb8)} c*={np.round(rec.c_target, 1).tolist()}"))
            st = self.ctl.state
        if st in ("DONE", "SETTLE", "MEASURE") and not self.params["manual"]:
            self.trim_now()                                                  # 바로 측정→트림 한 사이클 (부족분만 추가)
        elif st in ("PLAN", "PRIME"):
            pass                                                             # 아직 투입 전: 새 계획으로 그대로 진행
        else:
            with self.lock:
                self.events.append((round(self.t, 1), "UI", "투입 중: 새 목표는 다음 측정(MEASURE)부터 반영"))

    def trim_now(self):
        """지금 측정→트림 한 사이클 더. DONE 이후면 노드를 다시 무장한다."""
        with self.lock:
            if self.params["manual"]:
                return
            if self.ctl.state == "DONE":
                self.bus.send_cmd(dict(cmd="arm")); self.bus.send_cmd(dict(cmd="run_enable", on=True))
                self.ctl.result = None; self.ctl.trims = 0; self.ctl.aborted = ""
            self.ctl.state, self.ctl.t_state = "MEASURE", self.t
            self.ctl.events.append((round(self.t, 2), "UI → MEASURE (수동 트림 요청)"))
            self._last_stage = "MEASURE"
            if self.running and self.paused and not self.step_mode:
                self.paused = False


# ------------------------------------------------------------------ HTML
PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CMY 색 매칭 시뮬레이터</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{--bg:#f4f5f7;--card:#fff;--ink:#1d1d1f;--mut:#6b7280;--line:#e3e5e8;--acc:#2a6fdb;--bad:#c62828;--ok:#2e7d32;--warn:#b26a00}
*{box-sizing:border-box}body{margin:0;font-family:Pretendard,"Pretendard Variable",-apple-system,"Apple SD Gothic Neo","Noto Sans KR",system-ui,sans-serif;background:var(--bg);color:var(--ink);font-size:14px;letter-spacing:-.01em}
header{background:#1f2a3a;color:#fff;padding:10px 16px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
header h1{font-size:16px;margin:0;font-weight:700}header .st{font-size:13px;opacity:.9}header button{margin-left:auto;background:transparent;color:#fff;border-color:#55657a}
main{display:grid;grid-template-columns:330px 1fr;gap:12px;padding:12px;max-width:1500px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:12px}
.card h2{font-size:12px;margin:0 0 8px;color:var(--mut);font-weight:600;letter-spacing:.02em}
label{display:block;font-size:12px;color:var(--mut);margin-top:8px}
input,select,button{font:inherit}input[type=text],input[type=number],select{width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:7px;background:#fff}
input[type=range]{width:100%}
.row{display:flex;gap:8px;align-items:center}.row>*{flex:1}
button{padding:7px 10px;border:1px solid var(--line);background:#fff;border-radius:7px;cursor:pointer;font-weight:500}
button:hover{background:#f7f8fa}button.pri{background:var(--acc);color:#fff;border-color:var(--acc)}button.warn{border-color:var(--bad);color:var(--bad)}button.on{background:#e3f2fd;border-color:#90caf9}
.sw{display:flex;gap:10px;margin:4px 0 10px}.sw div{flex:1;text-align:center;font-size:12px;color:var(--mut)}.sw .box{height:56px;border-radius:8px;border:1px solid var(--line);margin-bottom:4px}
canvas{width:100%;height:160px;display:block;background:#fff}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:3px 4px;border-bottom:1px solid #eee;text-align:left}th{color:var(--mut);font-weight:600}
.log{height:150px;overflow:auto;font-size:12px;font-family:ui-monospace,Menlo,Consolas,monospace;background:#fafafa;border:1px solid var(--line);border-radius:7px;padding:6px}
.badge{display:inline-block;padding:2px 9px;border-radius:10px;font-size:12px;background:#eee;font-weight:600}.badge.run{background:#e3f2fd;color:#0d47a1}.badge.safe{background:#fdecea;color:var(--bad)}.badge.done{background:#e8f5e9;color:var(--ok)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:12.5px}.kv b{color:var(--mut);font-weight:500}
small,.help{color:var(--mut);font-size:12px;line-height:1.5}
.q{display:inline-block;width:15px;height:15px;line-height:15px;text-align:center;border-radius:50%;background:#e8ebf0;color:#556;font-size:10px;margin-left:4px;cursor:help;vertical-align:middle}
.cap{display:block;color:#8a8f98;font-size:11px;margin-top:2px;line-height:1.4}
abbr{text-decoration:none;border-bottom:1px dotted #999;cursor:help}
.stages{display:flex;gap:4px;margin:6px 0 4px}.stages div{flex:1;text-align:center;font-size:11px;padding:6px 2px;border-radius:6px;background:#f0f1f3;color:#8a8f98}.stages div.cur{background:var(--acc);color:#fff;font-weight:600}.stages div.past{background:#dfe8f8;color:#2a4a7a}.stages div{cursor:pointer}.stages div.until{outline:2px dashed var(--acc)}
.pump{border:1px solid var(--line);border-radius:8px;padding:8px;margin-top:8px}.pump .hd{display:flex;justify-content:space-between;font-size:12.5px;font-weight:600}.pump .hd span{font-weight:500;color:var(--mut)}
.help ol{margin:4px 0 0 18px;padding:0}.help li{margin:3px 0}
svg text{font-family:inherit}
@media (max-width:980px){main{grid-template-columns:1fr}}
</style></head><body>
<header><h1>CMY 색 매칭 시뮬레이터</h1><span class="st" id="hdr">—</span><button onclick="toggleHelp()">사용 안내</button></header>
<main>
<section>
 <div class="card" id="helpcard" style="display:none"><h2>사용 안내 — 화면과 단계</h2><div class="help">
  <b>왼쪽 열</b><ol>
  <li><b>실험 설정</b>: 시작 전 조건. 목표색(색상 피커 또는 C,M,Y mg/L), 초기 물·rpm, 제어 방식(closed = 카메라로 트림 / open = 피드포워드만), 펌프 구동(펄스 = 접점, analog = 4–20 mA), 도징 시간, 피드포워드 배율(0.97 = 3 % 적게 넣고 트림으로 채움), 카메라 잡음, 시드.</li>
  <li><b>실시간 제어</b>: 운전 중에 쓰는 것. 펌프별 속도 배율(0~150 %)·보류·밸브, 교반 rpm, 목표색 변경(다음 측정부터 반영), 지금 트림, 전체 정지(SAFE).</li>
  <li><b>고장 주입</b>: 시뮬레이션에만 있는 버튼. I/O 노드와 제어기가 어떻게 잡는지 본다.</li>
  <li><b>수동 모드</b>: 제어기 없이 밸브를 열고 스트로크 수를 정해 투입. 밸브를 안 열고 투입하면 I/O 노드가 거부(인터록).</li>
  <li><b>투입 계획</b>: 목표 농도에서 계산한 펌프별 mL·스트로크·mL/min·mA.</li></ol>
  <b>오른쪽 열</b><ol>
  <li><b>단계 표시줄</b>: PLAN(계획) → PRIME(준비) → DOSE(투입) → SETTLE(정착) → MEASURE(측정) → TRIM(보정) → DONE(완료). 현재 단계와 설명, 경과 시간.</li>
  <li><b>장비 모식도</b>: 스톡병 3개(잔량), 펌프(돌 때 깜빡임, spm), 밸브(초록 열림/회색 닫힘), 반응기(실제 색과 수위). 실제 패널 배치와 같은 순서.</li>
  <li><b>색 견본</b>: 목표 / 카메라가 본 색 / 실제 색. ΔE2000 이 1.5 아래면 매칭.</li>
  <li><b>그래프</b>: 농도(실선 실제, 점선 카메라 추정, 가는 점선 목표), ΔE2000, 펌프 spm.</li>
  <li><b>이벤트·알람</b>: AI 노드 상태 전이, I/O 노드 알람(INTERLOCK, NO_STROKE, SAFE…), 고장 주입, UI 조작.</li></ol>
  <b>용어</b><ol>
  <li><b>ΔE2000</b>: 사람 눈 기준 두 색의 거리(CIEDE2000). 1 이하 거의 구분 못 함, 2~4 일반인이 구분, 5 이상 다른 색. 1.5 아래를 매칭으로 본다.</li>
  <li><b>c*</b> 목표 농도, <b>ĉ</b> 카메라가 추정한 농도, <b>c</b> 진짜 농도(시뮬레이터만 앎). 단위 mg/L.</li>
  <li><b>스트로크(str)</b>: 다이아프램 펌프의 1회 토출, 0.19 mL. <b>spm</b>: 분당 스트로크 = 펌프 속도(최대 200 = 38 mL/min).</li>
  <li><b>펄스</b>: 접점 신호 1회 = 스트로크 1회로 펌프를 구동하는 방식. <b>아날로그</b>: 4–20 mA 전류로 속도 지령.</li>
  <li><b>피드포워드</b>: 계산한 양을 먼저 넣는 것. <b>트림(카메라 트림)</b>: 카메라로 재서 모자란 염료만 추가하는 보정. <b>피드포워드 배율</b> 0.97 = 3 % 적게 넣고 트림으로 채움.</li>
  <li><b>도징 시간</b>: 계산한 양을 몇 분에 걸쳐 넣을지. <b>속도 배율</b>: 운전 중 펌프 속도에 곱하는 값(투입량은 불변). <b>시드</b>: 난수 시작값(재현용).</li></ol>
  <b>실제 장비에서의 대응</b>: 왼쪽 설정·실시간 제어 = AI 노드(ai_node_main)가 보내는 명령, 오른쪽 상태 = I/O 노드 텔레메트리. 버튼 하나가 명령 JSON 하나다(docs/PROTOCOL.md).</div></div>
 <div class="card"><h2>실험 설정</h2>
  <label>목표색 (hex 또는 C,M,Y mg/L)<span class="q" title="만들고 싶은 색. #RRGGBB 또는 염료 농도 C,M,Y (mg/L). 카메라 모델로 역산해 목표 농도 c* 를 만든다">?</span></label>
  <div class="row"><input type="color" id="pick" value="#5A8F7B" style="width:46px;flex:none;height:34px;padding:0;border:1px solid var(--line);border-radius:7px"><input type="text" id="target" value="#5A8F7B"><button onclick="applyTarget()" style="flex:none" title="운전 중이면 즉시 새 목표로 바꾼다 (투입 전: 새 계획 / 투입 후: 바로 측정→트림 / 투입 중: 다음 측정부터). 시작 전이면 시작할 때 쓰인다">적용</button></div>
  <span class="cap" id="targetNote">시작 전: 시작할 때 이 색을 목표로 씀 · 운전 중: '적용' 을 누르면 즉시 새 목표</span>
  <div class="row"><div><label>초기 물 [mL]<span class="q" title="반응기에 미리 넣어 둔 물(heel). 같은 염료량이라도 물이 많으면 농도가 낮아진다">?</span></label><input type="number" id="heel" value="2000"></div><div><label>교반 rpm<span class="q" title="교반기 회전수. 혼합시간 ≈ 3000/rpm 초. 낮으면 색이 고르게 섞이는 데 오래 걸려 정착(SETTLE)이 길어진다">?</span></label><input type="number" id="rpm" value="300"></div></div>
  <div class="row"><div><label>제어<span class="q" title="closed: 투입 뒤 카메라로 재서 모자란 염료를 추가(트림). open: 계산한 양만 넣고 끝(피드포워드만)">?</span></label><select id="mode"><option value="closed">closed (카메라 트림)</option><option value="open">open (피드포워드만)</option></select></div>
   <div><label>펌프 구동<span class="q" title="pulse: MCC 152 DIO 접점 펄스 1회 = 펌프 스트로크 1회 (XTR111 보드 없음). analog: 4–20 mA 전류로 속도 지령">?</span></label><select id="pump_mode"><option value="pulse">pulse (접점)</option><option value="analog">analog (4–20 mA)</option></select></div></div>
  <div class="row"><div><label>도징 시간 [min]<span class="q" title="계산된 투입량을 몇 분에 걸쳐 넣을지. 가장 많이 넣는 펌프가 최대 속도(200 spm)를 넘지 않게 자동으로 늘어난다">?</span></label><input type="number" id="dose_min" value="1.5" step="0.5"></div><div><label>피드포워드 배율<span class="q" title="계산한 투입량에 곱하는 값. 0.97 = 3 % 적게 넣고 모자란 만큼 카메라 트림으로 채운다. 과투입은 되돌릴 수 없어서 일부러 적게 넣는다">?</span></label><input type="number" id="ff" value="0.97" step="0.01"></div></div>
  <div class="row"><div><label>카메라 잡음<span class="q" title="픽셀 밝기 잡음(표준편차, 0~1 선형). 클수록 카메라 추정 ĉ 가 흔들린다. ROI 평균으로 줄어든다">?</span></label><input type="number" id="noise" value="0.02" step="0.005"></div><div><label>시드<span class="q" title="난수 시작값. 같은 시드면 잡음·펌프 오차가 똑같이 재현된다. 바꾸면 다른 실험 한 번">?</span></label><input type="number" id="seed" value="0"></div></div>
  <div class="row" style="margin-top:6px;align-items:flex-end"><div><label>도달 가능한 가장 가까운 색</label><div class="box" id="swReach" style="height:28px;border-radius:6px;border:1px solid var(--line)"></div></div><div><small id="reachNote">—</small></div></div>
  <label><input type="checkbox" id="manual"> 수동 모드 (제어기 없이 직접 밸브·펌프 조작)<span class="q" title="자동 제어기를 끄고 아래 '수동 조작' 카드로 밸브 열기 → 스트로크 수 투입을 직접 한다. 실제 장비 첫 시운전과 같은 절차">?</span></label>
  <label><input type="checkbox" id="stepmode" onchange="stepMode(this.checked)"> 단계마다 멈춤 (PLAN → PRIME → … 한 단계씩 보기)<span class="q" title="단계가 바뀔 때마다 자동 일시정지. '다음 단계' 또는 '계속' 으로 진행">?</span></label>
  <div class="row" style="margin-top:10px"><button onclick="prepare()" title="실행하지 않고 계획만 세워 PLAN 상태(0 s)에서 멈춘다">준비 (0 s)</button><button class="pri" onclick="start()" title="위 설정으로 새 실험을 시작한다 (진행 중이면 처음부터)">시작 / 재시작</button><button onclick="pause()" id="pbtn" title="시뮬레이션 시간을 멈추거나 다시 흐르게 한다">일시정지</button></div>
  <span class="cap">준비 = 계획만 · 시작 = 처음부터 운전 · 일시정지/계속 = 시간 멈춤</span>
  <div class="row" style="margin-top:6px"><button onclick="nextStage()" title="다음 단계 전이에서 자동으로 멈춘다 (단계마다 멈춤 켜짐)">▶ 다음 단계</button><button onclick="stepSec(1)" title="멈춘 채 1 초만 진행">+1 s</button><button onclick="stepSec(10)" title="멈춘 채 10 초만 진행">+10 s</button><button onclick="stepSec(60)" title="멈춘 채 60 초만 진행">+60 s</button></div>
  <span class="cap">다음 단계 = PLAN→PRIME→DOSE… 한 칸씩 · +N s = 멈춘 채 그만큼만 진행</span>
  <label>속도 <span id="spv">10</span>×<span class="q" title="시뮬레이션 시간 배속. 10× 면 실제 1 초에 시뮬레이션 10 초. 실제 장비에서는 항상 1×">?</span></label><input type="range" id="speed" min="1" max="60" value="10" oninput="setSpeed(this.value)">
 </div>
 <div class="card"><h2>실시간 제어 (운전 중)</h2>
  <div id="pumpctl"></div>
  <span class="cap">배율·보류는 남은 스트로크(투입량)는 그대로 두고 속도만 바꾼다 → 최종 색은 같고 걸리는 시간만 달라진다. '정지' 는 남은 투입을 취소한다.</span>
  <label>교반 rpm <span id="rpmv">300</span><span class="q" title="교반기 속도를 운전 중 바꾼다. 낮추면 섞이는 시간이 길어져 카메라가 보는 색이 늦게 따라온다">?</span></label><input type="range" id="rpmlive" min="0" max="1000" step="10" value="300" onchange="liveRpm(this.value)" oninput="$('rpmv').textContent=this.value">
  <span class="cap">목표색은 위 '실험 설정' 의 목표색 칸에서 바꾸고 '적용' 을 누르면 운전 중에도 즉시 반영됩니다.</span>
  <div class="row" style="margin-top:8px"><button onclick="trimNow()" title="지금 카메라로 재고(MEASURE) 모자란 염료를 추가 투입(TRIM) 한 사이클">지금 트림</button><button class="warn" onclick="live({op:'safe'})" title="I/O 노드 SAFE: 운전 허가 OFF → 펌프 0 → 밸브 닫힘. 실제 비상정지와 같은 순서">전체 정지 (SAFE)</button></div>
 </div>
 <div class="card"><h2>카메라 보정<span class="q" title="camera_tools fit 이 만든 calibration.json (실측 E 행렬·기준 I0). 올리면 시뮬레이터의 색↔농도 변환과 제어기 역산이 실제 카메라 기준으로 바뀐다. 다음 준비/시작부터 적용">?</span></h2>
  <div class="kv"><b>현재</b><span id="calName">—</span><b>조건수 κ</b><span id="calCond">—</span><b>I0</b><span id="calI0">—</span><b>E</b><span id="calE" style="font-family:ui-monospace,Menlo,monospace;font-size:11px;white-space:pre"></span></div>
  <small id="calNote"></small>
  <div class="row" style="margin-top:8px"><input type="file" id="calFile" accept=".json" style="flex:1;min-width:0;font-size:12px"><button onclick="uploadCal()" style="flex:none">불러오기</button></div>
  <div class="row" style="margin-top:6px"><input type="text" id="calPath" placeholder="또는 서버 경로: /home/user/calibration.json" style="flex:1;min-width:0"><button onclick="loadCalPath()" style="flex:none">경로로</button><button onclick="resetCal()" style="flex:none">기본으로</button></div>
  <span class="cap">워크스테이션에서 UI 를 돌리면 파일 선택이 가장 쉽습니다. 라즈베리파이 AI 노드에서 만든 calibration.json 을 복사해 올리세요.</span>
 </div>
 <div class="card"><h2>고장 주입<span class="q" title="시뮬레이션 전용. 실제 장비에서 생길 수 있는 문제를 넣어 I/O 노드 알람과 제어기 반응을 본다">?</span></h2>
  <span class="cap">탱크 고갈 → 펌프 수위 정지·NO_STROKE · 밸브 고착 → 릴리프 순환·RELIEF · 카메라 −10 % → 추정 ĉ 가 전부 커 보임 · 스톡 −15 % → 덜 진해져 트림이 채움 · 교반 60 rpm → 정착 지연 · AI 노드 사망 → 1 s 뒤 워치독 SAFE</span>
  <div class="row"><button onclick="fault('tank_empty','P-101')">C 탱크 고갈</button><button onclick="fault('valve_stuck','XV-102')">XV-102 고착</button></div>
  <div class="row" style="margin-top:6px"><button onclick="fault('camera_drift','0.9')">카메라 −10 %</button><button onclick="fault('stock_conc','P-103=850')">Y 스톡 −15 %</button></div>
  <div class="row" style="margin-top:6px"><button onclick="fault('rpm','60')">교반 60 rpm</button><button onclick="fault('ai_crash','')">AI 노드 사망</button></div>
 </div>
 <div class="card" id="manualcard" style="display:none"><h2>수동 조작</h2>
  <div class="row"><select id="mpump"><option>P-101</option><option>P-102</option><option>P-103</option></select><input type="number" id="mstrokes" value="50" title="스트로크 수"><input type="number" id="mma" value="12" step="0.5" title="mA (속도)"></div>
  <div class="row" style="margin-top:6px"><button onclick="mvalve(true)">밸브 열기</button><button onclick="mvalve(false)">밸브 닫기</button><button class="pri" onclick="mdose()">투입</button><button onclick="mstop()">정지</button></div>
  <small>인터록: 밸브를 먼저 열어야 투입이 됩니다. 닫힌 채 투입하면 I/O 노드가 거부합니다.</small>
 </div>
 <div class="card"><h2>투입 계획<span class="q" title="목표 농도 c* 에서 계산한 펌프별 투입량. mL = 부피, 스트로크 = mL ÷ 0.19, mL/min = 속도, mA = 아날로그 모드일 때의 전류 지령(펄스 모드는 spm 으로 환산)">?</span></h2><table id="plan"></table>
  <span class="cap">V_j = c_j × V_f ÷ c_stock (스톡 1 g/L), 스트로크 = V_j ÷ 0.19 mL, 여기에 피드포워드 배율을 곱한 값</span></div>
</section>
<section>
 <div class="card">
  <div class="stages" id="stages"></div><div class="help" id="stagedesc">—</div>
  <small>칩을 누르면 그 단계 설명이 보이고, 운전 중이면 그 단계에 도달할 때 자동으로 멈춥니다.</small>
 </div>
 <div class="card"><h2>장비 모식도 (P&amp;ID, 실제 패널 배치)</h2><svg id="mimic" viewBox="0 0 900 430" width="100%" height="430"></svg>
  <small>라인마다: 스톡병 → gamma/X 펌프(다기능 밸브) → 튜브 → 패널 수직관 → 티(볼밸브 분기, 수동) → 압력계/트랜스미터 PT → 맥동 댐퍼 PD → DHV-U 배압 밸브(2 bar) → 솔레노이드 XV(신설) → 체크밸브 → 반응기</small></div>
 <div class="card">
  <div class="sw"><div><div class="box" id="swT"></div>목표 <span id="hexT"></span></div><div><div class="box" id="swC"></div>카메라 <span id="hexC"></span><span class="q" title="카메라 ROI 평균 RGB (잡음·글레어 포함). 매칭 판정은 이 값과 목표의 ΔE2000 으로 한다">?</span></div><div><div class="box" id="swR"></div>실제 <span id="hexR"></span><span class="q" title="진짜 농도에서 계산한 색 (시뮬레이터만 앎). 카메라 견본과 다르면 그만큼이 카메라 오차">?</span></div></div>
  <div id="gauge" style="margin:4px 0 10px">
   <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--mut)"><span>매칭 정도 (ΔE2000, 카메라 기준)</span><span id="gaugeTxt">—</span></div>
   <div style="position:relative;height:14px;border-radius:7px;overflow:hidden;background:linear-gradient(90deg,#2e7d32 0 15%,#8bc34a 15% 20%,#ffc107 20% 40%,#ff7043 40% 60%,#c62828 60% 100%)">
    <div id="gaugeMk" style="position:absolute;top:-2px;width:3px;height:18px;background:#111;left:0"></div></div>
   <div style="display:flex;justify-content:space-between;font-size:10px;color:#888"><span>0</span><span>1.5 매칭</span><span>2</span><span>4 구분</span><span>6</span><span>10+</span></div>
   <div id="dyeErr" style="display:grid;grid-template-columns:auto 1fr auto;gap:2px 8px;font-size:11px;margin-top:6px;align-items:center"></div>
  </div>
  <div class="kv"><b>상태</b><span><span class="badge" id="iomode">—</span> <span id="ctl"></span></span>
   <b><abbr title="CIEDE2000 색차. 사람 눈이 느끼는 두 색의 거리. 1 이하 거의 구분 못 함, 1~2 전문가가 나란히 보면 구분, 2~4 일반인이 구분, 5 이상 다른 색. 여기서는 1.5 아래를 매칭으로 본다">ΔE2000</abbr></b><span id="de"></span><b><abbr title="목표색을 카메라 모델로 역산한 염료 농도 c* (mg/L). 이 농도가 되도록 투입량을 계산한다">목표 농도 C/M/Y</abbr></b><span id="ct"></span><b><abbr title="ĉ (c-hat): 카메라 RGB → 흡광도 → 3×3 행렬 역산으로 '추정한' 농도. 실제 장비에서 알 수 있는 값은 이것뿐">추정 ĉ</abbr></b><span id="ch"></span><b><abbr title="시뮬레이터만 아는 진짜 농도 (물질수지). 실제 장비에서는 모른다. ĉ 와의 차이가 카메라 오차">실제 c</abbr></b><span id="cr"></span>
   <b>반응기</b><span id="rx"></span><b>밸브</b><span id="valves"></span></div>
 </div>
 <div class="card"><h2>농도 [mg/L] — 실선 실제, 점선 카메라 추정, 가는 점선 목표</h2><canvas id="c1"></canvas></div>
 <div class="card"><h2>ΔE2000 — 검정 실제, 회색 카메라 (초록 점선 = 매칭 기준 1.5)</h2><canvas id="c2"></canvas></div>
 <div class="card"><h2>펌프 spm — 분당 스트로크 (C 파랑 · M 자홍 · Y 노랑). 1 스트로크 = 0.19 mL, 최대 200 spm = 38 mL/min</h2><canvas id="c3"></canvas></div>
 <div class="card"><h2>이벤트 · 알람<span class="q" title="AI = 제어기 상태 전이, IO = I/O 노드 알람(INTERLOCK 거부, NO_STROKE 스트로크 없음, RELIEF 릴리프, SAFE 전이), UI = 사용자 조작">?</span></h2><div class="log" id="log"></div></div>
</section>
</main>
<script>
const $=id=>document.getElementById(id);
let H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]},n=0,ct=[0,0,0],paused=false,S=null;
const COL=["#00AEEF","#EC008C","#E6B800"],PUMPS=["P-101","P-102","P-103"],DYE=["C","M","Y"];
$('pick').oninput=e=>{$('target').value=e.target.value.toUpperCase();reach();markDirty()};$('target').oninput=()=>{markDirty()};$('target').onchange=reach;
function markDirty(){if(S&&S.running&&$('target').value.toUpperCase()!==(S.requested_target||'').toUpperCase())$('targetNote').textContent='⚠ 바뀐 목표색이 아직 적용되지 않았습니다 — 적용 을 누르세요';}
async function applyTarget(){if(S&&S.running){await live({op:'target',target:$('target').value});$('targetNote').textContent='적용됨: 운전 중 목표를 '+$('target').value.toUpperCase()+' 로 바꿈'}else{$('targetNote').textContent='시작하면 이 색을 목표로 씁니다'}}
async function reach(){try{const r=await (await fetch('/api/reach?target='+encodeURIComponent($('target').value))).json();$('swReach').style.background=r.hex;
 $('reachNote').textContent=r.resid>1.5?`⚠ 이 염료로는 정확히 못 만듦 (잔차 ΔE ${r.resid}). 가장 가까운 색 ${r.hex}, c*=${r.c.join('/')}`:`도달 가능 (ΔE ${r.resid}), c*=${r.c.join('/')} mg/L`}catch(e){}}
$('manual').onchange=e=>{$('manualcard').style.display=e.target.checked?'block':'none'};
function toggleHelp(){const h=$('helpcard');h.style.display=h.style.display==='none'?'block':'none'}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});return r.json()}
async function start(){H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]};n=0;
 await post('/api/start',cfgBody());await post('/api/stepmode',{on:$('stepmode').checked});
 $('rpmlive').value=$('rpm').value;$('rpmv').textContent=$('rpm').value;$('targetNote').textContent='운전 중: 목표색을 바꾸고 적용 을 누르면 즉시 반영';}
async function pause(){const s=await post('/api/pause');paused=s.paused;$('pbtn').textContent=paused?'계속':'일시정지'}
function cfgBody(){return {target:$('target').value,heel_mL:+$('heel').value,rpm:+$('rpm').value,mode:$('mode').value,pump_mode:$('pump_mode').value,
  dose_min:+$('dose_min').value,flow_factor:+$('ff').value,pixel_noise:+$('noise').value,seed:+$('seed').value,manual:$('manual').checked,speed:+$('speed').value}}
async function prepare(){H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]};n=0;await post('/api/reset',cfgBody());$('rpmlive').value=$('rpm').value;$('rpmv').textContent=$('rpm').value}
async function nextStage(){$('stepmode').checked=true;await post('/api/next')}
async function stepSec(sec){await post('/api/step',{seconds:sec})}
async function stepMode(on){await post('/api/stepmode',{on})}
async function runUntil(stage){await post('/api/run_until',{stage})}
async function setSpeed(v){$('spv').textContent=v;await post('/api/speed',{speed:+v})}
async function fault(k,a){await post('/api/fault',{kind:k,arg:a})}
async function live(b){await post('/api/live',b)}
async function liveRpm(v){await live({op:'rpm',rpm:+v})}
async function uploadCal(){const f=$('calFile').files[0];if(!f){alert('calibration.json 파일을 고르세요');return}const txt=await f.text();let data;try{data=JSON.parse(txt)}catch(e){alert('JSON 이 아닙니다');return}
 const r=await post('/api/calib',{data,name:f.name});if(r.error)alert('오류: '+r.error);H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]};n=0;reach()}
async function loadCalPath(){const r=await post('/api/calib',{path:$('calPath').value});if(r.error)alert('오류: '+r.error);H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]};n=0;reach()}
async function resetCal(){await post('/api/calib',{reset:true});H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]};n=0;reach()}
function showCal(c){$('calName').textContent=c.name+(c.custom?' (실측)':'');$('calCond').textContent=c.cond+(c.cond>3?' ⚠ 역산 불안정':'');$('calI0').textContent=c.I0.join(' / ');
 $('calE').textContent=c.E.map(r=>r.map(v=>v.toFixed(4)).join('  ')).join('\n');$('calNote').textContent=(c.samples?`보정 시료 ${c.samples}개 · `:'')+(c.note||'')}
async function trimNow(){await live({op:'trim_now'})}
async function mvalve(open){const p=$('mpump').value;await post('/api/manual',{cmd:'valve',id:'XV-'+p.slice(2),open})}
async function mdose(){await post('/api/manual',{cmd:'dose',id:$('mpump').value,mA:+$('mma').value,strokes:+$('mstrokes').value})}
async function mstop(){await post('/api/manual',{cmd:'stop',id:$('mpump').value})}
// 펌프별 실시간 제어 카드 (한 번 만들고 값만 갱신)
function buildPumpCtl(){$('pumpctl').innerHTML=PUMPS.map((p,j)=>`<div class="pump" id="pc${j}"><div class="hd">${p} <span style="color:${COL[j]}">●</span> ${DYE[j]} <span id="pcs${j}" title="spm = 분당 스트로크(펌프 속도), str = 지금까지 센 스트로크 수(1 스트로크 = 0.19 mL), 남은 = 이번 투입에서 남은 스트로크">—</span></div>
 <label>속도 배율 <span id="pcv${j}">100</span> %<span class="q" title="펌프 속도에 곱하는 값. 50 % 면 절반 속도로 같은 양을 넣는다 (최종 색 동일, 시간 2배). 150 % 는 상한 200 spm 까지">?</span></label><input type="range" min="0" max="150" value="100" id="pcr${j}" oninput="$('pcv${j}').textContent=this.value" onchange="live({op:'rate',id:'${p}',factor:this.value/100})">
 <div class="row" style="margin-top:6px"><button id="pch${j}" onclick="toggleHold(${j})" title="펌프를 잠시 멈춘다. 남은 스트로크는 유지되어 재개하면 이어서 넣는다">보류</button><button id="pcvl${j}" onclick="toggleValve(${j})" title="이 라인의 솔레노이드 밸브 XV. 닫힌 채 펌프 명령이 오면 I/O 노드가 거부(INTERLOCK)">밸브</button><button onclick="live({op:'stop_pump',id:'${p}'})" title="이번 투입을 취소하고 펌프를 멈춘다 (남은 스트로크 폐기)">정지</button></div></div>`).join('')}
buildPumpCtl();
function toggleHold(j){const on=!(S&&S.pumps_live[PUMPS[j]]&&S.pumps_live[PUMPS[j]].hold);live({op:'hold',id:PUMPS[j],on})}
function toggleValve(j){const v='XV-'+PUMPS[j].slice(2);const open=!(S&&S.io.valves[v]);live({op:'valve',id:v,open})}
function line(cv,series,opts){const c=cv.getContext('2d');const W=cv.width=cv.clientWidth*devicePixelRatio,Hh=cv.height=cv.clientHeight*devicePixelRatio;c.clearRect(0,0,W,Hh);
 const t=H.t;if(t.length<2)return;const pad=36*devicePixelRatio,x0=pad,x1=W-8,y0=8,y1=Hh-20*devicePixelRatio;let ymax=opts.ymax||0;
 series.forEach(s=>s.y.forEach(v=>{if(v!=null&&v>ymax)ymax=v}));(opts.hlines||[]).forEach(v=>{if(v>ymax)ymax=v});ymax=Math.max(ymax*1.1,opts.ymin||1);const tmin=t[0],tmax=t[t.length-1];
 const X=v=>x0+(v-tmin)/(tmax-tmin||1)*(x1-x0),Y=v=>y1-(v/ymax)*(y1-y0);
 c.strokeStyle='#eee';c.lineWidth=1;c.fillStyle='#888';c.font=`${11*devicePixelRatio}px Pretendard, sans-serif`;
 for(let i=0;i<=4;i++){const y=y0+(y1-y0)*i/4;c.beginPath();c.moveTo(x0,y);c.lineTo(x1,y);c.stroke();c.fillText((ymax*(1-i/4)).toFixed(opts.dec==null?1:opts.dec),4,y+4)}
 c.fillText(tmin.toFixed(0)+' s',x0,Hh-4);c.fillText(tmax.toFixed(0)+' s',x1-40*devicePixelRatio,Hh-4);
 (opts.hlines||[]).forEach((v,i)=>{c.setLineDash([2,3]);c.strokeStyle=opts.hcolors?opts.hcolors[i]:COL[i];c.lineWidth=1;c.beginPath();c.moveTo(x0,Y(v));c.lineTo(x1,Y(v));c.stroke();c.setLineDash([])});
 series.forEach(s=>{c.strokeStyle=s.color;c.lineWidth=(s.width||1.5)*devicePixelRatio;c.setLineDash(s.dash||[]);c.beginPath();let st=false;
  s.y.forEach((v,i)=>{if(v==null){st=false;return}const x=X(t[i]),y=Y(v);if(!st){c.moveTo(x,y);st=true}else c.lineTo(x,y)});c.stroke();c.setLineDash([])});}
function draw(){line($('c1'),[0,1,2].flatMap(j=>[{y:H.c_true.map(v=>v[j]),color:COL[j]},{y:H.c_hat.map(v=>v[j]),color:COL[j],dash:[4,3],width:1}]),{hlines:ct,dec:1});
 line($('c2'),[{y:H.dE_true,color:'#000'},{y:H.dE,color:'#888',dash:[4,3],width:1}],{ymin:5,hlines:[1.5],hcolors:['#2e7d32'],dec:1});
 line($('c3'),[0,1,2].map(j=>({y:H.spm.map(v=>v[j]),color:COL[j]})),{ymin:50,dec:0});}
// 장비 모식도 — 실제 패널 P&ID (라인 3개 수직, 하단 펌프·스톡병, 우측 반응기)
let blink=0;
function mimic(s){blink=(blink+1)%2;const g=$('mimic');const tanks=s.reactor.tanks,V=s.reactor.V_mL;const rt=s.true_hex?'#'+s.true_hex.map(v=>v.toString(16).padStart(2,'0')).join(''):'#ffffff';
 const names=['Metal/C','NaOH/M','Ammonia/Y'];let out=`<defs><marker id="arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#777"/></marker></defs>`;
 out+=`<text x="12" y="18" font-size="12" fill="#444">CHEMICAL FEEDER 패널 (ProMinent)  ·  배압 DHV-U 2 bar  ·  댐퍼 HIDRACAR 0.09 L  ·  압력 ${s.pressure_bar==null?'—':s.pressure_bar} bar</text>`;
 const yOut=40,yDHV=70,yPD=108,yPT=150,yTee=200,yBall=232,yTube=262,yPump=320,yBottle=388;
 PUMPS.forEach((p,j)=>{const x=90+j*150;const pm=s.pumps_live[p]||{};const on=(pm.spm||0)>0;const v=s.io.valves['XV-'+p.slice(2)];const lv=Math.max(0,Math.min(1,tanks[j]/2000));
  // 출구 → 반응기 라인 (상단 헤더)
  out+=`<path d="M${x},${yOut} L${x},28 L640,28" fill="none" stroke="${v?'#4caf50':'#ccc'}" stroke-width="3"/>`;
  // 솔레노이드 XV (신설) + 체크밸브
  out+=`<rect x="${x-14}" y="${yOut-2}" width="28" height="16" rx="3" fill="${v?'#4caf50':'#bdbdbd'}"/><text x="${x+20}" y="${yOut+11}" font-size="10" fill="#555">XV-${p.slice(2)} ${v?'열림':'닫힘'}</text>
   <polygon points="${x-7},${yOut+22} ${x+7},${yOut+22} ${x},${yOut+32}" fill="#999"/><text x="${x+12}" y="${yOut+31}" font-size="9" fill="#777">CV</text>`;
  // DHV-U 배압 밸브 (주황)
  out+=`<line x1="${x}" y1="${yOut+16}" x2="${x}" y2="${yDHV}" stroke="#999" stroke-width="3"/><circle cx="${x}" cy="${yDHV+12}" r="12" fill="#f57c00"/><text x="${x+16}" y="${yDHV+16}" font-size="10" fill="#555">DHV-U 2 bar</text>`;
  // 맥동 댐퍼 (노랑 라벨)
  out+=`<line x1="${x}" y1="${yDHV+24}" x2="${x}" y2="${yPD}" stroke="#999" stroke-width="3"/><rect x="${x-10}" y="${yPD}" width="20" height="30" rx="4" fill="#efe9d8" stroke="#bbb"/><rect x="${x-10}" y="${yPD+10}" width="20" height="8" fill="#f9d64b"/><text x="${x+16}" y="${yPD+20}" font-size="10" fill="#555">PD</text>`;
  // 압력계 / 트랜스미터
  out+=`<line x1="${x}" y1="${yPD+30}" x2="${x}" y2="${yPT}" stroke="#999" stroke-width="3"/><circle cx="${x}" cy="${yPT+12}" r="12" fill="#fff" stroke="#888" stroke-width="2"/><text x="${x}" y="${yPT+16}" text-anchor="middle" font-size="9" fill="#333">PT</text><text x="${x+16}" y="${yPT+16}" font-size="10" fill="#555">압력계→4–20 mA</text>`;
  // 티 + 볼밸브 분기 (수동)
  out+=`<line x1="${x}" y1="${yPT+24}" x2="${x}" y2="${yTee}" stroke="#999" stroke-width="3"/><circle cx="${x}" cy="${yTee}" r="4" fill="#777"/>
   <line x1="${x}" y1="${yTee}" x2="${x-34}" y2="${yTee}" stroke="#999" stroke-width="3"/><line x1="${x-34}" y1="${yTee}" x2="${x-34}" y2="${yBall}" stroke="#999" stroke-width="3"/>
   <rect x="${x-44}" y="${yBall}" width="20" height="10" fill="#fff" stroke="#1976d2" stroke-width="2"/><line x1="${x-34}" y1="${yBall}" x2="${x-34}" y2="${yBall-10}" stroke="#1976d2" stroke-width="3"/><text x="${x-58}" y="${yBall+24}" font-size="9" fill="#777">볼밸브(수동)</text>`;
  // 패널 수직관 → 튜브 → 펌프
  out+=`<line x1="${x}" y1="${yTee}" x2="${x}" y2="${yTube}" stroke="#999" stroke-width="3"/><path d="M${x},${yTube} C${x+30},${yTube+20} ${x+30},${yPump-30} ${x},${yPump-18}" fill="none" stroke="#ccc" stroke-width="3" stroke-dasharray="5 3"/>`;
  // 펌프 gamma/X + 다기능 밸브
  out+=`<rect x="${x-24}" y="${yPump-18}" width="48" height="36" rx="6" fill="${on?(blink?'#ff9800':'#ffe0b2'):'#ffe0b2'}" stroke="#e65100" stroke-width="2"/><text x="${x}" y="${yPump+4}" text-anchor="middle" font-size="10" fill="#333">${p.slice(2)}</text>
   <rect x="${x-10}" y="${yPump-30}" width="20" height="10" fill="#333"/><circle cx="${x+10}" cy="${yPump-25}" r="4" fill="#d32f2f"/>
   <text x="${x}" y="${yPump+32}" text-anchor="middle" font-size="10" fill="#555">${names[j]} · ${pm.spm||0} spm · ${pm.strokes||0} str${pm.hold?' · 보류':''}${pm.scale!=null&&pm.scale!=1?' · ×'+pm.scale:''}</text>`;
  // 스톡병 (흡입)
  out+=`<line x1="${x}" y1="${yPump+18}" x2="${x}" y2="${yBottle}" stroke="#999" stroke-width="2"/><rect x="${x-16}" y="${yBottle}" width="32" height="36" rx="5" fill="#fff" stroke="#9aa"/><rect x="${x-14}" y="${yBottle+2+32*(1-lv)}" width="28" height="${32*lv}" rx="3" fill="${COL[j]}" opacity=".6"/>
   <text x="${x}" y="${yBottle+34+14}" text-anchor="middle" font-size="9" fill="#555">${DYE[j]} ${Math.round(tanks[j])} mL</text>`;});
 const lv=Math.max(0,Math.min(1,V/5000));
 out+=`<path d="M640,28 L700,28 L700,60" fill="none" stroke="#999" stroke-width="3" marker-end="url(#arr)"/>
  <rect x="600" y="60" width="200" height="220" rx="14" fill="#fff" stroke="#888" stroke-width="2"/><rect x="604" y="${64+212*(1-lv)}" width="192" height="${212*lv}" rx="12" fill="${rt}"/>
  <line x1="700" y1="60" x2="700" y2="250" stroke="#999" stroke-width="2" stroke-dasharray="4 3"/><rect x="665" y="238" width="70" height="7" fill="#999" transform="rotate(${blink?12:-12} 700 241)"/>
  <text x="700" y="298" text-anchor="middle" font-size="12" fill="#444">반응기 ${V} mL · ${s.reactor.rpm} rpm</text><text x="700" y="316" text-anchor="middle" font-size="11" fill="#555">ΔE2000 ${s.dE==null?'—':s.dE} · 운전허가 ${s.io.run_enable?'ON':'OFF'} · I/O ${s.io.mode}</text>
  <rect x="612" y="330" width="40" height="30" fill="#eee" stroke="#aaa"/><text x="632" y="349" text-anchor="middle" font-size="9" fill="#555">카메라</text><line x1="652" y1="345" x2="700" y2="300" stroke="#aaa" stroke-dasharray="3 3"/>
  <text x="700" y="400" text-anchor="middle" font-size="10" fill="#777">파란 사각 = 수동 볼밸브 · 주황 원 = 배압 밸브 · 초록/회색 = 솔레노이드 열림/닫힘 · 주황 상자 = 펌프(돌면 깜빡임)</text>`;
 g.innerHTML=out;}
const STAGE_DESC={PLAN:'목표색을 농도 c*(C,M,Y)로 역산하고 펌프별 투입 부피·스트로크·속도를 정한다',PRIME:'I/O 노드 무장(arm), 교반기 지령, 운전 허가, 밸브 열기',DOSE:'세 펌프가 스트로크를 세며 동시에 색소를 넣는다. 끝나면 밸브를 닫는다',SETTLE:'혼합시간 × 3 만큼 기다린다 (교반 rpm 이 낮으면 길어짐)',MEASURE:'카메라 2 s 평균 → ĉ 와 ΔE2000',TRIM:'ĉ 가 목표보다 모자란 염료만 추가 투입 (과투입은 되돌릴 수 없음)',DONE:'운전 허가 OFF, SAFE. 지금 트림으로 한 사이클 더 할 수 있음'};
let pickedStage=null;
function matchGauge(s){const de=s.dE;const txt=$('gaugeTxt'),mk=$('gaugeMk');
 if(de==null||isNaN(de)){txt.textContent='—';mk.style.left='0';return}
 const pos=Math.min(100,de/10*100);mk.style.left=`calc(${pos}% - 1px)`;
 const grade=de<1?'거의 동일':de<1.5?'매칭 ✓':de<2?'근접 (전문가가 구분)':de<4?'차이 있음 (눈으로 구분)':de<6?'뚜렷한 차이':'다른 색';
 txt.textContent=`ΔE ${de.toFixed(2)} · ${grade}`;txt.style.color=de<1.5?'#2e7d32':de<4?'#b26a00':'#c62828';
 const ch=H.c_hat.length?H.c_hat[H.c_hat.length-1]:[0,0,0];const ct=s.c_target;let html='';
 ['C','M','Y'].forEach((d,j)=>{const err=ch[j]-ct[j];const pct=ct[j]>0?err/ct[j]*100:0;const w=Math.min(50,Math.abs(pct));
  html+=`<span style="color:${COL[j]};font-weight:600">${d}</span><div style="position:relative;height:8px;background:#f0f1f3;border-radius:4px"><div style="position:absolute;left:50%;top:0;width:1px;height:8px;background:#999"></div><div style="position:absolute;top:1px;height:6px;border-radius:3px;background:${COL[j]};${err<0?`right:50%;width:${w}%`:`left:50%;width:${w}%`}"></div></div><span style="color:${Math.abs(pct)<3?'#2e7d32':Math.abs(pct)<8?'#b26a00':'#c62828'}">${err>=0?'+':''}${err.toFixed(1)} mg/L (${pct>=0?'+':''}${pct.toFixed(0)} %) ${err<-0.4?'부족→트림':(err>0.4?'과잉(못 뺌)':'OK')}</span>`});
 $('dyeErr').innerHTML=html;}
function stages(s){const st=s.stage;$('stages').innerHTML=st.names.map((nm,i)=>`<div class="${i===st.index?'cur':(i<st.index?'past':'')}${s.run_until===st.keys[i]?' until':''}" onclick="pickStage('${st.keys[i]}')" title="클릭: 설명 보기 / 이 단계에서 멈춤">${st.keys[i]}<br>${nm}</div>`).join('');
 const base=(st.index>=0?`${st.keys[st.index]} · ${st.desc} · 경과 ${st.elapsed} s`:st.desc);
 $('stagedesc').innerHTML=base+(s.paused?' · <b>일시정지</b>':'')+(s.step_mode?' · 단계마다 멈춤':'')+(s.run_until?` · ${s.run_until} 에서 멈춤 예정`:'')+(pickedStage&&pickedStage!==st.key?`<br><span style="color:#2a6fdb">${pickedStage}: ${STAGE_DESC[pickedStage]}</span>`:'')}
function pickStage(k){pickedStage=k;if(S&&S.running&&S.stage.index<S.stage.keys.indexOf(k))runUntil(k)}
async function poll(){try{const s=await (await fetch('/api/state?since='+n)).json();
 if(s.n<n){H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]};n=0;const s2=await (await fetch('/api/state?since=0')).json();Object.assign(s,s2)}
 for(const k of Object.keys(H))H[k]=H[k].concat(s.hist[k]||[]);n=s.n;ct=s.c_target;S=s;
 $('hdr').textContent=`t = ${s.t} s · ${s.speed}× · ${s.params.pump_mode} 펌프 · ${s.params.mode}${s.paused?' · 일시정지':''}`;
 paused=s.paused;$('pbtn').textContent=s.paused?'계속':'일시정지';$('stepmode').checked=s.step_mode;
 $('swT').style.background=s.target_hex;$('hexT').textContent=s.target_hex;$('swC').style.background=s.camera_hex;$('hexC').textContent=s.camera_hex;
 const rt=s.true_hex?'#'+s.true_hex.map(v=>v.toString(16).padStart(2,'0')).join('').toUpperCase():'#FFFFFF';$('swR').style.background=rt;$('hexR').textContent=rt;
 const b=$('iomode');b.textContent='I/O '+s.io.mode;b.className='badge '+(s.io.mode==='RUN'?'run':'safe');
 $('ctl').textContent=(s.done?'완료 · ':'')+'제어기 '+s.ctl_state+(s.trims?` · 트림 ${s.trims}회`:'')+(s.aborted?' · 중단: '+s.aborted:'');if(s.done)b.className='badge done';
 $('de').textContent=(s.dE==null?'—':s.dE)+'  (실제 '+(H.dE_true.length?H.dE_true[H.dE_true.length-1]:'—')+')';
 $('ct').textContent=s.c_target.join(' / ');$('ch').textContent=(H.c_hat.length?H.c_hat[H.c_hat.length-1]:[]).join(' / ');$('cr').textContent=s.reactor.c_true.join(' / ');
 $('rx').textContent=`${s.reactor.V_mL} mL · ${s.reactor.rpm} rpm · 탱크 ${s.reactor.tanks.join(' / ')} mL`;
 $('valves').textContent=Object.entries(s.io.valves).filter(([k])=>k!=='XV-104').map(([k,v])=>`${k.slice(3)} ${v?'열림':'닫힘'}`).join(' · ')+(s.io.run_enable?' · 운전허가 ON':' · 운전허가 OFF');
 $('plan').innerHTML='<tr><th>펌프</th><th>mL</th><th>스트로크</th><th>mL/min</th><th>mA</th></tr>'+s.plan.map(d=>`<tr><td>${d.id}</td><td>${d.volume_mL}</td><td>${d.strokes}</td><td>${d.rate}</td><td>${d.mA}</td></tr>`).join('');
 PUMPS.forEach((p,j)=>{const pm=s.pumps_live[p]||{};const v=s.io.valves['XV-'+p.slice(2)];$('pcs'+j).textContent=`${pm.spm||0} spm · ${pm.strokes||0} str${pm.remaining!=null?' · 남은 '+pm.remaining:''}`;
  const hb=$('pch'+j);hb.textContent=pm.hold?'재개':'보류';hb.className=pm.hold?'on':'';const vb=$('pcvl'+j);vb.textContent=v?'밸브 닫기':'밸브 열기';vb.className=v?'on':'';
  if(document.activeElement!==$('pcr'+j)&&pm.scale!=null){$('pcr'+j).value=Math.round(pm.scale*100);$('pcv'+j).textContent=Math.round(pm.scale*100)}});
 if(s.calib)showCal(s.calib);
 if(document.activeElement!==$('target')&&s.requested_target&&String(s.requested_target).startsWith('#')&&$('target').value.toUpperCase()!==s.requested_target.toUpperCase()&&!$('targetNote').textContent.startsWith('⚠')){$('target').value=s.requested_target.toUpperCase();$('pick').value=s.requested_target}
 matchGauge(s);
 $('log').innerHTML=s.events.slice().reverse().map(e=>`<div><span style="color:#888">${e[0]}s</span> <b>${e[1]}</b> ${e[2]}</div>`).join('');
 stages(s);mimic(s);draw();}catch(e){console.log(e)}setTimeout(poll,500)}
poll();reach();window.addEventListener('resize',draw);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    session: SimSession = None

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/reach"):
            from urllib.parse import unquote
            tgt = unquote(self.path.split("target=")[1].split("&")[0]) if "target=" in self.path else "#5A8F7B"
            cfg = self.session.cfg
            try:
                if tgt.startswith("#"):
                    rec, resid = make_recipe(cfg, tgt, None)
                else:
                    rec, resid = make_recipe(cfg, None, [float(v) for v in tgt.split(",")])
                return self._json(dict(hex=optics.rgb8_to_hex(rec.target_rgb8), resid=round(float(resid), 2), c=[round(float(v), 1) for v in rec.c_target]))
            except Exception as e:
                return self._json(dict(error=str(e)), 400)
        if self.path.startswith("/api/state"):
            since = 0
            if "since=" in self.path:
                try:
                    since = int(self.path.split("since=")[1].split("&")[0])
                except ValueError:
                    since = 0
            return self._json(self.session.state(since))
        b = PAGE.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        s = self.session
        if self.path == "/api/start":
            speed = float(body.pop("speed", s.speed))
            with s.lock:
                s.reset(body)
            s.speed = speed; s.start(); return self._json(dict(ok=True))
        if self.path == "/api/pause":
            s.paused = not s.paused; return self._json(dict(paused=s.paused))
        if self.path == "/api/reset":                      # 준비 (0 s): 계획만 세우고 멈춰 있음
            speed = float(body.pop("speed", s.speed))
            with s.lock:
                s.reset(body)
            s.speed = speed; s.start(paused=True); return self._json(dict(ok=True))
        if self.path == "/api/step":                       # 일시정지 중 N 초 진행
            if not s.running:
                s.start(paused=True)
            s.paused = True; s.advance(float(body.get("seconds", 1.0))); return self._json(dict(t=s.t))
        if self.path == "/api/stepmode":
            s.step_mode = bool(body.get("on"))
            if not s.step_mode and s.running and s.paused:
                s.paused = False                                   # 단계 모드를 끄면 바로 이어서 진행
            return self._json(dict(step_mode=s.step_mode))
        if self.path == "/api/next":                       # 다음 단계까지 진행 (단계 모드 켬)
            s.step_mode = True
            if not s.running:
                s.start(paused=False)
            s.paused = False; return self._json(dict(ok=True))
        if self.path == "/api/run_until":                  # 특정 단계에 도달하면 멈춤
            s.run_until = body.get("stage")
            if not s.running:
                s.start(paused=False)
            s.paused = False; return self._json(dict(run_until=s.run_until))
        if self.path == "/api/speed":
            s.speed = float(np.clip(float(body.get("speed", 10)), 0.1, 200)); return self._json(dict(speed=s.speed))
        if self.path == "/api/fault":
            s.inject(body["kind"], str(body.get("arg", ""))); return self._json(dict(ok=True))
        if self.path == "/api/manual":
            s.manual(body); return self._json(dict(ok=True))
        if self.path == "/api/calib":                      # 실제 카메라 보정 불러오기 / 되돌리기
            try:
                if body.get("reset"):
                    return self._json(s.load_calibration(None))
                if "data" in body:
                    return self._json(s.load_calibration(data=body["data"], name=body.get("name", "업로드")))
                return self._json(s.load_calibration(path=body["path"], name=body["path"]))
            except Exception as e:
                return self._json(dict(error=str(e)), 400)
        if self.path == "/api/live":                       # 운전 중 실시간 제어
            op = body.get("op")
            if op == "rate":
                s.manual(dict(cmd="rate_scale", id=body["id"], factor=float(body["factor"])))
            elif op == "hold":
                s.manual(dict(cmd="hold", id=body["id"], on=bool(body["on"])))
            elif op == "valve":
                s.manual(dict(cmd="valve", id=body["id"], open=bool(body["open"])))
            elif op == "stop_pump":
                s.manual(dict(cmd="stop", id=body["id"]))
            elif op == "rpm":
                s.set_rpm(float(body["rpm"]))
            elif op == "target":
                s.change_target(str(body["target"]))
            elif op == "trim_now":
                s.trim_now()
            elif op == "safe":
                s.manual(dict(cmd="safe"))
            else:
                return self._json(dict(error="unknown op"), 400)
            return self._json(dict(ok=True))
        return self._json(dict(error="unknown"), 404)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ui", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--port", type=int, default=8050)
    ap.add_argument("--autostart", action="store_true", help="서버 시작과 함께 기본 실험 실행")
    a = ap.parse_args(argv)
    Handler.session = SimSession()
    if a.autostart:
        Handler.session.start()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"CMY 시뮬레이터 UI: http://{a.host}:{a.port}   (Ctrl+C 로 종료)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        Handler.session.running = False
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
