"""실험 실행기: 한 번 실행(run), 유량 스윕(sweep), 고장 주입, 그래프, 데이터셋 기록."""
from __future__ import annotations
import csv, json, pathlib
from dataclasses import replace
import numpy as np
from .config import SystemConfig, PUMP_IDS, VALVE_IDS, DYES, PULSE_PUMP_IDS
from .nodes import Bus, SimPlant, SimHAL, IONode, AINode
from .control import Recipe, Controller, target_from_hex, target_from_cmy, plan_doses
from .vision import DatasetRecorder
from . import optics


# ------------------------------------------------------------------ 고장 주입
def parse_fault(spec: str):
    """'tank_empty:P-102@30' → (30.0, 'tank_empty', 'P-102'). '@' 없으면 t=0."""
    t = 0.0
    if "@" in spec:
        spec, ts = spec.split("@")
        t = float(ts)
    kind, _, arg = spec.partition(":")
    return t, kind, arg


def apply_fault(kind: str, arg: str, plant: SimPlant, ai: AINode, io: IONode):
    if kind == "tank_empty":                      # 스톡 탱크가 거의 비어 수위 스위치 직전
        j = PUMP_IDS.index(arg) if arg in PUMP_IDS else 3 + list(PULSE_PUMP_IDS).index(arg)
        plant.tanks[j].volume_mL = plant.tanks[j].spec.low_level_mL + 3.0
    elif kind == "valve_stuck":                   # 솔레노이드 코일은 켜지는데 밸브가 안 열림
        plant.valves[arg].stuck_closed = True
    elif kind == "signal_loss":                   # 4–20 mA 케이블 단선 → 펌프가 0 mA 를 봄
        plant.channels[arg].xtr.spec = replace(plant.channels[arg].xtr.spec, i_max_mA=0.0)
    elif kind == "ai_crash":                      # AI 노드 프로세스 사망 → 하트비트 중단
        ai.alive = False
    elif kind == "camera_drift":                  # 노출/조명 변화 (자동노출 꺼놓지 않았을 때)
        plant.camera.exposure = float(arg)
    elif kind == "rpm":
        plant.stirrer_mA = 4.0 + 16.0 * float(arg) / plant.cfg.reactor.rpm_max
        io.stirrer_mA = plant.stirrer_mA
    elif kind == "stock_conc":                    # 'P-101=900' 스톡 농도가 라벨과 다름 (칭량 오차)
        pid, v = arg.split("=")
        plant.tanks[PUMP_IDS.index(pid)].conc_mg_L = float(v)
    elif kind == "ph_drift":                      # pH 프로브 오프셋 드리프트 (+0.3 등)
        plant.reactor.ph_probe.offset += float(arg or 0.3)
    elif kind == "acid_load":                     # 산 부하 [mol/min] 시작 (금속염 피드가 OH− 소모)
        plant.reactor.acid_load_mol_min = float(arg or 0.0002)
    elif kind == "pump_air":                      # 튜브 공기 유입: 스트로크는 세지만 토출이 절반
        pid = arg or "P-101"
        plant.pumps[pid].spec = replace(plant.pumps[pid].spec, stroke_mL=plant.pumps[pid].spec.stroke_mL * 0.5)
    elif kind == "temp_step":                     # 칠러 이상: 반응기 온도 급변
        plant.reactor.temp_C += float(arg or 5.0)
    else:
        raise ValueError(f"unknown fault {kind}")


