"""CLI.

  python -m cmysim plan   --target "#5A8F7B"
  python -m cmysim run    --target "#5A8F7B" --mode closed --plot run.png --csv run.csv --dataset ds/
  python -m cmysim run    --cmy 20,12,8 --mode open --fault tank_empty:P-102@40 --fault ai_crash@200
  python -m cmysim sweep  --target "#5A8F7B" --factors 0.7,0.85,1,1.15,1.3 --csv sweep.csv
  python -m cmysim calib
"""
from __future__ import annotations
import argparse, sys
import numpy as np
from .config import SystemConfig, PUMP_IDS
from .control import plan_doses
from .experiment import run_once, make_recipe, print_result, plot_result, save_timeseries_csv, sweep, print_sweep, dump_json
from . import optics


def build_cfg(a) -> SystemConfig:
    cfg = SystemConfig(seed=a.seed, dt=a.dt)
    cfg.reactor.heel_mL = a.heel
    cfg.reactor.rpm = a.rpm
    if a.stroke_length:
        cfg.pump.stroke_length = a.stroke_length
    return cfg


def common(p):
    p.add_argument("--target", help="목표색 hex, 예 '#5A8F7B'")
    p.add_argument("--cmy", help="목표 농도 mg/L 'C,M,Y' (hex 대신)")
    p.add_argument("--heel", type=float, default=2000.0, help="반응기 초기 물 [mL]")
    p.add_argument("--rpm", type=float, default=300.0)
    p.add_argument("--dose-min", type=float, default=2.0, help="피드포워드 도징 시간 [min]")
    p.add_argument("--stroke-length", type=float, default=None, help="펌프 스트로크 길이 0.3~1.0")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--dt", type=float, default=0.1)
    p.add_argument("--de-match", type=float, default=1.5)


def recipe_from_args(cfg, a, **kw):
    cmy = [float(x) for x in a.cmy.split(",")] if a.cmy else None
    return make_recipe(cfg, a.target, cmy, dose_minutes=a.dose_min, de_match=a.de_match, **kw)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cmysim", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("plan", help="투입량/유량 계획만 출력"); common(p)
    p = sp.add_parser("run", help="한 번 실행"); common(p)
    p.add_argument("--mode", choices=("open", "closed"), default="closed")
    p.add_argument("--duration", type=float, default=600.0)
    p.add_argument("--fault", action="append", default=[], help="예: tank_empty:P-102@40, valve_stuck:XV-101, signal_loss:P-103@30, ai_crash@120, camera_drift:0.9@60, rpm:80, stock_conc:P-101=900")
    p.add_argument("--e-cal-err", type=float, default=0.0, help="AI 노드 보정 행렬 E 의 상대 오차 (예 0.05)")
    p.add_argument("--plot"); p.add_argument("--csv"); p.add_argument("--json"); p.add_argument("--dataset")
    p = sp.add_parser("sweep", help="펌프별 유량 배율 스윕"); common(p)
    p.add_argument("--factors", default="0.7,0.85,1.0,1.15,1.3")
    p.add_argument("--which", default="C,M,Y")
    p.add_argument("--mode", choices=("open", "closed"), default="open")
    p.add_argument("--duration", type=float, default=400.0)
    p.add_argument("--csv")
    p = sp.add_parser("calib", help="MCC 152 → XTR111 2점 교정 시연")
    p.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    if a.cmd == "calib":
        from .nodes import SimPlant
        cfg = SystemConfig(seed=a.seed)
        plant = SimPlant(cfg)
        for pid in PUMP_IDS:
            ch = plant.channels[pid]; ch.enable(True)
            before = [ch.set_mA(m) for m in (5.0, 12.0, 19.0)]
            slope = ch.calibrate_two_point(lambda: plant.adc.read_mA_via_shunt(ch.actual_mA))
            after = [ch.set_mA(m) for m in (5.0, 12.0, 19.0)]
            print(f"{pid}: 이득오차 {ch.ao.gain_err*100:+.2f} %  교정 전 5/12/19 mA → {np.round(before,3)}  교정 후 → {np.round(after,3)}  (측정 기울기 {slope:.4f})")
        return 0

    cfg = build_cfg(a)
    rec, resid = recipe_from_args(cfg, a)
    print(f"목표 RGB {optics.rgb8_to_hex(rec.target_rgb8)}  목표 농도 C/M/Y = {np.round(rec.c_target, 2)} mg/L"
          + (f"  (요청색과의 도달 가능 잔차 ΔE2000 = {resid:.2f})" if resid > 0.05 else ""))
    print(f"E 조건수 κ = {optics.condition_number(cfg.camera.E):.2f}")
    if a.cmd == "plan":
        for d in plan_doses(cfg, cfg.reactor.heel_mL, rec.c_target, rec.dose_minutes):
            print(f"  {d['id']} ({d['valve']}): {d['volume_mL']:.2f} mL = {d['strokes']:.1f} 스트로크, "
                  f"{d['rate_mL_min']:.2f} mL/min → {d['mA']:.2f} mA, {d['minutes']:.2f} min")
        return 0
    if a.cmd == "run":
        rec.mode = a.mode
        res = run_once(cfg, rec, a.duration, faults=a.fault, dataset_dir=a.dataset, E_cal_err=a.e_cal_err,
                       run_id=f"{a.mode}_{(a.target or a.cmy).strip('#')}", verbose=True)
        if a.plot:
            plot_result(res, a.plot); print("그래프:", a.plot)
        if a.csv:
            save_timeseries_csv(res, a.csv); print("시계열 CSV:", a.csv)
        if a.json:
            dump_json(res, a.json); print("결과 JSON:", a.json)
        if a.dataset:
            print("데이터셋:", a.dataset)
        return 0
    if a.cmd == "sweep":
        rows = sweep(cfg, rec, [float(x) for x in a.factors.split(",")], tuple(a.which.split(",")),
                     a.duration, a.csv, a.mode)
        print_sweep(rows)
        if a.csv:
            print("CSV:", a.csv)
        return 0


if __name__ == "__main__":
    sys.exit(main())
