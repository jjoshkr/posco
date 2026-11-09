"""브라우저 시뮬레이션 인터페이스 — 색소 색 매칭 실험을 직접 돌려 본다.

  python -m cmysim.ui                 → http://localhost:8050
  python -m cmysim.ui --port 8060 --host 0.0.0.0

표준 라이브러리만 사용(http.server + threading). 페이지는 인라인 HTML/JS(외부 CDN 없음, 오프라인 OK).
한 화면에서: 목표색 선택 → 시작 → 농도·ΔE·펌프 그래프, 목표/카메라 색 견본, I/O 노드 상태·알람, 고장 주입, 속도 조절,
수동 모드(밸브 열기, 스트로크 투입)까지 할 수 있다. 내부는 experiment.run_once 와 같은 SimPlant / IONode / AINode / Controller.
"""
from __future__ import annotations
import argparse, json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import numpy as np
from .config import SystemConfig, PUMP_IDS, VALVE_IDS, rig_prominent_feeder
from .nodes import Bus, SimPlant, SimHAL, IONode, AINode
from .control import Controller, plan_doses
from .experiment import make_recipe, apply_fault
from . import optics


class SimSession:
    """한 번의 실험. 백그라운드 스레드가 speed 배속으로 시뮬레이션을 진행한다."""

    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.running = False
        self.paused = False
        self.speed = 10.0
        self.params = {}
        self.reset()

    # ---- 구성
    def reset(self, params: dict | None = None):
        p = dict(target="#5A8F7B", heel_mL=2000, rpm=300, mode="closed", dose_min=1.5, flow_factor=0.97,
                 pump_mode="pulse", pixel_noise=0.02, seed=0, manual=False, de_match=1.5)
        p.update(params or {})
        self.params = p
        cfg = rig_prominent_feeder(p["pump_mode"])
        cfg.seed = int(p["seed"]); cfg.dac.calibrated = True
        cfg.reactor.heel_mL = float(p["heel_mL"]); cfg.reactor.rpm = float(p["rpm"])
        cfg.camera.pixel_noise = float(p["pixel_noise"])
        self.cfg = cfg
        if str(p["target"]).startswith("#"):
            rec, resid = make_recipe(cfg, p["target"], None, mode=p["mode"], dose_minutes=float(p["dose_min"]),
                                     de_match=float(p["de_match"]), flow_factor=np.array([float(p["flow_factor"])] * 3))
        else:
            cmy = [float(v) for v in str(p["target"]).split(",")]
            rec, resid = make_recipe(cfg, None, cmy, mode=p["mode"], dose_minutes=float(p["dose_min"]),
                                     de_match=float(p["de_match"]), flow_factor=np.array([float(p["flow_factor"])] * 3))
        self.recipe, self.target_resid = rec, resid
        self.plant = SimPlant(cfg); self.bus = Bus(); self.io = IONode(cfg, SimHAL(self.plant), self.bus)
        self.ctl = Controller(cfg, rec)
        self.ai = AINode(cfg, self.bus, self.plant.camera, self.ctl)
        self.ai.alive = not p["manual"]
        self.t = 0.0
        self.hist = {k: [] for k in ("t", "c_true", "c_hat", "dE", "dE_true", "spm", "strokes", "V", "tank", "valves", "state", "mode", "rgb", "rgb_true")}
        self.events = []
        self.plan = plan_doses(cfg, cfg.reactor.heel_mL, rec.c_target, rec.dose_minutes, rec.flow_factor)
        self._n_alarm = 0
        if p["manual"]:                                    # 수동 모드: 노드 무장 + 운전 허가만 해 둔다
            self.bus.send_cmd(dict(cmd="arm")); self.bus.send_cmd(dict(cmd="run_enable", on=True))

    # ---- 진행
    def step(self):
        cfg, dt = self.cfg, self.cfg.dt
        self.t += dt
        if self.params["manual"]:
            self.bus.send_cmd(dict(cmd="heartbeat"))
        self.io.tick(self.t)
        self.ai.tick(self.t, self.plant.reactor.c_obs)
        self.plant.step(dt)
        if len(self.io.alarms) > self._n_alarm:
            for a in self.io.alarms[self._n_alarm:]:
                self.events.append((round(a[0], 1), "IO", a[1]))
            self._n_alarm = len(self.io.alarms)
        if int(round(self.t / dt)) % 5 == 0:                 # 0.5 s 마다 기록
            cam = cfg.camera
            rgb_true = optics.conc_to_rgb8(cam.E, cam.I0, self.plant.reactor.c_true, cam.gamma, cam.glare)
            tele = self.bus.latest() or {}
            pm = tele.get("pumps", {})
            h = self.hist
            h["t"].append(round(self.t, 1))
            h["c_true"].append([round(float(v), 2) for v in self.plant.reactor.c_true])
            h["c_hat"].append([round(float(v), 2) for v in self.ctl.c_hat])
            h["dE"].append(round(float(self.ctl.de), 2) if self.ctl.de == self.ctl.de else None)
            h["dE_true"].append(round(optics.delta_e2000(rgb_true, self.recipe.target_rgb8), 2))
            h["spm"].append([round(pm.get(p, {}).get("spm", 0.0), 1) for p in PUMP_IDS])
            h["strokes"].append([round(self.io.strokes[p]) for p in PUMP_IDS])
            h["V"].append(round(self.plant.reactor.V_mL, 1))
            h["tank"].append([round(tk.volume_mL, 1) for tk in self.plant.tanks[:3]])
            h["valves"].append([int(self.io.valve_on[v]) for v in VALVE_IDS])
            h["state"].append(self.ctl.state); h["mode"].append(self.io.mode)
            h["rgb"].append([int(v) for v in self.ctl.rgb]); h["rgb_true"].append([int(v) for v in rgb_true])
            for k in h:                                        # 메모리 상한 (최근 2시간)
                if len(h[k]) > 14400:
                    del h[k][:len(h[k]) - 14400]
        if self.ctl.events and (not self.events or self.events[-1][2] != self.ctl.events[-1][1] or self.events[-1][1] != "AI"):
            last = self.ctl.events[-1]
            if not any(e[1] == "AI" and e[2] == last[1] and e[0] == round(last[0], 1) for e in self.events[-10:]):
                self.events.append((round(last[0], 1), "AI", last[1]))

    def _loop(self):
        acc = 0.0; last = time.monotonic()
        while self.running:
            now = time.monotonic(); wall = now - last; last = now
            if not self.paused:
                acc += wall * self.speed
                n = int(acc / self.cfg.dt); acc -= n * self.cfg.dt
                with self.lock:
                    for _ in range(min(n, 200)):
                        self.step()
            time.sleep(0.02)

    def start(self):
        if self.thread and self.thread.is_alive():
            self.running = False; self.thread.join(1.0)
        self.running, self.paused = True, False
        self.thread = threading.Thread(target=self._loop, daemon=True); self.thread.start()

    # ---- 상태 (JSON)
    def state(self, since: int = 0) -> dict:
        with self.lock:
            tele = self.bus.latest() or {}
            h = self.hist
            n = len(h["t"])
            sl = slice(max(0, since), n)
            cam = self.cfg.camera
            return dict(
                t=round(self.t, 1), running=self.running, paused=self.paused, speed=self.speed, params=self.params,
                target_hex=optics.rgb8_to_hex(self.recipe.target_rgb8), target_resid=round(float(self.target_resid), 2),
                c_target=[round(float(v), 2) for v in self.recipe.c_target],
                camera_hex=optics.rgb8_to_hex(self.ctl.rgb), true_hex=(h["rgb_true"][-1] if n else None),
                ctl_state=self.ctl.state, done=self.ctl.done, dE=(None if self.ctl.de != self.ctl.de else round(float(self.ctl.de), 2)),
                trims=self.ctl.trims, aborted=self.ctl.aborted,
                io=dict(mode=self.io.mode, run_enable=self.io.run_en, valves=dict(self.io.valve_on),
                        pumps={p: dict(spm=round((tele.get("pumps", {}).get(p, {}) or {}).get("spm", 0.0), 1),
                                       strokes=round(self.io.strokes[p]), dosed_mL=round(self.io.dosed_mL[p], 2),
                                       mode=(tele.get("pumps", {}).get(p, {}) or {}).get("mode", "")) for p in PUMP_IDS},
                        est_V=round(self.cfg.reactor.heel_mL + sum(self.io.dosed_mL.values()), 1), alarms=len(self.io.alarms)),
                reactor=dict(V_mL=round(self.plant.reactor.V_mL, 1), rpm=round(self.plant.reactor.rpm),
                             c_true=[round(float(v), 2) for v in self.plant.reactor.c_true],
                             tanks=[round(tk.volume_mL, 1) for tk in self.plant.tanks[:3]]),
                plan=[dict(id=d["id"], volume_mL=round(d["volume_mL"], 2), strokes=round(d["strokes"]), rate=round(d["rate_mL_min"], 2),
                           mA=round(d["mA"], 2)) for d in self.plan],
                events=self.events[-60:], n=n,
                hist={k: h[k][sl] for k in ("t", "c_true", "c_hat", "dE", "dE_true", "spm", "strokes", "V", "tank", "valves", "rgb", "rgb_true")},
            )

    # ---- 조작
    def inject(self, kind: str, arg: str):
        with self.lock:
            apply_fault(kind, arg, self.plant, self.ai, self.io)
            self.io.alarms.append((self.t, f"FAULT_INJECTED {kind} {arg}"))
            self.events.append((round(self.t, 1), "IO", f"FAULT_INJECTED {kind} {arg}"))
            self._n_alarm = len(self.io.alarms)

    def manual(self, cmd: dict):
        with self.lock:
            self.bus.send_cmd(cmd)