# ------------------------------------------------------------------ 한 번 실행
def run_once(cfg: SystemConfig, recipe: Recipe, duration_s: float = 600.0, faults=(), dataset_dir=None,
             E_cal_err: float = 0.0, run_id="run", verbose=False, controller=None) -> dict:
    plant = SimPlant(cfg)
    bus = Bus()
    io = IONode(cfg, SimHAL(plant), bus)
    E_cal = cfg.camera.E * (1 + E_cal_err)       # AI 노드가 가진 보정 행렬이 실제와 다를 때
    ctl = controller if controller is not None else Controller(cfg, recipe, E_cal=E_cal)
    if hasattr(ctl, "fault_hook"):               # 레시피 실행기의 inject_fault 스텝 → 공정 모델에 주입
        def _hook(kind, arg, _plant=plant, _io=io):
            apply_fault(kind, arg, _plant, ai, _io); _io.alarms.append((_io.t, f"FAULT_INJECTED {kind} {arg}"))
        ctl.fault_hook = _hook
    ai = AINode(cfg, bus, plant.camera, ctl)
    rec = DatasetRecorder(dataset_dir, plant.camera, de_match=recipe.de_match) if dataset_dir else None
    fault_list = sorted(parse_fault(f) for f in faults)

    hist = {k: [] for k in ("t", "c_true", "c_obs", "c_hat", "rgb", "dE", "dE_true", "cmd_mA", "fb_spm",
                            "tank_mL", "V_mL", "state", "mode", "pressure", "ph", "temp", "rpm", "flow", "mass", "ph_true", "naoh_mL", "acid_mL", "turb", "S")}
    t, n = 0.0, int(round(duration_s / cfg.dt))
    t_done = None
    for k in range(n + 1):
        t = k * cfg.dt
        while fault_list and fault_list[0][0] <= t:
            _, kind, arg = fault_list.pop(0)
            apply_fault(kind, arg, plant, ai, io)
            io.alarms.append((t, f"FAULT_INJECTED {kind} {arg}"))
        io.tick(t)
        ai.tick(t, plant.reactor.c_obs)
        plant.step(cfg.dt)

        cam = cfg.camera
        rgb_ideal = optics.conc_to_rgb8(cam.E, cam.I0, plant.reactor.c_true, cam.gamma, cam.glare)
        de_true = optics.delta_e2000(rgb_ideal, recipe.target_rgb8)
        if k % 5 == 0:                               # 0.5 s 간격 기록
            hist["t"].append(t)
            hist["c_true"].append(plant.reactor.c_true.copy())
            hist["c_obs"].append(plant.reactor.c_obs.copy())
            hist["c_hat"].append(ctl.c_hat.copy())
            hist["rgb"].append(ctl.rgb.copy())
            hist["dE"].append(ctl.de)
            hist["dE_true"].append(de_true)
            hist["cmd_mA"].append([io.cmd_mA[p] for p in PUMP_IDS])
            hist["fb_spm"].append([plant.pumps[p].s.spm_actual for p in PUMP_IDS])
            hist["tank_mL"].append([tk.volume_mL for tk in plant.tanks])
            hist["V_mL"].append(plant.reactor.V_mL)
            hist["state"].append(ctl.state)
            hist["mode"].append(io.mode)
            hist["pressure"].append(max(pp.s.pressure_bar for pp in plant.pumps.values()))
            hist["ph"].append(io.hal.read_ph()); hist["temp"].append(io.hal.read_temp_C()); hist["rpm"].append(plant.reactor.rpm)
            hist["ph_true"].append(plant.reactor.ph_true); hist["naoh_mL"].append(plant.reactor.naoh_mL); hist["acid_mL"].append(plant.reactor.acid_mL)
            hist["turb"].append(plant.reactor.turbidity_ntu); hist["S"].append(plant.reactor.precip.S)
            hist["flow"].append([io.flow_state[p]["flow_mL_min"] if io.flow_state[p]["valid"] else float("nan") for p in PUMP_IDS])
            hist["mass"].append([io.flow_state[p]["mass_g"] if io.flow_state[p]["mass_g"] is not None else float("nan") for p in PUMP_IDS])
        if rec:
            rec.maybe_record(t, plant.reactor.c_true, ctl.c_hat, plant.reactor.c_obs, ctl.rgb,
                             recipe.target_rgb8, ctl.de, run_id)
        if ctl.done and t_done is None:
            t_done = t
        if t_done is not None and t - t_done > 3.0:
            break
    if rec:
        rec.close()

    for key in ("c_true", "c_obs", "c_hat", "rgb", "cmd_mA", "fb_spm", "tank_mL", "flow", "mass"):
        hist[key] = np.array(hist[key], float)
    for key in ("t", "dE", "dE_true", "V_mL", "pressure", "ph", "temp", "rpm", "ph_true", "naoh_mL", "acid_mL", "turb", "S"):
        hist[key] = np.array(hist[key], float)

    cam = cfg.camera
    rgb_final_ideal = optics.conc_to_rgb8(cam.E, cam.I0, plant.reactor.c_true, cam.gamma, cam.glare)
    de_arr = hist["dE_true"]
    idx = np.where(de_arr < recipe.de_match)[0]
    t_match = float(hist["t"][idx[0]]) if len(idx) else None
    res = dict(
        run_id=run_id, mode=recipe.mode, flow_factor=list(map(float, recipe.flow_factor)),
        target_hex=optics.rgb8_to_hex(recipe.target_rgb8), final_hex=optics.rgb8_to_hex(rgb_final_ideal),
        camera_hex=optics.rgb8_to_hex(ctl.rgb),
        c_target=[round(float(v), 3) for v in recipe.c_target],
        c_true=[round(float(v), 3) for v in plant.reactor.c_true],
        c_hat=[round(float(v), 3) for v in ctl.c_hat],
        dE2000_true=round(float(de_true), 3), dE2000_camera=round(float(ctl.de), 3),
        dE76_true=round(optics.delta_e76(rgb_final_ideal, recipe.target_rgb8), 3),
        matched=bool(de_true < recipe.de_match), t_first_match_s=t_match,
        t_done_s=t_done, trims=ctl.trims, aborted=ctl.aborted,
        measurements=getattr(ctl, "measurements", None), recipe_log=getattr(ctl, "log", None),
        dosed_mL={p: round((plant.pulse_pumps[p].volume_total_mL if p in plant.pulse_pumps else plant.pumps[p].s.volume_total_mL), 2) for p in PUMP_IDS},
        pulse_dosed_mL={p: round(pp.volume_total_mL, 2) for p, pp in plant.pulse_pumps.items()},
        strokes_pulse={p: pp.strokes_total for p, pp in plant.pulse_pumps.items()},
        pump_mode=cfg.pump_mode,
        acid_mL=round(plant.reactor.acid_mL, 2), naoh_mL=round(plant.reactor.naoh_mL, 2),
        turbidity_ntu=round(plant.reactor.turbidity_ntu, 1), solid_g=round(plant.reactor.precip.solid_mol * 100.09, 3),
        feed_mL=dict(plant.reactor.feed_mL), d50_um=round(plant.reactor.precip.d50_um, 1),
        strokes={p: (plant.pulse_pumps[p].strokes_total if p in plant.pulse_pumps else plant.pumps[p].s.strokes_total) for p in PUMP_IDS},
        reactor_mL=round(plant.reactor.V_mL, 1), tank_mL=[round(tk.volume_mL, 1) for tk in plant.tanks],
        io_mode=io.mode, alarms=[(round(a[0], 1), a[1]) for a in io.alarms],
        events=ctl.events, plan=ctl.plan if (recipe.mode == "open" or controller is not None) else plan_doses(
            cfg, cfg.reactor.heel_mL, recipe.c_target, recipe.dose_minutes, recipe.flow_factor),
        overflow=plant.reactor.overflow, hist=hist,
    )
    if verbose:
        print_result(res)
    return res


