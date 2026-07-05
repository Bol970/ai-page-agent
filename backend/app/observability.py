"""Опциональный трейсинг через Langfuse Cloud.

Ключи не заданы — возвращаем None, приложение работает без трейсинга.
Исходящий трафик Langfuse идёт через PROXY_URL (apply_proxy выставляет
HTTPS_PROXY, SDK на httpx его уважает)."""
from app.config import Settings


def build_langfuse_handler(settings: Settings):
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return CallbackHandler()
    except Exception as exc:  # noqa: BLE001
        print(f"Langfuse отключён: {exc}")
        return None