# ------------------------------------------------------------------ HTML
PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>CMY 색 매칭 시뮬레이터</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#222;--mut:#666;--line:#ddd;--acc:#2a6fdb;--bad:#c62828;--ok:#2e7d32}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans KR",sans-serif;background:var(--bg);color:var(--ink)}
header{background:#1f2a3a;color:#fff;padding:10px 16px;display:flex;align-items:center;gap:16px}
header h1{font-size:16px;margin:0;font-weight:600}header .st{font-size:13px;opacity:.9}
main{display:grid;grid-template-columns:320px 1fr;gap:12px;padding:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.card h2{font-size:13px;margin:0 0 8px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
label{display:block;font-size:12px;color:var(--mut);margin-top:8px}
input,select,button{font:inherit}input[type=text],input[type=number],select{width:100%;box-sizing:border-box;padding:6px;border:1px solid var(--line);border-radius:6px}
.row{display:flex;gap:8px}.row>*{flex:1}
button{padding:7px 10px;border:1px solid var(--line);background:#fff;border-radius:6px;cursor:pointer}
button.pri{background:var(--acc);color:#fff;border-color:var(--acc)}button.warn{border-color:var(--bad);color:var(--bad)}
.sw{display:flex;gap:10px;margin:8px 0}.sw div{flex:1;text-align:center;font-size:12px}.sw .box{height:54px;border-radius:6px;border:1px solid var(--line)}
canvas{width:100%;height:170px;display:block;background:#fff}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:3px 4px;border-bottom:1px solid #eee;text-align:left}
.log{height:160px;overflow:auto;font-size:12px;font-family:ui-monospace,Menlo,Consolas,monospace;background:#fafafa;border:1px solid var(--line);border-radius:6px;padding:6px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;background:#eee}.badge.run{background:#e3f2fd;color:#0d47a1}.badge.safe{background:#fdecea;color:var(--bad)}.badge.done{background:#e8f5e9;color:var(--ok)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:12px}.kv b{color:var(--mut);font-weight:500}
small{color:var(--mut)}
@media (max-width:900px){main{grid-template-columns:1fr}}
</style></head><body>
<header><h1>CMY 색 매칭 시뮬레이터</h1><span class="st" id="hdr">—</span></header>
<main>
<section>
 <div class="card"><h2>실험 설정</h2>
  <label>목표색 (hex 또는 C,M,Y mg/L)</label>
  <div class="row"><input type="color" id="pick" value="#5A8F7B" style="width:48px;flex:none;height:34px;padding:0;border:1px solid var(--line);border-radius:6px"><input type="text" id="target" value="#5A8F7B"></div>
  <div class="row"><div><label>초기 물 [mL]</label><input type="number" id="heel" value="2000"></div><div><label>교반 rpm</label><input type="number" id="rpm" value="300"></div></div>
  <div class="row"><div><label>제어</label><select id="mode"><option value="closed">closed (카메라 트림)</option><option value="open">open (피드포워드만)</option></select></div>
   <div><label>펌프 구동</label><select id="pump_mode"><option value="pulse">pulse (접점)</option><option value="analog">analog (4–20 mA)</option></select></div></div>
  <div class="row"><div><label>도징 시간 [min]</label><input type="number" id="dose_min" value="1.5" step="0.5"></div><div><label>피드포워드 배율</label><input type="number" id="ff" value="0.97" step="0.01"></div></div>
  <div class="row"><div><label>카메라 잡음</label><input type="number" id="noise" value="0.02" step="0.005"></div><div><label>시드</label><input type="number" id="seed" value="0"></div></div>
  <label><input type="checkbox" id="manual"> 수동 모드 (제어기 없이 직접 밸브·펌프 조작)</label>
  <div class="row" style="margin-top:10px"><button class="pri" onclick="start()">시작 / 재시작</button><button onclick="pause()" id="pbtn">일시정지</button><button class="warn" onclick="safe()">SAFE</button></div>
  <label>속도 <span id="spv">10</span>×</label><input type="range" id="speed" min="1" max="60" value="10" oninput="setSpeed(this.value)">
 </div>
 <div class="card"><h2>고장 주입</h2>
  <div class="row"><button onclick="fault('tank_empty','P-101')">C 탱크 고갈</button><button onclick="fault('valve_stuck','XV-102')">XV-102 고착</button></div>
  <div class="row" style="margin-top:6px"><button onclick="fault('camera_drift','0.9')">카메라 −10 %</button><button onclick="fault('stock_conc','P-103=850')">Y 스톡 −15 %</button></div>
  <div class="row" style="margin-top:6px"><button onclick="fault('rpm','60')">교반 60 rpm</button><button onclick="fault('ai_crash','')">AI 노드 사망</button></div>
 </div>
 <div class="card" id="manualcard" style="display:none"><h2>수동 조작</h2>
  <div class="row"><select id="mpump"><option>P-101</option><option>P-102</option><option>P-103</option></select><input type="number" id="mstrokes" value="50" title="스트로크 수"><input type="number" id="mma" value="12" step="0.5" title="mA (속도)"></div>
  <div class="row" style="margin-top:6px"><button onclick="mvalve(true)">밸브 열기</button><button onclick="mvalve(false)">밸브 닫기</button><button class="pri" onclick="mdose()">투입</button><button onclick="mstop()">정지</button></div>
  <small>인터록: 밸브를 먼저 열어야 투입이 됩니다. 닫힌 채 투입하면 I/O 노드가 거부합니다.</small>
 </div>
 <div class="card"><h2>투입 계획</h2><table id="plan"></table></div>
</section>
<section>
 <div class="card">
  <div class="sw"><div><div class="box" id="swT"></div>목표 <span id="hexT"></span></div><div><div class="box" id="swC"></div>카메라 <span id="hexC"></span></div><div><div class="box" id="swR"></div>실제 <span id="hexR"></span></div></div>
  <div class="kv"><b>상태</b><span><span class="badge" id="iomode">—</span> <span id="ctl"></span></span>
   <b>ΔE2000</b><span id="de"></span><b>목표 농도 C/M/Y</b><span id="ct"></span><b>추정 ĉ</b><span id="ch"></span><b>실제 c</b><span id="cr"></span>
   <b>반응기</b><span id="rx"></span><b>펌프</b><span id="pumps"></span><b>밸브</b><span id="valves"></span></div>
 </div>
 <div class="card"><h2>농도 [mg/L] — 실선 실제, 점선 카메라 추정, 가는선 목표</h2><canvas id="c1"></canvas></div>
 <div class="card"><h2>ΔE2000 — 검정 실제, 회색 카메라</h2><canvas id="c2"></canvas></div>
 <div class="card"><h2>펌프 spm (C 파랑 · M 자홍 · Y 노랑)</h2><canvas id="c3"></canvas></div>
 <div class="card"><h2>이벤트 · 알람</h2><div class="log" id="log"></div></div>
</section>
</main>
<script>
const $=id=>document.getElementById(id);
let H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]},n=0,ct=[0,0,0],paused=false;
const COL=["#00AEEF","#EC008C","#E6B800"];
$('pick').oninput=e=>{$('target').value=e.target.value.toUpperCase()};
$('manual').onchange=e=>{$('manualcard').style.display=e.target.checked?'block':'none'};
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});return r.json()}
async function start(){H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]};n=0;
 await post('/api/start',{target:$('target').value,heel_mL:+$('heel').value,rpm:+$('rpm').value,mode:$('mode').value,pump_mode:$('pump_mode').value,
  dose_min:+$('dose_min').value,flow_factor:+$('ff').value,pixel_noise:+$('noise').value,seed:+$('seed').value,manual:$('manual').checked,speed:+$('speed').value});}