def make_recipe(cfg: SystemConfig, target_hex=None, target_cmy=None, **kw) -> tuple[Recipe, float]:
    if target_cmy is not None:
        rgb, c = target_from_cmy(cfg, target_cmy)
        resid = 0.0
    else:
        rgb, c, resid = target_from_hex(cfg, target_hex or "#5A8F7B")
    return Recipe(target_rgb8=rgb, c_target=c, **kw), resid


# ------------------------------------------------------------------ 출력
def print_result(res: dict):
    print(f"\n=== {res['run_id']}  mode={res['mode']}  flow_factor={res['flow_factor']}")
    print(f"목표색 {res['target_hex']}  최종(이상 카메라) {res['final_hex']}  카메라 관측 {res['camera_hex']}")
    print(f"c_target(mg/L) C/M/Y = {res['c_target']}\nc_true            = {res['c_true']}\nc_hat(카메라 추정)= {res['c_hat']}")
    print(f"ΔE2000 진짜 {res['dE2000_true']}  카메라 {res['dE2000_camera']}  ΔE76 {res['dE76_true']}  "
          f"매칭={'예' if res['matched'] else '아니오'}  첫 매칭 t={res['t_first_match_s']} s  종료 t={res['t_done_s']} s  트림 {res['trims']}회")
    print("투입량 mL:", res["dosed_mL"], " 스트로크:", res["strokes"], f" 반응기 {res['reactor_mL']} mL  탱크 잔량 {res['tank_mL']} mL")
    print("계획:", [f"{d['id']} {d['volume_mL']:.1f} mL @ {d['rate_mL_min']:.2f} mL/min ({d['mA']:.2f} mA, {d['strokes']:.0f} str)" for d in res["plan"]])
    if res["alarms"]:
        print("알람/이벤트(I/O):", res["alarms"][:12])
    print("제어기 이벤트:", res["events"][:12])


