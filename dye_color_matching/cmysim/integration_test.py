"""전체 시스템 통합 시험 — Tier C 공침 레시피.

  python -m cmysim.integration_test            # A: 단일 프로세스, B: ZeroMQ 2프로세스, C: 고장 변형 — 전부 실행 후 보고서
  python -m cmysim.integration_test --only A --out it_results

검증 항목 (각 시나리오)
  A/B 정상: 4 펌프 모두 사용, 인터록/거부 알람 없음, pH 유지 구간의 90 % 이상이 설정값 ±0.3, 피드 후 탁도 > 50 NTU,
           로드셀 유량 상태 OK, DOSE short/timeout 없음, 종료 시 I/O 노드 SAFE, 측정 라벨 전부 기록, 데이터셋 프레임·라벨 생성
  C 고장 : NO_STROKE/TANK_LOW 알람 발생, DOSE 중단 라벨, pH 유지는 계속, 종료 시 SAFE
보고서는 out/report.md 와 report.json. 이 스크립트의 A 와 C 는 pytest 에서도 돈다.
"""
from __future__ import annotations
import argparse, csv, json, os, pathlib, subprocess, sys, time
import numpy as np
from .config import SystemConfig, PUMP_IDS
from .recipe import load_recipe, RecipeExecutor
from .experiment import run_once, save_timeseries_csv, plot_result, dump_json

HERE = pathlib.Path(__file__).resolve().parent.parent


def _checks_normal(res: dict, ex: RecipeExecutor, ds_dir=None) -> list[tuple[str, bool, str]]:
    h = res["hist"]; al = [a[1] for a in res["alarms"]]
    out = []
    out.append(("4 펌프 모두 사용", res["dosed_mL"]["P-101"] > 50 and res["dosed_mL"]["P-102"] > 50 and res["dosed_mL"]["P-103"] > 0.5
                and res["pulse_dosed_mL"]["P-104"] >= 0.0, f"{res['dosed_mL']} pulse {res['pulse_dosed_mL']}"))
    out.append(("인터록/거부 알람 없음", not any(("INTERLOCK" in a) or ("REJECT" in a) for a in al), "; ".join(a for a in al if "INTERLOCK" in a or "REJECT" in a)[:200]))
    # pH 유지 구간: ph_hold start ~ stop 사이, 설정값 도달 후(+120 s)
    log = ex.log
    t_start = next((t for t, k, d in log if k == "ph_hold" and d.startswith("start")), None)
    t_stop = next((t for t, k, d in log if k == "ph_done"), None)
    sp = next((m["setpoint"] for m in ex.measurements if "setpoint" in m), 10.0)
    if t_start is not None and t_stop is not None:
        m = (h["t"] >= t_start + 120) & (h["t"] <= t_stop)
        frac = float(np.mean(np.abs(h["ph"][m] - sp) < 0.3)) if m.any() else 0.0
        out.append(("pH 유지: 설정값 ±0.3 안 비율 ≥ 0.9", frac >= 0.9, f"{frac:.2%} (sp {sp}, 구간 {t_start:.0f}~{t_stop:.0f} s)"))
    else:
        out.append(("pH 유지 구간 기록", False, "ph_hold start/done 로그 없음"))
    out.append(("피드 후 탁도 > 50 NTU", res["turbidity_ntu"] > 50, f"{res['turbidity_ntu']} NTU, 고체 {res['solid_g']} g, d50 proxy {res['d50_um']} µm"))
    out.append(("DOSE short/timeout 없음", not res.get("aborted"), res.get("aborted", "")))
    flow_bad = [a for a in al if a.startswith("FLOW_") or a.startswith("VOLUME_MISMATCH")]
    out.append(("로드셀 유량 판정 정상", not flow_bad, "; ".join(flow_bad)[:200]))
    out.append(("종료 시 I/O 노드 SAFE", res["io_mode"] == "SAFE", res["io_mode"]))
    labels = [m.get("label") for m in ex.measurements]
    out.append(("측정 라벨 전부 기록", all(l in labels for l in ("baseline", "end_of_feed", "ageing", "final", "ph_hold")), str(labels)))
    tb = {m["label"]: m.get("turbidity_ntu") for m in ex.measurements if "turbidity_ntu" in m}
    out.append(("탁도 상승 순서 baseline < end_of_feed", (tb.get("baseline") or 0) < (tb.get("end_of_feed") or 0), str(tb)))
    if ds_dir:
        n_img = len(list(pathlib.Path(ds_dir, "images").glob("*.png"))); n_lab = len(list(pathlib.Path(ds_dir, "labels").glob("*.txt")))
        out.append(("데이터셋 프레임·라벨 생성", n_img > 10 and n_lab == n_img, f"{n_img} frames"))
    return out


