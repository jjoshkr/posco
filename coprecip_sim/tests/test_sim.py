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