def save_timeseries_csv(res: dict, path):
    h = res["hist"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "state", "io_mode", "cC_true", "cM_true", "cY_true", "cC_hat", "cM_hat", "cY_hat",
                    "R", "G", "B", "dE2000_cam", "dE2000_true", "mA_101", "mA_102", "mA_103",
                    "spm_101", "spm_102", "spm_103", "tankC_mL", "tankM_mL", "tankY_mL", "tankA_mL", "reactor_mL", "p_bar",
                    "ph", "temp_C", "rpm", "flow_101", "flow_102", "flow_103", "mass_101", "mass_102", "mass_103", "ph_true", "naoh_mL", "acid_mL", "turb_ntu", "S"])
        for i in range(len(h["t"])):
            w.writerow([h["t"][i], h["state"][i], h["mode"][i], *np.round(h["c_true"][i], 3), *np.round(h["c_hat"][i], 3),
                        *np.round(h["rgb"][i], 1), round(h["dE"][i], 3), round(h["dE_true"][i], 3),
                        *np.round(h["cmd_mA"][i], 2), *np.round(h["fb_spm"][i], 1), *np.round(h["tank_mL"][i], 1),
                        round(h["V_mL"][i], 1), round(h["pressure"][i], 2),
                        round(h["ph"][i], 3), round(h["temp"][i], 2), round(h["rpm"][i], 1),
                        *np.round(h["flow"][i], 3), *np.round(h["mass"][i], 2), round(h["ph_true"][i], 3), round(h["naoh_mL"][i], 2), round(h["acid_mL"][i], 2), round(h["turb"][i], 1), round(h["S"][i], 2)])


