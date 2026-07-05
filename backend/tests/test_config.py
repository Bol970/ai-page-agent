import pytest
import os
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


def test_load_settings_new_defaults(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    for var in ("TTS_VOICE", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "CHATS_DB_PATH"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings()
    assert s.tts_voice == "ru-RU-SvetlanaNeural"
    assert s.audio_dir == os.path.join(".", "audio")  # рядом с chats.db
    assert s.langfuse_public_key == ""
    assert s.langfuse_secret_key == ""
    assert s.langfuse_host == "https://cloud.langfuse.com"


def test_load_settings_langfuse_and_audio_dir(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    monkeypatch.setenv("TTS_VOICE", "ru-RU-DmitryNeural")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-1")
    monkeypatch.setenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
    monkeypatch.setenv("CHATS_DB_PATH", "/data/db/chats.db")
    s = load_settings()
    assert s.tts_voice == "ru-RU-DmitryNeural"
    assert s.langfuse_public_key == "pk-lf-1"
    assert s.langfuse_secret_key == "sk-lf-1"
    assert s.langfuse_host == "https://us.cloud.langfuse.com"
    assert s.audio_dir == "/data/db/audio"
