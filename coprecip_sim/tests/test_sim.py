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
