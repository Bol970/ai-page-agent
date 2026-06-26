import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    exa_api_key: str
    page_text_limit: int
    chats_db_path: str = "chats.db"
    proxy_url: str = ""


def load_settings() -> Settings:
    api_key = os.getenv("OPENROUTER_API_KEY")
    exa_key = os.getenv("EXA_API_KEY")
    missing = [n for n, v in [("OPENROUTER_API_KEY", api_key), ("EXA_API_KEY", exa_key)] if not v]
    if missing:
        raise RuntimeError(f"Не заданы переменные окружения: {', '.join(missing)}. Скопируйте .env.example в .env и заполните.")
    return Settings(
        openrouter_api_key=api_key,
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        exa_api_key=exa_key,
        page_text_limit=int(os.getenv("PAGE_TEXT_LIMIT", "12000")),
        chats_db_path=os.getenv("CHATS_DB_PATH", "chats.db"),
        proxy_url=os.getenv("PROXY_URL", ""),
    )


def apply_proxy(proxy_url: str) -> None:
    """Если задан прокси — направляем исходящие HTTP(S) через него.
    exa-py (requests) и openai/langchain (httpx) читают эти env-переменные.
    Локальные адреса оставляем напрямую."""
    if not proxy_url:
        return
    for var in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ[var] = proxy_url
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
    os.environ.setdefault("no_proxy", "localhost,127.0.0.1")


settings = None  # ленивая инициализация: заполняется в main.py при старте
