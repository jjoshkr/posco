"""장비·공정 사양. 숫자 출처는 README의 '가정과 출처' 표 참고."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

DYES = ("C", "M", "Y")           # 염료 순서 = 펌프 순서 (P-101, P-102, P-103)
PUMP_IDS = ("P-101", "P-102", "P-103")          # 아날로그(4–20 mA) 펌프
VALVE_IDS = ("XV-101", "XV-102", "XV-103")
PULSE_PUMP_IDS = ("P-104",)                      # 펄스(접점) 구동 펌프: 1 펄스 = 1 스트로크. 산 펌프 (양방향 pH 제어)
PULSE_VALVES = {"P-104": "XV-104"}


@dataclass
class PumpSpec:
    """ProMinent gamma/ X (GMXa 1602 기준) 솔레노이드 다이아프램 정량펌프, Analog(4–20 mA) 모드."""
    model: str = "GMXa 1602"
    stroke_mL: float = 0.19          # 1회 토출량 (100 % 스트로크 길이)
    max_spm: float = 200.0           # 최대 스트로크/분
    stroke_length: float = 1.0       # 0.3~1.0 권장 (30~100 %)
    i_start_mA: float = 4.4          # 첫 스트로크가 나오는 전류
    i_full_mA: float = 19.6          # 최고 속도 전류
    i_fault_mA: float = 3.8          # 이 아래면 신호 이상 → 펌프 정지(알람)
    repro: float = 0.01              # 토출 재현성 ±1 %
    input_ohm: float = 120.0         # mA 입력 저항
    fb_option_c: bool = True         # 옵션 C: 실제 스트로크를 4–20 mA로 출력
    relief_bar: float = 3.0          # 배압/릴리프 밸브 설정 (토출 막힘 시 이 압력으로 탱크 복귀)


@dataclass
class PulsePumpSpec:
    """gamma/X 외부 접점(펄스) 모드: 무전압 접점 1회 = 스트로크 1회. DIO → 포토커플러 → 펌프 접점 입력."""
    model: str = "GMXa 1602 (pulse)"
    stroke_mL: float = 0.19
    stroke_length: float = 1.0
    max_spm: float = 200.0
    pulse_ms: float = 20.0           # 접점 닫힘 유지 시간 (펌프 최소 펄스폭 이상)
    repro: float = 0.01


@dataclass
class DacChainSpec:
    """MCC 152 AO(0–5 V, 12 bit) → XTR111(RSET 2.49 kΩ, 4.016 mA/V) → 펌프."""
    v_full: float = 5.0
    bits: int = 12
    gain_err: float = 0.0            # 채널별 이득 오차 (MCC 152 최대 ±1.5 %)
    offset_V: float = 0.0
    mA_per_V: float = 4.016          # XTR111: I = 10·V/RSET
    i_max_mA: float = 24.0           # 전류 제한
    calibrated: bool = False         # True: 시작 시 2점 교정 수행 (실제 절차 bench calib 과 동일)


@dataclass
class AdcSpec:
    """MCC 118: 8ch, ±10 V, 12 bit. 4–20 mA 신호는 250 Ω 션트로 1–5 V."""
    v_range: float = 10.0
    bits: int = 12
    noise_V: float = 0.003
    shunt_ohm: float = 250.0


@dataclass
class TankSpec:
    volume_mL: float = 2000.0        # GL45 2 L 스톡병
    conc_mg_L: float = 1000.0        # 스톡 1.00 g/L (role == "dye")
    low_level_mL: float = 100.0      # 수위 스위치 (펌프 수위 입력 → 자동 정지)
    role: str = "dye"                # "dye" | "naoh" | "acid" | "cacl2" | "na2co3" | "citrate"  (dye 외에는 conc_mol_L 사용)
    conc_mol_L: float = 0.1


@dataclass
class ReactorSpec:
    v_max_mL: float = 5000.0         # 반응기 공칭 5 L
    heel_mL: float = 2000.0          # 초기 DI수
    rpm: float = 300.0
    rpm_max: float = 1000.0          # 교반기 4–20 mA ↔ 0–rpm_max (가정)
    mix_K: float = 3000.0            # t_m ≈ mix_K / rpm [s]  (300 rpm → 10 s)
    temp_C: float = 25.0
    ph: float = 7.0                  # 초기 pH
    buffers: tuple = ((0.005, 6.35),)   # 완충종 (conc mol/L, pKa). Tier B 구연산: ((0.01, 4.8),)
    probe_tau_s: float = 8.0         # pH 프로브 1차 지연
    acid_load_mol_min: float = 0.0   # 산 부하 (금속염 피드가 OH− 를 소모하는 효과), 레시피/고장으로 바꿈
    dye_mg_L: tuple = (0.0, 0.0, 0.0)  # heel 에 미리 녹여 둔 염료 (Tier C: 펌프는 피드에 쓰므로)


@dataclass
class CameraSpec:
    """흰 배경 반사형 기준. E에는 L_eff가 이미 포함(단위: 흡광도 / (mg/L))."""
    E: np.ndarray = field(default_factory=lambda: np.array([
        [0.030, 0.004, 0.000],   # R 채널 ← C(시안)이 주로 흡수
        [0.005, 0.028, 0.003],   # G 채널 ← M(마젠타)
        [0.000, 0.004, 0.025],   # B 채널 ← Y(옐로)
    ]))
    I0: np.ndarray = field(default_factory=lambda: np.array([0.90, 0.90, 0.90]))  # 물만 있을 때 선형 세기
    gamma: float = 2.2
    glare: float = 0.015             # 유리/수면 정반사 (염료와 무관한 가산 성분)
    pixel_noise: float = 0.02        # 픽셀 단위 선형 세기 잡음 (표준편차)
    roi_pixels: int = 4000           # ROI 평균에 쓰는 픽셀 수
    exposure_drift: float = 0.0      # 1.0 = 정상, 0.9 = 10 % 어두워짐 (고장 주입용)
    turb_K_ntu: float = 300.0        # 탁도 → 백색 혼입 w = NTU/(NTU+K). 침전이 생기면 카메라가 흰빛으로 덮인다
    fps: float = 10.0


@dataclass
class NetworkSpec:
    telemetry_hz: float = 10.0
    heartbeat_timeout_s: float = 1.0 # AI 노드 하트비트 끊기면 I/O 노드 SAFE


@dataclass
class SystemConfig:
    pump: PumpSpec = field(default_factory=PumpSpec)
    pulse_pump: PulsePumpSpec = field(default_factory=PulsePumpSpec)
    dac: DacChainSpec = field(default_factory=DacChainSpec)
    adc: AdcSpec = field(default_factory=AdcSpec)
    # 탱크 0~2 = 염료(또는 naoh 역할), 탱크 3 = P-104 (기본 산 0.1 M)
    tanks: tuple = field(default_factory=lambda: (TankSpec(), TankSpec(), TankSpec(), TankSpec(role="acid", conc_mol_L=0.1)))
    reactor: ReactorSpec = field(default_factory=ReactorSpec)
    camera: CameraSpec = field(default_factory=CameraSpec)
    net: NetworkSpec = field(default_factory=NetworkSpec)
    dt: float = 0.1                  # 시뮬레이션 시간 간격 [s]
    seed: int = 0
    # MCC 152 2장 채널 배정 (대화에서 확정된 것)
    channel_map: dict = field(default_factory=lambda: {
        "P-101": ("mcc152#1", "AO0"), "P-102": ("mcc152#1", "AO1"),
        "P-103": ("mcc152#2", "AO0"), "STIRRER": ("mcc152#2", "AO1"),
        "XV-101": ("mcc152#1", "DIO4"), "XV-102": ("mcc152#1", "DIO5"),
        "XV-103": ("mcc152#2", "DIO4"), "RUN_ENABLE": ("mcc152#2", "DIO5"),
        "P-104": ("mcc152#2", "DIO6"), "XV-104": ("mcc152#2", "DIO7"),       # 펄스 펌프 + 밸브 (예비 DIO 사용)
        "FB-101": ("mcc118", "CH1"), "FB-102": ("mcc118", "CH2"), "FB-103": ("mcc118", "CH3"),
        "PH": ("mcc118", "CH0"), "PRESSURE": ("mcc118", "CH4"), "TEMP": ("mcc134", "CH0"),
    })


def pump_max_rate_mL_min(cfg: SystemConfig) -> float:
    p = cfg.pump
    return p.stroke_mL * p.stroke_length * p.max_spm
