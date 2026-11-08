from agent import tracing


def test_nothing_is_traced_without_langfuse_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert tracing.trace_config("CLM-1001") == {}


def test_traces_go_into_one_session(monkeypatch):
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    config = tracing.trace_config("CLM-1001")
    assert config.get("metadata") == {"langfuse_session_id": "CLM-1001"}
    assert config.get("callbacks")
