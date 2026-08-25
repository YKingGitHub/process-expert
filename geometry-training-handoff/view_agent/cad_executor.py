#!/usr/bin/env python3
"""Validate generated CadQuery code, execute it, and export a STEP file."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


ALLOWED_IMPORTS = {"cadquery", "math"}
FORBIDDEN_NAMES = {
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "urllib",
    "__builtins__",
    "__import__",
}
FORBIDDEN_ATTRIBUTES = {
    "dump",
    "export",
    "exportDXF",
    "exportStep",
    "exportStl",
    "exportSvg",
    "exporters",
    "importers",
    "load",
    "open",
    "popen",
    "read",
    "read_text",
    "save",
    "system",
    "write",
    "write_text",
}
FORBIDDEN_NODES = (
    ast.AsyncFunctionDef,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.FunctionDef,
    ast.Global,
    ast.Lambda,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Yield,
    ast.YieldFrom,
)


class UnsafeCadCode(ValueError):
    pass


def validate_source(source: str) -> ast.Module:
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise UnsafeCadCode(f"syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            raise UnsafeCadCode(f"forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] not in ALLOWED_IMPORTS:
                    raise UnsafeCadCode(f"forbidden import: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module not in ALLOWED_IMPORTS:
                raise UnsafeCadCode(f"forbidden import: {node.module}")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise UnsafeCadCode(f"forbidden name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise UnsafeCadCode(f"private attribute access: {node.attr}")
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            raise UnsafeCadCode(f"forbidden attribute access: {node.attr}")
    return tree


def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0 or name.split(".", 1)[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"import not allowed: {name}")
    return __import__(name, globals, locals, fromlist, level)


def execute_to_step(source: str, step_path: Path) -> None:
    tree = validate_source(source)
    safe_builtins = {
        "__import__": restricted_import,
        "abs": abs,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
    namespace = {"__builtins__": safe_builtins}
    exec(compile(tree, "<generated-cadquery>", "exec"), namespace, namespace)
    solid = namespace.get("solid")
    if solid is None:
        raise ValueError("generated code did not assign the final object to `solid`")

    import cadquery as cq

    step_path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(solid, str(step_path))
    if not step_path.is_file() or step_path.stat().st_size == 0:
        raise RuntimeError("CadQuery returned without producing a non-empty STEP file")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", type=Path, required=True)
    parser.add_argument("--step", type=Path, required=True)
    args = parser.parse_args()

    result = {"ok": False, "step": str(args.step.resolve())}
    try:
        execute_to_step(args.code.read_text(encoding="utf-8"), args.step.resolve())
        result["ok"] = True
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)
        print(json.dumps(result, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
