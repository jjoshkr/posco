"""AI 노드 실행 스크립트 (Raspberry Pi 5 + AI HAT+ + RealSense).

  python -m cmysim.ai_node_main --io-ip 192.168.10.2 --target "#5A8F7B" --mode closed \
         --camera camera.json --log run1.csv --dataset ds_run1/

  --monitor    : I/O 노드에 연결하지 않고 카메라 측정만 출력 (배선 전 점검용)
  --no-io      : 명령을 보내지 않고 화면에만 찍음 (제어기 상태기계 점검; 텔레메트리가 없어 DOSE 에서 멈춤)

구조: 카메라 → ROI RGB·흡광도 → Controller.step() → ZeroMQ 로 I/O 노드에 명령, 하트비트 0.2 s.
종료(Ctrl+C, 예외, DONE) 시 반드시 run_enable OFF + safe 를 보낸다. I/O 노드는 하트비트가 1 s 끊겨도 스스로 SAFE 가 된다.
"""
from __future__ import annotations
import argparse, csv, pathlib, signal, sys, time
import numpy as np
from .config import SystemConfig
from .camera import CameraSettings, open_camera, Calibration
from .control import Controller, plan_doses
from .experiment import make_recipe
from .vision import DatasetRecorder
from . import optics


class NullBus:
    """--no-io: 명령을 기록만 한다."""
    def __init__(self):
        self.log = []

    def send_cmd(self, m):
        self.log.append(m); print("  [cmd]", m)

    def latest(self):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ai_node_main", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--io-ip", default="192.168.10.2")
    ap.add_argument("--cmd-port", type=int, default=5555); ap.add_argument("--tele-port", type=int, default=5556)
    ap.add_argument("--camera", default="camera.json")
    ap.add_argument("--target"); ap.add_argument("--cmy")
    ap.add_argument("--target-file", help="camera_tools target 이 저장한 json (같은 카메라로 찍은 목표 시료)")
    ap.add_argument("--recipe", help="YAML 레시피 (recipe_cli example 참고). 주면 --target/--mode 대신 레시피 스텝대로 실행")
    ap.add_argument("--mode", choices=("open", "closed"), default="closed")
    ap.add_argument("--heel", type=float, default=2000.0); ap.add_argument("--rpm", type=float, default=300.0)
    ap.add_argument("--dose-min", type=float, default=2.0); ap.add_argument("--de-match", type=float, default=1.5)
    ap.add_argument("--flow-factor", default="1,1,1", help="피드포워드 배율 (과투입 방지용 0.97,0.97,0.97 권장)")
    ap.add_argument("--max-minutes", type=float, default=30.0)
    ap.add_argument("--log", default="ai_node_log.csv"); ap.add_argument("--dataset")
    ap.add_argument("--hz", type=float, default=10.0, help="제어 루프 주기")
    ap.add_argument("--monitor", action="store_true"); ap.add_argument("--no-io", action="store_true")
    ap.add_argument("--preview", action="store_true", help="OpenCV 창에 ROI·색 견본 표시 (모니터 연결 시)")
    ap.add_argument("--anomaly", help="anomaly train 이 저장한 모델 폴더. 0.5 s 마다 오토인코더 점수·CUSUM 을 내고 알람을 로그에 남김")
    ap.add_argument("--yolo", help="학습된 가중치 (.pt/.onnx/.hef). 기포·액체 상태를 로그에 남기고 기포가 많으면 트림을 보류")
    ap.add_argument("--yolo-every", type=int, default=5, help="몇 프레임마다 YOLO 를 돌릴지")
    ap.add_argument("--bubble-hold", type=int, default=3, help="이 개수 이상 기포가 보이면 카메라 추정을 믿지 않고 TRIM 을 미룸")
    a = ap.parse_args(argv)

    # 1) 설정 + 실측 보정값
    cs = CameraSettings.load(a.camera)
    cfg = SystemConfig(dt=1.0 / a.hz)
    cfg.camera.fps = a.hz
    cfg.reactor.heel_mL, cfg.reactor.rpm = a.heel, a.rpm
    try:
        cal = Calibration.load(cs.calib_path); cal.apply_to(cfg)
        print(f"보정 로드 {cs.calib_path}: κ={cal.cond}  I0={np.round(cfg.camera.I0, 3)}")
    except FileNotFoundError:
        if not a.monitor:
            print(f"보정 파일 {cs.calib_path} 이 없습니다. camera_tools reference/sample/fit 먼저."); return 1
        print("경고: 보정 없음 — 설명용 E 로 표시만 합니다.")

    ff = np.array([float(v) for v in a.flow_factor.split(",")])
    if a.target_file:
        import json
        from .control import Recipe
        tf = json.loads(open(a.target_file).read())
        rec, resid = Recipe(target_rgb8=np.array(tf["rgb"], float), c_target=np.array(tf["c"], float), mode=a.mode,
                            dose_minutes=a.dose_min, de_match=a.de_match, flow_factor=ff), 0.0
    else:
        cmy = [float(v) for v in a.cmy.split(",")] if a.cmy else None
        rec, resid = make_recipe(cfg, a.target, cmy, mode=a.mode, dose_minutes=a.dose_min, de_match=a.de_match, flow_factor=ff)
    print(f"목표 {optics.rgb8_to_hex(rec.target_rgb8)}  c* = {np.round(rec.c_target, 2)} mg/L"
          + (f"  (도달 가능 잔차 ΔE {resid:.2f})" if resid > 0.05 else ""))
    for d in plan_doses(cfg, cfg.reactor.heel_mL, rec.c_target, rec.dose_minutes, rec.flow_factor):
        print(f"  {d['id']}: {d['volume_mL']:.2f} mL = {d['strokes']:.0f} str @ {d['rate_mL_min']:.2f} mL/min → {d['mA']:.2f} mA")

    # 2) 카메라, 버스
    cam = open_camera(cs)
    if a.monitor or a.no_io:
        bus = NullBus()
    else:
        from .zmq_bridge import ZmqBus
        bus = ZmqBus("ai", a.io_ip, a.cmd_port, a.tele_port)
        print(f"I/O 노드 {a.io_ip} 에 연결. 텔레메트리 대기...")
        t0 = time.time()
        while bus.latest() is None and time.time() - t0 < 10:
            bus.send_cmd(dict(cmd="heartbeat", t=0.0)); time.sleep(0.2)
        if bus.latest() is None:
            print("텔레메트리가 오지 않습니다. I/O 노드(python -m cmysim.io_node_main run) 와 이더넷 연결을 확인하세요.")
            cam.stop(); return 2
        print("텔레메트리 수신:", bus.latest())

    if a.recipe:
        from .recipe import load_recipe, expand_matrix, RecipeExecutor
        rr = load_recipe(a.recipe)
        runs = expand_matrix(rr)
        if len(runs) > 1:
            print(f"matrix 레시피는 실물에서 한 번에 하나씩 실행합니다. 첫 번째({runs[0]['name']})를 실행합니다.")
        ctl = RecipeExecutor(cfg, runs[0], sim=False)
        rec = ctl.r
        print(f"레시피 {ctl.name}: 스텝 {len(ctl.steps)}개, 목표 {optics.rgb8_to_hex(rec.target_rgb8)} c*={np.round(rec.c_target, 2)}")
    else:
        ctl = Controller(cfg, rec)
    ds = DatasetRecorder(a.dataset, cam, de_match=a.de_match, roi=cs.roi) if a.dataset else None
    det = None
    if a.yolo:
        from .yolo_infer import VisionEvents
        det = VisionEvents(a.yolo); print("YOLO 로드:", a.yolo, det.backend)
    yolo_res = dict(liquid=None, liquid_conf=0.0, bubbles=0, ms=0.0)
    frame_i = 0
    adet = None
    if a.anomaly:
        from .anomaly import Detector
        adet = Detector.load(a.anomaly); adet.fb.heel = cfg.reactor.heel_mL
        adet.fb.c_stock = np.array([tk.conc_mg_L for tk in cfg.tanks], float)
        print(f"이상탐지 로드 {a.anomaly}: {adet.model.kind}, 특징 {len(adet.features)}개, 창 {adet.W}×{adet.dt}s, 임계 {adet.thr:.4f}")
    ad_res = dict(score=0.0, ratio=0.0, alarm=False, cusum=0.0, cusum_alarm=False, top=[])
    next_ad = 0.0
    logf = open(a.log, "w", newline=""); w = csv.writer(logf)
    w.writerow(["t_s", "state", "R", "G", "B", "A_R", "A_G", "A_B", "cC_hat", "cM_hat", "cY_hat", "dE2000", "io_mode",
                "mA_101", "mA_102", "mA_103", "spm_101", "spm_102", "spm_103", "ph", "p_bar", "temp_C",
                "yolo_liquid", "yolo_conf", "yolo_bubbles", "yolo_ms", "ad_ratio", "ad_cusum", "ad_alarm", "ad_top",
                "flow_101", "flow_102", "flow_103", "mass_101", "mass_102", "mass_103", "flow_status"])
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("flag", True))

    def shutdown(reason):
        print("종료:", reason)
        if not isinstance(bus, NullBus):
            for _ in range(3):
                bus.send_cmd(dict(cmd="run_enable", on=False)); bus.send_cmd(dict(cmd="safe")); time.sleep(0.1)

    # 3) 루프
    t_start, last_hb, period, next_print = time.monotonic(), -1.0, 1.0 / a.hz, 0.0
    try:
        while not stop["flag"]:
            t = time.monotonic() - t_start
            frame = cam.read()
            rgb, A = cam.roi_rgb8(frame), cam.roi_absorbance(frame, cfg.camera.I0)
            tele = bus.latest()
            frame_i += 1
            if det is not None and frame_i % a.yolo_every == 0:
                yolo_res = det.detect(frame)
                if yolo_res["bubbles"] >= a.bubble_hold and ctl.state == "MEASURE":
                    ctl.t_state = t                      # 기포가 가라앉을 때까지 측정 구간을 연장
                    print(f"{t:7.1f}s 기포 {yolo_res['bubbles']}개 → 측정 보류")
            if a.monitor:
                c = optics.nnls3(cfg.camera.E, A)
                de = optics.delta_e2000(rgb, rec.target_rgb8)
                print(f"{t:7.1f}s RGB {rgb.astype(int)} {optics.rgb8_to_hex(rgb)}  A {np.round(A,3)}  ĉ {np.round(c,2)}  ΔE {de:5.2f}")
                row_state, c_hat, de_v = "MONITOR", c, de
            else:
                if t - last_hb >= 0.2:
                    bus.send_cmd(dict(cmd="heartbeat", t=round(t, 2))); last_hb = t
                ctl.step(t, tele, rgb, bus, A)
                row_state, c_hat, de_v = ctl.state, ctl.c_hat, ctl.de
                if t >= next_print:
                    next_print = t + 1.0
                    print(f"{t:7.1f}s {ctl.state:8s} RGB {rgb.astype(int)} ĉ {np.round(c_hat,2)} ΔE {de_v:5.2f}"
                          + (f"  io={tele['mode']} V≈{tele['est_volume_mL']} mL" if tele else ""))
            pm = tele["pumps"] if tele else None
            if adet is not None and t >= next_ad and pm:
                next_ad = t + adet.dt
                row_ad = dict(t=t, mA_101=pm["P-101"]["cmd_mA"], mA_102=pm["P-102"]["cmd_mA"], mA_103=pm["P-103"]["cmd_mA"],
                              spm_101=pm["P-101"]["spm"], spm_102=pm["P-102"]["spm"], spm_103=pm["P-103"]["spm"],
                              p_bar=tele["pressure_bar"], ph=tele["ph"], temp_C=tele["temp_C"], rpm=float("nan"),
                              **{f"flow_{k}": (tk.get("flow_mL_min") if tk.get("valid") else float("nan"))
                                 for k, tk in ((p[-3:], tele.get("tanks", {}).get(p, {})) for p in ("P-101", "P-102", "P-103"))},
                              cC_hat=float(c_hat[0]), cM_hat=float(c_hat[1]), cY_hat=float(c_hat[2]), dE=float(de_v))
                o = adet.push(row_ad)
                if o:
                    was = ad_res["alarm"] or ad_res["cusum_alarm"]; ad_res = o
                    if (o["alarm"] or o["cusum_alarm"]) and not was:
                        print(f"{t:7.1f}s 이상탐지 알람: 점수/임계 {o['ratio']:.2f} CUSUM {o['cusum']:.1f} 주요 특징 {o['top'][0][0]}")
            w.writerow([round(t, 2), row_state, *rgb.astype(int), *np.round(A, 4), *np.round(c_hat, 3), round(float(de_v), 3),
                        tele["mode"] if tele else "", *([pm[p]["cmd_mA"] for p in pm] if pm else ["", "", ""]),
                        *([pm[p]["spm"] for p in pm] if pm else ["", "", ""]),
                        *([tele["ph"], tele["pressure_bar"], tele["temp_C"]] if tele else ["", "", ""]),
                        yolo_res["liquid"] or "", round(yolo_res["liquid_conf"], 3), yolo_res["bubbles"], round(yolo_res["ms"], 1),
                        round(ad_res["ratio"], 3), round(ad_res["cusum"], 2), int(ad_res["alarm"] or ad_res["cusum_alarm"]),
                        ad_res["top"][0][0] if ad_res["top"] else "",
                        *[(tele.get("tanks", {}).get(p, {}).get("flow_mL_min", "") if tele else "") for p in ("P-101", "P-102", "P-103")],
                        *[(tele.get("tanks", {}).get(p, {}).get("mass_g", "") if tele else "") for p in ("P-101", "P-102", "P-103")],
                        ";".join(f"{p[-3:]}:{tele['tanks'][p]['status']}" for p in tele.get("tanks", {}) if tele["tanks"][p]["status"] != "OK") if tele else ""])
            if ds:
                ds.maybe_record(t, None, c_hat, None, rgb, rec.target_rgb8, de_v, run_id="real", image=frame)
            if a.preview:
                _preview(frame, cs.roi, rgb, rec.target_rgb8, de_v, row_state)
            if not a.monitor and ctl.done:
                print("완료:", {k: v for k, v in ctl.result.items() if k not in ("log", "measurements")})
                if a.recipe:
                    import json as _json
                    lp = pathlib.Path(a.log).with_suffix(".recipe.json")
                    lp.write_text(_json.dumps(dict(log=ctl.log, measurements=ctl.measurements), ensure_ascii=False, indent=1))
                    print("레시피 로그:", lp)
                break
            if t > a.max_minutes * 60:
                print("최대 시간 초과"); break
            time.sleep(max(0.0, period - ((time.monotonic() - t_start) - t)))
    except Exception as e:                      # 어떤 예외든 SAFE 로
        shutdown(f"예외 {e!r}"); raise
    finally:
        shutdown("정상 종료" if not stop["flag"] else "사용자 중단")
        logf.close()
        if ds:
            ds.close()
        cam.stop()
        try:
            import cv2; cv2.destroyAllWindows()
        except Exception:
            pass
    return 0


def _preview(frame, roi, rgb, target, de, state):
    import cv2
    x, y, w, h = [int(v) for v in roi]
    img = frame[:, :, ::-1].copy()
    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
    cv2.rectangle(img, (10, 10), (70, 70), tuple(int(v) for v in rgb[::-1]), -1)
    cv2.rectangle(img, (80, 10), (140, 70), tuple(int(v) for v in np.asarray(target)[::-1]), -1)
    cv2.putText(img, f"{state} dE={de:.2f}", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.imshow("AI node (q=stop)", img)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        raise KeyboardInterrupt


if __name__ == "__main__":
    sys.exit(main())
