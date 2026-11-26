"""염료 색역(gamut) 분석 — PDF 'R, G, B를 각각 하나만 흡수하는 염료 조합과 색역', '목표색 #53F3B6이 추출 안 되는 이유' 의 체크리스트.

  python -m cmysim.gamut check  --target "#53F3B6" [--calib calibration.json] [--ideal]
  python -m cmysim.gamut matrix [--calib calibration.json]            E, κ(E), 교차 흡수 비율 출력
  python -m cmysim.gamut map    [--calib ...] [--target ...] --out gamut.png   a*b* 평면 색역 지도 (matplotlib)
  python -m cmysim.gamut compare a.json b.json ...                     염료 후보 세트 비교 (κ, 교차 흡수, 색역 부피)
  python -m cmysim.gamut hull   [--calib ...] --out hull.json          도달 가능 색 구름 (UI/보고서용)

용어
  A = E c        A: 채널별 흡광도 (R,G,B), E: 3×3 감쇠 행렬 [흡광도/(mg/L)], c: 농도 (C,M,Y) ≥ 0
  색역 안        c = E⁻¹A 의 세 성분이 모두 ≥ 0 이고, 보정한 농도 범위 안
  색역 밖        어느 성분이 음수 → 비음수 최소제곱(NNLS)으로 가장 가까운 c 를 쓰고 잔차 ΔE2000 을 보고한다
  이상적 CMY     E 가 대각행렬(교차 흡수 0). 이때는 흰색보다 어두운 모든 색이 색역 안
"""
from __future__ import annotations
import argparse
import json
import pathlib
import numpy as np
from . import optics
from .config import SystemConfig, rig_prominent_feeder

DYES = ("C", "M", "Y")
CHANNELS = ("R", "G", "B")


# ------------------------------------------------------------------ 행렬 분석
def analyze_matrix(E) -> dict:
    """E 의 품질: 조건수, 대각 우세, 교차 흡수 비율(열 기준: 그 염료가 주 채널 외 채널을 얼마나 먹나)."""
    E = np.asarray(E, float)
    diag = np.diag(E)
    cross = {}
    for j, dye in enumerate(DYES):
        col = E[:, j]
        main = col[j]
        cross[dye] = {CHANNELS[i]: (round(float(col[i] / main), 4) if main > 0 else None) for i in range(3) if i != j}
    worst = max((v for d in cross.values() for v in d.values() if v is not None), default=0.0)
    return dict(E=np.round(E, 6).tolist(), cond=round(float(np.linalg.cond(E)), 3), diag=np.round(diag, 6).tolist(),
                cross=cross, worst_cross=round(float(worst), 4),
                diag_dominant=bool(all(abs(E[i, i]) > sum(abs(E[i, k]) for k in range(3) if k != i) for i in range(3))),
                grade=("좋음" if np.linalg.cond(E) < 2 and worst < 0.15 else "보통" if np.linalg.cond(E) < 3 and worst < 0.3 else "나쁨"))


def ideal_matrix(E) -> np.ndarray:
    """같은 주 흡수 계수를 가진 '이상적 CMY' (교차 흡수 0) — PDF 1 의 대각 E."""
    return np.diag(np.diag(np.asarray(E, float)))


# ------------------------------------------------------------------ 보정 농도 범위
def calibrated_range(cal) -> dict:
    """calibration.json 의 samples 에서 염료별 보정 농도 상한. 없으면 None."""
    rng = {d: None for d in DYES}
    for s in (getattr(cal, "samples", None) or []):
        d = s.get("dye")
        if d in rng and "conc" in s:
            rng[d] = max(rng[d] or 0.0, float(s["conc"]))
    return rng


