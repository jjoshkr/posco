"""로드셀(HX711) 중량 유량 계측 — 스톡병마다 로드셀을 두고 무게 감소율로 실제 유량을 잰다.

왜: 정량펌프는 개루프라 튜브 마모·공기 유입·체크밸브 역류가 생기면 스트로크는 세는데 액은 안 나간다.
    질량유량(로드셀) 과 지령 유량·스트로크 계수를 비교하면 그 차이가 곧 고장 신호이자 이상탐지의 정답 라벨이 된다.

연결 (권장 → 차선)
  serial : Arduino/ESP32 가 HX711 여러 개를 읽어 USB 시리얼로 "ms,raw0,raw1,raw2" 를 보낸다 (firmware/hx711_bridge.ino).
           HX711 은 비트뱅 타이밍이 까다롭고 I/O 노드의 GPIO 는 MCC HAT 아래에 묻혀 있어 이 방식이 가장 안정적이다.
  gpio   : Pi GPIO 에 직접 (lgpio, Pi 5). HAT 이 안 쓰는 GPIO(5, 6, 22~25, 27) 를 스태킹 헤더로 빼야 한다.
  sim    : 시뮬레이터 탱크에서 가짜 raw 값 생성.

처리
  raw → (raw − tare) / counts_per_g = 질량[g] → 밀도로 mL → 이동창 최소제곱 기울기 = 유량[mL/min]
  병을 건드리면(급격한 점프) 그 창은 무효 처리하고 다시 쌓는다.
  FlowCheck: 지령 유량·스트로크 부피와 비교해 FLOW_LOW(공기/마모/정지), TANK_LOW, DISTURBED 판정.

  python -m cmysim.loadcell read   --backend serial --port /dev/ttyUSB0
  python -m cmysim.loadcell tare   --ch 0                      빈 병(또는 현재 상태)을 0 으로
  python -m cmysim.loadcell calib  --ch 0 --mass 500           기준 분동 500 g 올리고 실행 → counts_per_g
  python -m cmysim.loadcell flow   --backend serial            질량·유량 실시간 표시
  python -m cmysim.loadcell demo                               시뮬레이션 데모 (펌프 20 mL/min, 50 s 에 공기 유입)
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json, math, pathlib, sys, time
from collections import deque
import numpy as np


# ------------------------------------------------------------------ 설정
@dataclass
class LoadCellConfig:
    backend: str = "serial"                     # serial | gpio | sim
    port: str = "/dev/ttyUSB0"
    baud: int = 115200
    gpio_pins: list = field(default_factory=lambda: [[5, 6], [22, 23], [24, 25]])   # [DOUT, SCK] × 채널
    channels: list = field(default_factory=lambda: ["C", "M", "Y"])
    tare: list = field(default_factory=lambda: [0.0, 0.0, 0.0])                      # raw counts
    counts_per_g: list = field(default_factory=lambda: [420.0, 420.0, 420.0])        # 5 kg 셀 + 128 배 기준 대략값
    density_g_mL: list = field(default_factory=lambda: [1.0, 1.0, 1.0])
    rate_hz: float = 10.0
    window_s: float = 10.0                      # 유량 추정 창
    jump_g: float = 3.0                         # 이보다 큰 급변 = 병을 건드림
    settle_s: float = 3.0                       # 급변 후 무효 시간
    low_mass_g: float = 100.0                   # 탱크 저수위 경고

    @classmethod
    def load(cls, path="loadcell.json"):
        p = pathlib.Path(path)
        return cls(**json.loads(p.read_text())) if p.exists() else cls()

    def save(self, path="loadcell.json"):
        pathlib.Path(path).write_text(json.dumps(asdict(self), indent=1, ensure_ascii=False))


# ------------------------------------------------------------------ 백엔드
class ReaderBase:
    def __init__(self, cfg: LoadCellConfig):
        self.cfg = cfg
        self.n = len(cfg.channels)

    def start(self): return self
    def stop(self): pass
    def read_raw(self) -> list[float | None]: ...       # 채널별 raw counts (없으면 None)

    def read_g(self) -> list[float | None]:
        raw = self.read_raw()
        return [None if r is None else (r - self.cfg.tare[i]) / self.cfg.counts_per_g[i] for i, r in enumerate(raw)]

    def average_raw(self, n=20, delay=None) -> list[float]:
        delay = 1.0 / self.cfg.rate_hz if delay is None else delay
        acc = [[] for _ in range(self.n)]
        for _ in range(n):
            for i, r in enumerate(self.read_raw()):
                if r is not None:
                    acc[i].append(r)
            time.sleep(delay)
        return [float(np.median(a)) if a else float("nan") for a in acc]


class SerialHX711(ReaderBase):
    """firmware/hx711_bridge.ino 가 보내는 'ms,raw0,raw1,...' 줄을 읽는다. 마지막 값을 보관."""

    def start(self):
        import serial
        self.ser = serial.Serial(self.cfg.port, self.cfg.baud, timeout=0.2)
        self.last = [None] * self.n
        time.sleep(1.5)                           # 아두이노 리셋 대기
        self.ser.reset_input_buffer()
        return self

    def _pump(self):
        while self.ser.in_waiting:
            line = self.ser.readline().decode(errors="ignore").strip()
            parts = line.split(",")
            if len(parts) >= self.n + 1 and parts[0].isdigit():
                try:
                    vals = [float(v) for v in parts[1:1 + self.n]]
                    self.last = [None if math.isnan(v) else v for v in vals]
                except ValueError:
                    pass

    def read_raw(self):
        self._pump()
        if all(v is None for v in self.last):
            line = self.ser.readline().decode(errors="ignore").strip()
            if line:
                self.ser.reset_input_buffer()
                self._pump()
        return list(self.last)

    def stop(self):
        try:
            self.ser.close()
        except Exception:
            pass


class HX711GPIO(ReaderBase):
    """Pi 5 GPIO 직결 (lgpio). 채널 A, 128 배. SCK High 가 60 µs 를 넘으면 칩이 슬립하므로 가능한 한 짧게."""

    def start(self):
        import lgpio
        self.lg = lgpio
        self.h = lgpio.gpiochip_open(4 if pathlib.Path("/dev/gpiochip4").exists() else 0)   # Pi 5: gpiochip4
        for dout, sck in self.cfg.gpio_pins[:self.n]:
            lgpio.gpio_claim_input(self.h, dout)
            lgpio.gpio_claim_output(self.h, sck, 0)
        return self

    def _read_one(self, dout, sck, timeout=0.5):
        lg, h = self.lg, self.h
        t0 = time.monotonic()
        while lg.gpio_read(h, dout) == 1:                 # DOUT Low = 변환 완료
            if time.monotonic() - t0 > timeout:
                return None
            time.sleep(0.001)
        val = 0
        for _ in range(24):
            lg.gpio_write(h, sck, 1); lg.gpio_write(h, sck, 0)
            val = (val << 1) | lg.gpio_read(h, dout)
        lg.gpio_write(h, sck, 1); lg.gpio_write(h, sck, 0)   # 25번째 펄스: 다음 변환 채널 A 128 배
        if val & 0x800000:
            val -= 1 << 24
        return float(val)

    def read_raw(self):
        return [self._read_one(d, s) for d, s in self.cfg.gpio_pins[:self.n]]

    def stop(self):
        try:
            self.lg.gpiochip_close(self.h)
        except Exception:
            pass


class SimLoadCell(ReaderBase):
    """시뮬레이터 탱크 질량 → raw counts. 잡음·느린 드리프트·병 건드림 주입 가능."""

    def __init__(self, cfg: LoadCellConfig, tanks, rng, noise_g=0.05, drift_g_per_h=2.0, bottle_g=(350.0, 350.0, 350.0)):
        super().__init__(cfg)
        self.tanks, self.rng, self.noise_g, self.drift = tanks, rng, noise_g, drift_g_per_h / 3600.0
        self.bottle = list(bottle_g)
        self.t = 0.0
        self.bump = [0.0] * self.n                 # 병을 건드린 효과 (g)
        cfg.tare = [cfg.counts_per_g[i] * self.bottle[i] for i in range(self.n)]   # 빈 병 tare 가 끝난 상태로 시작

    def step(self, dt):
        self.t += dt

    def read_raw(self):
        out = []
        for i, tk in enumerate(self.tanks[:self.n]):
            g = tk.volume_mL * self.cfg.density_g_mL[i] + self.bottle[i] + self.drift * self.t + self.bump[i] + self.rng.normal(0, self.noise_g)
            out.append(g * self.cfg.counts_per_g[i])
        return out


def open_reader(cfg: LoadCellConfig, **kw) -> ReaderBase:
    cls = {"serial": SerialHX711, "gpio": HX711GPIO, "sim": SimLoadCell}[cfg.backend]
    return cls(cfg, **kw).start() if cfg.backend == "sim" else cls(cfg).start()


# ------------------------------------------------------------------ 유량 추정
class FlowEstimator:
    """채널 하나: (t, g) 이동창 → 기울기(유량), 누적 투입, 무효(건드림) 판정."""

    def __init__(self, cfg: LoadCellConfig, i: int):
        self.cfg, self.i = cfg, i
        self.buf: deque = deque()
        self.m_start = None; self.invalid_until = -1.0; self.last_g = None
        self.flow_mL_min = 0.0; self.mass_g = float("nan"); self.valid = False; self.n_disturb = 0

    def reset_batch(self):
        self.m_start = self.last_g

    def push(self, t: float, g: float | None) -> dict:
        if g is None or math.isnan(g):
            self.valid = False
            return self.state(t)
        self.mass_g = g
        if self.m_start is None:
            self.m_start = g
        # 급변 감지: 창의 회귀 예측과 비교
        if len(self.buf) >= 5:
            ts = np.array([b[0] for b in self.buf]); gs = np.array([b[1] for b in self.buf])
            a, b = np.polyfit(ts - ts[0], gs, 1)
            pred = a * (t - ts[0]) + b
            if abs(g - pred) > self.cfg.jump_g:
                self.buf.clear(); self.invalid_until = t + self.cfg.settle_s; self.n_disturb += 1
        self.buf.append((t, g))
        while self.buf and t - self.buf[0][0] > self.cfg.window_s:
            self.buf.popleft()
        self.last_g = g
        if t < self.invalid_until or len(self.buf) < 4 or (self.buf[-1][0] - self.buf[0][0]) < 0.5 * self.cfg.window_s:
            self.valid = False
        else:
            ts = np.array([b[0] for b in self.buf]); gs = np.array([b[1] for b in self.buf])
            slope_g_s = np.polyfit(ts - ts[0], gs, 1)[0]
            self.flow_mL_min = float(-slope_g_s * 60.0 / self.cfg.density_g_mL[self.i])
            self.valid = True
        return self.state(t)

    @property
    def delivered_mL(self) -> float:
        if self.m_start is None or self.last_g is None:
            return 0.0
        return (self.m_start - self.last_g) / self.cfg.density_g_mL[self.i]

    def state(self, t):
        return dict(mass_g=round(self.mass_g, 2) if not math.isnan(self.mass_g) else None,
                    flow_mL_min=round(self.flow_mL_min, 3), delivered_mL=round(self.delivered_mL, 3), valid=self.valid,
                    low=(not math.isnan(self.mass_g)) and self.mass_g < self.cfg.low_mass_g)


class FlowCheck:
    """펌프 지령(기대 유량)·스트로크 부피 vs 로드셀. 상태: OK / FLOW_LOW / FLOW_HIGH / TANK_LOW / DISTURBED / NO_DATA."""

    def __init__(self, ratio_low=0.6, ratio_high=1.5, min_expected_mL_min=2.0, hold_s=6.0):
        self.rl, self.rh, self.min_exp, self.hold = ratio_low, ratio_high, min_expected_mL_min, hold_s
        self.since = {}

    def check(self, t, pid, expected_mL_min, est_state: dict, stroke_mL=None) -> tuple[str, float]:
        if est_state.get("mass_g") is None:
            return "NO_DATA", float("nan")
        if est_state.get("low"):
            return "TANK_LOW", float("nan")
        if not est_state.get("valid"):
            return "DISTURBED", float("nan")
        ratio = est_state["flow_mL_min"] / expected_mL_min if expected_mL_min > self.min_exp else float("nan")
        status = "OK"
        if expected_mL_min > self.min_exp:
            if ratio < self.rl:
                status = "FLOW_LOW"
            elif ratio > self.rh:
                status = "FLOW_HIGH"
        # hold_s 이상 지속될 때만 보고 (창 지연·맥동 때문)
        key = (pid, status)
        if status != "OK":
            self.since.setdefault(key, t)
            if t - self.since[key] < self.hold:
                return "OK", ratio
        else:
            self.since = {k: v for k, v in self.since.items() if k[0] != pid}
        return status, ratio


# ------------------------------------------------------------------ CLI
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="loadcell", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="loadcell.json")
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("read", "tare", "calib", "flow"):
        p = sp.add_parser(name); p.add_argument("--backend"); p.add_argument("--port")
        if name in ("tare", "calib"):
            p.add_argument("--ch", type=int, required=True); p.add_argument("-n", type=int, default=30)
        if name == "calib":
            p.add_argument("--mass", type=float, required=True, help="올린 기준 분동 [g]")
    sp.add_parser("demo")
    a = ap.parse_args(argv)
    cfg = LoadCellConfig.load(a.config)

    if a.cmd == "demo":
        return demo()
    if a.backend:
        cfg.backend = a.backend
    if a.port:
        cfg.port = a.port
    rd = open_reader(cfg)
    try:
        if a.cmd == "read":
            while True:
                raw = rd.read_raw(); g = rd.read_g()
                print(time.strftime("%H:%M:%S"), " ".join(f"{c}: raw={('%.0f' % r) if r is not None else '-'} {('%.2f g' % v) if v is not None else '-'}"
                                                           for c, r, v in zip(cfg.channels, raw, g)))
                time.sleep(1.0 / cfg.rate_hz)
        elif a.cmd == "tare":
            med = rd.average_raw(a.n)
            cfg.tare[a.ch] = med[a.ch]; cfg.save(a.config)
            print(f"ch{a.ch} ({cfg.channels[a.ch]}) tare = {med[a.ch]:.0f} counts → {a.config}")
        elif a.cmd == "calib":
            med = rd.average_raw(a.n)
            cpg = (med[a.ch] - cfg.tare[a.ch]) / a.mass
            cfg.counts_per_g[a.ch] = cpg; cfg.save(a.config)
            print(f"ch{a.ch} ({cfg.channels[a.ch]}) counts_per_g = {cpg:.3f}  (raw {med[a.ch]:.0f}, tare {cfg.tare[a.ch]:.0f}, {a.mass} g) → {a.config}")
        elif a.cmd == "flow":
            ests = [FlowEstimator(cfg, i) for i in range(rd.n)]
            t0 = time.monotonic()
            while True:
                t = time.monotonic() - t0
                g = rd.read_g()
                st = [e.push(t, v) for e, v in zip(ests, g)]
                print(f"{t:7.1f}s " + "  ".join(f"{c}: {s['mass_g']} g {s['flow_mL_min']:+.2f} mL/min {'' if s['valid'] else '(무효)'} 누적 {s['delivered_mL']:.1f} mL"
                                           for c, s in zip(cfg.channels, st)))
                time.sleep(1.0 / cfg.rate_hz)
    except KeyboardInterrupt:
        pass
    finally:
        rd.stop()
    return 0


def demo():
    """시뮬레이션: 펌프 20 mL/min 으로 투입, 50 s 에 공기 유입(토출 절반), 80 s 에 병을 건드림."""
    from .config import SystemConfig
    from .process import StockTank
    cfg = SystemConfig(); lc = LoadCellConfig(backend="sim")
    rng = np.random.default_rng(0)
    tanks = [StockTank(ts, d) for ts, d in zip(cfg.tanks, "CMY")]
    rd = SimLoadCell(lc, tanks, rng)
    est = FlowEstimator(lc, 0); chk = FlowCheck()
    dt, t = 0.1, 0.0
    print(f"{'t':>6} {'mass g':>9} {'flow mL/min':>12} {'expected':>9} {'ratio':>6} status")
    while t < 120:
        rate = 20.0 if t < 100 else 0.0
        eff = 0.5 if 50 <= t < 100 else 1.0
        tanks[0].draw(rate * eff / 60.0 * dt)
        if abs(t - 80.0) < dt / 2:
            rd.bump[0] = 15.0                       # 병에 손을 댐
        if abs(t - 82.0) < dt / 2:
            rd.bump[0] = 0.0                        # 손을 뗌
        rd.step(dt)
        st = est.push(t, rd.read_g()[0])
        status, ratio = chk.check(t, "P-101", rate, st)
        if abs(t - round(t)) < 1e-9 and int(t) % 5 == 0:
            print(f"{t:6.1f} {st['mass_g']:>9} {st['flow_mL_min']:>12.2f} {rate:>9.1f} {ratio:>6.2f} {status}")
        t = round(t + dt, 3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