def plot_result(res: dict, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    h = res["hist"]
    t = h["t"]
    fig, ax = plt.subplots(4, 1, figsize=(10, 11), sharex=True)
    cols = ("#00AEEF", "#EC008C", "#FFD400")
    for j, d in enumerate(DYES):
        ax[0].plot(t, h["c_true"][:, j], color=cols[j], label=f"{d} true")
        ax[0].plot(t, h["c_hat"][:, j], color=cols[j], ls="--", label=f"{d} camera est.")
        ax[0].axhline(res["c_target"][j], color=cols[j], ls=":", lw=1)
    ax[0].set_ylabel("conc [mg/L]"); ax[0].legend(ncol=3, fontsize=8); ax[0].set_title(
        f"{res['run_id']}: target {res['target_hex']} → final {res['final_hex']}  ΔE2000={res['dE2000_true']}")
    ax[1].plot(t, h["dE_true"], "k", label="ΔE2000 (true)")
    ax[1].plot(t, h["dE"], "gray", ls="--", label="ΔE2000 (camera)")
    ax[1].axhline(1.5, color="g", ls=":", label="match threshold"); ax[1].set_ylim(0, min(60, np.nanmax(h["dE_true"]) * 1.1 + 1))
    ax[1].set_ylabel("ΔE2000"); ax[1].legend(fontsize=8)
    for j, p in enumerate(PUMP_IDS):
        ax[2].plot(t, h["cmd_mA"][:, j], color=cols[j], label=f"{p} cmd mA")
        ax[2].plot(t, 4 + 16 * h["fb_spm"][:, j] / 200, color=cols[j], ls="--", lw=0.8)
    ax[2].set_ylabel("pump mA (cmd — / fb --)"); ax[2].legend(fontsize=8, ncol=3)
    for j, d in enumerate(DYES):
        ax[3].plot(t, h["tank_mL"][:, j], color=cols[j], label=f"tank {d}")
    ax3b = ax[3].twinx(); ax3b.plot(t, h["V_mL"], "k", lw=1, label="reactor mL"); ax3b.set_ylabel("reactor [mL]")
    ax[3].set_ylabel("stock tank [mL]"); ax[3].set_xlabel("t [s]"); ax[3].legend(fontsize=8, loc="lower left")
    # 색 견본
    for i, (lab, hx) in enumerate((("target", res["target_hex"]), ("final", res["final_hex"]), ("camera", res["camera_hex"]))):
        fig.patches.append(plt.Rectangle((0.80 + 0.065 * i, 0.93), 0.05, 0.04, transform=fig.transFigure, color=hx))
        fig.text(0.805 + 0.065 * i, 0.915, lab, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ------------------------------------------------------------------ 유량 스윕
def sweep(cfg: SystemConfig, base: Recipe, factors, which=("C", "M", "Y"), duration_s=400.0, csv_path=None,
          mode="open") -> list[dict]:
    """펌프별 유량(=투입량) 배율을 바꿔 가며 최종 ΔE 를 본다. 같은 시간에 더/덜 흘리면 색이 어떻게 비껴가는가."""
    rows = []
    for name in which:
        j = DYES.index(name)
        for f in factors:
            ff = np.ones(3); ff[j] = f
            r = replace(base, flow_factor=ff, mode=mode)
            res = run_once(cfg, r, duration_s, run_id=f"sweep_{name}x{f:g}")
            rows.append(dict(dye=name, factor=f, dE2000=res["dE2000_true"], matched=res["matched"],
                             final_hex=res["final_hex"], c_true=res["c_true"],
                             dosed_mL=[res["dosed_mL"][p] for p in PUMP_IDS], t_first_match_s=res["t_first_match_s"]))
    if csv_path:
        with open(csv_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    return rows


def print_sweep(rows):
    print(f"\n{'dye':>4} {'factor':>7} {'ΔE2000':>8} {'match':>6} {'final':>9}   c_true (C, M, Y) mg/L        dosed mL")
    for r in rows:
        print(f"{r['dye']:>4} {r['factor']:>7g} {r['dE2000']:>8.2f} {'O' if r['matched'] else 'X':>6} {r['final_hex']:>9}   "
              f"{r['c_true']}   {r['dosed_mL']}")


def dump_json(res: dict, path):
    d = {k: v for k, v in res.items() if k != "hist"}
    pathlib.Path(path).write_text(json.dumps(d, ensure_ascii=False, indent=1, default=float))
