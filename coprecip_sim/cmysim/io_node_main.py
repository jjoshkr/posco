"""I/O 노드 실행 스크립트 (Raspberry Pi 5 + MCC 118 + MCC 134 + MCC 152 ×2).

  python -m cmysim.io_node_main list                         보드 목록·주소 확인 (daqhats_list_boards 와 같음)
  python -m cmysim.io_node_main run   [--config io_node.json] [--log io_log.csv]
  python -m cmysim.io_node_main run   --sim                   보드 없이 SimPlant 로 I/O 노드 흉내 (AI 노드와 이더넷 시험)
  python -m cmysim.io_node_main bench ramp 0                 AO0 를 0→5 V 계단으로 (멀티미터로 확인)
  python -m cmysim.io_node_main bench dio 4 1                DIO4 = 1 (LED/포토커플러)
  python -m cmysim.io_node_main bench blink 5                DIO5 깜빡임
  python -m cmysim.io_node_main bench read                   EF·아날로그 입력·온도 연속 표시
  python -m cmysim.io_node_main bench pump P-101 12          P-101 에 12 mA (OD 켬, RUN_ENABLE 은 켜지 않음)
  python -m cmysim.io_node_main bench calib P-101            2점 교정 (멀티미터 값을 물어봄) → io_node.json 에 저장
  python -m cmysim.io_node_main bench safe                   전부 안전 상태

run 은 10 Hz 로 IONode.tick() 을 돌리며 ZeroMQ(PULL 5555 / PUB 5556)로 AI 노드와 통신한다.
AI 노드 하트비트가 1 s 끊기면 IONode 가 SAFE, 이 프로세스가 죽어도 finally 에서 close() 로 출력을 끈다.
"""
from __future__ import annotations
import argparse, csv, signal, sys, time
import numpy as np
from .config import SystemConfig, PUMP_IDS
from .nodes import IONode, SimPlant, SimHAL
from .daqhats_hal import DaqHatsHAL, IOConfig


def cmd_list():
    import daqhats as dh
    boards = dh.hat_list(dh.HatIDs.ANY)
    if not boards:
        print("보드를 찾지 못했습니다. 40핀 헤더 접촉과 주소 점퍼를 확인하세요."); return 1
    for h in boards:
        print(f"주소 {h.address}: {h.product_name} (id {h.id}, ver {h.version})")
    return 0


def cmd_bench(a, io: IOConfig):
    hal = DaqHatsHAL(io)
    boards = {"mcc152#1": "#1", "mcc152#2": "#2"}
    try:
        op = a.args[0]
        board = a.board
        if op == "ramp":
            ch = int(a.args[1])
            for v in (0, 1, 2, 3, 4, 5, 0):
                hal.b[board].a_out_write(ch, float(v)); print(f"{board} AO{ch} = {v} V"); time.sleep(a.hold)
        elif op == "dio":
            ch, val = int(a.args[1]), int(a.args[2])
            hal._dio_out(board, ch, val); print(f"{board} DIO{ch} = {val}")
            time.sleep(a.hold)
        elif op == "blink":
            ch = int(a.args[1])
            for i in range(10):
                hal._dio_out(board, ch, i % 2); time.sleep(0.3)
            hal._dio_out(board, ch, 0)
        elif op == "read":
            while True:
                s = hal.snapshot()
                ef = " ".join(f"{k}:{'FAULT' if v else 'ok'}" for k, v in s["ef_fault"].items())
                print(f"{time.strftime('%H:%M:%S')} EF[{ef}] AI {s['ai_mA']} T={s['temp_C']:.2f}"); time.sleep(0.5)
        elif op == "pump":
            pid, mA = a.args[1], float(a.args[2])
            print(f"주의: 밸브/운전허가는 건드리지 않습니다. 펌프가 Pause 상태인지 확인하세요. {pid} ← {mA} mA, {a.hold}s 유지")
            hal.pump_enable(pid, True); hal.pump_set_mA(pid, mA); time.sleep(a.hold)
            print("피드백", round(hal.read_feedback_mA(pid), 3), "mA  EF", hal.read_ef_faults().get(pid))
            hal.pump_set_mA(pid, 0.0); hal.pump_enable(pid, False)
        elif op == "calib":
            pid = a.args[1]
            def ask():
                return float(input("  멀티미터 전류 [mA]: "))
            slope, gain, offset = hal.calibrate_pump_channel(pid, ask, settle=1.0)
            io.save(a.config)
            print(f"{pid}: 실측 기울기 {slope:.4f}, gain {gain:.4f}, offset {offset:+.4f} mA → {a.config} 저장")
        elif op == "safe":
            hal.close(); print("안전 상태")
        else:
            print("알 수 없는 벤치 명령", op); return 2
    except KeyboardInterrupt:
        pass
    finally:
        hal.close()
    return 0


