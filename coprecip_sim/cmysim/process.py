"""공정 모델: 스톡 탱크, 반응기 물질수지, 교반 혼합 지연."""
from __future__ import annotations
import numpy as np
from .config import TankSpec, ReactorSpec, DYES
from .ph_control import PHModel, PHProbe, BufferSpecies


class StockTank:
    def __init__(self, spec: TankSpec, dye: str):
        self.spec, self.dye = spec, dye
        self.volume_mL = spec.volume_mL
        self.conc_mg_L = spec.conc_mg_L

    def draw(self, vol_mL: float) -> float:
        """빨아낸 부피를 돌려준다 (탱크가 비면 0)."""
        v = min(vol_mL, max(self.volume_mL, 0.0))
        self.volume_mL -= v
        return v

    @property
    def level_ok(self) -> bool:
        return self.volume_mL > self.spec.low_level_mL

    @property
    def level_frac(self) -> float:
        return self.volume_mL / self.spec.volume_mL


class Reactor:
    """완전혼합 반투입(semi-batch) 반응기.

    - 진짜 농도 c_true = m / V (물질수지)
    - 카메라가 보는 농도 c_obs 는 교반 혼합시간 t_m = mix_K/rpm 에 따라 1차 지연 (τ = t_m/3 → t_m 에서 95 %)
    """

    def __init__(self, spec: ReactorSpec, rng=None):
        self.spec = spec
        self.V_mL = spec.heel_mL
        self.m_mg = np.zeros(3)
        self.c_obs = np.zeros(3)
        self.rpm = spec.rpm
        self.temp_C = spec.temp_C
        self.overflow = False
        self.ph_model = PHModel(spec.heel_mL / 1000.0, spec.ph, [BufferSpecies(c, pk) for c, pk in spec.buffers])
        self.ph_probe = PHProbe(spec.probe_tau_s, rng=rng)
        self.ph_mixed = spec.ph
        self.ph = spec.ph                 # 프로브가 읽는 값 (SimHAL.read_ph 가 트랜스미터로 양자화)
        self.acid_load_mol_min = spec.acid_load_mol_min
        self.naoh_mL = 0.0

    def add(self, dye_idx: int, vol_mL: float, conc_mg_L: float):
        self.m_mg[dye_idx] += vol_mL * conc_mg_L / 1000.0
        self.V_mL += vol_mL
        self.ph_model.add_water(vol_mL)
        if self.V_mL > self.spec.v_max_mL:
            self.overflow = True

    def add_base(self, vol_mL: float, conc_mol_L: float):
        """NaOH 투입 (pH 제어용 펌프). 염료 질량은 그대로, 부피만 늘고 염기가 더해진다."""
        self.V_mL += vol_mL
        self.naoh_mL += vol_mL
        self.ph_model.add_base(vol_mL, conc_mol_L)
        if self.V_mL > self.spec.v_max_mL:
            self.overflow = True

    @property
    def c_true(self) -> np.ndarray:
        return self.m_mg / (self.V_mL / 1000.0)

    def mixing_time_s(self) -> float:
        return np.inf if self.rpm < 1 else self.spec.mix_K / self.rpm

    def step(self, dt: float):
        tm = self.mixing_time_s()
        if self.acid_load_mol_min > 0:
            self.ph_model.add_acid(self.acid_load_mol_min / 60.0 * dt)
        ph_true = self.ph_model.pH()
        if np.isfinite(tm):
            tau = tm / 3.0
            self.c_obs += (self.c_true - self.c_obs) * (1 - np.exp(-dt / tau))
            self.ph_mixed += (ph_true - self.ph_mixed) * (1 - np.exp(-dt / tau))
        self.ph = self.ph_probe.step(self.ph_mixed, dt)

    @property
    def ph_true(self) -> float:
        return self.ph_model.pH()

    def final_volume_for(self, c_target: np.ndarray, c_stock: np.ndarray) -> float:
        """목표 농도 c_target 을 heel 에 스톡으로 맞출 때의 최종 부피. V_f = V_heel / (1 − Σ c_j/c_s,j)."""
        return self.V_mL / (1.0 - float(np.sum(c_target / c_stock)))


def dose_volumes(V_heel_mL: float, c_target: np.ndarray, c_stock: np.ndarray) -> np.ndarray:
    """세 염료를 동시에 넣을 때 각 투입 부피 V_j = c_j · V_f / c_s,j (대화의 V_dose 식을 3성분으로 확장)."""
    frac = np.sum(c_target / c_stock)
    if frac >= 1.0:
        raise ValueError("스톡 농도로는 도달할 수 없는 목표 농도")
    V_f = V_heel_mL / (1.0 - frac)
    return c_target * V_f / c_stock