async function pause(){const s=await post('/api/pause');paused=s.paused;$('pbtn').textContent=paused?'계속':'일시정지'}
async function safe(){await post('/api/manual',{cmd:'safe'})}
async function setSpeed(v){$('spv').textContent=v;await post('/api/speed',{speed:+v})}
async function fault(k,a){await post('/api/fault',{kind:k,arg:a})}
async function mvalve(open){const p=$('mpump').value;await post('/api/manual',{cmd:'valve',id:'XV-'+p.slice(2),open})}
async function mdose(){await post('/api/manual',{cmd:'dose',id:$('mpump').value,mA:+$('mma').value,strokes:+$('mstrokes').value})}
async function mstop(){await post('/api/manual',{cmd:'stop',id:$('mpump').value})}
function line(cv,series,opts){const c=cv.getContext('2d');const W=cv.width=cv.clientWidth*devicePixelRatio,Hh=cv.height=cv.clientHeight*devicePixelRatio;c.scale(1,1);c.clearRect(0,0,W,Hh);
 const t=H.t;if(t.length<2)return;const pad=36*devicePixelRatio,x0=pad,x1=W-8,y0=8,y1=Hh-20*devicePixelRatio;let ymax=opts.ymax||0;
 series.forEach(s=>s.y.forEach(v=>{if(v!=null&&v>ymax)ymax=v}));ymax=Math.max(ymax*1.1,opts.ymin||1);const tmin=t[0],tmax=t[t.length-1];
 const X=v=>x0+(v-tmin)/(tmax-tmin||1)*(x1-x0),Y=v=>y1-(v/ymax)*(y1-y0);
 c.strokeStyle='#eee';c.lineWidth=1;for(let i=0;i<=4;i++){const y=y0+(y1-y0)*i/4;c.beginPath();c.moveTo(x0,y);c.lineTo(x1,y);c.stroke();c.fillStyle='#888';c.font=`${11*devicePixelRatio}px sans-serif`;c.fillText((ymax*(1-i/4)).toFixed(opts.dec==null?1:opts.dec),4,y+4)}
 c.fillStyle='#888';c.fillText(tmin.toFixed(0)+' s',x0,Hh-4);c.fillText(tmax.toFixed(0)+' s',x1-40*devicePixelRatio,Hh-4);
 if(opts.hlines)opts.hlines.forEach((v,i)=>{c.setLineDash([2,3]);c.strokeStyle=COL[i]||'#999';c.lineWidth=1;c.beginPath();c.moveTo(x0,Y(v));c.lineTo(x1,Y(v));c.stroke();c.setLineDash([])});
 series.forEach(s=>{c.strokeStyle=s.color;c.lineWidth=(s.width||1.5)*devicePixelRatio;c.setLineDash(s.dash||[]);c.beginPath();let started=false;
  s.y.forEach((v,i)=>{if(v==null){started=false;return}const x=X(t[i]),y=Y(v);if(!started){c.moveTo(x,y);started=true}else c.lineTo(x,y)});c.stroke();c.setLineDash([])});}
