"""Executable boundaries complement, rather than replace, source review."""

import ast
from pathlib import Path

from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from agent.tools import CLAIM_TOOLS, QUEUE_TOOLS

AGENT = Path(__file__).resolve().parents[1]


def test_backend_transport_has_one_owner():
    for path in AGENT.glob("*.py"):
        tree = ast.parse(path.read_text())
        if path.name != "api.py":
            literals = [
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            ]
            assert not any(
                value.startswith("/api/") or "BACKEND_URL" in value
                for value in literals
            ), path
            assert not any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "Client"
                for node in ast.walk(tree)
            ), path
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {"agent.main", "agent.queue"}, path
                assert not (node.module or "").startswith("backend"), path
                if node.module == "agent":
                    assert not {"main", "queue"} & {item.name for item in node.names}, (
                        path
                    )
                if path.name == "harness.py" and (node.module or "").startswith(
                    "agent."
                ):
                    assert node.module in {"agent.context", "agent.model"}


def test_agent_construction_and_tools_have_single_owners():
    for path in AGENT.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_agent"
            ):
                assert path.name == "harness.py"
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    target = (
                        decorator.func if isinstance(decorator, ast.Call) else decorator
                    )
                    if isinstance(target, ast.Name) and target.id == "tool":
                        assert path.name == "tools.py"
                        assert "runtime" in {arg.arg for arg in node.args.args}


def test_runtime_dependencies_are_not_model_inputs():
    for tool in [*CLAIM_TOOLS, *QUEUE_TOOLS]:
        properties = convert_to_openai_tool(tool)["function"]["parameters"][
            "properties"
        ]
        assert (
            not {
                "runtime",
                "api",
                "run_id",
                "parent_run_id",
                "thread_id",
                "url",
                "path",
            }
            & properties.keys()
        )
        assert isinstance(tool, StructuredTool)
        assert tool.func is not None
        assert tool.func.__module__ == "agent.tools"
        assert tool.func.__closure__ is None