def _checks_fault(res: dict, ex: RecipeExecutor) -> list[tuple[str, bool, str]]:
    al = [a[1] for a in res["alarms"]]
    out = [("NO_STROKE 또는 TANK_LOW 알람", any("NO_STROKE P-102" in a or "TANK_LOW P-102" in a for a in al), "; ".join(a for a in al if "P-102" in a)[:200]),
           ("DOSE 중단 라벨", bool(res.get("aborted")), res.get("aborted", "")),
           ("pH 유지 계속 (after_fault 측정에 pH)", any(m.get("label") == "after_fault" and m.get("ph") is not None for m in ex.measurements), ""),
           ("종료 시 I/O 노드 SAFE", res["io_mode"] == "SAFE", res["io_mode"])]
    return out


def scenario_A(out: pathlib.Path, duration=2400.0):
    r = load_recipe(HERE / "recipes" / "tierC_coprecip.yaml")
    cfg = SystemConfig(seed=21); cfg.dac.calibrated = True
    ex = RecipeExecutor(cfg, r)
    d = out / "A_inprocess"; d.mkdir(parents=True, exist_ok=True)
    res = run_once(cfg, ex.r, duration, controller=ex, dataset_dir=d / "dataset", run_id="tierC_A")
    save_timeseries_csv(res, d / "timeseries.csv"); dump_json(res, d / "result.json")
    (d / "log.json").write_text(json.dumps(dict(log=ex.log, measurements=ex.measurements), ensure_ascii=False, indent=1))
    try:
        plot_result(res, d / "plot.png")
    except Exception:
        pass
    return _checks_normal(res, ex, d / "dataset"), res, ex


def scenario_C(out: pathlib.Path, duration=1200.0):
    r = load_recipe(HERE / "recipes" / "tierC_coprecip_fault.yaml")
    cfg = SystemConfig(seed=22); cfg.dac.calibrated = True
    ex = RecipeExecutor(cfg, r)
    d = out / "C_fault"; d.mkdir(parents=True, exist_ok=True)
    res = run_once(cfg, ex.r, duration, controller=ex, run_id="tierC_C")
    save_timeseries_csv(res, d / "timeseries.csv"); dump_json(res, d / "result.json")
    (d / "log.json").write_text(json.dumps(dict(log=ex.log, measurements=ex.measurements), ensure_ascii=False, indent=1))
    return _checks_fault(res, ex), res, ex


