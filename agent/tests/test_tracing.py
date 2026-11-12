from agent import tracing


def test_nothing_is_traced_without_langfuse_keys():
    with tracing.trace("CLM-1001-1") as config:
        assert config == {}


def test_a_claim_is_traced_with_its_own_callbacks(monkeypatch):
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "false")

    with tracing.trace("CLM-1001-1") as config:
        assert config.get("callbacks")
