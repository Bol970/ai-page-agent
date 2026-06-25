import os
from exa_py import Exa
from langchain_core.tools import tool


@tool
def exa_search(query: str) -> str:
    """Ищет актуальную информацию в интернете через сервис EXA.
    Используй этот инструмент, когда на текущей странице нет ответа
    или нужны свежие данные. На вход — поисковый запрос."""
    exa = Exa(api_key=os.environ["EXA_API_KEY"])
    response = exa.search_and_contents(query, num_results=5, text=True)
    blocks = []
    for r in response.results:
        text = (r.text or "")[:600]
        blocks.append(f"### {r.title}\nURL: {r.url}\n{text}")
    if not blocks:
        return "По запросу ничего не найдено."
    return "\n\n".join(blocks)
