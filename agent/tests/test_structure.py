"""Checks on how the code is organized, so structure can't drift past a review."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_MODULES = [p for p in (ROOT / "agent").glob("*.py") if p.name != "api.py"]


def test_only_api_module_talks_http():
    for path in AGENT_MODULES:
        tree = ast.parse(path.read_text())
        assert "httpx" not in path.read_text(), path.name
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not node.value.startswith(("/api/", "http://")), path.name


def test_tools_are_module_level_not_built_inside_functions():
    for path in AGENT_MODULES:
        for function in ast.walk(ast.parse(path.read_text())):
            if not isinstance(function, ast.FunctionDef):
                continue
            for inner in ast.walk(function):
                if inner is not function and isinstance(inner, ast.FunctionDef):
                    decorators = {ast.unparse(d) for d in inner.decorator_list}
                    assert "tool" not in decorators, f"{path.name}: {inner.name}"


def test_backend_routes_hold_no_sql():
    source = (ROOT / "backend" / "main.py").read_text()
    assert "sqlite3" not in source
    assert "execute(" not in source


def test_no_float_annotations_for_money():
    for path in [*AGENT_MODULES, *(ROOT / "backend").glob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text())):
            assert not (isinstance(node, ast.Name) and node.id == "float"), path.name


def test_backend_never_imports_the_agent():
    for path in (ROOT / "backend").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            assert not any(n.split(".")[0] == "agent" for n in names), path.name
