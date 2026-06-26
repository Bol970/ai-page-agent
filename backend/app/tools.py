import os
from exa_py import Exa
from langchain_core.tools import tool


@tool
def exa_search(query: str) -> str:
    """Ищет актуальную информацию в интернете через сервис EXA.
    Используй этот инструмент, когда на текущей странице нет ответа
    или нужны свежие данные. На вход — поисковый запрос."""
    try:
        exa = Exa(api_key=os.environ["EXA_API_KEY"])
        response = exa.search_and_contents(query, num_results=5, text=True)
    except Exception as exc:  # noqa: BLE001
        # Сетевой/Cloudflare-блок или сбой EXA не должен ронять весь ответ —
        # возвращаем короткое сообщение (без HTML тела ошибки), агент ответит по странице.
        return (
            f"Веб-поиск через EXA сейчас недоступен ({type(exc).__name__}). "
            "Ответь по содержимому страницы, если возможно."
        )
    blocks = []
    for r in response.results:
        text = (r.text or "")[:600]
        blocks.append(f"### {r.title}\nURL: {r.url}\n{text}")
    if not blocks:
        return "По запросу ничего не найдено."
    return "\n\n".join(blocks)
