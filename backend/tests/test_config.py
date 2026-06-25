import os
from app.config import load_settings


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
    import pytest
    with pytest.raises(RuntimeError):
        load_settings()
