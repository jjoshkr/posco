"""레시피 CLI.

  python -m cmysim.recipe_cli example  > my.yaml                       템플릿 출력
  python -m cmysim.recipe_cli validate my.yaml
  python -m cmysim.recipe_cli expand   my.yaml                          matrix 전개 결과 (실행 목록)
  python -m cmysim.recipe_cli run      my.yaml --sim --out results/     시뮬레이션 실행 (matrix 면 전부) + 요약 CSV/JSON/그래프
  실제 장치:  python -m cmysim.ai_node_main --recipe my.yaml ...
"""
from __future__ import annotations
import argparse, csv, json, pathlib, sys
import numpy as np
from .config import SystemConfig
from .recipe import load_recipe, validate, expand_matrix, EXAMPLE, RecipeExecutor


def main(argv=None):
    ap = argparse.ArgumentParser(prog="recipe_cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("example")
    p = sp.add_parser("validate"); p.add_argument("recipe")
    p = sp.add_parser("expand"); p.add_argument("recipe")
    p = sp.add_parser("run"); p.add_argument("recipe"); p.add_argument("--sim", action="store_true", default=True)
    p.add_argument("--out", default="recipe_results"); p.add_argument("--duration", type=float, default=900.0)
    p.add_argument("--seed", type=int, default=0); p.add_argument("--plot", action="store_true"); p.add_argument("--dataset", action="store_true")
    p.add_argument("--e-cal-err", type=float, default=0.0)
    a = ap.parse_args(argv)

    if a.cmd == "example":
        print(EXAMPLE, end=""); return 0
    r = load_recipe(a.recipe)
    errs = validate(r)
    if a.cmd == "validate":
        print("OK:", r.get("name"), f"스텝 {len(r.get('steps', []))}개" if not errs else "\n".join("오류: " + e for e in errs))
        return 1 if errs else 0
    if errs:
        print("\n".join("오류: " + e for e in errs)); return 1
    runs = expand_matrix(r)
    if a.cmd == "expand":
        for rr in runs:
            print(rr["name"], rr.get("matrix_point", {}))
        return 0

    from .experiment import run_once, print_result, plot_result, save_timeseries_csv, dump_json
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows = []
    for k, rr in enumerate(runs):
        cfg = SystemConfig(seed=a.seed + k)
        ex = RecipeExecutor(cfg, rr, E_cal=None if a.e_cal_err == 0 else None, sim=True)
        if a.e_cal_err:
            ex.E = cfg.camera.E * (1 + a.e_cal_err)
        res = run_once(cfg, ex.r, a.duration, controller=ex, run_id=rr["name"], verbose=True,
                       dataset_dir=(out / rr["name"] / "dataset") if a.dataset else None)
        (out / rr["name"]).mkdir(exist_ok=True)
        dump_json(res, out / rr["name"] / "result.json")
        save_timeseries_csv(res, out / rr["name"] / "timeseries.csv")
        (out / rr["name"] / "log.json").write_text(json.dumps(dict(log=ex.log, measurements=ex.measurements), ensure_ascii=False, indent=1))
        if a.plot:
            plot_result(res, out / rr["name"] / "plot.png")
        rows.append(dict(name=rr["name"], **{k2: v for k2, v in rr.get("matrix_point", {}).items()},
                         dE2000_true=res["dE2000_true"], matched=res["matched"], t_done_s=res["t_done_s"], trims=res["trims"],
                         aborted=res.get("aborted", ""), measurements=len(ex.measurements),
                         **{f"dosed_{p[-3:]}": v for p, v in res["dosed_mL"].items()}))
    keys = sorted({k for r_ in rows for k in r_.keys()}, key=lambda k: (k != "name", k))
    with open(out / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    print("\n=== 요약 (", out / "summary.csv", ")")
    for r_ in rows:
        print(" ", {k: r_.get(k) for k in keys if k not in ("measurements",)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
