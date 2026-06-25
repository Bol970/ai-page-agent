from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from app.tools import exa_search
from app.config import Settings

SYSTEM_BASE = (
    "Ты — ассистент, который помогает пользователю разобраться с открытой "
    "веб-страницей. Отвечай на русском. Сначала используй содержимое страницы "
    "ниже. Если на странице нет ответа или нужна свежая информация из "
    "интернета — вызови инструмент exa_search и сошлись на найденные источники."
)


def build_page_system_message(title: str, url: str, text: str, limit: int) -> str:
    snippet = (text or "")[:limit]
    return (
        f"{SYSTEM_BASE}\n\n"
        f"=== СТРАНИЦА ===\n"
        f"Заголовок: {title}\n"
        f"URL: {url}\n\n"
        f"Содержимое:\n{snippet}"
    )


def build_agent(settings: Settings):
    model = ChatOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        temperature=0,
    )
    checkpointer = MemorySaver()
    return create_agent(model, tools=[exa_search], checkpointer=checkpointer)
