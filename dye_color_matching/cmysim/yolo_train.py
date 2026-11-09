"""YOLO 학습 파이프라인 (워크스테이션에서 학습 → ONNX → Hailo HEF → AI HAT+ 추론).

  python -m cmysim.yolo_train gen      --out ds_sim --runs 12                      시뮬레이션으로 라벨 달린 프레임 생성
  python -m cmysim.yolo_train prepare  --src ds_sim/* ds_run1 --out yolo_ds        train/val 분할 + data.yaml + 회귀 CSV
  python -m cmysim.yolo_train train    --data yolo_ds/data.yaml --model yolo11n.pt --epochs 50 --imgsz 320
  python -m cmysim.yolo_train train    --data yolo_ds_cls --task classify --model yolo11n-cls.pt      (프레임 상태 분류)
  python -m cmysim.yolo_train export   --weights runs/detect/cmy/weights/best.pt                   ONNX (Hailo 컴파일용)
  python -m cmysim.yolo_train infer    --weights best.pt --source yolo_ds/images/val                 또는 --source camera.json
  python -m cmysim.yolo_train regress  --csv yolo_ds/regression.csv                                 색→농도 회귀 (YOLO 보조)

역할 분담 (대화에서 정리한 대로)
  - YOLO detect  : 기포·거품·침전·이물 같은 '사건' 과 액체 ROI 의 on/off_target 상태
  - YOLO classify: 프레임 한 장의 on_target / off_target (가장 가벼움, Hailo 에서 수백 fps)
  - 회귀         : 색 → 농도 같은 연속값은 YOLO 가 아니라 optics 역산 또는 작은 회귀 모델
"""
from __future__ import annotations
import argparse, csv, json, pathlib, random, shutil, sys
import numpy as np
from .vision import CLASSES


# ------------------------------------------------------------------ gen: 시뮬레이션 데이터 생성
def cmd_gen(a):
    from .config import SystemConfig
    from .experiment import run_once, make_recipe
    from . import optics
    rng = random.Random(a.seed)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    faults_pool = [[], [], ["stock_conc:P-101=900"], ["stock_conc:P-103=930"], ["camera_drift:0.92@40"], ["rpm:120"], ["tank_empty:P-102@25"]]
    for i in range(a.runs):
        cfg = SystemConfig(seed=a.seed + i)
        cfg.camera.pixel_noise = rng.uniform(0.01, 0.03)
        c = np.array([rng.uniform(5, 40), rng.uniform(3, 20), rng.uniform(5, 35)])
        rec, _ = make_recipe(cfg, target_cmy=c, mode=rng.choice(["open", "closed"]), dose_minutes=rng.uniform(0.5, 1.5))
        faults = rng.choice(faults_pool)
        d = out / f"run{i:02d}"
        res = run_once(cfg, rec, duration_s=a.duration, faults=faults, dataset_dir=d, run_id=f"run{i:02d}")
        print(f"run{i:02d}: target {optics.rgb8_to_hex(rec.target_rgb8)} faults={faults} ΔE={res['dE2000_true']} frames={len(list((d/'images').glob('*.png')))}")
    print("완료:", out)


