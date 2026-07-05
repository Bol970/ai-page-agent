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
    tts_voice: str = "ru-RU-SvetlanaNeural"
    audio_dir: str = "audio"
    tts_provider: str = "edge"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "XB0fDUnXU5powFXDhCwa"
    elevenlabs_model: str = "eleven_multilingual_v2"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_environment: str = "default"


def load_settings() -> Settings:
    api_key = os.getenv("OPENROUTER_API_KEY")
    exa_key = os.getenv("EXA_API_KEY")
    missing = [n for n, v in [("OPENROUTER_API_KEY", api_key), ("EXA_API_KEY", exa_key)] if not v]
    if missing:
        raise RuntimeError(f"Не заданы переменные окружения: {', '.join(missing)}. Скопируйте .env.example в .env и заполните.")
    chats_db_path = os.getenv("CHATS_DB_PATH", "chats.db")
    return Settings(
        openrouter_api_key=api_key,
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        exa_api_key=exa_key,
        page_text_limit=int(os.getenv("PAGE_TEXT_LIMIT", "12000")),
        chats_db_path=chats_db_path,
        proxy_url=os.getenv("PROXY_URL", ""),
        tts_voice=os.getenv("TTS_VOICE", "ru-RU-SvetlanaNeural"),
        # аудио живёт рядом с БД чатов
        audio_dir=os.path.join(os.path.dirname(chats_db_path) or ".", "audio"),
        tts_provider=os.getenv("TTS_PROVIDER", "edge"),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "XB0fDUnXU5powFXDhCwa"),
        elevenlabs_model=os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        langfuse_host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        langfuse_environment=os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "default"),
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
