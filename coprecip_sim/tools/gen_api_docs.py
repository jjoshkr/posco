"""독스트링에서 API 참조(docs/API.md)를 만든다.  python tools/gen_api_docs.py"""
from __future__ import annotations
import importlib, inspect, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULES = ["config", "optics", "hardware", "process", "precip", "ph_control", "vision", "camera", "loadcell", "nodes", "daqhats_hal",
           "control", "recipe", "recipe_cli", "experiment", "anomaly", "yolo_train", "yolo_infer", "ai_node_main", "io_node_main",
           "zmq_bridge", "integration_test"]


def first_para(doc):
    doc = inspect.cleandoc(doc or "")
    return doc.split("\n\n")[0].strip()


def sig(obj):
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "(...)"


out = ["# API 참조", "", "`tools/gen_api_docs.py` 가 독스트링에서 생성. 자세한 설명은 각 모듈 상단 독스트링과 README 참고.", ""]
for name in MODULES:
    mod = importlib.import_module(f"cmysim.{name}")
    out += [f"## cmysim.{name}", ""]
    if mod.__doc__:
        out += ["```", inspect.cleandoc(mod.__doc__), "```", ""]
    members = [(n, o) for n, o in vars(mod).items() if not n.startswith("_") and getattr(o, "__module__", None) == mod.__name__]
    classes = [(n, o) for n, o in members if inspect.isclass(o)]
    funcs = [(n, o) for n, o in members if inspect.isfunction(o)]
    consts = [(n, o) for n, o in vars(mod).items() if n.isupper() and not n.startswith("_") and not inspect.ismodule(o) and not callable(o)]
    if consts:
        out += ["상수: " + ", ".join(f"`{n}`" for n, _ in consts), ""]
    for cn, cls in classes:
        out += [f"### class {cn}{sig(cls) if not hasattr(cls, '__dataclass_fields__') else ''}", ""]
        if hasattr(cls, "__dataclass_fields__"):
            out += ["| 필드 | 기본 |", "|---|---|"]
            for fn, f in cls.__dataclass_fields__.items():
                d = f.default if f.default is not inspect._empty and str(f.default) != "<dataclasses._MISSING_TYPE object>" else "(factory)"
                out.append(f"| {fn} | `{d}` |")
            out.append("")
        fp = first_para(cls.__doc__)
        if fp:
            out += [fp, ""]
        for mn, m in inspect.getmembers(cls, predicate=inspect.isfunction):
            if mn.startswith("_") and mn != "__init__":
                continue
            if m.__qualname__.split(".")[0] != cn:
                continue
            out.append(f"- `{mn}{sig(m)}`" + (f" — {first_para(m.__doc__).splitlines()[0]}" if m.__doc__ else ""))
        out.append("")
    for fn, f in funcs:
        out.append(f"- `{fn}{sig(f)}`" + (f" — {first_para(f.__doc__).splitlines()[0]}" if f.__doc__ else ""))
    if funcs:
        out.append("")
(ROOT / "docs" / "API.md").write_text("\n".join(out), encoding="utf-8")
print("wrote docs/API.md", len(out), "lines")