# ------------------------------------------------------------------ prepare: 분할 + yaml + 회귀 CSV
def cmd_prepare(a):
    srcs = [pathlib.Path(s) for s in a.src]
    out = pathlib.Path(a.out)
    cls_out = pathlib.Path(a.out + "_cls")
    if a.clean:
        for d in (out, cls_out):
            if d.exists():
                shutil.rmtree(d)
    for sp in ("train", "val"):
        (out / "images" / sp).mkdir(parents=True, exist_ok=True)
        (out / "labels" / sp).mkdir(parents=True, exist_ok=True)
    for sp in ("train", "val"):
        for c in CLASSES[:2]:
            (cls_out / sp / c).mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    rows, n = [], {"train": 0, "val": 0}
    srcs = sorted(srcs)
    # 실행 단위 분할: val 비율에 맞춰 결정적으로 고른다 (실행이 2개 이상이면 val 이 비지 않게)
    k = max(1, int(round(1.0 / max(a.val, 1e-6))))
    val_runs = {s.name for i, s in enumerate(srcs) if (i + 1) % k == 0} if len(srcs) > 1 else set()
    for src in srcs:
        idx_path = src / "index.jsonl"
        if not idx_path.exists():
            print("건너뜀 (index.jsonl 없음):", src); continue
        recs = [json.loads(l) for l in idx_path.read_text().splitlines() if l.strip()]
        # 분할은 '실행 단위' 가 기본 (같은 실행의 연속 프레임이 train/val 에 섞이면 점수가 부풀려짐)
        if a.split_by == "run":
            split_all = "val" if src.name in val_runs else "train"
        for r in recs:
            sp = split_all if a.split_by == "run" else ("val" if rng.random() < a.val else "train")
            img = src / "images" / f"{r['frame']}.png"; lab = src / "labels" / f"{r['frame']}.txt"
            if not img.exists():
                continue
            name = f"{src.name}_{r['frame']}"
            link(img, out / "images" / sp / f"{name}.png", a.copy)
            if lab.exists():
                link(lab, out / "labels" / sp / f"{name}.txt", a.copy)
            link(img, cls_out / sp / CLASSES[r["cls"]] / f"{name}.png", a.copy)
            rows.append(dict(path=str((out / "images" / sp / f"{name}.png").resolve()), split=sp, src=src.name, t=r["t"],
                             cls=r["cls"], dE2000=r["dE2000"], R=r["rgb"][0], G=r["rgb"][1], B=r["rgb"][2],
                             tR=r["target_rgb"][0], tG=r["target_rgb"][1], tB=r["target_rgb"][2],
                             cC_hat=r["c_hat"][0], cM_hat=r["c_hat"][1], cY_hat=r["c_hat"][2],
                             cC=(r["c_true"] or [None] * 3)[0], cM=(r["c_true"] or [None] * 3)[1], cY=(r["c_true"] or [None] * 3)[2],
                             n_bubbles=r.get("n_bubbles", 0)))
            n[sp] += 1
    names = "\n".join(f"  {i}: {c}" for i, c in enumerate(CLASSES))
    (out / "data.yaml").write_text(f"path: {out.resolve()}\ntrain: images/train\nval: images/val\nnames:\n{names}\n")
    with open(out / "regression.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    cnt = {sp: {c: sum(1 for r in rows if r["split"] == sp and r["cls"] == i) for i, c in enumerate(CLASSES[:2])} for sp in n}
    print(f"detect: {out}/data.yaml  train {n['train']} / val {n['val']}  클래스 분포 {cnt}")
    print(f"classify: {cls_out}  (yolo classify 폴더 구조)")
    print(f"regression: {out}/regression.csv")
    if n["val"] == 0:
        print("경고: val 이 비었습니다. --split-by frame 또는 --val 을 키우세요.")


def link(src, dst, copy):
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if copy:
        shutil.copy2(src, dst)
    else:
        try:
            dst.symlink_to(src.resolve())
        except OSError:
            shutil.copy2(src, dst)


# ------------------------------------------------------------------ train / export / infer (ultralytics)
def _yolo():
    try:
        from ultralytics import YOLO
    except ImportError:
        sys.exit("ultralytics 가 없습니다: pip install ultralytics  (워크스테이션에서; Pi 에서는 학습하지 않음)")
    return YOLO


def cmd_train(a):
    YOLO = _yolo()
    model = YOLO(a.model)
    kw = dict(data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device, workers=a.workers,
              name=a.name, exist_ok=True, seed=a.seed, verbose=True, plots=True)
    if a.project:
        kw["project"] = a.project                      # 기본: runs/<task>/<name>
    if a.task == "detect":
        # 색이 라벨 자체(on/off_target)이므로 색상 증강은 끈다
        kw.update(hsv_h=0.0, hsv_s=0.0, hsv_v=0.1, fliplr=0.5, mosaic=0.5 if a.epochs > 5 else 0.0)
    else:
        kw.update(hsv_h=0.0, hsv_s=0.0, hsv_v=0.1)
    res = model.train(**kw)
    best = pathlib.Path(model.trainer.best) if hasattr(model, "trainer") else None
    print("best weights:", best)
    try:
        m = model.val(data=a.data, imgsz=a.imgsz, device=a.device, plots=False)
        if a.task == "detect":
            print(f"val mAP50 {m.box.map50:.3f}  mAP50-95 {m.box.map:.3f}  per-class mAP50 {np.round(m.box.ap50, 3).tolist()}")
        else:
            print(f"val top1 {m.top1:.3f}")
    except Exception as e:
        print("검증 요약 생략:", e)
    return best


def cmd_export(a):
    YOLO = _yolo()
    try:
        import onnx  # noqa: F401
    except ImportError:
        sys.exit("onnx 가 없습니다: pip install onnx onnxslim")
    model = YOLO(a.weights)
    # Hailo Dataflow Compiler 는 NMS 없는 ONNX(opset ≤ 17 권장), 고정 입력 크기를 원한다
    path = model.export(format="onnx", imgsz=a.imgsz, opset=a.opset, simplify=True, dynamic=False, nms=False)
    print("ONNX:", path)
    print("""다음 단계 (x86 워크스테이션, Hailo Dataflow Compiler 설치 후):
  hailomz compile yolov8n --ckpt %s --hw-arch hailo8 --calib-path yolo_ds/images/train --classes %d
  → .hef 파일을 AI 노드로 복사하고  python -m cmysim.yolo_train infer --weights model.hef --source camera.json
  (hailo_model_zoo 의 yolov8 계열 설정을 쓰면 후처리(NMS)가 Hailo 쪽에 붙는다. yolo11 은 모델 주 버전에 따라 지원 여부 확인)""" % (path, len(CLASSES)))


def cmd_infer(a):
    from .yolo_infer import VisionEvents
    det = VisionEvents(a.weights, conf=a.conf, imgsz=a.imgsz)
    src = pathlib.Path(a.source)
    if src.suffix == ".json":                                   # 카메라 라이브
        from .camera import CameraSettings, open_camera
        cam = open_camera(CameraSettings.load(str(src)))
        try:
            import time
            while True:
                r = det.detect(cam.read())
                print(f"{time.strftime('%H:%M:%S')} liquid={r['liquid']} ({r['liquid_conf']:.2f}) bubbles={r['bubbles']} ms={r['ms']:.0f}")
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            cam.stop()
        return
    imgs = sorted(src.glob("*.png")) + sorted(src.glob("*.jpg")) if src.is_dir() else [src]
    from .vision import write_png
    agree, n = 0, 0
    for p in imgs[: a.limit]:
        img = _read_rgb(p)
        r = det.detect(img)
        lab = p.parent.parent / "labels" / p.parent.name / (p.stem + ".txt")
        truth = ""
        if lab.exists():
            cls0 = [int(l.split()[0]) for l in lab.read_text().splitlines() if l.strip() and int(l.split()[0]) < 2]
            if cls0:
                truth = CLASSES[cls0[0]]; n += 1; agree += (truth == r["liquid"])
        print(f"{p.name}: liquid={r['liquid']} ({r['liquid_conf']:.2f}) bubbles={r['bubbles']} {('truth=' + truth) if truth else ''}")
        if a.save:
            write_png(pathlib.Path(a.save) / p.name, det.draw(img, r))
    if n:
        print(f"액체 상태 일치 {agree}/{n} = {agree / n:.2%}")


def _read_rgb(path):
    try:
        import cv2
        return cv2.imread(str(path))[:, :, ::-1].copy()
    except Exception:
        from PIL import Image
        return np.asarray(Image.open(path).convert("RGB"))


# ------------------------------------------------------------------ regress: 색 → 농도 (YOLO 보조, numpy 만으로)
def features(R, G, B, I0=(0.9, 0.9, 0.9), gamma=2.2):
    v = np.stack([R, G, B], -1) / 255.0
    lin = np.clip(v, 1e-4, 1) ** gamma
    A = -np.log10(np.clip(lin / np.asarray(I0), 1e-4, None))
    return np.concatenate([A, A ** 2, lin, np.ones((*A.shape[:-1], 1))], -1)


def cmd_regress(a):
    rows = list(csv.DictReader(open(a.csv)))
    rows = [r for r in rows if r["cC"] not in ("", "None")]
    if not rows:
        sys.exit("c_true 가 있는 행이 없습니다 (실제 프레임은 진짜 농도를 모르므로 시뮬레이션 데이터나 보정 시료가 필요)")
    def xy(sp):
        rs = [r for r in rows if r["split"] == sp]
        X = features(*[np.array([float(r[k]) for r in rs]) for k in ("R", "G", "B")])
        Y = np.array([[float(r[k]) for k in ("cC", "cM", "cY")] for r in rs])
        return X, Y
    Xtr, Ytr = xy("train"); Xva, Yva = xy("val")
    lam = a.ridge
    W = np.linalg.solve(Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1]), Xtr.T @ Ytr)
    def rmse(X, Y):
        return np.sqrt(((np.clip(X @ W, 0, None) - Y) ** 2).mean(0))
    print(f"train n={len(Ytr)} RMSE(C,M,Y) mg/L = {np.round(rmse(Xtr, Ytr), 3)}")
    if len(Yva):
        print(f"val   n={len(Yva)} RMSE(C,M,Y) mg/L = {np.round(rmse(Xva, Yva), 3)}")
        # 비교: 기록된 optics 역산(c_hat) 의 오차
        ch = np.array([[float(r[k]) for k in ("cC_hat", "cM_hat", "cY_hat")] for r in rows if r["split"] == "val"])
        print(f"참고: optics 역산 c_hat 의 val RMSE = {np.round(np.sqrt(((ch - Yva) ** 2).mean(0)), 3)}")
    np.save(a.out, W); print("가중치 저장:", a.out, "(features() 와 함께 사용: c = clip(features(R,G,B) @ W, 0))")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="yolo_train", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("gen"); p.add_argument("--out", default="ds_sim"); p.add_argument("--runs", type=int, default=12)
    p.add_argument("--duration", type=float, default=240.0); p.add_argument("--seed", type=int, default=100)
    p = sp.add_parser("prepare"); p.add_argument("--src", nargs="+", required=True); p.add_argument("--out", default="yolo_ds")
    p.add_argument("--val", type=float, default=0.25); p.add_argument("--split-by", choices=("run", "frame"), default="run")
    p.add_argument("--copy", action="store_true", help="심볼릭 링크 대신 복사"); p.add_argument("--clean", action="store_true"); p.add_argument("--seed", type=int, default=0)
    p = sp.add_parser("train"); p.add_argument("--data", required=True); p.add_argument("--task", choices=("detect", "classify"), default="detect")
    p.add_argument("--model", default="yolo11n.pt"); p.add_argument("--epochs", type=int, default=50); p.add_argument("--imgsz", type=int, default=320)
    p.add_argument("--batch", type=int, default=16); p.add_argument("--device", default="cpu"); p.add_argument("--workers", type=int, default=2)
    p.add_argument("--project", default=None); p.add_argument("--name", default="cmy"); p.add_argument("--seed", type=int, default=0)
    p = sp.add_parser("export"); p.add_argument("--weights", required=True); p.add_argument("--imgsz", type=int, default=320); p.add_argument("--opset", type=int, default=12)
    p = sp.add_parser("infer"); p.add_argument("--weights", required=True); p.add_argument("--source", required=True)
    p.add_argument("--conf", type=float, default=0.25); p.add_argument("--imgsz", type=int, default=320); p.add_argument("--limit", type=int, default=50); p.add_argument("--save")
    p = sp.add_parser("regress"); p.add_argument("--csv", required=True); p.add_argument("--ridge", type=float, default=1e-3); p.add_argument("--out", default="color_regressor.npy")
    a = ap.parse_args(argv)
    return {"gen": cmd_gen, "prepare": cmd_prepare, "train": cmd_train, "export": cmd_export, "infer": cmd_infer, "regress": cmd_regress}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