# ------------------------------------------------------------------ 목표색 검사 (PDF 2 체크리스트 2·3)
def check_target(cfg: SystemConfig, target_hex: str, cal=None) -> dict:
    cam = cfg.camera
    E, I0 = np.asarray(cam.E, float), np.asarray(cam.I0, float)
    rgb = optics.hex_to_rgb8(target_hex)
    I = np.clip(optics.code_to_linear(rgb, cam.gamma) - cam.glare, 1e-6, None)
    A = -np.log10(np.clip(I / I0, 1e-6, None))
    brighter = [CHANNELS[i] for i in range(3) if A[i] < -0.005]          # 물보다 밝은 채널 (8비트 반올림 여유 ≈ 1 코드값)
    A_pos = np.clip(A, 0, None)
    c_raw = np.linalg.solve(E, A_pos) if np.linalg.cond(E) < 1e8 else np.full(3, np.nan)
    negative = [DYES[j] for j in range(3) if c_raw[j] < -0.05]          # 측정 잡음 수준(0.05 mg/L)은 음수로 치지 않음
    c_nnls = optics.nnls3(E, A_pos)
    reach = optics.conc_to_rgb8(E, I0, c_nnls, cam.gamma, cam.glare)
    de = optics.delta_e2000(rgb, reach)
    in_gamut = (not brighter) and (not negative)
    rng = calibrated_range(cal) if cal is not None else {d: None for d in DYES}
    over = [d for j, d in enumerate(DYES) if rng[d] is not None and c_nnls[j] > rng[d] * 1.0001]
    stock = [tk.conc_mg_L for tk in cfg.tanks[:3]]
    over_stock = [d for j, d in enumerate(DYES) if c_nnls[j] >= stock[j]]
    # 왜 못 만드나 — 한 줄 설명
    if brighter:
        why = f"물(흰색)보다 밝은 채널 {','.join(brighter)}: 염료는 빛을 빼기만 하므로 불가"
    elif negative:
        why = (f"{','.join(negative)} 농도가 음수여야 함: 다른 염료의 교차 흡수가 이미 그 채널을 "
               f"{', '.join(f'{CHANNELS[j]} {A_pos[j]:.3f}' for j in range(3) if DYES[j] in negative)} 보다 더 먹음 → 색역 밖")
    elif over_stock:
        why = f"{','.join(over_stock)} 필요 농도가 스톡 농도 이상: 스톡을 더 진하게 해야 함"
    elif over:
        why = f"{','.join(over)} 필요 농도가 보정 범위 밖: Beer–Lambert 선형성 보장 못함 (보정 농도를 넓히거나 목표를 연하게)"
    else:
        why = "색역 안"
    return dict(target=optics.rgb8_to_hex(rgb), A=np.round(A, 4).tolist(), brighter_than_water=brighter,
                c_raw=np.round(c_raw, 2).tolist(), negative=negative, in_gamut=bool(in_gamut),
                c=np.round(c_nnls, 2).tolist(), nearest=optics.rgb8_to_hex(reach), resid_dE=round(float(de), 2),
                calibrated_max=rng, over_calibrated=over, over_stock=over_stock, stock=stock, why=why,
                cond=round(float(np.linalg.cond(E)), 3))


# ------------------------------------------------------------------ 색역 구름 (도달 가능 색의 집합)
def gamut_cloud(cfg: SystemConfig, n: int = 12, c_max=None) -> dict:
    """농도 격자 (0..c_max)³ 를 RGB 로 보내 Lab 점 구름을 만든다. c_max: 염료별 상한 (기본 스톡의 1/3 또는 흡광도 1.2)."""
    cam = cfg.camera
    E, I0 = np.asarray(cam.E, float), np.asarray(cam.I0, float)
    if c_max is None:
        c_max = [min(tk.conc_mg_L / 3.0, 1.2 / max(E[j, j], 1e-9)) for j, tk in enumerate(cfg.tanks[:3])]
    grid = [np.linspace(0, cm, n) for cm in c_max]
    pts = []
    for cc in grid[0]:
        for cm in grid[1]:
            for cy in grid[2]:
                c = np.array([cc, cm, cy])
                rgb = optics.conc_to_rgb8(E, I0, c, cam.gamma, cam.glare)
                lab = optics.srgb8_to_lab(rgb)
                pts.append(dict(c=np.round(c, 2).tolist(), hex=optics.rgb8_to_hex(rgb), lab=np.round(lab, 2).tolist()))
    labs = np.array([p["lab"] for p in pts])
    return dict(n=n, c_max=np.round(c_max, 2).tolist(), points=pts,
                L_range=[round(float(labs[:, 0].min()), 1), round(float(labs[:, 0].max()), 1)],
                ab_area=round(float(_hull_area(labs[:, 1], labs[:, 2])), 1))


