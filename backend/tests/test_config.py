import pytest
from app.config import load_settings, apply_proxy


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "key1")
    monkeypatch.setenv("EXA_API_KEY", "key2")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    s = load_settings()
    assert s.openrouter_api_key == "key1"
    assert s.exa_api_key == "key2"
    assert s.openrouter_model == "openai/gpt-4o-mini"
    assert s.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert s.page_text_limit == 12000


def test_load_settings_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()


def test_load_settings_reads_proxy(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    monkeypatch.setenv("PROXY_URL", "http://127.0.0.1:8118")
    assert load_settings().proxy_url == "http://127.0.0.1:8118"


def test_apply_proxy_sets_env(monkeypatch):
    for v in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.delenv(v, raising=False)
    apply_proxy("http://127.0.0.1:8118")
    import os
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:8118"
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:8118"


def test_apply_proxy_empty_noop(monkeypatch):
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    apply_proxy("")
    import os
    assert "HTTPS_PROXY" not in os.environ
