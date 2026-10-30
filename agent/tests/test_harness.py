from agent import harness


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert harness.model().model_name == "deepseek/deepseek-v4.1-flash"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert harness.model().model_name == "openrouter/free"


def test_model_has_a_request_timeout(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert harness.model().request_timeout == harness.MODEL_TIMEOUT_SECONDS
