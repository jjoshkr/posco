"""카메라 설정·보정 CLI (AI 노드에서 실행).

  python -m cmysim.camera_tools preview   [--save shot.png]      ROI 표시 (창 없으면 PNG 저장)
  python -m cmysim.camera_tools roi       --roi 220,140,200,200  ROI 지정 (또는 --pick 으로 마우스 선택)
  python -m cmysim.camera_tools settings  --exposure 120 --gain 16 --wb 4600 --kind realsense
  python -m cmysim.camera_tools reference                        물만 채운 상태 → 기준 영상 I0 저장
  python -m cmysim.camera_tools sample    --dye C --conc 10      단일 염료 시료 측정값 추가 (염료마다 4~5 농도)
  python -m cmysim.camera_tools fit                              E 행렬 피팅 → calibration.json
  python -m cmysim.camera_tools check     [--cmy 10,5,8]         현재 프레임으로 농도 역산 (혼합 검증)
  python -m cmysim.camera_tools monitor   --target "#5A8F7B"     RGB / A / ĉ / ΔE 연속 출력
  python -m cmysim.camera_tools target    --save target.json      목표 시료를 같은 카메라로 찍어 목표 RGB·c* 저장

순서: settings → roi → reference → sample ×(3염료×4~5) → fit → check → ai_node_main
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time
import numpy as np
from .camera import CameraSettings, open_camera, Calibration, fit_E
from .vision import write_png
from . import optics


def _draw_roi_png(frame, roi, path):
    img = frame.copy()
    x, y, w, h = [int(v) for v in roi]
    img[y:y + h, [x, x + w - 1], :] = [255, 0, 0]
    img[[y, y + h - 1], x:x + w, :] = [255, 0, 0]
    write_png(path, img)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="camera_tools", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="camera.json")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("preview"); p.add_argument("--save", default="preview.png"); p.add_argument("--window", action="store_true")
    p = sp.add_parser("roi"); p.add_argument("--roi"); p.add_argument("--pick", action="store_true")
    p = sp.add_parser("settings")
    for k in ("kind", "device", "ref_path", "calib_path"):
        p.add_argument("--" + k)
    for k in ("exposure", "gain", "wb", "gamma"):
        p.add_argument("--" + k, type=float)
    for k in ("width", "height", "fps"):
        p.add_argument("--" + k, type=int)
    p = sp.add_parser("reference"); p.add_argument("-n", type=int, default=30)
    p = sp.add_parser("sample"); p.add_argument("--dye", required=True, choices=("C", "M", "Y")); p.add_argument("--conc", type=float, required=True)
    p.add_argument("-n", type=int, default=15); p.add_argument("--samples", default="calib_samples.json")
    p = sp.add_parser("fit"); p.add_argument("--samples", default="calib_samples.json"); p.add_argument("--glare", type=float, default=0.0)
    p = sp.add_parser("check"); p.add_argument("--cmy"); p.add_argument("-n", type=int, default=15)
    p = sp.add_parser("monitor"); p.add_argument("--target", default="#5A8F7B"); p.add_argument("--hz", type=float, default=2.0)
    p = sp.add_parser("target", help="목표 시료(기준 색 용액)를 같은 카메라로 찍어 목표 RGB 와 c* 를 저장")
    p.add_argument("--save", default="target.json"); p.add_argument("-n", type=int, default=15)
    a = ap.parse_args(argv)

    s = CameraSettings.load(a.config)

    if a.cmd == "settings":
        for k in ("kind", "device", "ref_path", "calib_path", "width", "height", "fps", "exposure", "gain", "gamma"):
            v = getattr(a, k)
            if v is not None:
                setattr(s, k, v)
        if a.wb is not None:
            s.white_balance = a.wb
        s.save(a.config); print(json.dumps(s.__dict__, indent=1, ensure_ascii=False)); return 0

    if a.cmd == "roi" and a.roi:
        s.roi = [int(v) for v in a.roi.split(",")]; s.save(a.config); print("ROI =", s.roi); return 0

    cam = open_camera(s)
    try:
        if a.cmd == "preview":
            f = cam.read()
            print("frame", f.shape, "ROI mean RGB", cam.roi_rgb8(f), getattr(cam, "info", lambda: {})())
            if a.window:
                import cv2
                x, y, w, h = s.roi
                bgr = cv2.rectangle(f[:, :, ::-1].copy(), (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.imshow("preview (q to quit)", bgr)
                while cv2.waitKey(30) & 0xFF != ord("q"):
                    f = cam.read(); x, y, w, h = s.roi
                    cv2.imshow("preview (q to quit)", cv2.rectangle(f[:, :, ::-1].copy(), (x, y), (x + w, y + h), (0, 0, 255), 2))
                cv2.destroyAllWindows()
            else:
                _draw_roi_png(f, s.roi, a.save); print("saved", a.save)
        elif a.cmd == "roi":
            import cv2
            f = cam.read()
            r = cv2.selectROI("select ROI (ENTER)", f[:, :, ::-1].copy(), showCrosshair=False)
            cv2.destroyAllWindows()
            s.roi = [int(v) for v in r]; s.save(a.config); print("ROI =", s.roi)
        elif a.cmd == "reference":
            ref = cam.capture_reference(a.n)
            I0 = ref.reshape(-1, 3).mean(0)
            print(f"기준 영상 저장 {s.ref_path}  I0(ROI 평균 선형) = {np.round(I0, 4)}  "
                  f"균일도(픽셀 std/mean) = {np.round(ref.reshape(-1,3).std(0)/I0, 3)}")
            if I0.max() > 0.95:
                print("경고: 포화 근처. 노출을 줄이세요 (목표 0.6~0.85).")
        elif a.cmd == "sample":
            if cam.ref is None:
                print("기준 영상이 없습니다. 먼저 reference 를 실행하세요."); return 1
            rgb, A, sd = cam.average(a.n)
            p = pathlib.Path(a.samples)
            data = json.loads(p.read_text()) if p.exists() else []
            data.append(dict(dye=a.dye, conc=a.conc, A=A.round(5).tolist(), rgb=rgb.tolist(), std=sd.round(5).tolist(), t=time.time()))
            p.write_text(json.dumps(data, indent=1))
            print(f"{a.dye} {a.conc} mg/L: RGB {rgb}  A(R,G,B) = {np.round(A,4)} ± {np.round(sd,4)}  (총 {len(data)}개)")
            if A.max() > 1.0:
                print("경고: 흡광도 > 1. 더 묽은 농도로 보정 범위를 잡으세요 (PDF 8장 5번).")
        elif a.cmd == "fit":
            data = json.loads(pathlib.Path(a.samples).read_text())
            E, rep = fit_E(data)
            I0 = cam.ref.reshape(-1, 3).mean(0) if cam.ref is not None else np.array([0.9] * 3)
            cal = Calibration(E=E.round(6).tolist(), I0=I0.round(5).tolist(), gamma=s.gamma, glare=a.glare,
                              cond=round(optics.condition_number(E), 3), samples=data,
                              note=f"fitted {time.strftime('%Y-%m-%d %H:%M')} from {a.samples}")
            cal.save(s.calib_path)
            print("E =\n", E.round(5)); print("조건수 κ =", cal.cond, "(작을수록 좋음, 3 이하 권장)")
            for d, r in rep.items():
                print(f"  {d}: n={r['n']} conc={r['conc']} R²(R,G,B)={r['r2']} maxA={r['max_A']:.3f}")
            print("저장:", s.calib_path)
        elif a.cmd in ("check", "monitor", "target"):
            cal = Calibration.load(s.calib_path)
            E, I0 = np.array(cal.E), np.array(cal.I0)
            if a.cmd == "target":
                rgb, A, sd = cam.average(a.n)
                c = optics.nnls3(E, A)
                out = dict(rgb=rgb.tolist(), hex=optics.rgb8_to_hex(rgb), A=A.round(5).tolist(), c=c.round(4).tolist(),
                           note=f"captured {time.strftime('%Y-%m-%d %H:%M')} with {s.calib_path}")
                pathlib.Path(a.save).write_text(json.dumps(out, indent=1))
                print(f"목표 시료: RGB {rgb} {out['hex']}  c*(C,M,Y) = {np.round(c,2)} mg/L  → {a.save}")
                print("ai_node_main --target-file", a.save, "로 사용. (hex 보다 같은 카메라로 찍은 이 값이 ΔE 기준으로 정확합니다)")
            elif a.cmd == "check":
                rgb, A, sd = cam.average(a.n)
                c = optics.nnls3(E, A)
                print(f"RGB {rgb}  A {np.round(A,4)}  →  ĉ(C,M,Y) = {np.round(c,2)} mg/L")
                if a.cmy:
                    ct = np.array([float(v) for v in a.cmy.split(",")])
                    print(f"기대 {ct}  오차 {np.round(c-ct,2)} mg/L  ({np.round(100*(c-ct)/np.maximum(ct,1e-9),1)} %)")
            else:
                tgt = optics.hex_to_rgb8(a.target)
                c_t = optics.rgb8_to_conc(E, I0, tgt, cal.gamma, cal.glare)
                print(f"목표 {a.target} → c* = {np.round(c_t,2)} mg/L   (Ctrl+C 로 종료)")
                while True:
                    f = cam.read()
                    rgb, A = cam.roi_rgb8(f), cam.roi_absorbance(f, I0)
                    c = optics.nnls3(E, A)
                    print(f"{time.strftime('%H:%M:%S')}  RGB {rgb.astype(int)} {optics.rgb8_to_hex(rgb)}  A {np.round(A,3)}  "
                          f"ĉ {np.round(c,2)}  ΔE2000 {optics.delta_e2000(rgb, tgt):5.2f}")
                    time.sleep(1.0 / a.hz)
    except KeyboardInterrupt:
        pass
    finally:
        cam.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
