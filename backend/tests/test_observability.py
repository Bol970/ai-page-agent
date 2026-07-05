from app.config import Settings
from app.observability import build_langfuse_handler


def _settings(**kw):
    return Settings("k", "u", "m", "e", 100, **kw)


def test_no_keys_returns_none():
    assert build_langfuse_handler(_settings()) is None


def test_partial_keys_return_none():
    assert build_langfuse_handler(_settings(langfuse_public_key="pk-lf-x")) is None
    assert build_langfuse_handler(_settings(langfuse_secret_key="sk-lf-x")) is None


def test_both_keys_build_handler():
    handler = build_langfuse_handler(
        _settings(langfuse_public_key="pk-lf-x", langfuse_secret_key="sk-lf-x")
    )
    assert handler is not None
