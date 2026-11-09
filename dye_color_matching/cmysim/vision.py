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

    turbidity_ntu: float = 0.0        # SimPlant 가 매 스텝 갱신

    def linear_mean(self, c_obs: np.ndarray) -> np.ndarray:
        s = self.spec
        A = optics.conc_to_absorbance(s.E, c_obs)
        I = optics.absorbance_to_linear(A, s.I0, s.glare)
        w = self.turbidity_ntu / (self.turbidity_ntu + s.turb_K_ntu) if self.turbidity_ntu > 0 else 0.0
        return (I * (1 - w) + 0.95 * w) * self.exposure         # 현탁 고체의 산란 = 흰색 혼입

    def roi_rgb8(self, c_obs: np.ndarray) -> np.ndarray:
        """ROI 평균 RGB 코드값 (픽셀 잡음은 √N 으로 줄어든다)."""
        I = self.linear_mean(c_obs)
        noise = self.rng.normal(0, self.spec.pixel_noise / np.sqrt(self.spec.roi_pixels), 3)
        return np.round(optics.linear_to_code(I + noise, self.spec.gamma))

    def frame(self, c_obs: np.ndarray, bubbles: int = 0) -> np.ndarray:
        """H×W×3 uint8 합성 프레임. 기포(밝은 원) 위치는 self.last_bubbles 에 (x, y, r) 로 남겨 YOLO 라벨에 쓴다."""
        I = self.linear_mean(c_obs)
        img = I[None, None, :] * self._vignette[:, :, None]
        img = img + self.rng.normal(0, self.spec.pixel_noise, img.shape)
        self.last_bubbles = []
        yy, xx = np.ogrid[:self.size[0], :self.size[1]]
        for _ in range(bubbles):
            r = int(self.rng.integers(2, 6))
            y, x = int(self.rng.integers(r, self.size[0] - r)), int(self.rng.integers(r, self.size[1] - r))
            m = (yy - y) ** 2 + (xx - x) ** 2 < r * r
            img[m] = (0.95 - 0.1 * ((yy - y) ** 2 + (xx - x) ** 2)[m] / (r * r))[:, None]   # 가장자리 어두운 구슬 모양
            self.last_bubbles.append((x, y, r))
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


CLASSES = ("liquid_on_target", "liquid_off_target", "bubble")


class DatasetRecorder:
    """YOLO 학습용 프레임/라벨 기록.

    라벨 (YOLO detect 형식, 정규화 cx cy w h)
      0 liquid_on_target / 1 liquid_off_target : 액체 ROI 박스. on_target 기준은 ΔE2000 < de_match
      2 bubble                                  : 합성 프레임에서는 그린 기포 위치를 자동 라벨. 실제 프레임은 사람이 추가 (CVAT/LabelImg)
    index.jsonl 에는 회귀용 연속값(진짜 농도, 추정 농도, RGB, ΔE)을 남긴다.
    """

    def __init__(self, out_dir, cam, every_s: float = 2.0, de_match: float = 2.0, roi=None):
        self.dir = pathlib.Path(out_dir)
        (self.dir / "images").mkdir(parents=True, exist_ok=True)
        (self.dir / "labels").mkdir(parents=True, exist_ok=True)
        self.cam, self.every, self.de_match, self.roi = cam, every_s, de_match, roi
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
        if self.roi is not None:                                   # 실제 카메라: camera.json 의 ROI
            x, y, rw, rh = self.roi
            lines = [f"{cls} {(x + rw / 2) / w:.5f} {(y + rh / 2) / h:.5f} {rw / w:.5f} {rh / h:.5f}"]
        else:                                                       # 합성: 중앙 80 %
            lines = [f"{cls} 0.5 0.5 0.8 0.8"]
        if image is None:
            for (bx, by, br) in getattr(self.cam, "last_bubbles", []):
                lines.append(f"2 {bx / w:.5f} {by / h:.5f} {2 * br / w:.5f} {2 * br / h:.5f}")
        (self.dir / "labels" / f"{name}.txt").write_text("\n".join(lines) + "\n")
        rec = dict(frame=name, t=round(t, 2), c_true=(None if c_true is None else [round(float(v), 3) for v in c_true]),
                   c_hat=[round(float(v), 3) for v in c_hat], rgb=[int(v) for v in rgb8],
                   target_rgb=[int(v) for v in target_rgb8], dE2000=round(float(de), 3), cls=cls,
                   n_bubbles=len(lines) - 1)
        self.index.append(rec)
        self.n += 1

    def close(self):
        (self.dir / "index.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in self.index) + "\n")
        (self.dir / "classes.txt").write_text("\n".join(CLASSES) + "\n")
        names = "\n".join(f"  {i}: {c}" for i, c in enumerate(CLASSES))
        (self.dir / "dataset.yaml").write_text(f"path: {self.dir.resolve()}\ntrain: images\nval: images\nnames:\n{names}\n")