function draw(){const c1=$('c1'),c2=$('c2'),c3=$('c3');
 line(c1,[0,1,2].flatMap(j=>[{y:H.c_true.map(v=>v[j]),color:COL[j]},{y:H.c_hat.map(v=>v[j]),color:COL[j],dash:[4,3],width:1}]),{hlines:ct,dec:1});
 line(c2,[{y:H.dE_true,color:'#000'},{y:H.dE,color:'#888',dash:[4,3],width:1}],{ymin:5,hlines:[],dec:1});
 line(c3,[0,1,2].map(j=>({y:H.spm.map(v=>v[j]),color:COL[j]})),{ymin:50,dec:0});}
async function poll(){try{const s=await (await fetch('/api/state?since='+n)).json();
 if(s.n<n){H={t:[],c_true:[],c_hat:[],dE:[],dE_true:[],spm:[],valves:[]};n=0;const s2=await (await fetch('/api/state?since=0')).json();Object.assign(s,s2)}
 for(const k of Object.keys(H))H[k]=H[k].concat(s.hist[k]||[]);n=s.n;ct=s.c_target;
 $('hdr').textContent=`t = ${s.t} s · ${s.speed}× · ${s.params.pump_mode} 펌프 · ${s.params.mode}`;
 $('swT').style.background=s.target_hex;$('hexT').textContent=s.target_hex;$('swC').style.background=s.camera_hex;$('hexC').textContent=s.camera_hex;
 const rt=s.true_hex?'#'+s.true_hex.map(v=>v.toString(16).padStart(2,'0')).join('').toUpperCase():'#FFFFFF';$('swR').style.background=rt;$('hexR').textContent=rt;
 const b=$('iomode');b.textContent='I/O '+s.io.mode;b.className='badge '+(s.io.mode==='RUN'?'run':'safe');
 $('ctl').textContent=(s.done?'완료 ':'')+'제어기 '+s.ctl_state+(s.trims?` · 트림 ${s.trims}회`:'')+(s.aborted?' · 중단: '+s.aborted:'');if(s.done)b.className='badge done';
 $('de').textContent=(s.dE==null?'—':s.dE)+'  (실제 '+(H.dE_true.length?H.dE_true[H.dE_true.length-1]:'—')+')';
 $('ct').textContent=s.c_target.join(' / ');$('ch').textContent=(s.hist.c_hat.length?H.c_hat[H.c_hat.length-1]:[]).join(' / ');$('cr').textContent=s.reactor.c_true.join(' / ');
 $('rx').textContent=`${s.reactor.V_mL} mL · ${s.reactor.rpm} rpm · 탱크 ${s.reactor.tanks.join(' / ')} mL`;
 $('pumps').textContent=Object.entries(s.io.pumps).map(([k,v])=>`${k.slice(2)}: ${v.spm} spm, ${v.strokes} str, ${v.dosed_mL} mL`).join(' · ');
 $('valves').textContent=Object.entries(s.io.valves).filter(([k])=>k!=='XV-104').map(([k,v])=>`${k.slice(3)} ${v?'열림':'닫힘'}`).join(' · ')+(s.io.run_enable?' · 운전허가 ON':' · 운전허가 OFF');
 $('plan').innerHTML='<tr><th>펌프</th><th>mL</th><th>스트로크</th><th>mL/min</th><th>mA</th></tr>'+s.plan.map(d=>`<tr><td>${d.id}</td><td>${d.volume_mL}</td><td>${d.strokes}</td><td>${d.rate}</td><td>${d.mA}</td></tr>`).join('');
 $('log').innerHTML=s.events.slice().reverse().map(e=>`<div><span style="color:#888">${e[0]}s</span> <b>${e[1]}</b> ${e[2]}</div>`).join('');
 draw();}catch(e){console.log(e)}setTimeout(poll,500)}
