"""Tier C 공침 아날로그: CaCl₂ + Na₂CO₃ → CaCO₃ (+염료 공동 담지) 의 단순 모델 (통합 시험용, 정량 모델 아님).

- 화학종: Ca²⁺, 총 탄산(C_T), 고체 CaCO₃, 구연산(착화제, 침전 억제)
- 탄산 평형: pKa1 6.35, pKa2 10.33 → 유리 CO₃²⁻ 분율 α₂(pH)
- 과포화도 S = [Ca²⁺][CO₃²⁻] / Ksp (Ksp 3.3e-9, 칼사이트). S > 1 이면 침전 r = k·V·(√S − 1)² [mol/s], 구연산은 k 를 줄임
- 탁도 NTU ≈ k_turb × 고체 농도[g/L]. 입경 d50 은 자리표시자 proxy (실제 답은 현미경 + YOLO)
- pH 결합: Na₂CO₃ 투입 = 강양이온 2n + 탄산 완충 n (두 pKa 를 독립 단양성자산으로 근사), CaCl₂ 투입 = 중성(강양이온 2n + 강음이온 2n),
  CaCO₃ 침전 = Ca²⁺ 2m 제거 + 탄산 m 제거 → pH 가 내려간다 (실제 거동과 정성적으로 같음)
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .ph_control import BufferSpecies

KSP = 3.3e-9
PKA1, PKA2 = 6.35, 10.33
MW_CACO3 = 100.09


@dataclass
class PrecipSpec:
    k_precip: float = 2e-6         # mol/(L·s) at (√S−1)² = 1
    k_turb_ntu_per_g_L: float = 400.0
    citrate_inhibit: float = 50.0  # k /= (1 + citrate_mM × 이 값/1000)  … 자리표시자


class PrecipModel:
    def __init__(self, ph_model, spec: PrecipSpec | None = None):
        self.spec = spec or PrecipSpec()
        self.ph = ph_model
        self.ca_mol = 0.0; self.ct_mol = 0.0; self.solid_mol = 0.0; self.citrate_mol = 0.0
        self.turbidity_ntu = 0.0; self.S = 0.0; self.d50_um = 0.0
        self._b1 = BufferSpecies(0.0, PKA1); self._b2 = BufferSpecies(0.0, PKA2)
        self.ph.buffers += [self._b1, self._b2]
        self.precip_rate_mol_s = 0.0

    # ---- 피드
    def add_cacl2(self, vol_mL: float, conc_mol_L: float):
        n = vol_mL / 1000.0 * conc_mol_L
        self.ca_mol += n
        self.ph.B += 2 * n; self.ph.A += 2 * n          # 중성염
        self.ph.add_water(vol_mL)

    def add_na2co3(self, vol_mL: float, conc_mol_L: float):
        n = vol_mL / 1000.0 * conc_mol_L
        self.ct_mol += n
        self.ph.B += 2 * n                              # Na⁺ 2n
        self.ph.add_water(vol_mL)
        self._sync_buffers()

    def add_citrate(self, vol_mL: float, conc_mol_L: float):
        self.citrate_mol += vol_mL / 1000.0 * conc_mol_L
        self.ph.add_water(vol_mL)

    def _sync_buffers(self):
        V = self.ph.V
        self._b1.conc_mol_L = self.ct_mol / V
        self._b2.conc_mol_L = self.ct_mol / V

    # ---- 시간 전진
    def step(self, dt: float, pH: float):
        V = self.ph.V
        if self.ct_mol <= 0 or self.ca_mol <= 0:
            self.S = 0.0; self.precip_rate_mol_s = 0.0
        else:
            h = 10 ** (-pH); k1, k2 = 10 ** -PKA1, 10 ** -PKA2
            alpha2 = (k1 * k2) / (h * h + k1 * h + k1 * k2)
            ca, co3 = self.ca_mol / V, self.ct_mol / V * alpha2
            self.S = ca * co3 / KSP
            if self.S > 1.0:
                citr_mM = self.citrate_mol / V * 1000.0
                k = self.spec.k_precip / (1.0 + citr_mM * self.spec.citrate_inhibit / 1000.0)
                r = k * V * (math.sqrt(self.S) - 1.0) ** 2             # mol/s
                m = min(r * dt, self.ca_mol, self.ct_mol * alpha2 * 0.5)  # 가용량 제한
                self.ca_mol -= m; self.ct_mol -= m; self.solid_mol += m
                self.ph.B -= 2 * m                                     # Ca²⁺ 제거 (탄산 완충도 같이 줄어 pH 하강)
                self.precip_rate_mol_s = m / dt if dt > 0 else 0.0
                self._sync_buffers()
            else:
                self.precip_rate_mol_s = 0.0
        solid_g_L = self.solid_mol * MW_CACO3 / V
        self.turbidity_ntu = self.spec.k_turb_ntu_per_g_L * solid_g_L
        # 입경 proxy: 과포화도가 낮고 구연산이 적을수록 크다 (0~30 µm). 실제 값은 현미경/YOLO 로.
        s_eff = max(self.S, 1.0)
        self.d50_um = 30.0 / (1.0 + math.log(s_eff)) / (1.0 + self.citrate_mol / V * 1000.0 / 5.0) if self.solid_mol > 0 else 0.0
        return dict(S=self.S, solid_g_L=solid_g_L, turbidity_ntu=self.turbidity_ntu, d50_um=self.d50_um,
                    ca_mM=self.ca_mol / V * 1000.0, ct_mM=self.ct_mol / V * 1000.0)
