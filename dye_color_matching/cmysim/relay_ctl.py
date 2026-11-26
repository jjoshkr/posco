"""릴레이 HAT(Relay_module_v1: MCP23017 ×2 → ULN2803 → 32CH 릴레이) 만 붙은 Pi 에서 터미널로 릴레이·밸브를 제어한다.
MCC 보드가 없어도 동작한다. 밸브 이름(XV-101…)은 io_node.json 의 mcp23017.relays 를 따른다.

  python -m cmysim.relay_ctl scan                      0x20~0x27 에서 응답하는 칩
  python -m cmysim.relay_ctl status                    릴레이 상태 (되읽기)
  python -m cmysim.relay_ctl on 1 9                    릴레이 1, 9 ON        (off 1 / off = 전부)
  python -m cmysim.relay_ctl valve XV-101 open         밸브 이름으로 (close)
  python -m cmysim.relay_ctl hold 1 3.0                릴레이 1 을 3 초 켰다 끔
  python -m cmysim.relay_ctl walk 1.0 1 9 17 25        순차 (기본: relays 에 정의된 것 전부)
  python -m cmysim.relay_ctl seq "XV-101:5,XV-102:5,XV-103:5"   밸브를 차례로 n 초씩 (자동 운전 흉내)
  python -m cmysim.relay_ctl shell                     대화형 (on/off/valve/status/q)
옵션: --addr 0x20 0x24 (U1, U2 주소) · --bus 1 · --config io_node.json · --sim (칩 없이)
종료·Ctrl+C·오류 때 전부 OFF. 칩 상태를 되읽어 명령과 다르면 경고.
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time

IODIRA, IODIRB, GPIOA, GPIOB, OLATA, OLATB = 0x00, 0x01, 0x12, 0x13, 0x14, 0x15
DEFAULT_RELAYS = {"XV-101": 1, "XV-102": 2, "XV-103": 3, "XV-104": 4}


class SimBus:
    """smbus2 흉내: 칩 두 개의 레지스터를 들고 있다 (리셋 상태 IODIR=0xFF)."""
    def __init__(self, present=(0x20, 0x24)):
        self.reg = {a: {IODIRA: 0xFF, IODIRB: 0xFF, OLATA: 0, OLATB: 0} for a in present}
        self.log = []
    def write_byte_data(self, addr, reg, val):
        if addr not in self.reg: raise OSError(121, "Remote I/O error")
        self.reg[addr][reg] = val & 0xFF; self.log.append((addr, reg, val))
    def read_byte_data(self, addr, reg):
        if addr not in self.reg: raise OSError(121, "Remote I/O error")
        r = self.reg[addr]
        if reg in (GPIOA, GPIOB):                       # 핀 레벨 = 출력 핀은 래치, 입력 핀은 0
            olat, iodir = (r[OLATA], r[IODIRA]) if reg == GPIOA else (r[OLATB], r[IODIRB])
            return olat & (iodir ^ 0xFF)
        return r.get(reg, 0)


def open_bus(busno: int, sim: bool):
    if sim:
        return SimBus()
    try:
        import smbus2
    except ImportError:
        sys.exit("smbus2 가 없습니다:  pip install smbus2   (또는 --sim)")
    try:
        return smbus2.SMBus(busno)
    except FileNotFoundError:
        sys.exit(f"/dev/i2c-{busno} 가 없습니다. I2C 를 켜세요:  sudo raspi-config nonint do_i2c 0  (재부팅)")
    except PermissionError:
        sys.exit("I2C 권한이 없습니다:  sudo usermod -aG i2c $USER  후 다시 로그인하거나 sudo 로 실행")


def scan(bus, lo=0x20, hi=0x27):
    found = []
    for a in range(lo, hi + 1):
        try:
            bus.read_byte_data(a, IODIRA); found.append(a)
        except OSError:
            pass
    return found


class RelayCtl:
    def __init__(self, bus, addr_u1=0x20, addr_u2=0x24, relays=None, reset_gpio=27, sim=False):
        from .daqhats_hal import MCP23017Relays
        self.relays = dict(relays or DEFAULT_RELAYS)
        cfg = {"addr_u1": addr_u1, "addr_u2": addr_u2, "active_high": True, "relays": self.relays,
               "rst_gpio": (None if sim else reset_gpio)}
        # 쓰는 릴레이 외에 1~32 전부 제어할 수 있게 전 채널을 출력으로 등록
        cfg_all = dict(cfg); cfg_all["relays"] = {**{f"R{n}": n for n in range(1, 33)}, **self.relays}
        self.mcp = MCP23017Relays(cfg_all, bus=bus)
        self.bus = bus; self.state = {n: False for n in range(1, 33)}

    def resolve(self, token: str) -> list[int]:
        """'1' / '1-8' / 'XV-101' / 'all' / 'inst' → 릴레이 번호 목록."""
        t = token.strip()
        if t.lower() == "all": return list(range(1, 33))
        if t.lower() == "inst": return sorted(set(v for v in self.relays.values()))
        if t.upper() in self.relays: return [int(self.relays[t.upper()])]
        if "-" in t and t.replace("-", "").isdigit():
            a, b = t.split("-"); return list(range(int(a), int(b) + 1))
        if t.isdigit() and 1 <= int(t) <= 32: return [int(t)]
        raise ValueError(f"'{token}': 릴레이 번호(1~32), 범위(1-8), 밸브 이름({', '.join(self.relays)}), all, inst 중 하나")

    def set(self, n: int, on: bool):
        self.mcp.set(n, on); self.state[n] = on

    def all_off(self):
        for n in range(1, 33):
            if self.state[n]: self.set(n, False)
        self.mcp.all_off()

    def readback(self) -> list[str]:
        """칩 레지스터를 읽어 명령과 비교. 문제 목록(비어 있으면 정상)."""
        issues = []
        for chip in ("U1", "U2"):
            addr = self.mcp.addr[chip]
            try:
                dira, dirb = self.bus.read_byte_data(addr, IODIRA), self.bus.read_byte_data(addr, IODIRB)
                gpa, gpb = self.bus.read_byte_data(addr, GPIOA), self.bus.read_byte_data(addr, GPIOB)
            except OSError as e:
                issues.append(f"{chip}(0x{addr:02X}): 응답 없음 ({e})"); continue
            if dira == 0xFF and dirb == 0xFF:
                issues.append(f"{chip}(0x{addr:02X}): 방향 레지스터가 입력으로 돌아감 — 칩이 리셋됨(전원 순간 저하?)")
            for n in range(1, 33):
                c, port, bit = self.mcp.locate(n)
                if c != chip: continue
                lvl = ((gpa if port == "A" else gpb) >> bit) & 1
                if bool(lvl) != self.state[n]:
                    issues.append(f"릴레이 {n} ({chip} GP{port}{bit}): 명령 {'ON' if self.state[n] else 'OFF'} 인데 핀 {'High' if lvl else 'Low'} — 납땜 브리지/쇼트 의심")
        return issues

    def status_line(self) -> str:
        on = [n for n in range(1, 33) if self.state[n]]
        names = {v: k for k, v in self.relays.items()}
        return "ON: " + (", ".join(f"{n}{'('+names[n]+')' if n in names else ''}" for n in on) if on else "없음")


def load_relays(config_path: str):
    p = pathlib.Path(config_path)
    if not p.exists():
        return DEFAULT_RELAYS, None
    d = json.loads(p.read_text()); m = d.get("mcp23017") or {}
    return (m.get("relays") or DEFAULT_RELAYS), m


def main(argv=None):
    ap = argparse.ArgumentParser(prog="relay_ctl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bus", type=int, default=1); ap.add_argument("--addr", nargs=2, default=None, metavar=("U1", "U2"))
    ap.add_argument("--config", default="io_node.json"); ap.add_argument("--sim", action="store_true"); ap.add_argument("--no-verify", action="store_true")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("scan"); sp.add_parser("status"); sp.add_parser("shell")
    p = sp.add_parser("on"); p.add_argument("targets", nargs="+")
    p = sp.add_parser("off"); p.add_argument("targets", nargs="*")
    p = sp.add_parser("valve"); p.add_argument("name"); p.add_argument("action", choices=("open", "close"))
    p = sp.add_parser("hold"); p.add_argument("target"); p.add_argument("seconds", type=float)
    p = sp.add_parser("walk"); p.add_argument("seconds", type=float); p.add_argument("targets", nargs="*")
    p = sp.add_parser("seq"); p.add_argument("plan", help='"XV-101:5,XV-102:5" 또는 "1:2,9:2"'); p.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args(argv)

    relays, mcfg = load_relays(a.config)
    addr_u1 = int(a.addr[0], 0) if a.addr else int((mcfg or {}).get("addr_u1", 0x20))
    addr_u2 = int(a.addr[1], 0) if a.addr else int((mcfg or {}).get("addr_u2", 0x24))
    bus = open_bus(a.bus, a.sim)
    if a.cmd == "scan":
        f = scan(bus); print("응답한 주소:", ", ".join(f"0x{x:02X}" for x in f) or "없음")
        if not f: print("→ HAT 장착·3.3 V·SDA/SCL 납땜, I2C 켜짐 여부 확인")
        elif len(f) == 1: print("→ 하나만 보임: 두 칩의 점퍼가 같거나(둘 다 0x20) 한 칩이 응답 없음")
        print(f"이 프로그램이 쓸 주소: U1 0x{addr_u1:02X}, U2 0x{addr_u2:02X}  (다르면 --addr 로 지정)")
        return 0
    found = scan(bus)
    for name, ad in (("U1", addr_u1), ("U2", addr_u2)):
        if ad not in found:
            sys.exit(f"{name} 주소 0x{ad:02X} 에서 응답이 없습니다. 응답한 주소: {', '.join(f'0x{x:02X}' for x in found) or '없음'}. 점퍼(JP1~3 = U1, JP4~6 = U2)와 --addr 확인")
    ctl = RelayCtl(bus, addr_u1, addr_u2, relays, sim=a.sim)
    print(f"연결: U1 0x{addr_u1:02X}, U2 0x{addr_u2:02X} · 밸브 매핑 {relays} · 시작 상태 전부 OFF")

    def verify():
        if a.no_verify: return
        for s in ctl.readback(): print("  ⚠", s)

    def apply(tokens, on):
        ns = [n for t in tokens for n in ctl.resolve(t)]
        for n in ns: ctl.set(n, on)
        print(("ON  " if on else "OFF ") + ", ".join(map(str, ns)), "→", ctl.status_line()); verify()

    try:
        if a.cmd == "status":
            print(ctl.status_line()); verify()
        elif a.cmd == "on":
            apply(a.targets, True); input("Enter 를 누르면 전부 끄고 종료합니다... ") if sys.stdin.isatty() else None
        elif a.cmd == "off":
            if a.targets: apply(a.targets, False)
            else: ctl.all_off(); print("전부 OFF")
        elif a.cmd == "valve":
            apply([a.name], a.action == "open")
            if a.action == "open" and sys.stdin.isatty(): input("Enter 를 누르면 닫고 종료합니다... ")
        elif a.cmd == "hold":
            apply([a.target], True); time.sleep(a.seconds); apply([a.target], False)
        elif a.cmd == "walk":
            ns = [n for t in (a.targets or ["inst"]) for n in ctl.resolve(t)]
            for n in ns:
                ctl.set(n, True); print(f"릴레이 {n} ON"); verify(); time.sleep(a.seconds); ctl.set(n, False); print(f"릴레이 {n} OFF"); time.sleep(0.3)
        elif a.cmd == "seq":
            steps = [(s.split(":")[0].strip(), float(s.split(":")[1])) for s in a.plan.split(",") if s.strip()]
            for r in range(a.repeat):
                for tok, sec in steps:
                    apply([tok], True); time.sleep(sec); apply([tok], False)
        elif a.cmd == "shell":
            print("명령: on <n|XV-101|1-8|all> · off [...] · valve <이름> open|close · status · walk <초> · q")
            while True:
                try: line = input("relay> ").strip()
                except EOFError: break
                if not line: continue
                w = line.split()
                try:
                    if w[0] == "q": break
                    elif w[0] == "on": apply(w[1:], True)
                    elif w[0] == "off": (apply(w[1:], False) if len(w) > 1 else (ctl.all_off(), print("전부 OFF")))
                    elif w[0] == "valve": apply([w[1]], w[2] == "open")
                    elif w[0] == "status": print(ctl.status_line()); verify()
                    elif w[0] == "walk":
                        for n in [x for t in (w[2:] or ["inst"]) for x in ctl.resolve(t)]:
                            ctl.set(n, True); print(f"릴레이 {n} ON"); time.sleep(float(w[1])); ctl.set(n, False)
                    else: print("모르는 명령")
                except (ValueError, IndexError) as e:
                    print("입력 오류:", e)
    except KeyboardInterrupt:
        pass
    finally:
        ctl.all_off(); print("종료: 릴레이 전부 OFF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