poll();window.addEventListener('resize',draw);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    session: SimSession = None

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            since = 0
            if "since=" in self.path:
                try:
                    since = int(self.path.split("since=")[1].split("&")[0])
                except ValueError:
                    since = 0
            return self._json(self.session.state(since))
        b = PAGE.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        s = self.session
        if self.path == "/api/start":
            speed = float(body.pop("speed", s.speed))
            with s.lock:
                s.reset(body)
            s.speed = speed; s.start(); return self._json(dict(ok=True))
        if self.path == "/api/pause":
            s.paused = not s.paused; return self._json(dict(paused=s.paused))
        if self.path == "/api/speed":
            s.speed = float(np.clip(float(body.get("speed", 10)), 0.1, 200)); return self._json(dict(speed=s.speed))
        if self.path == "/api/fault":
            s.inject(body["kind"], str(body.get("arg", ""))); return self._json(dict(ok=True))
        if self.path == "/api/manual":
            s.manual(body); return self._json(dict(ok=True))
        return self._json(dict(error="unknown"), 404)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ui", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--port", type=int, default=8050)
    ap.add_argument("--autostart", action="store_true", help="서버 시작과 함께 기본 실험 실행")
    a = ap.parse_args(argv)
    Handler.session = SimSession()
    if a.autostart:
        Handler.session.start()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"CMY 시뮬레이터 UI: http://{a.host}:{a.port}   (Ctrl+C 로 종료)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        Handler.session.running = False
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