def cmd_run(a, io: IOConfig):
    from .zmq_bridge import ZmqBus
    cfg = SystemConfig(dt=1.0 / a.hz)
    cfg.net.telemetry_hz = a.hz
    if a.sim:
        plant = SimPlant(cfg); hal = SimHAL(plant)
        print("보드 없이 시뮬레이션 공정으로 I/O 노드를 돌립니다 (AI 노드 연동 시험용).")
    else:
        plant, hal = None, DaqHatsHAL(io)
        print("보드 초기화 완료:", {k: v for k, v in io.addresses.items()})
    bus = ZmqBus("io", cmd_port=a.cmd_port, tele_port=a.tele_port)
    node = IONode(cfg, hal, bus)
    logf = open(a.log, "w", newline=""); w = csv.writer(logf)
    w.writerow(["t_s", "mode", "run_enable", *[f"cmd_mA_{p[-3:]}" for p in PUMP_IDS], *[f"spm_{p[-3:]}" for p in PUMP_IDS],
                *[f"strokes_{p[-3:]}" for p in PUMP_IDS], "XV-101", "XV-102", "XV-103", "ph", "p_bar", "temp_C", "ef", "alarms"])
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("flag", True))
    t0, period, n_alarm, overrun, next_log = time.monotonic(), 1.0 / a.hz, 0, 0, 0.0
    print(f"I/O 노드 시작: {a.hz} Hz, cmd PULL:{a.cmd_port}, tele PUB:{a.tele_port}. Ctrl+C 로 종료.")
    try:
        while not stop["flag"]:
            t = time.monotonic() - t0
            node.tick(t)
            if plant is not None:
                plant.step(cfg.dt)
            ef = hal.read_ef_faults() if hasattr(hal, "read_ef_faults") else {}
            for pid, bad in ef.items():
                if bad and node.cmd_mA.get(pid, 0) > 0:
                    node.alarm(f"EF {pid}: XTR111 fault (open load / over-temp)")
            if len(node.alarms) > n_alarm:
                for al in node.alarms[n_alarm:]:
                    print(f"[{al[0]:7.1f}s] {al[1]}")
                n_alarm = len(node.alarms)
            if t >= next_log:
                next_log = t + 1.0
                w.writerow([round(t, 2), node.mode, node.run_en, *[round(node.cmd_mA[p], 2) for p in PUMP_IDS],
                            *[round(hal.read_feedback_mA(p), 2) for p in PUMP_IDS], *[round(node.strokes[p], 1) for p in PUMP_IDS],
                            *[int(node.valve_on[v]) for v in ("XV-101", "XV-102", "XV-103")],
                            round(hal.read_ph(), 2), round(hal.read_pressure_bar(), 2), round(hal.read_temp_C(), 2),
                            ";".join(k for k, v in ef.items() if v), len(node.alarms)])
                logf.flush()
                if a.verbose:
                    print(f"{t:7.1f}s {node.mode:4s} en={int(node.run_en)} mA={[round(node.cmd_mA[p],1) for p in PUMP_IDS]} "
                          f"str={[round(node.strokes[p]) for p in PUMP_IDS]} valves={[int(node.valve_on[v]) for v in node.valve_on]} "
                          f"hb_age={t - node.last_hb:.1f}s")
            el = (time.monotonic() - t0) - t
            if el > period:
                overrun += 1
            time.sleep(max(0.0, period - el))
    finally:
        node.safe("process exit")
        if hasattr(hal, "close"):
            hal.close()
        logf.close()
        print(f"종료. 루프 지연 초과 {overrun}회, 알람 {len(node.alarms)}개, 로그 {a.log}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="io_node_main", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="io_node.json")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list")
    p = sp.add_parser("run"); p.add_argument("--sim", action="store_true"); p.add_argument("--hz", type=float, default=10.0)
    p.add_argument("--log", default="io_log.csv"); p.add_argument("--cmd-port", type=int, default=5555); p.add_argument("--tele-port", type=int, default=5556)
    p.add_argument("--verbose", "-v", action="store_true")
    p = sp.add_parser("bench"); p.add_argument("args", nargs="+"); p.add_argument("--board", default="mcc152#1"); p.add_argument("--hold", type=float, default=3.0)
    p = sp.add_parser("init-config", help="기본 io_node.json 을 써 둔다 (주소·핀 바꿀 때 편집)")
    a = ap.parse_args(argv)
    io = IOConfig.load(a.config)
    if a.cmd == "list":
        return cmd_list()
    if a.cmd == "init-config":
        io.save(a.config); print("저장:", a.config); return 0
    if a.cmd == "bench":
        return cmd_bench(a, io)
    return cmd_run(a, io)


if __name__ == "__main__":
    sys.exit(main())