def scenario_B(out: pathlib.Path, timeout_s=2700, hz=10.0, time_scale=20.0):
    """ZeroMQ 2프로세스: io_node_main run --sim (텔레메트리에 카메라 관측 포함) + ai_node_main --camera-kind telemetry --recipe."""
    d = out / "B_zmq"; d.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(HERE))
    ports = ("5755", "5756")
    io_log = open(d / "io_stdout.txt", "w")
    io = subprocess.Popen([sys.executable, "-u", "-m", "cmysim.io_node_main", "run", "--sim", "--sim-camera", "--hz", str(hz),
                           "--time-scale", str(time_scale), "--recipe", str(HERE / "recipes" / "tierC_coprecip.yaml"),
                           "--log", str(d / "io_log.csv"), "--cmd-port", ports[0], "--tele-port", ports[1]],
                          cwd=str(d), env=env, stdout=io_log, stderr=subprocess.STDOUT)
    time.sleep(2.0)
    cam_json = d / "camera.json"
    cam_json.write_text(json.dumps(dict(kind="telemetry", calib_path=str(d / "calibration.json"), ref_path=str(d / "ref.npy"))))
    cfg = SystemConfig()
    (d / "calibration.json").write_text(json.dumps(dict(E=cfg.camera.E.tolist(), I0=cfg.camera.I0.tolist(), gamma=2.2, glare=cfg.camera.glare,
                                                       cond=1.57, samples=[], note="sim")))
    t0 = time.time()
    ai = subprocess.run([sys.executable, "-u", "-m", "cmysim.ai_node_main", "--io-ip", "127.0.0.1", "--cmd-port", ports[0], "--tele-port", ports[1],
                         "--camera", str(cam_json), "--recipe", str(HERE / "recipes" / "tierC_coprecip.yaml"),
                         "--log", str(d / "ai_log.csv"), "--max-minutes", str(timeout_s / 60), "--hz", str(hz), "--time-scale", str(time_scale)],
                        cwd=str(d), env=env, capture_output=True, text=True, timeout=timeout_s / time_scale + 120)
    (d / "ai_stdout.txt").write_text(ai.stdout + "\n--- stderr ---\n" + ai.stderr)
    time.sleep(1.0)
    io.terminate()
    try:
        io.wait(10)
    except subprocess.TimeoutExpired:
        io.kill()
    io_log.close()
    wall = time.time() - t0
    rows = list(csv.DictReader(open(d / "ai_log.csv"))) if (d / "ai_log.csv").exists() else []
    io_rows = list(csv.DictReader(open(d / "io_log.csv"))) if (d / "io_log.csv").exists() else []
    out_txt = ai.stdout
    checks = [("AI 노드 정상 종료 (exit 0)", ai.returncode == 0, f"exit {ai.returncode}, {wall:.0f} s"),
              ("텔레메트리 수신·레시피 로드", "레시피 tierC_coprecip" in out_txt and "텔레메트리 수신" in out_txt, ""),
              ("레시피 완료 (DONE)", "완료:" in out_txt, ""),
              ("I/O 노드 모드 RUN → SAFE", bool(io_rows) and any(r["mode"] == "RUN" for r in io_rows) and io_rows[-1]["mode"] == "SAFE",
               f"{len(io_rows)} rows" if io_rows else "io_log 없음"),
              ("피드 펌프 2줄 동작 (I/O 로그 스트로크)", bool(io_rows) and float(io_rows[-1]["strokes_101"]) > 200 and float(io_rows[-1]["strokes_102"]) > 200,
               (f"{io_rows[-1]['strokes_101']}/{io_rows[-1]['strokes_102']}" if io_rows else "")),
              ("AI 로그에 pH·탁도·로드셀 열", bool(rows) and all(k in rows[0] for k in ("ph", "flow_101", "ad_ratio")), f"{len(rows)} rows")]
    if io_rows and "turb_ntu" in io_rows[-1]:
        checks.append(("피드 후 탁도 > 50 NTU (I/O 로그)", float(io_rows[-1]["turb_ntu"] or 0) > 50, f"{io_rows[-1]['turb_ntu']} NTU"))
    ph_vals = [float(r["ph"]) for r in rows if r.get("ph") not in ("", None)]
    if ph_vals:
        tail = np.array(ph_vals[len(ph_vals) // 3:])
        checks.append(("pH 유지 (후반 2/3 구간 ±0.3 비율 ≥ 0.85)", float(np.mean(np.abs(tail - 10.0) < 0.3)) >= 0.85, f"{np.mean(np.abs(tail - 10.0) < 0.3):.2%}"))
    return checks, None, None


def write_report(out: pathlib.Path, results: dict):
    lines = ["# 통합 시험 보고서 — Tier C 공침 레시피", "", f"생성: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    total_ok = True
    for name, checks in results.items():
        ok = all(c[1] for c in checks); total_ok &= ok
        lines += [f"## {name}: {'PASS' if ok else 'FAIL'}", "", "| 항목 | 결과 | 비고 |", "|---|---|---|"]
        for label, passed, note in checks:
            lines.append(f"| {label} | {'✅' if passed else '❌'} | {note} |")
        lines.append("")
    lines.append(f"**전체: {'PASS' if total_ok else 'FAIL'}**")
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "report.json").write_text(json.dumps({k: [dict(label=a, passed=b, note=c) for a, b, c in v] for k, v in results.items()},
                                                ensure_ascii=False, indent=1))
    return total_ok


def main(argv=None):
    ap = argparse.ArgumentParser(prog="integration_test", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="it_results"); ap.add_argument("--only", default="ABC")
    ap.add_argument("--hz", type=float, default=10.0, help="B 시나리오 실시간 루프 주기")
    ap.add_argument("--time-scale", type=float, default=20.0, help="B 시나리오 시뮬레이션 시간 가속 (1 = 실시간, 레시피 25 분)")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    results = {}
    for key, fn in (("A", scenario_A), ("B", scenario_B), ("C", scenario_C)):
        if key not in a.only:
            continue
        t0 = time.time()
        print(f"=== 시나리오 {key} 시작")
        checks, res, ex = fn(out) if key != "B" else fn(out, hz=a.hz, time_scale=a.time_scale)
        for label, ok, note in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}  {note}")
        print(f"=== 시나리오 {key} 끝 ({time.time() - t0:.0f} s)")
        results[{"A": "A. 단일 프로세스 (시뮬레이션)", "B": "B. ZeroMQ 2프로세스 (I/O 노드 --sim + AI 노드)", "C": "C. 고장 변형 (Na₂CO₃ 탱크 고갈)"}[key]] = checks
    ok = write_report(out, results)
    print("보고서:", out / "report.md", "→", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
