import ast
from pathlib import Path


def test_app_factory_only_composes_services_and_routers():
    root = Path(__file__).resolve().parents[1]
    source = (root / "main.py").read_text()
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and any(sql in node.value for sql in ("SELECT ", "INSERT ", "UPDATE "))
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr in ("get", "post", "put", "delete")
        for node in ast.walk(tree)
    )
    for path in (root / "routes").glob("*.py"):
        assert not any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(sql in node.value for sql in ("SELECT ", "INSERT ", "UPDATE "))
            for node in ast.walk(ast.parse(path.read_text()))
        ), path


def test_generic_contracts_do_not_depend_on_queue_workflow():
    root = Path(__file__).resolve().parents[1]
    assert "backend.harness_models" not in (root / "documents.py").read_text()
    assert "backend.harness" not in (root / "contracts.py").read_text()
