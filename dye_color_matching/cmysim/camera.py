"""실제 카메라 (AI 노드, Raspberry Pi 5).

세 가지 백엔드가 같은 인터페이스를 가진다.
  RealSenseCamera : Intel RealSense D4xx 컬러 스트림 (pyrealsense2)
  Picamera2Camera : 라즈베리파이 전용 카메라 (picamera2)
  OpenCVCamera    : /dev/videoN (USB 웹캠, 또는 RealSense 를 UVC 로 열 때)

공통
  read()            → H×W×3 uint8 RGB 프레임
  roi_rgb8(frame)   → ROI 평균 RGB 코드값 (3,)            … ΔE 계산·표시용
  roi_absorbance()  → ROI 평균 흡광도 A (3,)              … 농도 역산용
                      기준 영상(물만) 이 있으면 픽셀별 A 를 구해 평균 (PDF 8장: 광원 불균일 대책)
노출·게인·화이트밸런스는 반드시 수동 고정 (PDF 8장). 설정은 camera.json 에 둔다.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
import json, pathlib, time
import numpy as np
from . import optics


@dataclass
class CameraSettings:
    kind: str = "realsense"            # realsense | picamera2 | opencv
    width: int = 640
    height: int = 480
    fps: int = 30
    exposure: float = 100.0            # RealSense: 1~10000 (단위 ~0.1 ms, D435 컬러 기준). picamera2: µs
    gain: float = 16.0                 # RealSense 컬러 게인 0~128
    white_balance: float = 4600.0      # K
    device: str = ""                   # opencv 는 /dev/video 번호, realsense 는 시리얼 (빈 값 = 첫 장치)
    roi: list = field(default_factory=lambda: [220, 140, 200, 200])   # x, y, w, h
    gamma: float = 2.2                 # 코드값 → 선형 (sRGB 근사). "srgb" 정식 곡선을 쓰려면 0
    warmup_frames: int = 15
    ref_path: str = "camera_ref.npy"   # 물만 있을 때 ROI 선형 세기 (픽셀별)
    calib_path: str = "calibration.json"

    @classmethod
    def load(cls, path="camera.json"):
        p = pathlib.Path(path)
        return cls(**json.loads(p.read_text())) if p.exists() else cls()

    def save(self, path="camera.json"):
        pathlib.Path(path).write_text(json.dumps(asdict(self), indent=1, ensure_ascii=False))


def code_to_linear(V, gamma):
    v = np.clip(np.asarray(V, float), 0, 255) / 255.0
    if gamma and gamma > 0:
        return v ** gamma
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)   # 정식 sRGB


class CameraBase:
    def __init__(self, s: CameraSettings):
        self.s = s
        self.last_frame: np.ndarray | None = None
        self.ref: np.ndarray | None = None           # ROI 픽셀별 기준 선형 세기 (h, w, 3)
        p = pathlib.Path(s.ref_path)
        if p.exists():
            self.ref = np.load(p)

    # ---- 백엔드가 구현
    def start(self): ...
    def stop(self): ...
    def _grab(self) -> np.ndarray: ...

    # ---- 공통
    def read(self) -> np.ndarray:
        self.last_frame = self._grab()
        return self.last_frame

    def frame(self, *_a, **_k) -> np.ndarray:        # DatasetRecorder 호환
        return self.last_frame if self.last_frame is not None else self.read()

    def roi_crop(self, frame=None) -> np.ndarray:
        f = self.last_frame if frame is None else frame
        if f is None:
            f = self.read()
        x, y, w, h = [int(v) for v in self.s.roi]
        return f[y:y + h, x:x + w, :]

    def roi_rgb8(self, frame=None) -> np.ndarray:
        return np.round(self.roi_crop(frame).reshape(-1, 3).mean(axis=0))

    def roi_linear(self, frame=None) -> np.ndarray:
        return code_to_linear(self.roi_crop(frame), self.s.gamma)

    def roi_absorbance(self, frame=None, I0_vec=None) -> np.ndarray:
        """픽셀별 기준 영상이 있으면 A = mean(−log10(I/I_ref)), 없으면 ROI 평균과 I0 벡터로."""
        I = self.roi_linear(frame)
        if self.ref is not None and self.ref.shape == I.shape:
            A = -np.log10(np.clip(I, 1e-4, None) / np.clip(self.ref, 1e-4, None))
            return np.clip(A.reshape(-1, 3).mean(axis=0), 0, None)
        I0 = np.asarray(I0_vec if I0_vec is not None else (self.ref.reshape(-1, 3).mean(0) if self.ref is not None else [0.9] * 3))
        return np.clip(-np.log10(np.clip(I.reshape(-1, 3).mean(0), 1e-4, None) / I0), 0, None)

    def capture_reference(self, n=30, delay=0.05) -> np.ndarray:
        """물만 채운 상태에서 n 프레임 평균 → 픽셀별 기준 선형 세기 저장."""
        acc = None
        for _ in range(n):
            lin = self.roi_linear(self.read())
            acc = lin if acc is None else acc + lin
            time.sleep(delay)
        self.ref = acc / n
        np.save(self.s.ref_path, self.ref)
        return self.ref

    def average(self, n=10, delay=0.03):
        """n 프레임의 (ROI 평균 RGB, 흡광도) 평균."""
        rgbs, As = [], []
        for _ in range(n):
            f = self.read()
            rgbs.append(self.roi_rgb8(f)); As.append(self.roi_absorbance(f))
            time.sleep(delay)
        return np.mean(rgbs, 0), np.mean(As, 0), np.std(As, 0)


# ------------------------------------------------------------------ RealSense
class RealSenseCamera(CameraBase):
    def start(self):
        import pyrealsense2 as rs
        self.rs = rs
        self.pipe, cfg = rs.pipeline(), rs.config()
        if self.s.device:
            cfg.enable_device(self.s.device)
        cfg.enable_stream(rs.stream.color, self.s.width, self.s.height, rs.format.rgb8, self.s.fps)
        prof = self.pipe.start(cfg)
        dev = prof.get_device()
        color = next(sn for sn in dev.query_sensors() if sn.get_info(rs.camera_info.name).lower().startswith("rgb"))
        self.sensor = color

        def set_opt(opt, val):
            if color.supports(opt):
                r = color.get_option_range(opt)
                color.set_option(opt, float(np.clip(val, r.min, r.max)))
        # PDF 8장: 자동 노출·화이트밸런스 끄고 고정
        set_opt(rs.option.enable_auto_exposure, 0)
        set_opt(rs.option.exposure, self.s.exposure)
        set_opt(rs.option.gain, self.s.gain)
        set_opt(rs.option.enable_auto_white_balance, 0)
        set_opt(rs.option.white_balance, self.s.white_balance)
        set_opt(rs.option.backlight_compensation, 0)
        for _ in range(self.s.warmup_frames):
            self.pipe.wait_for_frames()
        return self

    def _grab(self):
        frames = self.pipe.wait_for_frames(timeout_ms=2000)
        c = frames.get_color_frame()
        return np.asanyarray(c.get_data()).copy()          # rgb8 → (H, W, 3)

    def stop(self):
        try:
            self.pipe.stop()
        except Exception:
            pass

    def info(self) -> dict:
        rs = self.rs
        out = {}
        for name in ("exposure", "gain", "white_balance", "enable_auto_exposure", "enable_auto_white_balance"):
            opt = getattr(rs.option, name)
            if self.sensor.supports(opt):
                out[name] = self.sensor.get_option(opt)
        return out


# ------------------------------------------------------------------ Pi 카메라
class Picamera2Camera(CameraBase):
    def start(self):
        from picamera2 import Picamera2
        self.cam = Picamera2()
        conf = self.cam.create_video_configuration(main={"size": (self.s.width, self.s.height), "format": "RGB888"})
        self.cam.configure(conf)
        self.cam.set_controls({"AeEnable": False, "AwbEnable": False,
                               "ExposureTime": int(self.s.exposure), "AnalogueGain": float(max(self.s.gain, 1.0)),
                               "ColourGains": (1.8, 1.6)})      # 화이트밸런스 고정 (값은 조명에 맞춰 조정)
        self.cam.start()
        time.sleep(0.5)
        for _ in range(self.s.warmup_frames):
            self.cam.capture_array()
        return self

    def _grab(self):
        a = self.cam.capture_array()
        return a[:, :, ::-1].copy() if a.shape[2] == 3 else a[:, :, :3][:, :, ::-1].copy()   # BGR→RGB

    def stop(self):
        try:
            self.cam.stop()
        except Exception:
            pass


# ------------------------------------------------------------------ OpenCV
class OpenCVCamera(CameraBase):
    def start(self):
        import cv2
        self.cv2 = cv2
        idx = int(self.s.device) if self.s.device.isdigit() else (self.s.device or 0)
        self.cap = cv2.VideoCapture(idx)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.s.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.s.height)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)          # v4l2: 1 = manual
        self.cap.set(cv2.CAP_PROP_EXPOSURE, self.s.exposure)
        self.cap.set(cv2.CAP_PROP_GAIN, self.s.gain)
        self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        self.cap.set(cv2.CAP_PROP_WB_TEMPERATURE, self.s.white_balance)
        if not self.cap.isOpened():
            raise RuntimeError(f"camera {idx} open failed")
        for _ in range(self.s.warmup_frames):
            self.cap.read()
        return self

    def _grab(self):
        ok, bgr = self.cap.read()
        if not ok:
            raise RuntimeError("frame grab failed")
        return bgr[:, :, ::-1].copy()

    def stop(self):
        try:
            self.cap.release()
        except Exception:
            pass


# ------------------------------------------------------------------ 가짜 카메라 (워크스테이션에서 CLI 점검용)
class FakeCamera(CameraBase):
    """카메라 없이 camera_tools / ai_node_main 흐름을 돌려 보기 위한 백엔드.
    device 필드에 'C,M,Y' mg/L 를 적으면 그 농도의 액체를 보는 것처럼 프레임을 만든다 (기본 0,0,0 = 물).
    환경변수 CMYSIM_FAKE_CONC 가 있으면 그 값이 우선한다 (실행 중 바꿔 가며 시험)."""

    def start(self):
        import os
        from .config import CameraSpec
        spec = CameraSpec()
        self.E, self.I0 = spec.E, spec.I0
        self.rng = np.random.default_rng(0)
        yy, xx = np.mgrid[0:self.s.height, 0:self.s.width]
        self.vig = 1 - 0.1 * (((xx - self.s.width / 2) / self.s.width) ** 2 + ((yy - self.s.height / 2) / self.s.height) ** 2)
        self._os = os
        return self

    def _conc(self):
        txt = self._os.environ.get("CMYSIM_FAKE_CONC") or (self.s.device if "," in self.s.device else "0,0,0")
        return np.array([float(v) for v in txt.split(",")])

    def _grab(self):
        I = optics.absorbance_to_linear(self.E @ self._conc(), self.I0)[None, None, :] * self.vig[:, :, None]
        I = I + self.rng.normal(0, 0.004, I.shape)
        return optics.linear_to_code(I, 2.2).astype(np.uint8)

    def stop(self):
        pass


class TelemetryCamera(CameraBase):
    """카메라 대신 I/O 노드(--sim --sim-camera) 텔레메트리의 'sim_camera' 관측을 쓴다. 2프로세스 통합시험용.
    AI 노드가 start() 뒤에 .bus 를 붙여 준다."""

    def start(self):
        self.bus = None; self._rgb = np.array([242.0, 242.0, 242.0]); return self

    def _grab(self):
        tele = self.bus.latest() if self.bus is not None else None
        sc = (tele or {}).get("sim_camera")
        if sc and sc.get("rgb"):
            self._rgb = np.array(sc["rgb"], float)
        return np.tile(self._rgb.astype(np.uint8), (self.s.height, self.s.width, 1))

    def roi_rgb8(self, frame=None):
        if frame is None:
            self.read()
        return self._rgb.copy()

    def roi_absorbance(self, frame=None, I0_vec=None):
        I = code_to_linear(self._rgb, self.s.gamma)
        I0 = np.asarray(I0_vec if I0_vec is not None else [0.9] * 3, float)
        return np.clip(-np.log10(np.clip(I / I0, 1e-4, None)), 0, None)

    def stop(self):
        pass


def open_camera(s: CameraSettings) -> CameraBase:
    cls = {"realsense": RealSenseCamera, "picamera2": Picamera2Camera, "opencv": OpenCVCamera, "fake": FakeCamera,
           "telemetry": TelemetryCamera}[s.kind]
    return cls(s).start()


# ------------------------------------------------------------------ 보정 파일
@dataclass
class Calibration:
    E: list                                  # 3×3, 행 = R,G,B 채널, 열 = C,M,Y  [흡광도/(mg/L)]
    I0: list                                 # ROI 평균 기준 선형 세기
    gamma: float = 2.2
    glare: float = 0.0
    cond: float = 0.0
    samples: list = field(default_factory=list)   # {"dye","conc","A":[..],"rgb":[..],"std":[..]}
    note: str = ""

    def save(self, path):
        pathlib.Path(path).write_text(json.dumps(asdict(self), indent=1, ensure_ascii=False))

    @classmethod
    def load(cls, path):
        return cls(**json.loads(pathlib.Path(path).read_text()))

    def apply_to(self, cfg):
        """SystemConfig.camera 에 실측값 주입 → Controller/계획이 그대로 쓴다."""
        cfg.camera.E = np.array(self.E, float)
        cfg.camera.I0 = np.array(self.I0, float)
        cfg.camera.gamma = self.gamma
        cfg.camera.glare = self.glare
        return cfg


def fit_E(samples: list, dyes=("C", "M", "Y")) -> tuple[np.ndarray, dict]:
    """단일 염료 시료들로 E 의 열을 구한다 (PDF 7장 단계 4): 염료 j 만 있을 때 A_k = E_kj · c_j → 원점 통과 기울기."""
    E = np.zeros((3, 3))
    report = {}
    for j, d in enumerate(dyes):
        pts = [(s["conc"], np.asarray(s["A"], float)) for s in samples if s["dye"] == d]
        if len(pts) < 2:
            raise ValueError(f"염료 {d}: 시료가 {len(pts)}개 — 서로 다른 농도 2개 이상 필요 (권장 4~5개)")
        c = np.array([p[0] for p in pts]); A = np.array([p[1] for p in pts])
        slope = (c @ A) / (c @ c)                               # 채널별 최소제곱 기울기 (원점 통과)
        E[:, j] = slope
        resid = A - np.outer(c, slope)
        ss_res = (resid ** 2).sum(0); ss_tot = ((A - A.mean(0)) ** 2).sum(0) + 1e-12
        report[d] = dict(n=len(pts), conc=c.tolist(), slope=slope.round(5).tolist(),
                         r2=np.round(1 - ss_res / ss_tot, 4).tolist(), max_A=float(A.max()))
    return E, report
