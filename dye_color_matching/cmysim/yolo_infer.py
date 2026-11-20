"""학습된 모델로 프레임에서 '사건' 을 읽는 래퍼 (AI 노드에서 사용).

VisionEvents(weights).detect(rgb_frame) → {"liquid": "liquid_on_target"|"liquid_off_target"|None, "liquid_conf", "bubbles", "boxes", "ms"}

백엔드
  .pt / .onnx : ultralytics (CPU; 워크스테이션 또는 Pi CPU 에서 수 fps)
  .hef        : Hailo-8 (AI HAT+). hailo_platform 이 설치된 Pi 에서만. 후처리는 hailo_model_zoo 의 YOLO NMS 를 쓴다고 가정.
"""
from __future__ import annotations
import time
import numpy as np
from .vision import CLASSES


class VisionEvents:
    def __init__(self, weights: str, conf: float = 0.25, imgsz: int = 320):
        self.weights, self.conf, self.imgsz = str(weights), conf, imgsz
        self.backend = "hailo" if self.weights.endswith(".hef") else "ultralytics"
        if self.backend == "ultralytics":
            from ultralytics import YOLO
            self.model = YOLO(self.weights)
            self.task = getattr(self.model, "task", "detect")
        else:
            self._init_hailo()

    # ---------------- Hailo (AI HAT+)
    def _init_hailo(self):
        from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, \
            InputVStreamParams, OutputVStreamParams, FormatType
        self.hef = HEF(self.weights)
        self.vdev = VDevice()
        params = ConfigureParams.create_from_hef(self.hef, interface=HailoStreamInterface.PCIe)
        self.ng = self.vdev.configure(self.hef, params)[0]
        self.in_params = InputVStreamParams.make(self.ng, format_type=FormatType.UINT8)
        self.out_params = OutputVStreamParams.make(self.ng, format_type=FormatType.FLOAT32)
        self.in_info = self.hef.get_input_vstream_infos()[0]
        self._InferVStreams = InferVStreams
        self.task = "detect"

    def _hailo_detect(self, rgb):
        h, w = self.in_info.shape[:2]
        import cv2
        x = cv2.resize(rgb, (w, h))[None]
        with self.ng.activate():
            with self._InferVStreams(self.ng, self.in_params, self.out_params) as pipe:
                out = pipe.infer({self.in_info.name: x})
        # hailo_model_zoo YOLO 후처리 출력: 클래스별 [N, 5] (y0, x0, y1, x1, score), 정규화
        dets = list(out.values())[0][0]
        boxes = []
        for ci, arr in enumerate(dets):
            for y0, x0, y1, x1, s in np.asarray(arr).reshape(-1, 5):
                if s >= self.conf:
                    boxes.append((ci, float(s), x0 * rgb.shape[1], y0 * rgb.shape[0], x1 * rgb.shape[1], y1 * rgb.shape[0]))
        return boxes

    # ---------------- 공통
    def detect(self, rgb: np.ndarray) -> dict:
        t0 = time.perf_counter()
        boxes = []
        if self.backend == "ultralytics":
            r = self.model.predict(rgb[:, :, ::-1], conf=self.conf, imgsz=self.imgsz, verbose=False)[0]   # BGR 입력
            if self.task == "classify":
                ci = int(r.probs.top1); s = float(r.probs.top1conf)
                return dict(liquid=CLASSES[ci] if ci < 2 else None, liquid_conf=s, bubbles=0, boxes=[],
                            ms=(time.perf_counter() - t0) * 1000)
            for b in r.boxes:
                x0, y0, x1, y1 = b.xyxy[0].tolist()
                boxes.append((int(b.cls), float(b.conf), x0, y0, x1, y1))
        else:
            boxes = self._hailo_detect(rgb)
        liquid = [b for b in boxes if b[0] < 2]
        best = max(liquid, key=lambda b: b[1]) if liquid else None
        return dict(liquid=CLASSES[best[0]] if best else None, liquid_conf=best[1] if best else 0.0,
                    bubbles=sum(1 for b in boxes if b[0] == 2), boxes=boxes, ms=(time.perf_counter() - t0) * 1000)

    def draw(self, rgb, result):
        img = rgb.copy()
        col = {0: (0, 200, 0), 1: (220, 0, 0), 2: (0, 120, 255)}
        for ci, s, x0, y0, x1, y1 in result["boxes"]:
            x0, y0, x1, y1 = [int(round(v)) for v in (x0, y0, x1, y1)]
            img[y0:y1 + 1, [max(x0, 0), min(x1, img.shape[1] - 1)], :] = col[ci]
            img[[max(y0, 0), min(y1, img.shape[0] - 1)], x0:x1 + 1, :] = col[ci]
        return img
