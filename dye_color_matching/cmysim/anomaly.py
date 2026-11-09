"""다변량 시계열 이상탐지 (오토인코더) — 대화의 '4. AI 설계' 세 번째 갈래.

입력 특징 (0.5 s 간격, 정상 실행으로 표준화)
  펌프 3대: 지령 mA, 피드백 spm, 스트로크 잔차(지령으로 기대되는 spm − 실제 spm)
  물질수지 잔차: 스트로크 계수로 기대되는 농도 − 카메라 추정 농도 (염료 3개)
  카메라: ĉ(C,M,Y), ΔE2000, dΔE/dt
  공정: 토출 압력, pH, 온도, rpm (있는 것만)
모델 (같은 인터페이스 fit / score / save / load)
  PCAAutoencoder : numpy 만. 창을 펼쳐 PCA 로 압축·복원. Pi 에서 추론 기본값
  ConvAutoencoder: PyTorch 1D-CNN. 워크스테이션에서 학습, 가중치는 numpy 로도 저장해 Pi 에서 torch 없이 추론 가능
점수 = 창 복원오차(MSE). 임계값 = 정상 검증 점수의 분위수. CUSUM 으로 느린 드리프트 누적.
융합 점수 S = Σ w_i·z_i  (ΔE, AE 점수, pH 오차, 유량 잔차, YOLO 확률) 는 fusion_score().

  python -m cmysim.anomaly gen   --out ad_ds --normal 24 --faults 16
  python -m cmysim.anomaly train --data ad_ds --model pca  --out ad_pca
  python -m cmysim.anomaly train --data ad_ds --model conv --out ad_conv --epochs 40
  python -m cmysim.anomaly eval  --data ad_ds --model-dir ad_conv
  python -m cmysim.anomaly score --csv run_timeseries.csv --model-dir ad_conv --plot score.png
  실시간: ai_node_main --anomaly ad_conv
"""
from __future__ import annotations
import argparse, csv, json, math, pathlib, random, sys
import numpy as np

STROKE_ML, I_START, I_FULL, MAX_SPM = 0.19, 4.4, 19.6, 200.0
FEATURES_BASE = ["mA_101", "mA_102", "mA_103", "spm_101", "spm_102", "spm_103",
                 "r_spm_101", "r_spm_102", "r_spm_103", "r_mb_C", "r_mb_M", "r_mb_Y",
                 "cC_hat", "cM_hat", "cY_hat", "dE", "d_dE", "p_bar"]
FEATURES_OPT = ["ph", "temp_C", "rpm", "flow_101", "flow_102", "flow_103", "r_flow_101", "r_flow_102", "r_flow_103"]


# ------------------------------------------------------------------ 특징
def spm_expected(mA):
    mA = np.asarray(mA, float)
    return np.where(mA < I_START, 0.0, np.clip(MAX_SPM * (mA - I_START) / (I_FULL - I_START), 0, MAX_SPM))


def canonical_rows(path) -> list[dict]:
    """시뮬레이션 timeseries.csv / AI 노드 ai_node_log.csv 어느 쪽이든 공통 키로 바꾼다."""
    rows = list(csv.DictReader(open(path)))
    out = []
    for r in rows:
        g = lambda *ks: next((float(r[k]) for k in ks if k in r and r[k] not in ("", "None", "nan")), float("nan"))
        out.append(dict(t=g("t_s", "t"), mA_101=g("mA_101"), mA_102=g("mA_102"), mA_103=g("mA_103"),
                        spm_101=g("spm_101"), spm_102=g("spm_102"), spm_103=g("spm_103"), p_bar=g("p_bar"),
                        ph=g("ph"), temp_C=g("temp_C"), rpm=g("rpm"),
                        flow_101=g("flow_101"), flow_102=g("flow_102"), flow_103=g("flow_103"),
                        cC_hat=g("cC_hat"), cM_hat=g("cM_hat"), cY_hat=g("cY_hat"), dE=g("dE2000_cam", "dE2000")))
    return out


