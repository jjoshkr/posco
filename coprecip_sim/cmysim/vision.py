"""AI 노드 쪽 카메라 모델 (RealSense D4xx RGB 대역) + 데이터셋 기록기.

- 프레임: 반응기 ROI를 합성. 색은 optics 모델, 여기에 픽셀 잡음·비네팅·기포 반점을 얹는다.
- 라벨: 프레임마다 JSON(진짜 농도, 추정 농도, ΔE, 목표) + YOLO txt(클래스 0=on_target, 1=off_target, 액체 ROI 박스).
  나중에 진짜 RealSense 프레임으로 바꿔 끼워도 라벨 형식은 같다.
"""
from __future__ import annotations
import json, struct, zlib, pathlib
import numpy as np
from .config import CameraSpec
from . import optics


class SyntheticCamera:
    def __init__(self, spec: CameraSpec, rng: np.random.Generator, size=(96, 128)):
        self.spec, self.rng, self.size = spec, rng, size
        self.exposure = 1.0
        yy, xx = np.mgrid[0:size[0], 0:size[1]]
        cy, cx = (size[0] - 1) / 2, (size[1] - 1) / 2
        r = np.sqrt(((yy - cy) / cy) ** 2 + ((xx - cx) / cx) ** 2)
        self._vignette = 1.0 - 0.08 * r ** 2   # 조명 불균일 (PDF 8장 '픽셀별 기준 영상' 대책 대상)

    def linear_mean(self, c_obs: np.ndarray) -> np.ndarray:
        s = self.spec
        A = optics.conc_to_absorbance(s.E, c_obs)
        return optics.absorbance_to_linear(A, s.I0, s.glare) * self.exposure

    def roi_rgb8(self, c_obs: np.ndarray) -> np.ndarray:
        """ROI 평균 RGB 코드값 (픽셀 잡음은 √N 으로 줄어든다)."""
        I = self.linear_mean(c_obs)
        noise = self.rng.normal(0, self.spec.pixel_noise / np.sqrt(self.spec.roi_pixels), 3)
        return np.round(optics.linear_to_code(I + noise, self.spec.gamma))

    def frame(self, c_obs: np.ndarray, bubbles: int = 0) -> np.ndarray:
        """H×W×3 uint8 합성 프레임."""
        I = self.linear_mean(c_obs)
        img = I[None, None, :] * self._vignette[:, :, None]
        img = img + self.rng.normal(0, self.spec.pixel_noise, img.shape)
        for _ in range(bubbles):
            y, x = self.rng.integers(0, self.size[0]), self.rng.integers(0, self.size[1])
            yy, xx = np.ogrid[:self.size[0], :self.size[1]]
            m = (yy - y) ** 2 + (xx - x) ** 2 < 9
            img[m] = 0.95
        return optics.linear_to_code(img, self.spec.gamma).astype(np.uint8)


def write_png(path, img: np.ndarray):
    """외부 라이브러리 없이 8비트 RGB PNG 저장."""
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    pathlib.Path(path).write_bytes(png)


class DatasetRecorder:
    """YOLO 학습용 프레임/라벨 기록. on_target 기준은 ΔE2000 < de_match."""

    def __init__(self, out_dir, cam: SyntheticCamera, every_s: float = 2.0, de_match: float = 2.0):
        self.dir = pathlib.Path(out_dir)
        (self.dir / "images").mkdir(parents=True, exist_ok=True)
        (self.dir / "labels").mkdir(parents=True, exist_ok=True)
        self.cam, self.every, self.de_match = cam, every_s, de_match
        self._last, self.n = -1e9, 0
        self.index = []

    def maybe_record(self, t: float, c_true, c_hat, c_obs, rgb8, target_rgb8, de, run_id="run", image=None):
        """image 를 주면(실제 카메라 프레임) 그대로 저장하고, 없으면 합성 프레임을 만든다. c_true 는 실물에서는 None."""
        if t - self._last < self.every:
            return
        self._last = t
        name = f"{run_id}_{self.n:05d}"
        if image is not None:
            img = np.ascontiguousarray(image[:, :, :3]).astype(np.uint8)
        else:
            img = self.cam.frame(np.asarray(c_obs), bubbles=int(self.cam.rng.integers(0, 3)))
        write_png(self.dir / "images" / f"{name}.png", img)
        h, w = img.shape[:2]
        cls = 0 if de < self.de_match else 1
        # 액체 ROI = 프레임 중앙 80 % 박스 (YOLO: cls cx cy w h, 정규화)
        (self.dir / "labels" / f"{name}.txt").write_text(f"{cls} 0.5 0.5 0.8 0.8\n")
        rec = dict(frame=name, t=round(t, 2), c_true=(None if c_true is None else [round(float(v), 3) for v in c_true]),
                   c_hat=[round(float(v), 3) for v in c_hat], rgb=[int(v) for v in rgb8],
                   target_rgb=[int(v) for v in target_rgb8], dE2000=round(float(de), 3), cls=cls)
        self.index.append(rec)
        self.n += 1

    def close(self):
        (self.dir / "index.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in self.index) + "\n")
        (self.dir / "classes.txt").write_text("on_target\noff_target\n")
        (self.dir / "dataset.yaml").write_text(
            f"path: {self.dir.resolve()}\ntrain: images\nval: images\nnames:\n  0: on_target\n  1: off_target\n")
