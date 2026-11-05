"""python -m pytest coprecip_sim/tests -q  (저장소 루트에서) 또는 cd coprecip_sim && python -m pytest -q"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np
from cmysim.config import SystemConfig, PUMP_IDS
from cmysim import optics
from cmysim.process import dose_volumes, Reactor
from cmysim.hardware import GammaXPump, PumpChannel
from cmysim.control import plan_doses, Recipe
from cmysim.experiment import run_once, make_recipe
from cmysim.nodes import SimPlant, SimHAL, IONode, Bus


def test_optics_roundtrip():
    cfg = SystemConfig(); cam = cfg.camera
    c = np.array([20.0, 8.0, 15.0])
    rgb = optics.conc_to_rgb8(cam.E, cam.I0, c, cam.gamma, cam.glare)
    c_hat = optics.rgb8_to_conc(cam.E, cam.I0, rgb, cam.gamma, cam.glare)
    assert np.allclose(c, c_hat, atol=0.6)          # 8비트 양자화 한계 안
    assert optics.nnls3(cam.E, np.zeros(3)).sum() == 0


def test_delta_e2000_known_pair():
    # Sharma 테스트 데이터 1번 (Lab) 은 sRGB 경로라 직접 못 쓰므로 동일색=0, 흑백=큰 값만 확인
    assert optics.delta_e2000([100, 150, 200], [100, 150, 200]) == 0.0
    assert optics.delta_e2000([0, 0, 0], [255, 255, 255]) > 90


def test_dose_volume_mass_balance():
    c_t = np.array([30.0, 10.0, 25.0]); c_s = np.array([1000.0, 1000.0, 1000.0]); V0 = 2000.0
    V = dose_volumes(V0, c_t, c_s)
    r = Reactor(SystemConfig().reactor)
    for j in range(3):
        r.add(j, V[j], c_s[j])
    assert np.allclose(r.c_true, c_t, rtol=1e-9)


def test_pump_curve_and_fault():
    rng = np.random.default_rng(0)
    p = GammaXPump(SystemConfig().pump, rng, "P-101")
    assert p.spm_from_mA(4.0) == 0.0 and p.spm_from_mA(19.6) == 200.0
    assert abs(p.spm_from_mA(12.0) - 200 * (12 - 4.4) / 15.2) < 1e-9
    p.s.paused = False
    vol = []
    for _ in range(600):                          # 60 s @ 19.6 mA → 200 스트로크 ≈ 38 mL
        p.step(19.6, 0.1, True, vol.append)
    assert 195 <= p.s.strokes_total <= 201 and abs(sum(vol) - 38.0) < 1.5
    p.step(2.0, 0.1, True, vol.append)            # 3.8 mA 아래 → 알람
    assert p.s.fault.startswith("SIGNAL")


def test_dac_chain_calibration():
    cfg = SystemConfig()
    ch = PumpChannel(cfg.dac, gain_err=0.015); ch.enable(True)
    assert abs(ch.set_mA(12.0) - 12.18) < 0.03     # 교정 전 +1.5 %
    ch.calibrate_two_point(lambda: ch.actual_mA)
    assert abs(ch.set_mA(12.0) - 12.0) < 0.01


def test_interlock_valve_closed():
    cfg = SystemConfig(); plant = SimPlant(cfg); bus = Bus(); io = IONode(cfg, SimHAL(plant), bus)
    bus.send_cmd(dict(cmd="arm")); bus.send_cmd(dict(cmd="run_enable", on=True))
    bus.send_cmd(dict(cmd="pump", id="P-101", mA=12.0))     # 밸브 안 열고 펌프
    io.tick(0.1)
    assert io.cmd_mA["P-101"] == 0.0 and any("INTERLOCK" in a[1] for a in io.alarms)


def test_watchdog_goes_safe():
    cfg = SystemConfig(); plant = SimPlant(cfg); bus = Bus(); io = IONode(cfg, SimHAL(plant), bus)
    bus.send_cmd(dict(cmd="arm")); bus.send_cmd(dict(cmd="run_enable", on=True))
    bus.send_cmd(dict(cmd="valve", id="XV-101", open=True)); bus.send_cmd(dict(cmd="pump", id="P-101", mA=12.0))
    io.tick(0.1); assert io.mode == "RUN" and io.cmd_mA["P-101"] == 12.0
    io.tick(1.5)                                   # 하트비트 없음
    assert io.mode == "SAFE" and io.cmd_mA["P-101"] == 0.0 and not plant.run_enabled


def test_closed_loop_reaches_target():
    cfg = SystemConfig(seed=1)
    rec, _ = make_recipe(cfg, "#5A8F7B", dose_minutes=1.0)
    res = run_once(cfg, rec, 400.0)
    assert res["matched"] and res["dE2000_true"] < 1.5 and res["io_mode"] == "SAFE"
    assert np.allclose(res["c_true"], res["c_target"], atol=0.5)


def test_closed_loop_trims_stock_error():
    """스톡이 라벨보다 묽을 때(900 mg/L) open 은 빗나가고 closed 는 트림으로 맞춘다."""
    cfg = SystemConfig(seed=2)
    rec, _ = make_recipe(cfg, "#5A8F7B", dose_minutes=1.0)
    faults = ["stock_conc:P-101=900", "stock_conc:P-103=920"]
    ro = run_once(cfg, Recipe(**{**rec.__dict__, "mode": "open"}), 400.0, faults=faults)
    rc = run_once(cfg, rec, 600.0, faults=faults)
    assert ro["dE2000_true"] > 1.5 and rc["dE2000_true"] < 1.5 and rc["trims"] >= 1


def test_tank_empty_stops_pump_and_dose_times_out():
    cfg = SystemConfig(seed=3)
    rec, _ = make_recipe(cfg, "#5A8F7B", dose_minutes=1.0)
    res = run_once(cfg, rec, 400.0, faults=["tank_empty:P-101@10"])
    assert any("NO_STROKE P-101" in a[1] for a in res["alarms"]) and res["aborted"].startswith("DOSE timeout")
    assert res["tank_mL"][0] <= cfg.tanks[0].low_level_mL + 0.01 and not res["matched"]


# ---------------- 실제 카메라 코드 (하드웨어 없이 검증 가능한 부분)
from cmysim.camera import CameraBase, CameraSettings, fit_E, Calibration, code_to_linear


class FakeCamera(CameraBase):
    """optics 모델로 만든 가짜 프레임을 내는 카메라 (RealSense 자리)."""
    def __init__(self, s, E, I0, c, noise=0.0, seed=0):
        super().__init__(s); self.E, self.I0, self.c, self.noise = E, I0, np.asarray(c, float), noise
        self.rng = np.random.default_rng(seed)
        yy, xx = np.mgrid[0:s.height, 0:s.width]
        self.vig = 1 - 0.1 * (((xx - s.width / 2) / s.width) ** 2 + ((yy - s.height / 2) / s.height) ** 2)

    def start(self): return self
    def stop(self): pass
    def _grab(self):
        I = optics.absorbance_to_linear(self.E @ self.c, self.I0)[None, None, :] * self.vig[:, :, None]
        I = I + self.rng.normal(0, self.noise, I.shape)
        return optics.linear_to_code(I, 2.2).astype(np.uint8)


def test_camera_pixelwise_reference_corrects_vignetting(tmp_path):
    cfg = SystemConfig(); E, I0 = cfg.camera.E, cfg.camera.I0
    s = CameraSettings(width=64, height=48, roi=[8, 8, 48, 32], ref_path=str(tmp_path / "ref.npy"))
    cam = FakeCamera(s, E, I0, [0, 0, 0], noise=0.004)
    cam.capture_reference(n=5, delay=0)
    cam.c = np.array([20.0, 8.0, 15.0])
    _, A, _ = cam.average(n=5, delay=0)
    c_hat = optics.nnls3(E, A)
    assert np.allclose(c_hat, cam.c, atol=0.8)
    assert cam.roi_rgb8().shape == (3,) and cam.roi_crop().shape == (32, 48, 3)


def test_fit_E_recovers_matrix(tmp_path):
    cfg = SystemConfig(); E, I0 = cfg.camera.E, cfg.camera.I0
    s = CameraSettings(width=32, height=32, roi=[4, 4, 24, 24], ref_path=str(tmp_path / "ref.npy"))
    cam = FakeCamera(s, E, I0, [0, 0, 0], noise=0.002); cam.capture_reference(n=5, delay=0)
    samples = []
    for j, d in enumerate("CMY"):
        for conc in (5, 10, 15, 20):
            cam.c = np.eye(3)[j] * conc
            _, A, sd = cam.average(n=3, delay=0)
            samples.append(dict(dye=d, conc=conc, A=A.tolist(), rgb=[0, 0, 0], std=sd.tolist()))
    E_fit, rep = fit_E(samples)
    assert np.allclose(E_fit, E, atol=0.0015)
    assert all(min(r["r2"][k] for k in range(3) if E[k, "CMY".index(d)] > 0.01) > 0.99 for d, r in rep.items())
    cal = Calibration(E=E_fit.tolist(), I0=I0.tolist()); cal.save(tmp_path / "cal.json")
    cfg2 = Calibration.load(tmp_path / "cal.json").apply_to(SystemConfig())
    assert np.allclose(cfg2.camera.E, E_fit)


def test_controller_accepts_absorbance_directly():
    from cmysim.control import Controller
    cfg = SystemConfig(); rec, _ = make_recipe(cfg, "#5A8F7B")
    ctl = Controller(cfg, rec)
    c = np.array([10.0, 5.0, 7.0])
    rgb = optics.conc_to_rgb8(cfg.camera.E, cfg.camera.I0, c, 2.2, cfg.camera.glare)
    ctl.estimate(rgb, A=cfg.camera.E @ c)
    assert np.allclose(ctl.c_hat, c, atol=1e-6)
    assert code_to_linear(255, 0) == 1.0 and abs(code_to_linear(128, 2.2) - (128 / 255) ** 2.2) < 1e-12


def test_dataset_recorder_accepts_real_frame(tmp_path):
    from cmysim.vision import DatasetRecorder
    cfg = SystemConfig(); plant = SimPlant(cfg)
    rec = DatasetRecorder(tmp_path / "ds", plant.camera, every_s=0.0)
    frame = np.full((48, 64, 3), 120, np.uint8)
    rec.maybe_record(0.0, None, np.zeros(3), None, np.array([120, 120, 120]), np.array([90, 143, 123]), 10.0, "real", image=frame)
    rec.close()
    assert (tmp_path / "ds/images/real_00000.png").stat().st_size > 100
    assert '"c_true": null' in (tmp_path / "ds/index.jsonl").read_text()


# ---------------- I/O 노드 실제 보드 층 (가짜 daqhats 로 핀 배정·안전 순서 검증)
import importlib
import fake_daqhats as fdh
from cmysim.daqhats_hal import DaqHatsHAL, IOConfig


def _hal():
    fdh.LOG.clear()
    return DaqHatsHAL(IOConfig(ai_average=1), daqhats_module=fdh)


def test_daqhats_boot_is_failsafe():
    hal = _hal()
    b1, b2 = hal.b["mcc152#1"], hal.b["mcc152#2"]
    assert b1.ao == [0.0, 0.0] and b2.ao == [0.0, 0.0]
    for b in (b1, b2):
        assert b.direction[0] == 0 and b.pin_level(0) == 1          # OD(A) 출력, High = 꺼짐
        assert b.direction[2] == 0 and b.pin_level(2) == 1          # OD(B)
        assert b.direction[1] == 1 and b.direction[3] == 1          # EF 입력
        assert b.direction[4] == 0 and b.pin_level(4) == 0          # 밸브 OFF
    assert b2.pin_level(5) == 0                                     # RUN_ENABLE OFF
    # AO 0 V 가 OD 방향 전환보다 먼저
    ops = [(e[0], e[1]) for e in fdh.LOG]
    assert ops.index((0, "ao_all")) < ops.index((0, "cfg"))
    assert hal.b["mcc134"].types[0] == fdh.TcTypes.TYPE_K


def test_daqhats_pump_valve_mapping():
    hal = _hal()
    b1, b2, adc = hal.b["mcc152#1"], hal.b["mcc152#2"], hal.b["mcc118"]
    hal.pump_set_mA("P-102", 12.0)
    assert abs(b1.ao[1] - 12.0 / 4.016) < 1e-9 and b1.ao[0] == 0.0
    hal.pump_enable("P-102", True);  assert b1.pin_level(2) == 0        # OD(B) Low = 출력 켜짐
    hal.pump_enable("P-102", False); assert b1.pin_level(2) == 1
    hal.pump_set_mA("P-103", 24.0); assert b2.ao[0] == 5.0              # 클립
    hal.valve("XV-103", True);  assert b2.pin_level(4) == 1
    hal.valve("XV-101", True);  assert b1.pin_level(4) == 1 and b1.pin_level(5) == 0
    hal.run_enable(True);       assert b2.pin_level(5) == 1
    hal.stirrer_set_mA(12.0);   assert abs(b2.ao[1] - 12.0 / 4.016) < 1e-9 and b2.pin_level(2) == 0
    adc.volts[1] = 3.0                                                  # 12 mA × 250 Ω
    assert abs(hal.read_feedback_mA("P-101") - 12.0) < 1e-9
    adc.volts[0] = 1.0 + 4.0 * 7.0 / 14.0                               # pH 7 → 12 mA → 3 V
    assert abs(hal.read_ph() - 7.0) < 1e-9
    adc.volts[4] = 1.0 + 4.0 * 0.3                                      # 3 bar → 8.8 mA → 2.2 V
    assert abs(hal.read_pressure_bar() - 3.0) < 1e-9
    b1.inputs[1] = 0
    assert hal.read_ef_faults() == {"P-101": True, "P-102": False, "P-103": False, "STIRRER": False}
    hal.b["mcc134"].temps[0] = fdh.mcc134.OPEN_TC_VALUE
    assert hal.read_temp_C() != hal.read_temp_C()                       # NaN


def test_daqhats_close_order_and_calibration():
    hal = _hal()
    hal.run_enable(True); hal.valve("XV-102", True); hal.pump_enable("P-101", True); hal.pump_set_mA("P-101", 15.0)
    fdh.LOG.clear(); hal.close()
    b1, b2 = hal.b["mcc152#1"], hal.b["mcc152#2"]
    assert fdh.LOG[0] == (1, "dio", 5, 0)                               # RUN_ENABLE 먼저
    assert b1.ao[0] == 0.0 and b1.pin_level(0) == 1 and b1.pin_level(5) == 0 and b2.pin_level(5) == 0
    # 2점 교정: 실제 체인이 +2 % 많이 낸다고 가정
    hal2 = _hal()
    slope, gain, offset = hal2.calibrate_pump_channel("P-101", lambda: hal2.b["mcc152#1"].ao[0] * 4.016 * 1.02, settle=0)
    assert abs(slope - 1.02) < 1e-9
    hal2.pump_set_mA("P-101", 12.0)
    assert abs(hal2.b["mcc152#1"].ao[0] * 4.016 * 1.02 - 12.0) < 1e-6


def test_ionode_on_daqhats_hal_with_loopback():
    """IONode 가 진짜 HAL 위에서 arm → 밸브 → dose 를 수행하고, 피드백 루프백으로 스트로크를 세는지."""
    hal = _hal()
    cfg = SystemConfig(); bus = Bus(); io = IONode(cfg, hal, bus)
    b1, adc = hal.b["mcc152#1"], hal.b["mcc118"]
    assert b1.pin_level(0) == 1 and b1.pin_level(5) == 0
    bus.send_cmd(dict(cmd="arm")); bus.send_cmd(dict(cmd="run_enable", on=True))
    bus.send_cmd(dict(cmd="valve", id="XV-101", open=True)); bus.send_cmd(dict(cmd="dose", id="P-101", mA=12.0, strokes=10))
    t = 0.0
    for _ in range(200):
        t += 0.1
        # 펌프 옵션 C 루프백: OD 켜지고 mA 가 걸리면 100 spm 에 해당하는 12 mA 피드백 (3 V)
        adc.volts[1] = 3.0 if (b1.pin_level(0) == 0 and b1.ao[0] > 0) else 1.0
        bus.send_cmd(dict(cmd="heartbeat"))
        io.tick(t)
        if io.dose_target["P-101"] is None and io.strokes["P-101"] > 0:
            break
    assert 10 <= io.strokes["P-101"] < 11.5                             # 계획 10 스트로크 (한 틱 지연 허용)
    assert b1.ao[0] == 0.0 and b1.pin_level(0) == 1                     # 끝나면 0 mA + OD High
    assert io.mode == "RUN" and b1.pin_level(4) == 1                    # 밸브는 AI 노드가 닫을 때까지 열림
    io.tick(t + 2.0)                                                    # 하트비트 끊김
    assert io.mode == "SAFE" and b1.pin_level(4) == 0 and hal.b["mcc152#2"].pin_level(5) == 0


# ---------------- YOLO 데이터셋 파이프라인 (ultralytics 없이 검증 가능한 부분)
def test_recorder_bubble_labels_and_prepare(tmp_path):
    from cmysim.yolo_train import main as ymain
    import json as _json
    cfg = SystemConfig(seed=5); rec, _ = make_recipe(cfg, target_cmy=[20, 8, 15], dose_minutes=0.5)
    run_once(cfg, rec, 120.0, dataset_dir=tmp_path / "ds/run00", run_id="run00")
    labels = list((tmp_path / "ds/run00/labels").glob("*.txt"))
    assert labels
    txt = "\n".join(l.read_text() for l in labels)
    classes = {int(line.split()[0]) for line in txt.splitlines() if line.strip()}
    assert classes <= {0, 1, 2} and 2 in classes                       # 기포 자동 라벨 존재
    for line in txt.splitlines():
        vals = [float(v) for v in line.split()[1:]]
        assert all(0.0 <= v <= 1.0 for v in vals)
    idx = [_json.loads(l) for l in (tmp_path / "ds/run00/index.jsonl").read_text().splitlines()]
    assert any(r["n_bubbles"] > 0 for r in idx) and (tmp_path / "ds/run00/classes.txt").read_text().startswith("liquid_on_target")
    ymain(["prepare", "--src", str(tmp_path / "ds/run00"), "--out", str(tmp_path / "yolo"), "--split-by", "frame", "--copy"])
    assert (tmp_path / "yolo/data.yaml").exists() and (tmp_path / "yolo/regression.csv").exists()
    assert len(list((tmp_path / "yolo/images/train").glob("*.png"))) + len(list((tmp_path / "yolo/images/val").glob("*.png"))) == len(labels)
    assert (tmp_path / "yolo_cls/train/liquid_off_target").exists()
    ymain(["regress", "--csv", str(tmp_path / "yolo/regression.csv"), "--out", str(tmp_path / "w.npy")])
    assert (tmp_path / "w.npy").exists()


# ---------------- 레시피 실행기
from cmysim.recipe import validate as rvalidate, expand_matrix, RecipeExecutor, load_recipe, EXAMPLE
import yaml as _yaml


def test_recipe_validate_and_expand():
    r = _yaml.safe_load(EXAMPLE)
    assert rvalidate(r) == []
    bad = {"steps": [{"step": "dose", "pump": "P-9"}, {"step": "fly"}, {"foo": 1}]}
    errs = rvalidate(bad)
    assert len(errs) >= 3 and any("P-9" in e for e in errs) and any("fly" in e for e in errs)
    r["matrix"] = {"reactor.rpm": [150, 300], "steps[2].minutes": [1, 2]}
    runs = expand_matrix(r)
    assert len(runs) == 4 and runs[3]["reactor"]["rpm"] == 300 and runs[3]["steps"][2]["minutes"] == 2
    assert "matrix" not in runs[0] and runs[0]["name"].startswith("target_match_closed__")


def test_recipe_explicit_dose_and_measure():
    r = {"name": "t", "reactor": {"heel_mL": 2000, "rpm": 300}, "stocks": {"C": 800},
         "steps": [{"step": "stir", "rpm": 400},
                   {"step": "dose", "pumps": ["P-101", "P-103"], "ratio": [1, 3], "total_mL": 40, "minutes": 1},
                   {"step": "settle", "seconds": 15},
                   {"step": "measure", "label": "a"},
                   {"step": "dose", "pump": "P-102", "strokes": 50, "mA": 12.0},
                   {"step": "hold", "seconds": 20, "label": "b"},
                   {"step": "stop"}]}
    cfg = SystemConfig(seed=7)
    ex = RecipeExecutor(cfg, r)
    assert cfg.tanks[0].conc_mg_L == 800 and cfg.reactor.rpm == 300
    res = run_once(cfg, ex.r, 400.0, controller=ex)
    d = res["dosed_mL"]
    assert abs(d["P-101"] - 10) < 0.6 and abs(d["P-103"] - 30) < 1.0 and abs(d["P-102"] - 50 * 0.19) < 0.4
    assert [m["label"] for m in ex.measurements] == ["a", "b"] and ex.done and res["io_mode"] == "SAFE"
    assert abs(res["c_true"][0] - 10 * 800 / 2049.5) < 0.3                   # 800 mg/L 스톡 반영
    kinds = [k for _, k, _ in ex.log]
    assert kinds.count("step") == 7 and "done" in kinds


def test_recipe_fault_step_and_target(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text(_yaml.safe_dump({"name": "f", "target": {"hex": "#5A8F7B"},
                                  "steps": [{"step": "inject_fault", "kind": "tank_empty", "arg": "P-101"},
                                            {"step": "dose_to_target", "minutes": 0.5, "on_abort": "stop"},
                                            {"step": "measure", "label": "x"}, {"step": "stop"}]}))
    cfg = SystemConfig(seed=8)
    ex = RecipeExecutor(cfg, load_recipe(p))
    res = run_once(cfg, ex.r, 300.0, controller=ex)
    assert any(k == "fault" for _, k, _ in ex.log) and ex.aborted.startswith("DOSE") and res["tank_mL"][0] <= 100.01
    assert ex.done and not ex.measurements                                # on_abort: stop → measure 생략


# ---------------- 이상탐지
from cmysim import anomaly as AD


def _ad_dataset(tmp_path, n_normal=4, n_fault=2):
    from cmysim.experiment import save_timeseries_csv
    import json as _json
    for i in range(n_normal + n_fault):
        fault = i >= n_normal
        cfg = SystemConfig(seed=20 + i); rec, _ = make_recipe(cfg, target_cmy=[20 + i, 8, 15], dose_minutes=1.0)
        faults = ["tank_empty:P-101@30"] if fault else []
        res = run_once(cfg, rec, 150.0, faults=faults, run_id=f"r{i}")
        d = tmp_path / "ds" / ("fault" if fault else "normal") / f"r{i}"; d.mkdir(parents=True)
        save_timeseries_csv(res, d / "timeseries.csv")
        (d / "meta.json").write_text(_json.dumps(dict(fault_kind="tank_empty" if fault else "", fault_arg="P-101", t_fault=30.0 if fault else None)))
    return tmp_path / "ds"


def test_anomaly_features_offline_equals_online():
    rows = [dict(t=0.5 * i, mA_101=12.0, mA_102=0.0, mA_103=8.0, spm_101=100.0, spm_102=0.0, spm_103=47.0, p_bar=0.8,
                 ph=7.0, temp_C=25.0, rpm=300.0, cC_hat=0.1 * i, cM_hat=0.0, cY_hat=0.05 * i, dE=30 - i) for i in range(30)]
    fb = AD.FeatureBuilder(); feats = fb.available_features(rows)
    assert {"ph", "temp_C", "rpm"} <= set(feats) and "flow_101" not in feats       # 로드셀 열이 없으면 유량 특징 제외
    X = fb.matrix(rows, feats)
    fb.reset(); Y = np.array([[f[k] for k in feats] for f in (fb.push(r) for r in rows)])
    assert np.allclose(X, Y)
    j = feats.index("r_spm_101"); assert abs(X[-1, j] - (200 * (12 - 4.4) / 15.2 - 100)) < 1e-9
    assert X[-1, feats.index("d_dE")] == -2.0                                   # (−1)/0.5


def test_anomaly_pca_train_eval_online(tmp_path):
    ds = _ad_dataset(tmp_path)
    AD.main(["train", "--data", str(ds), "--model", "pca", "--out", str(tmp_path / "m"), "--val", "0.25", "--window", "10"])
    det = AD.Detector.load(tmp_path / "m")
    summary, res = AD.evaluate(det, ds, verbose=False)
    assert summary["n_fault"] == 2 and summary["detected"] == 2 and summary["median_delay_s"] < 15
    assert summary["false_alarm_rate"] < 0.05
    # 온라인 push 와 오프라인 score_rows 가 같은 점수
    rows = AD.resample(AD.canonical_rows(ds / "fault" / "r4" / "timeseries.csv"), 0.5)
    s, _, t = det.score_rows(rows)
    det.reset(); online = [o["score"] for o in (det.push(r) for r in rows) if o]
    assert np.allclose(s, online, rtol=1e-6)
    assert AD.fusion_score(dE=4.0, ae_ratio=2.0)[0] == 1.0 * 2.0 + 1.5 * 2.0


def test_anomaly_conv_numpy_matches_torch():
    try:
        import torch  # noqa: F401
    except ImportError:
        import pytest; pytest.skip("torch 없음")
    rng = np.random.default_rng(0)
    Xw = rng.normal(size=(64, 10, 6))
    m = AD.ConvAutoencoder(10, 6, latent=4, hidden=8).fit(Xw, epochs=2)
    s_t, _ = m.score(Xw[:5])
    m2 = AD.ConvAutoencoder(10, 6, latent=4, hidden=8); m2.np_weights = m.np_weights
    s_n, _ = m2.score(Xw[:5])
    assert np.allclose(s_t, s_n, rtol=1e-4, atol=1e-5)


# ---------------- 로드셀 유량
from cmysim.loadcell import LoadCellConfig, FlowEstimator, FlowCheck, SimLoadCell
from cmysim.process import StockTank


def test_flow_estimator_slope_and_disturbance():
    lc = LoadCellConfig(backend="sim"); est = FlowEstimator(lc, 0); chk = FlowCheck()
    rng = np.random.default_rng(1)
    t, g = 0.0, 2000.0
    for i in range(400):                               # 40 s @ 10 Hz, 20 mL/min = 0.3333 g/s
        t = i * 0.1; g = 2000.0 - 20 / 60 * t
        st = est.push(t, g + rng.normal(0, 0.05))
    assert st["valid"] and abs(st["flow_mL_min"] - 20.0) < 0.6 and abs(st["delivered_mL"] - 13.3) < 0.4
    assert chk.check(t, "P-101", 20.0, st)[0] == "OK"
    st = est.push(t + 0.1, g + 15.0)                   # 병을 건드림 → 무효
    assert not st["valid"] and est.n_disturb == 1 and chk.check(t + 0.1, "P-101", 20.0, st)[0] == "DISTURBED"
    # 공기 유입: 질량은 절반 속도로만 줄어듦 → 6 s 유지 후 FLOW_LOW
    est2 = FlowEstimator(lc, 0); chk2 = FlowCheck(); status = "OK"
    for i in range(400):
        tt = i * 0.1; st2 = est2.push(tt, 2000.0 - 10 / 60 * tt + rng.normal(0, 0.05))
        status, ratio = chk2.check(tt, "P-101", 20.0, st2)
    assert status == "FLOW_LOW" and abs(ratio - 0.5) < 0.1
    assert chk2.check(0, "P-102", 20.0, dict(mass_g=50.0, low=True, valid=True, flow_mL_min=0))[0] == "TANK_LOW"


def test_ionode_loadcell_telemetry_and_volume_mismatch():
    cfg = SystemConfig(seed=11); rec, _ = make_recipe(cfg, target_cmy=[20, 8, 15], dose_minutes=1.0)
    res = run_once(cfg, rec, 200.0, faults=["pump_air:P-101@20"])
    h = res["hist"]
    assert h["flow"].shape[1] == 3 and np.nanmax(h["mass"][:, 0]) > 1900           # 로드셀 질량 기록
    valid = ~np.isnan(h["flow"][:, 1])
    assert abs(np.nanmedian(h["flow"][valid & (h["cmd_mA"][:, 1] > 5), 1]) - np.nanmedian(
        h["fb_spm"][valid & (h["cmd_mA"][:, 1] > 5), 1]) * 0.19) < 1.0                 # 정상 펌프: 로드셀 ≈ 스트로크 유량
    al = " ".join(a[1] for a in res["alarms"])
    assert "FLOW_LOW P-101" in al and "VOLUME_MISMATCH P-101" in al
    assert "FLOW_LOW P-102" not in al and "FLOW_LOW P-103" not in al
    # 이상탐지 특징에 로드셀 유량이 들어가는지
    from cmysim.experiment import save_timeseries_csv
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        save_timeseries_csv(res, os.path.join(d, "ts.csv"))
        rows = AD.resample(AD.canonical_rows(os.path.join(d, "ts.csv")), 0.5)
    fb = AD.FeatureBuilder(); feats = fb.available_features(rows)
    assert "flow_101" in feats and "r_flow_101" in feats
    X = fb.matrix(rows, feats); j = feats.index("r_flow_101")
    t = np.array([r["t"] for r in rows])
    assert np.nanmean(X[(t > 40) & (t < 55), j]) > 5.0                               # 공기 유입 후 기대−실측 양수


# ---------------- pH 제어
from cmysim.ph_control import PHModel, PHProbe, PHController, PHGains, BufferSpecies, simulate, flow_to_mA


def test_ph_model_basic():
    m = PHModel(2.0, 7.0)
    assert abs(m.pH() - 7.0) < 1e-3
    p0 = m.pH(); m.add_base(10.0, 0.1); assert m.pH() > p0 + 0.2          # 염기 → pH 상승
    m.add_acid(0.002); assert m.pH() < 7.5                                 # 같은 몰의 산 → 되돌아옴
    m2 = PHModel(2.0, 5.0, [BufferSpecies(0.01, 4.8)])
    assert abs(m2.pH() - 5.0) < 1e-3 and m2.buffer_capacity() > 0.003      # 구연산 완충: β 수 mmol/L/pH
    pr = PHProbe(8.0, noise=0.0); pr.step(7.0, 0.0); ys = [pr.step(10.0, 1.0) for _ in range(8)]
    assert 8.7 < ys[-1] < 9.1                                              # 7 → 10 스텝, 1τ(8 s) 에서 63 %


def test_ph_controller_reaches_setpoint_without_overshoot():
    hist, ctl, model = simulate(10.5, 7.0, 2.0, 0.1, duration=600, seed=1)
    m = ctl.metrics()
    assert abs(hist["ph_meas"][-1] - 10.5) < 0.2 and m["overshoot"] < 0.3 and not ctl.fault
    assert np.where(np.abs(hist["ph_meas"] - 10.5) < 0.2)[0][0] * 0.5 < 400                     # 400 s 안에 ±0.2 도달
    # 산 부하가 들어와도 유지
    hist2, ctl2, _ = simulate(10.5, 7.0, 2.0, 0.1, load_mol_min=0.0002, load_start_s=200, duration=900, seed=2)
    assert abs(hist2["ph_meas"][-1] - 10.5) < 0.2 and hist2["flow"][-20:].mean() > 1.0   # 부하 보상 유량 (0.2 mmol/min ÷ 0.1 M = 2 mL/min)
    assert flow_to_mA(0) == 0.0 and abs(flow_to_mA(38.0) - 19.6) < 1e-9 and 4.4 < flow_to_mA(1.0) < 5.0


def test_ph_safety_limits():
    g = PHGains(cap_enabled=False, Kp=50.0)
    ctl = PHController(10.0, g, naoh_mol_L=0.1)
    ctl.update(0.0, 7.0); assert ctl.out == g.out_max
    ctl.update(1.0, 12.5); assert ctl.fault.startswith("PH_LIMIT") and ctl.out == 0.0
    ctl2 = PHController(10.0, g, naoh_mol_L=0.1)
    for i in range(200):                                                   # 100 s 동안 최대 투입인데 pH 가 안 움직임
        ctl2.update(i * 0.5, 7.0)
    assert ctl2.fault.startswith("STUCK")


def test_recipe_ph_control_step():
    r = {"name": "ph", "reactor": {"heel_mL": 2000, "rpm": 300},
         "ph": {"initial": 7.0, "naoh_pump": "P-103", "naoh_mol_L": 0.1},
         "steps": [{"step": "stir", "rpm": 300},
                   {"step": "ph_control", "pump": "P-103", "setpoint": 10.0, "seconds": 400, "label": "up"},
                   {"step": "stop"}]}
    cfg = SystemConfig(seed=9)
    ex = RecipeExecutor(cfg, r)
    assert cfg.tanks[2].role == "naoh"
    res = run_once(cfg, ex.r, 600.0, controller=ex)
    h = res["hist"]
    assert abs(h["ph"][-1] - 10.0) < 0.2 and h["naoh_mL"][-1] > 1.0 and res["dosed_mL"]["P-103"] > 1.0
    assert ex.measurements and ex.measurements[-1]["label"] == "up" and abs(ex.measurements[-1]["final_err"]) < 0.2
    assert res["c_true"][2] < 1e-6                                          # NaOH 펌프는 염료를 넣지 않음
    assert not any("INTERLOCK" in a[1] for a in res["alarms"])


# ---------------- 양방향 pH 제어 + 펄스 펌프
from cmysim.config import PULSE_PUMP_IDS


def test_bidirectional_ph_step_down_and_relay():
    hist, ctl, _ = simulate(10.5, 7.0, 2.0, 0.1, duration=900, seed=3, acid_mol_L=0.1, sp_steps=((400, 8.0),))
    m = ctl.metrics()
    assert abs(hist["ph_meas"][-1] - 8.0) < 0.2 and m["acid_mL"] > 1.0 and m["overshoot"] < 0.3 and not ctl.fault
    sgn = np.sign(hist["flow"]); nz = np.where(sgn != 0)[0]
    switches = [hist["t"][nz[i]] for i in range(1, len(nz)) if sgn[nz[i]] != sgn[nz[i - 1]]]
    assert all(b - a >= 10.0 - 1e-9 for a, b in zip(switches, switches[1:]))                   # 방향 전환 간격 ≥ min_switch_s
    _, ctl2, _ = simulate(10.0, 9.5, 2.0, 0.1, duration=900, mode="relay", acid_mol_L=0.1, relay_d=2.0)
    r = ctl2.relay_result()
    assert r and r["Ku"] > 0 and 20 < r["Tu"] < 300                                           # 부하 없이도 대칭 릴레이 진동


def test_ionode_pulse_pump_dosing_and_interlock():
    cfg = SystemConfig(seed=4); plant = SimPlant(cfg); bus = Bus(); io = IONode(cfg, SimHAL(plant), bus)
    bus.send_cmd(dict(cmd="arm")); bus.send_cmd(dict(cmd="run_enable", on=True))
    bus.send_cmd(dict(cmd="pulse_rate", id="P-104", spm=120)); io.tick(0.1)
    assert io.pulse_spm["P-104"] == 0.0 and any("INTERLOCK P-104" in a[1] for a in io.alarms)   # 밸브 닫힘
    bus.send_cmd(dict(cmd="valve", id="XV-104", open=True)); bus.send_cmd(dict(cmd="pulse_dose", id="P-104", strokes=20, spm=120))
    t = 0.1
    for _ in range(300):
        t += 0.1; bus.send_cmd(dict(cmd="heartbeat")); io.tick(t); plant.step(0.1)
        if io.pulse_target["P-104"] is None and io.pulse_strokes["P-104"] >= 20:
            break
    assert io.pulse_strokes["P-104"] == 20 and plant.pulse_pumps["P-104"].strokes_total == 20
    assert abs(plant.reactor.acid_mL - 20 * 0.19) < 0.2 and plant.reactor.ph_true < 6.9          # 산 0.1 M 3.8 mL → pH 하강
    tele = bus.latest(); assert tele["pulse_pumps"]["P-104"]["strokes"] == 20 and not tele["pulse_pumps"]["P-104"]["dosing"]
    assert 9.5 < t < 11.5                                                                       # 120 spm → 20 스트로크 ≈ 10 s


def test_daqhats_pulse_output_mapping():
    hal = _hal()
    fdh.LOG.clear(); hal.io.pulse_ms = 0.0
    assert hal.pulse("P-104") and fdh.LOG[:2] == [(1, "dio", 6, 1), (1, "dio", 6, 0)]
    hal.valve("XV-104", True); assert hal.b["mcc152#2"].pin_level(7) == 1
    hal.close(); assert hal.b["mcc152#2"].pin_level(7) == 0


def test_recipe_bidirectional_ph_with_pulse_acid_pump():
    r = load_recipe("recipes/tierB_ph_bidirectional.yaml")
    r["steps"] = r["steps"][:3] + [{"step": "stop"}]                                           # 동조 스텝 제외 (시간)
    cfg = SystemConfig(seed=12); ex = RecipeExecutor(cfg, r)
    assert cfg.tanks[3].role == "acid" and cfg.tanks[2].role == "naoh"
    res = run_once(cfg, ex.r, 800.0, controller=ex)
    labels = {m["label"]: m for m in ex.measurements}
    assert abs(labels["up"]["final_err"]) < 0.25 and abs(labels["down"]["final_err"]) < 0.25
    assert res["pulse_dosed_mL"]["P-104"] > 1.0 and res["acid_mL"] > 1.0 and labels["down"]["acid_mL"] > 1.0
    assert not any("INTERLOCK" in a[1] or "PULSE_IGNORED" in a[1] for a in res["alarms"])
