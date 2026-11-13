"""RGB 영상 ↔ CMY 농도 (PDF 'CMY 염료 농도의 RGB 영상 기반 정량 보고서' 7장 절차) + 색차."""
from __future__ import annotations
import itertools
import numpy as np


# ---------- Beer–Lambert 정방향 ----------
def conc_to_absorbance(E: np.ndarray, c: np.ndarray) -> np.ndarray:
    return E @ np.asarray(c, float)


def absorbance_to_linear(A: np.ndarray, I0: np.ndarray, glare: float = 0.0) -> np.ndarray:
    return I0 * 10.0 ** (-A) + glare


def linear_to_code(I: np.ndarray, gamma: float = 2.2) -> np.ndarray:
    """선형 세기(0~1) → 8비트 코드값 (감마 인코딩)."""
    return np.clip(I, 0.0, 1.0) ** (1.0 / gamma) * 255.0


def code_to_linear(V: np.ndarray, gamma: float = 2.2) -> np.ndarray:
    return (np.clip(np.asarray(V, float), 0.0, 255.0) / 255.0) ** gamma


def conc_to_rgb8(E, I0, c, gamma=2.2, glare=0.0) -> np.ndarray:
    return np.round(linear_to_code(absorbance_to_linear(conc_to_absorbance(E, c), I0, glare), gamma))


# ---------- 역산 ----------
def nnls3(E: np.ndarray, A: np.ndarray) -> np.ndarray:
    """3변수 비음수 최소제곱. 지지집합 8개를 전부 시험해 잔차 최소인 비음수 해를 고른다."""
    n = E.shape[1]
    best, best_r = np.zeros(n), np.inf
    for k in range(1, n + 1):
        for S in itertools.combinations(range(n), k):
            S = list(S)
            x, *_ = np.linalg.lstsq(E[:, S], A, rcond=None)
            if np.all(x >= -1e-12):
                r = np.linalg.norm(E[:, S] @ x - A)
                if r < best_r:
                    best_r, best = r, np.zeros(n)
                    best[S] = np.clip(x, 0, None)
    return best


def rgb8_to_conc(E, I0, rgb8, gamma=2.2, glare=0.0) -> np.ndarray:
    """단계 1 감마 제거 → 단계 2 흡광도 → 단계 5 비음수 최소제곱."""
    I = np.clip(code_to_linear(rgb8, gamma) - glare, 1e-6, None)
    A = -np.log10(np.clip(I / I0, 1e-6, None))
    return nnls3(E, np.clip(A, 0, None))


def condition_number(E) -> float:
    return float(np.linalg.cond(E))


# ---------- 색공간 / 색차 ----------
def srgb8_to_lab(rgb8) -> np.ndarray:
    v = np.asarray(rgb8, float) / 255.0
    lin = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = M @ lin
    wp = np.array([0.95047, 1.0, 1.08883])
    r = xyz / wp
    f = np.where(r > 216 / 24389, np.cbrt(r), (24389 / 27 * r + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def delta_e76(rgb_a, rgb_b) -> float:
    return float(np.linalg.norm(srgb8_to_lab(rgb_a) - srgb8_to_lab(rgb_b)))


def delta_e2000(rgb_a, rgb_b, kL=1.0, kC=1.0, kH=1.0) -> float:
    """CIEDE2000 (Sharma 2005 구현식)."""
    L1, a1, b1 = srgb8_to_lab(rgb_a)
    L2, a2, b2 = srgb8_to_lab(rgb_b)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cm ** 7 / (Cm ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)

    def hp(a, b):
        if a == 0 and b == 0:
            return 0.0
        h = np.degrees(np.arctan2(b, a))
        return h + 360 if h < 0 else h

    h1p, h2p = hp(a1p, b1), hp(a2p, b2)
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        d = h2p - h1p
        dhp = d - 360 if d > 180 else (d + 360 if d < -180 else d)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp / 2))
    Lpm = (L1 + L2) / 2
    Cpm = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hpm = h1p + h2p
    else:
        s = h1p + h2p
        hpm = s / 2 if abs(h1p - h2p) <= 180 else ((s + 360) / 2 if s < 360 else (s - 360) / 2)
    T = (1 - 0.17 * np.cos(np.radians(hpm - 30)) + 0.24 * np.cos(np.radians(2 * hpm))
         + 0.32 * np.cos(np.radians(3 * hpm + 6)) - 0.20 * np.cos(np.radians(4 * hpm - 63)))
    dth = 30 * np.exp(-((hpm - 275) / 25) ** 2)
    RC = 2 * np.sqrt(Cpm ** 7 / (Cpm ** 7 + 25.0 ** 7))
    SL = 1 + 0.015 * (Lpm - 50) ** 2 / np.sqrt(20 + (Lpm - 50) ** 2)
    SC = 1 + 0.045 * Cpm
    SH = 1 + 0.015 * Cpm * T
    RT = -np.sin(np.radians(2 * dth)) * RC
    return float(np.sqrt((dLp / (kL * SL)) ** 2 + (dCp / (kC * SC)) ** 2 + (dHp / (kH * SH)) ** 2
                         + RT * (dCp / (kC * SC)) * (dHp / (kH * SH))))


def hex_to_rgb8(s: str) -> np.ndarray:
    s = s.lstrip("#")
    return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], float)


def rgb8_to_hex(rgb8) -> str:
    return "#%02X%02X%02X" % tuple(int(round(float(v))) for v in np.clip(rgb8, 0, 255))
