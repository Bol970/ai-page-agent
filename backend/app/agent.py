from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from app.tools import (
    calculator,
    current_datetime,
    exa_search,
    extract_links,
    fetch_url,
    page_to_markdown,
    text_to_speech,
)
from app.config import Settings

SYSTEM_BASE = (
    "Ты — ассистент, который помогает пользователю разобраться с открытой "
    "веб-страницей. Отвечай на русском. Сначала используй содержимое страницы ниже.\n"
    "Твои инструменты:\n"
    "- exa_search — поиск в интернете, когда на странице нет ответа или нужна "
    "свежая информация; ссылайся на найденные источники;\n"
    "- page_to_markdown — конвертация текущей страницы в Markdown; результат "
    "выведи ДОСЛОВНО внутри блока ```markdown ... ```, без пересказа;\n"
    "- extract_links — список всех ссылок текущей страницы;\n"
    "- fetch_url — прочитать другую страницу по URL (например, ссылку с текущей);\n"
    "- calculator — точные вычисления; не считай в уме;\n"
    "- current_datetime — текущие дата и время; не угадывай их;\n"
    "- text_to_speech — озвучка текста; полученную ссылку на mp3 вставь в ответ как есть."
)

TOOLS = [
    exa_search,
    page_to_markdown,
    extract_links,
    fetch_url,
    calculator,
    current_datetime,
    text_to_speech,
]


def build_page_system_message(title: str, url: str, text: str, limit: int) -> str:
    snippet = (text or "")[:limit]
    return (
        f"{SYSTEM_BASE}\n\n"
        f"=== СТРАНИЦА ===\n"
        f"Заголовок: {title}\n"
        f"URL: {url}\n\n"
        f"Содержимое:\n{snippet}"
    )


def build_agent(settings: Settings) -> CompiledStateGraph:
    model = ChatOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        temperature=0,
    )
    return create_agent(model, tools=TOOLS)