def _hull_area(x, y) -> float:
    """2D 볼록껍질 면적 (Andrew monotone chain) — a*b* 평면에서 색역의 '넓이'."""
    P = sorted(set(zip(x.tolist(), y.tolist())))
    if len(P) < 3:
        return 0.0
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in P:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0: lower.pop()
        lower.append(p)
    for p in reversed(P):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0: upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return 0.5 * abs(sum(hull[i][0] * hull[(i + 1) % len(hull)][1] - hull[(i + 1) % len(hull)][0] * hull[i][1] for i in range(len(hull))))


# ------------------------------------------------------------------ 염료 후보 세트 비교 (PDF 1 §4)
def compare_sets(items: list[tuple[str, SystemConfig]], probes=("#53F3B6", "#59FF00", "#5A8F7B", "#8040A0", "#E0A000", "#404040")) -> list[dict]:
    rows = []
    for name, cfg in items:
        m = analyze_matrix(cfg.camera.E)
        cloud = gamut_cloud(cfg, n=8)
        res = {h: check_target(cfg, h)["resid_dE"] for h in probes}
        rows.append(dict(name=name, cond=m["cond"], worst_cross=m["worst_cross"], grade=m["grade"], ab_area=cloud["ab_area"],
                         L_min=cloud["L_range"][0], probes=res))
    return rows


# ------------------------------------------------------------------ 설정 도우미
def cfg_from(calib_path: str | None, ideal: bool = False) -> tuple[SystemConfig, object]:
    cfg, cal = rig_prominent_feeder(), None
    if calib_path:
        from .camera import Calibration
        cal = Calibration.load(calib_path)
        cal.apply_to(cfg)
    if ideal:
        cfg.camera.E = ideal_matrix(cfg.camera.E)
    return cfg, cal


