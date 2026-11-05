"""실제 두 Pi 사이에서 Bus 를 ZeroMQ 로 대체하는 최소 예시 (이 저장소에서는 실행하지 않음; pyzmq 필요).

I/O 노드:  PULL(tcp://*:5555) 로 명령 수신, PUB(tcp://*:5556) 으로 텔레메트리
AI  노드:  PUSH(tcp://<io-ip>:5555) 로 명령, SUB(tcp://<io-ip>:5556) 으로 텔레메트리

메시지 형식은 nodes.Bus 와 같은 JSON dict 이므로 IONode / AINode / Controller 코드는 그대로 쓴다.
"""
from __future__ import annotations
import json
from collections import deque


class ZmqBus:
    """nodes.Bus 와 같은 인터페이스. role='io' 또는 'ai'."""

    def __init__(self, role: str, io_ip: str = "192.168.10.2", cmd_port=5555, tele_port=5556):
        import zmq
        self.ctx, self.role = zmq.Context.instance(), role
        if role == "io":
            self.cmd_sock = self.ctx.socket(zmq.PULL); self.cmd_sock.bind(f"tcp://*:{cmd_port}")
            self.tele_sock = self.ctx.socket(zmq.PUB); self.tele_sock.bind(f"tcp://*:{tele_port}")
        else:
            self.cmd_sock = self.ctx.socket(zmq.PUSH); self.cmd_sock.connect(f"tcp://{io_ip}:{cmd_port}")
            self.tele_sock = self.ctx.socket(zmq.SUB); self.tele_sock.connect(f"tcp://{io_ip}:{tele_port}")
            self.tele_sock.setsockopt_string(zmq.SUBSCRIBE, "")
            self.tele_sock.setsockopt(zmq.CONFLATE, 1)      # 최신 텔레메트리만
        self._latest = None
        self.log: list = []

    # AI 노드 쪽
    def send_cmd(self, msg: dict):
        self.cmd_sock.send_json(msg)
        self.log.append(("cmd", msg))

    def latest(self):
        import zmq
        try:
            while True:
                self._latest = self.tele_sock.recv_json(flags=zmq.NOBLOCK)
        except zmq.Again:
            pass
        return self._latest

    # I/O 노드 쪽
    def drain_cmds(self):
        import zmq
        out = []
        try:
            while True:
                out.append(self.cmd_sock.recv_json(flags=zmq.NOBLOCK))
        except zmq.Again:
            pass
        return out

    def publish(self, msg: dict):
        self.tele_sock.send_json(msg)


def io_node_main(io_ip="0.0.0.0"):
    """Pi(I/O 노드) 에서: python -m cmysim.zmq_bridge io"""
    import time
    from .config import SystemConfig
    from .nodes import IONode, DaqHatsHAL
    cfg = SystemConfig()
    node = IONode(cfg, DaqHatsHAL(cfg), ZmqBus("io"))
    t0 = time.monotonic()
    while True:
        node.tick(time.monotonic() - t0)
        time.sleep(cfg.dt)


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["io"]:
        io_node_main()