def resample(rows: list[dict], dt=0.5) -> list[dict]:
    """불규칙/고속 로그를 dt 간격 평균으로."""
    if not rows:
        return rows
    out, bucket, t0 = [], [], rows[0]["t"]
    keys = [k for k in rows[0] if k != "t"]

    def mean_or_nan(vals):
        v = [x for x in vals if x == x]                      # NaN 제외 (전부 NaN 이면 NaN, 경고 없이)
        return float(np.mean(v)) if v else float("nan")

    for r in rows:
        if r["t"] - t0 >= dt and bucket:
            out.append(dict(t=t0, **{k: mean_or_nan([b[k] for b in bucket]) for k in keys}))
            t0 += dt * max(1, int((r["t"] - t0) // dt)); bucket = []
        bucket.append(r)
    if bucket:
        out.append(dict(t=t0, **{k: mean_or_nan([b[k] for b in bucket]) for k in keys}))
    return out


class FeatureBuilder:
    """오프라인(행 목록)과 온라인(한 행씩) 이 같은 코드로 같은 특징을 만든다."""

    def __init__(self, dt=0.5, heel_mL=2000.0, c_stock=(1000.0, 1000.0, 1000.0), features=None):
        self.dt, self.heel, self.c_stock = dt, heel_mL, np.asarray(c_stock, float)
        self.features = list(features) if features else None
        self.reset()

    def reset(self):
        self.dosed = np.zeros(3); self.prev_dE = None

    def available_features(self, rows):
        feats = list(FEATURES_BASE)
        for k in FEATURES_OPT:
            src = k.replace("r_flow", "flow")                      # r_flow_* 는 flow_* 가 있을 때 함께
            if any(not math.isnan(r.get(src, float("nan"))) for r in rows[:200]):
                feats.append(k)
        return feats

    def push(self, r: dict) -> dict:
        """한 행 → 특징 dict (상태: 누적 투입량, 이전 ΔE)."""
        mA = np.array([r["mA_101"], r["mA_102"], r["mA_103"]], float)
        spm = np.array([r["spm_101"], r["spm_102"], r["spm_103"]], float)
        spm = np.nan_to_num(spm); mA = np.nan_to_num(mA)
        r_spm = spm_expected(mA) - spm
        self.dosed += spm / 60.0 * self.dt * STROKE_ML
        V = self.heel + self.dosed.sum()
        c_exp = self.dosed * self.c_stock / V
        c_hat = np.array([r["cC_hat"], r["cM_hat"], r["cY_hat"]], float)
        dE = r["dE"]
        d_dE = 0.0 if self.prev_dE is None or math.isnan(dE) else (dE - self.prev_dE) / self.dt
        self.prev_dE = dE
        f = dict(zip(["mA_101", "mA_102", "mA_103"], mA)); f.update(zip(["spm_101", "spm_102", "spm_103"], spm))
        f.update(zip(["r_spm_101", "r_spm_102", "r_spm_103"], r_spm)); f.update(zip(["r_mb_C", "r_mb_M", "r_mb_Y"], c_exp - c_hat))
        f.update(cC_hat=c_hat[0], cM_hat=c_hat[1], cY_hat=c_hat[2], dE=dE, d_dE=d_dE, p_bar=r.get("p_bar", 0.0),
                 ph=r.get("ph", float("nan")), temp_C=r.get("temp_C", float("nan")), rpm=r.get("rpm", float("nan")))
        # 로드셀 유량: 무효 구간(NaN) 은 기대 유량으로 메워 잔차 0 (건드림을 고장으로 오인하지 않게)
        exp_flow = spm_expected(mA) * STROKE_ML
        for j, k in enumerate(("101", "102", "103")):
            fl = r.get("flow_" + k, float("nan"))
            fl = exp_flow[j] if (fl is None or math.isnan(fl)) else fl
            f["flow_" + k] = fl; f["r_flow_" + k] = exp_flow[j] - fl
        return f

    def matrix(self, rows: list[dict], features: list[str]) -> np.ndarray:
        self.reset()
        feats = [self.push(r) for r in rows]                 # push 는 행마다 정확히 한 번 (상태 누적)
        X = np.array([[f[k] for k in features] for f in feats], float)
        return np.nan_to_num(X)


def windows(X: np.ndarray, W: int, stride: int = 1) -> np.ndarray:
    if len(X) < W:
        return np.empty((0, W, X.shape[1]))
    idx = np.arange(0, len(X) - W + 1, stride)
    return np.stack([X[i:i + W] for i in idx])


# ------------------------------------------------------------------ 모델
class PCAAutoencoder:
    kind = "pca"

    def __init__(self, W, n_feat, var_keep=0.95):
        self.W, self.F, self.var_keep = W, n_feat, var_keep
        self.mean = None; self.comp = None

    def fit(self, Xw: np.ndarray, epochs=None, verbose=False):
        Z = Xw.reshape(len(Xw), -1)
        self.mean = Z.mean(0)
        U, S, Vt = np.linalg.svd(Z - self.mean, full_matrices=False)
        var = S ** 2 / (S ** 2).sum()
        k = int(np.searchsorted(np.cumsum(var), self.var_keep) + 1)
        self.comp = Vt[:k]
        if verbose:
            print(f"PCA: {k} 성분 (분산 {np.cumsum(var)[k-1]:.3f}) / {Z.shape[1]} 차원")
        return self

    def reconstruct(self, Xw):
        Z = Xw.reshape(len(Xw), -1) - self.mean
        return ((Z @ self.comp.T) @ self.comp + self.mean).reshape(Xw.shape)

    def score(self, Xw):
        err = (self.reconstruct(Xw) - Xw) ** 2
        return err.mean(axis=(1, 2)), err.mean(axis=1)          # (창 점수, 창별 특징 기여)

    def save(self, d):
        np.savez(pathlib.Path(d) / "pca.npz", mean=self.mean, comp=self.comp, W=self.W, F=self.F)

    @classmethod
    def load(cls, d):
        z = np.load(pathlib.Path(d) / "pca.npz")
        m = cls(int(z["W"]), int(z["F"])); m.mean, m.comp = z["mean"], z["comp"]; return m


class ConvAutoencoder:
    """1D-CNN 오토인코더 (torch). 추론은 numpy 로도 가능하도록 가중치를 npz 로 함께 저장한다."""
    kind = "conv"

    def __init__(self, W, n_feat, latent=8, hidden=32):
        self.W, self.F, self.latent, self.hidden = W, n_feat, latent, hidden
        self.np_weights = None

    def _build(self):
        import torch.nn as nn
        F, H, L, W = self.F, self.hidden, self.latent, self.W
        enc = nn.Sequential(nn.Conv1d(F, H, 5, padding=2), nn.ReLU(), nn.Conv1d(H, H, 5, padding=2, stride=2), nn.ReLU(),
                            nn.Flatten(), nn.Linear(H * ((W + 1) // 2), L))
        dec = nn.Sequential(nn.Linear(L, H * ((W + 1) // 2)), nn.ReLU(), nn.Unflatten(1, (H, (W + 1) // 2)),
                            nn.Upsample(size=W), nn.Conv1d(H, H, 5, padding=2), nn.ReLU(), nn.Conv1d(H, F, 5, padding=2))
        return nn.Sequential(enc, dec)

    def fit(self, Xw, epochs=40, lr=2e-3, batch=64, verbose=False, seed=0):
        import torch
        torch.manual_seed(seed)
        self.net = self._build()
        X = torch.tensor(Xw, dtype=torch.float32).permute(0, 2, 1)       # (N, F, W)
        opt = torch.optim.Adam(self.net.parameters(), lr=lr)
        n = len(X)
        for ep in range(epochs):
            perm = torch.randperm(n); tot = 0.0
            for i in range(0, n, batch):
                xb = X[perm[i:i + batch]]
                loss = ((self.net(xb) - xb) ** 2).mean()
                opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item() * len(xb)
            if verbose and (ep % 10 == 0 or ep == epochs - 1):
                print(f"epoch {ep:3d} loss {tot / n:.5f}")
        self.np_weights = self._export_numpy()
        return self

    # --- numpy 추론 (Pi 에서 torch 없이)
    def _export_numpy(self):
        import torch
        ws = []
        for m in self.net.modules():
            if m.__class__.__name__ in ("Conv1d", "Linear"):
                ws.append((m.__class__.__name__, m.weight.detach().numpy().copy(), m.bias.detach().numpy().copy(),
                           getattr(m, "stride", (1,))[0] if m.__class__.__name__ == "Conv1d" else 1))
        return ws

    def _np_forward(self, Xw):
        x = np.transpose(Xw, (0, 2, 1))                                      # (N, F, W)
        ws = self.np_weights; H, W = self.hidden, self.W
        def conv(x, w, b, stride):
            k = w.shape[2]; p = k // 2
            xp = np.pad(x, ((0, 0), (0, 0), (p, p)))
            Lout = (x.shape[2] + 2 * p - k) // stride + 1
            cols = np.stack([xp[:, :, i * stride:i * stride + k] for i in range(Lout)], 2)   # (N, Cin, Lout, k)
            return np.einsum("nilk,oik->nol", cols, w) + b[None, :, None]
        relu = lambda a: np.maximum(a, 0)
        x = relu(conv(x, *ws[0][1:]))                                       # enc conv1
        x = relu(conv(x, *ws[1][1:]))                                       # enc conv2 stride 2
        z = x.reshape(len(x), -1) @ ws[2][1].T + ws[2][2]                    # enc linear
        y = relu(z @ ws[3][1].T + ws[3][2]).reshape(len(x), H, (W + 1) // 2)   # dec linear
        idx = (np.arange(W) * ((W + 1) // 2) / W).astype(int)                # nearest upsample
        y = y[:, :, idx]
        y = relu(conv(y, *ws[4][1:]))
        y = conv(y, *ws[5][1:])
        return np.transpose(y, (0, 2, 1))

    def reconstruct(self, Xw):
        if self.np_weights is not None and not hasattr(self, "net"):
            return self._np_forward(Xw)
        import torch
        with torch.no_grad():
            X = torch.tensor(Xw, dtype=torch.float32).permute(0, 2, 1)
            return self.net(X).permute(0, 2, 1).numpy()

    def score(self, Xw):
        err = (self.reconstruct(Xw) - Xw) ** 2
        return err.mean(axis=(1, 2)), err.mean(axis=1)

    def save(self, d):
        d = pathlib.Path(d)
        arrs = {}
        for i, (kind, w, b, s) in enumerate(self.np_weights):
            arrs[f"w{i}"] = w; arrs[f"b{i}"] = b; arrs[f"s{i}"] = np.array(s); arrs[f"k{i}"] = np.array(kind)
        np.savez(d / "conv.npz", n=len(self.np_weights), W=self.W, F=self.F, latent=self.latent, hidden=self.hidden, **arrs)
        try:
            import torch; torch.save(self.net.state_dict(), d / "conv.pt")
        except Exception:
            pass

    @classmethod
    def load(cls, d):
        z = np.load(pathlib.Path(d) / "conv.npz")
        m = cls(int(z["W"]), int(z["F"]), int(z["latent"]), int(z["hidden"]))
        m.np_weights = [(str(z[f"k{i}"]), z[f"w{i}"], z[f"b{i}"], int(z[f"s{i}"])) for i in range(int(z["n"]))]
        return m


MODELS = {"pca": PCAAutoencoder, "conv": ConvAutoencoder}


# ------------------------------------------------------------------ 학습된 탐지기 (표준화 + 모델 + 임계값)
class Detector:
    def __init__(self, model, features, mu, sd, thr, W, dt=0.5, heel_mL=2000.0, c_stock=(1000,) * 3, cusum_k=0.5, cusum_h=30.0,
                 s_mu=0.0, s_sd=1.0):
        self.model, self.features, self.mu, self.sd, self.thr, self.W, self.dt = model, features, mu, sd, thr, W, dt
        self.fb = FeatureBuilder(dt, heel_mL, c_stock)
        self.cusum_k, self.cusum_h, self.s_mu, self.s_sd = cusum_k, cusum_h, s_mu, s_sd   # 정상 점수 통계 (CUSUM 용)
        self.buf: list = []; self.cusum = 0.0

    def calibrate_cusum(self, normal_scores_per_run: list, k=0.5, margin=1.5):
        """정상 실행들의 점수로 s_mu/s_sd 를 정하고, 정상에서 한 번도 안 울리도록 h 를 최대 CUSUM × margin 으로."""
        allv = np.concatenate(normal_scores_per_run)
        self.s_mu, self.s_sd, self.cusum_k = float(np.median(allv)), float(allv.std() + 1e-9), k
        peaks = [cusum_seq(sr, self.s_mu, self.s_sd, k).max() for sr in normal_scores_per_run if len(sr)]
        self.cusum_h = float(max(peaks) * margin + 1.0)
        return self.cusum_h

    def standardize(self, X):
        return (X - self.mu) / self.sd

    def score_rows(self, rows):
        X = self.standardize(self.fb.matrix(rows, self.features))
        Xw = windows(X, self.W)
        if len(Xw) == 0:
            return np.array([]), np.empty((0, len(self.features))), np.array([])
        s, contrib = self.model.score(Xw)
        t = np.array([r["t"] for r in rows])[self.W - 1:]
        return s, contrib, t

    # 온라인
    def reset(self):
        self.fb.reset(); self.buf = []; self.cusum = 0.0

    def push(self, row: dict) -> dict | None:
        f = self.fb.push(row)
        self.buf.append([f[k] for k in self.features]); self.buf = self.buf[-self.W:]
        if len(self.buf) < self.W:
            return None
        Xw = self.standardize(np.nan_to_num(np.array(self.buf, float)))[None]
        s, contrib = self.model.score(Xw)
        z = s[0] / self.thr
        self.cusum = max(0.0, self.cusum + (s[0] - self.s_mu) / self.s_sd - self.cusum_k)
        top = np.argsort(contrib[0])[::-1][:3]
        return dict(score=float(s[0]), thr=float(self.thr), ratio=float(z), alarm=bool(s[0] > self.thr),
                    cusum=float(self.cusum), cusum_alarm=bool(self.cusum > self.cusum_h),
                    top=[(self.features[i], float(contrib[0][i])) for i in top])

    def save(self, d):
        d = pathlib.Path(d); d.mkdir(parents=True, exist_ok=True)
        self.model.save(d)
        (d / "meta.json").write_text(json.dumps(dict(kind=self.model.kind, features=self.features, mu=self.mu.tolist(),
                                                     sd=self.sd.tolist(), thr=float(self.thr), W=self.W, dt=self.dt,
                                                     heel_mL=self.fb.heel, c_stock=self.fb.c_stock.tolist(),
                                                     cusum_k=self.cusum_k, cusum_h=self.cusum_h, s_mu=self.s_mu, s_sd=self.s_sd), indent=1))

    @classmethod
    def load(cls, d):
        d = pathlib.Path(d); m = json.loads((d / "meta.json").read_text())
        model = MODELS[m["kind"]].load(d)
        return cls(model, m["features"], np.array(m["mu"]), np.array(m["sd"]), m["thr"], m["W"], m["dt"], m["heel_mL"],
                   m["c_stock"], m.get("cusum_k", 0.5), m.get("cusum_h", 30.0), m.get("s_mu", 0.0), m.get("s_sd", 1.0))


def cusum_seq(s: np.ndarray, mu: float, sd: float, k: float = 0.5) -> np.ndarray:
    """z = (점수 − 정상 평균)/정상 표준편차; (z − k) 의 양의 누적합. 느린 드리프트(스톡 농도 오차, 공기 유입, 교반 저하)를 잡는다."""
    out, c = np.zeros(len(s)), 0.0
    for i, v in enumerate(s):
        c = max(0.0, c + (v - mu) / sd - k); out[i] = c
    return out


def fusion_score(dE=None, ae_ratio=None, ph_err=None, flow_resid=None, p_yolo=None,
                 w=(1.0, 1.5, 1.0, 1.0, 1.0), z_scale=(2.0, 1.0, 0.2, 10.0, 1.0)):
    """S = Σ w_i · z_i. z 는 각 항을 '정상 범위 폭' 으로 나눈 값. 1 을 넘으면 그 항이 정상 범위를 벗어난 것."""
    terms = [dE, ae_ratio, ph_err, flow_resid, p_yolo]
    S, parts = 0.0, {}
    for name, v, wi, zs in zip(("dE", "ae", "ph", "flow", "yolo"), terms, w, z_scale):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        z = abs(float(v)) / zs; S += wi * z; parts[name] = round(z, 3)
    return S, parts


# ------------------------------------------------------------------ 데이터셋 생성 (시뮬레이션)
FAULT_POOL = [("tank_empty", "P-101"), ("tank_empty", "P-102"), ("valve_stuck", "XV-103"), ("signal_loss", "P-103"),
              ("camera_drift", "0.9"), ("ph_drift", "0.4"), ("pump_air", "P-101"), ("rpm", "60"), ("temp_step", "6"),
              ("stock_conc", "P-102=850")]


def cmd_gen(a):
    from .config import SystemConfig
    from .experiment import run_once, make_recipe, save_timeseries_csv
    rng = random.Random(a.seed)
    out = pathlib.Path(a.out)
    for sub in ("normal", "fault"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    def one(i, fault):
        cfg = SystemConfig(seed=a.seed + i)
        cfg.dac.calibrated = True                     # 실제 절차처럼 펌프 채널 2점 교정 후 운전
        cfg.camera.pixel_noise = rng.uniform(0.01, 0.03)
        cfg.reactor.rpm = rng.choice([200, 300, 400, 500])
        c = np.array([rng.uniform(8, 35), rng.uniform(4, 15), rng.uniform(8, 30)])
        rec, _ = make_recipe(cfg, target_cmy=c, mode=rng.choice(["open", "closed"]), dose_minutes=rng.uniform(1.0, 2.5),
                             flow_factor=np.array([rng.uniform(0.95, 1.0)] * 3))
        faults, meta = [], dict(fault_kind="", fault_arg="", t_fault=None, rpm=cfg.reactor.rpm, c_target=c.round(2).tolist())
        if fault:
            kind, arg = rng.choice(FAULT_POOL)
            tf = round(rng.uniform(15, rec.dose_minutes * 60 * 0.8), 1)
            faults = [f"{kind}:{arg}@{tf}"]; meta.update(fault_kind=kind, fault_arg=arg, t_fault=tf)
        res = run_once(cfg, rec, duration_s=a.duration, faults=faults, run_id=f"{'fault' if fault else 'normal'}{i:03d}")
        d = out / ("fault" if fault else "normal") / res["run_id"]; d.mkdir(exist_ok=True)
        save_timeseries_csv(res, d / "timeseries.csv")
        meta.update(dE2000=res["dE2000_true"], matched=res["matched"], alarms=res["alarms"])
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=float))
        print(f"{res['run_id']}: rpm {cfg.reactor.rpm} {('FAULT ' + faults[0]) if faults else 'normal'}  ΔE={res['dE2000_true']}")
    for i in range(a.normal):
        one(i, False)
    for i in range(a.faults):
        one(1000 + i, True)
    print("완료:", out)


def load_runs(data_dir, sub, dt=0.5):
    runs = []
    for d in sorted(pathlib.Path(data_dir, sub).glob("*")):
        if (d / "timeseries.csv").exists():
            rows = resample(canonical_rows(d / "timeseries.csv"), dt)
            meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
            runs.append((d.name, rows, meta))
    return runs


# ------------------------------------------------------------------ 학습 · 평가
def cmd_train(a):
    runs = load_runs(a.data, "normal", a.dt)
    if len(runs) < 2:
        sys.exit("정상 실행이 2개 이상 필요합니다 (gen 먼저)")
    fb = FeatureBuilder(a.dt, a.heel, (a.c_stock,) * 3)
    features = fb.available_features(runs[0][1])
    n_val = max(1, int(len(runs) * a.val))
    tr, va = runs[n_val:], runs[:n_val]
    Xtr = [fb.matrix(r, features) for _, r, _ in tr]
    mu = np.concatenate(Xtr).mean(0); sd = np.concatenate(Xtr).std(0) + 1e-6
    Xw = np.concatenate([windows((X - mu) / sd, a.window, a.stride) for X in Xtr])
    print(f"특징 {len(features)}개, 학습 창 {Xw.shape}, 정상 실행 train {len(tr)} / val {len(va)}")
    model = MODELS[a.model](a.window, len(features))
    model.fit(Xw, epochs=a.epochs, verbose=True)
    s_tr, _ = model.score(Xw)
    s_va = np.concatenate([model.score(windows((fb.matrix(r, features) - mu) / sd, a.window))[0] for _, r, _ in va])
    thr = float(np.quantile(s_va, a.quantile)) if len(s_va) else float(np.quantile(s_tr, a.quantile))
    det = Detector(model, features, mu, sd, thr, a.window, a.dt, a.heel, (a.c_stock,) * 3)
    per_run = [model.score(windows((fb.matrix(r, features) - mu) / sd, a.window))[0] for _, r, _ in runs]
    h = det.calibrate_cusum(per_run)
    print(f"CUSUM: 정상 점수 중앙값 {det.s_mu:.4f} sd {det.s_sd:.4f}, h = {h:.1f}")
    det.save(a.out)
    print(f"임계값(정상 val {a.quantile:.3%} 분위) = {thr:.4f}   train 점수 중앙값 {np.median(s_tr):.4f}  val 중앙값 {np.median(s_va):.4f}")
    print("저장:", a.out)
    if (pathlib.Path(a.data) / "fault").exists():
        a.model_dir = a.out; cmd_eval(a)


def evaluate(det: Detector, data_dir, dt=0.5, verbose=True):
    res = []
    for sub in ("normal", "fault"):
        for name, rows, meta in load_runs(data_dir, sub, dt):
            s, contrib, t = det.score_rows(rows)
            if len(s) == 0:
                continue
            tf = meta.get("t_fault")
            cus = cusum_seq(s, det.s_mu, det.s_sd, det.cusum_k)
            alarm = (s > det.thr) | (cus > det.cusum_h)
            if tf is None:
                res.append(dict(run=name, kind="normal", far=float((s > det.thr).mean()), far_cusum=float((cus > det.cusum_h).mean()),
                                max_ratio=float(s.max() / det.thr)))
            else:
                m_after = t >= tf
                hit = np.where(alarm & m_after)[0]
                delay = float(t[hit[0]] - tf) if len(hit) else None
                how = ("cusum" if cus[hit[0]] > det.cusum_h and s[hit[0]] <= det.thr else "score") if len(hit) else ""
                top = det.features[int(np.argmax(contrib[hit[0]]))] if len(hit) else ""
                res.append(dict(run=name, kind=meta["fault_kind"], arg=meta["fault_arg"], t_fault=tf, detected=delay is not None,
                                delay_s=delay, how=how, far_before=float(alarm[~m_after].mean()) if (~m_after).any() else 0.0,
                                top_feature=top, max_ratio=float(s[m_after].max() / det.thr)))
    normal = [r for r in res if r["kind"] == "normal"]; faults = [r for r in res if r["kind"] != "normal"]
    summary = dict(n_normal=len(normal), false_alarm_rate=float(np.mean([r["far"] for r in normal])) if normal else None,
                   false_alarm_rate_cusum=float(np.mean([r["far_cusum"] for r in normal])) if normal else None,
                   n_fault=len(faults), detected=sum(r["detected"] for r in faults),
                   median_delay_s=float(np.median([r["delay_s"] for r in faults if r["delay_s"] is not None])) if any(r["detected"] for r in faults) else None)
    if verbose:
        if normal:
            print(f"\n정상 {summary['n_normal']}회: 창 단위 오경보율 점수 {summary['false_alarm_rate']:.3%} / CUSUM {summary['false_alarm_rate_cusum']:.3%}")
        print(f"고장 {summary['n_fault']}회: 탐지 {summary['detected']}  중앙 지연 {summary['median_delay_s']} s")
        print(f"{'run':>10} {'fault':>12} {'arg':>12} {'t_f':>6} {'det':>4} {'delay':>7} {'how':>6} {'FAR<':>6} {'max/thr':>8}  top feature")
        for r in faults:
            print(f"{r['run']:>10} {r['kind']:>12} {r['arg']:>12} {r['t_fault']:>6} {('O' if r['detected'] else 'X'):>4} "
                  f"{(f'{r['delay_s']:.1f}' if r['delay_s'] is not None else '-'):>7} {r['how']:>6} {r['far_before']:>6.2f} {r['max_ratio']:>8.2f}  {r['top_feature']}")
    return summary, res


def cmd_eval(a):
    det = Detector.load(a.model_dir)
    summary, res = evaluate(det, a.data, det.dt)
    pathlib.Path(a.model_dir, "eval.json").write_text(json.dumps(dict(summary=summary, runs=res), ensure_ascii=False, indent=1))


def cmd_score(a):
    det = Detector.load(a.model_dir)
    rows = resample(canonical_rows(a.csv), det.dt)
    s, contrib, t = det.score_rows(rows)
    cus = cusum_seq(s, det.s_mu, det.s_sd, det.cusum_k)
    alarms = np.where((s > det.thr) | (cus > det.cusum_h))[0]
    print(f"창 {len(s)}개, 임계 {det.thr:.4f}, 최대 점수/임계 {s.max() / det.thr:.2f}, 알람 창 {len(alarms)}개"
          + (f", 첫 알람 t={t[alarms[0]]:.1f}s (주요 특징 {det.features[int(np.argmax(contrib[alarms[0]]))]})" if len(alarms) else ""))
    if a.plot:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        ax[0].plot(t, s, "k"); ax[0].axhline(det.thr, color="r", ls="--", label="threshold"); ax[0].set_ylabel("AE score"); ax[0].legend()
        ax[1].plot(t, cus, "b"); ax[1].axhline(det.cusum_h, color="r", ls="--"); ax[1].set_ylabel("CUSUM"); ax[1].set_xlabel("t [s]")
        fig.tight_layout(); fig.savefig(a.plot, dpi=120); print("그래프:", a.plot)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="anomaly", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("gen"); p.add_argument("--out", default="ad_ds"); p.add_argument("--normal", type=int, default=24)
    p.add_argument("--faults", type=int, default=16); p.add_argument("--duration", type=float, default=300.0); p.add_argument("--seed", type=int, default=500)
    for name in ("train", "eval"):
        p = sp.add_parser(name); p.add_argument("--data", default="ad_ds"); p.add_argument("--dt", type=float, default=0.5)
        if name == "train":
            p.add_argument("--model", choices=tuple(MODELS), default="pca"); p.add_argument("--out", default="ad_model")
            p.add_argument("--window", type=int, default=20); p.add_argument("--stride", type=int, default=2)
            p.add_argument("--epochs", type=int, default=40); p.add_argument("--val", type=float, default=0.25)
            p.add_argument("--quantile", type=float, default=0.995); p.add_argument("--heel", type=float, default=2000.0)
            p.add_argument("--c-stock", type=float, default=1000.0)
        else:
            p.add_argument("--model-dir", default="ad_model")
    p = sp.add_parser("score"); p.add_argument("--csv", required=True); p.add_argument("--model-dir", default="ad_model"); p.add_argument("--plot")
    a = ap.parse_args(argv)
    return {"gen": cmd_gen, "train": cmd_train, "eval": cmd_eval, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