def _print_matrix(cfg):
    m = analyze_matrix(cfg.camera.E)
    print("E (행 R,G,B / 열 C,M,Y) [흡광도/(mg/L)]")
    for i, ch in enumerate(CHANNELS):
        print(f"  {ch}: " + "  ".join(f"{v:8.5f}" for v in m["E"][i]))
    print(f"조건수 κ(E) = {m['cond']}  (작을수록 좋음, 3 이하 권장)   대각 우세: {'예' if m['diag_dominant'] else '아니오'}   등급: {m['grade']}")
    print("교차 흡수 (주 채널 대비 비율): " + "; ".join(f"{d} → " + ", ".join(f"{ch} {v}" for ch, v in cr.items()) for d, cr in m["cross"].items()))
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gamut", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "matrix", "map", "hull"):
        p = sp.add_parser(name); p.add_argument("--calib", default=None); p.add_argument("--ideal", action="store_true", help="E 를 대각(이상적 CMY)으로")
        if name in ("check", "map"): p.add_argument("--target", default="#53F3B6")
        if name in ("map", "hull"): p.add_argument("--out", default=f"gamut.{'png' if name == 'map' else 'json'}"); p.add_argument("-n", type=int, default=12)
    p = sp.add_parser("compare"); p.add_argument("calibs", nargs="*"); p.add_argument("--ideal", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "compare":
        items = [("기본(설명용)", rig_prominent_feeder())] + [(pathlib.Path(c).name, cfg_from(c)[0]) for c in a.calibs]
        if a.ideal:
            items.append(("이상적 CMY(대각)", cfg_from(None, ideal=True)[0]))
        rows = compare_sets(items)
        print(f"{'세트':22s} {'κ(E)':>6s} {'교차max':>7s} {'등급':>4s} {'a*b*면적':>8s} {'L*min':>6s}  탐침색 잔차 ΔE (작을수록 넓은 색역)")
        for r in rows:
            print(f"{r['name'][:22]:22s} {r['cond']:6.2f} {r['worst_cross']:7.3f} {r['grade']:>4s} {r['ab_area']:8.0f} {r['L_min']:6.1f}  " + "  ".join(f"{h} {v:5.1f}" for h, v in r["probes"].items()))
        return 0

    cfg, cal = cfg_from(a.calib, a.ideal)
    if a.cmd == "matrix":
        _print_matrix(cfg); return 0
    if a.cmd == "check":
        _print_matrix(cfg)
        r = check_target(cfg, a.target, cal)
        print(f"\n목표 {r['target']}: 흡광도 A(R,G,B) = {r['A']}")
        print(f"  c = E⁻¹A (부호 검사) = {r['c_raw']}  →  음수 염료: {r['negative'] or '없음'}   물보다 밝은 채널: {r['brighter_than_water'] or '없음'}")
        print(f"  {'색역 안' if r['in_gamut'] else '색역 밖'}: {r['why']}")
        print(f"  NNLS 가장 가까운 c* (C/M/Y) = {r['c']} mg/L → {r['nearest']}  잔차 ΔE2000 = {r['resid_dE']}")
        print(f"  보정 농도 상한 = {r['calibrated_max']}  범위 초과: {r['over_calibrated'] or '없음'}   스톡 초과: {r['over_stock'] or '없음'}")
        return 0
    cloud = gamut_cloud(cfg, n=a.n)
    if a.cmd == "hull":
        pathlib.Path(a.out).write_text(json.dumps(cloud, ensure_ascii=False)); print("저장:", a.out, f"({len(cloud['points'])} 점, a*b* 면적 {cloud['ab_area']})"); return 0
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt   # 그림 글자는 영문 (한글 글꼴 없는 Pi 에서도 깨지지 않게)
    labs = np.array([p["lab"] for p in cloud["points"]]); cols = [p["hex"] for p in cloud["points"]]
    fig, ax = plt.subplots(1, 2, figsize=(11, 5))
    ax[0].scatter(labs[:, 1], labs[:, 2], c=cols, s=14, edgecolors="none"); ax[0].set_xlabel("a*  (green <- -> red)"); ax[0].set_ylabel("b*  (blue <- -> yellow)"); ax[0].set_title("reachable colours (a*b*)")
    ax[1].scatter(labs[:, 1], labs[:, 0], c=cols, s=14, edgecolors="none"); ax[1].set_xlabel("a*"); ax[1].set_ylabel("L*  (lightness)"); ax[1].set_title("reachable colours (a*L*)")
    r = check_target(cfg, a.target, cal); lt = optics.srgb8_to_lab(optics.hex_to_rgb8(r["target"])); ln = optics.srgb8_to_lab(optics.hex_to_rgb8(r["nearest"]))
    for k, (xi, yi) in enumerate(((1, 2), (1, 0))):
        ax[k].plot(lt[xi], lt[yi], "x", ms=12, mew=2.5, color="red", label=f"target {r['target']}"); ax[k].plot(ln[xi], ln[yi], "o", ms=10, mfc="none", mew=2, color="black", label=f"nearest {r['nearest']}  dE2000 {r['resid_dE']}")
        ax[k].plot([lt[xi], ln[xi]], [lt[yi], ln[yi]], "-", color="red", lw=1); ax[k].grid(alpha=.3); ax[k].legend(fontsize=8)
    fig.suptitle(f"cond(E) = {r['cond']}   {'ideal CMY (diagonal E)' if a.ideal else (a.calib or 'default E')}   {'in gamut' if r['in_gamut'] else 'OUT of gamut: needs negative ' + ','.join(r['negative'] or r['brighter_than_water'])}", fontsize=10)
    fig.tight_layout(); fig.savefig(a.out, dpi=130); print("저장:", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
