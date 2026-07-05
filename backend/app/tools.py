import ast
import operator
from datetime import datetime
from urllib.parse import urljoin

import os
import httpx
from bs4 import BeautifulSoup
from exa_py import Exa
from langchain_core.tools import tool
from markdownify import markdownify

from app import page_context


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


def _pow_guarded(a, b):
    if abs(b) > 1000:
        raise ValueError("слишком большая степень")
    return operator.pow(a, b)


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: _pow_guarded,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("недопустимый элемент выражения")


@tool
def calculator(expression: str) -> str:
    """Вычисляет арифметическое выражение: числа, скобки и операции
    + - * / // % **. Используй для любых точных расчётов вместо счёта в уме."""
    try:
        result = _eval_node(ast.parse(expression, mode="eval"))
    except ZeroDivisionError:
        return "Ошибка: деление на ноль."
    except Exception:  # noqa: BLE001
        return (
            "Не удалось вычислить. Допустимы только числа, скобки и операции "
            "+ - * / // % ** (степень не больше 1000)."
        )
    return f"{expression} = {result}"


_WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


@tool
def current_datetime() -> str:
    """Возвращает текущие дату, время и день недели. Используй, когда вопрос
    касается «сегодня», «сейчас», текущего года — не угадывай их."""
    try:
        now = datetime.now().astimezone()
        return f"Сейчас {now.isoformat(timespec='seconds')}, {_WEEKDAYS[now.weekday()]}."
    except Exception as exc:  # noqa: BLE001
        return f"Не удалось определить текущее время ({type(exc).__name__})."


PAGE_MD_LIMIT = 20000
MAX_LINKS = 100
_PAGE_UNAVAILABLE = "Содержимое страницы недоступно (HTML не передан расширением)."


def _clean_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return soup


@tool
def page_to_markdown() -> str:
    """Конвертирует текущую открытую страницу в Markdown. Используй, когда
    пользователь просит скопировать, сохранить или показать страницу в Markdown."""
    page = page_context.get_page()
    if page is None or not page.html:
        return _PAGE_UNAVAILABLE
    try:
        md = markdownify(str(_clean_html(page.html)), heading_style="ATX")
        md = "\n".join(line.rstrip() for line in md.splitlines())
        while "\n\n\n" in md:
            md = md.replace("\n\n\n", "\n\n")
        return md.strip()[:PAGE_MD_LIMIT]
    except Exception as exc:  # noqa: BLE001
        return f"Не удалось сконвертировать страницу ({type(exc).__name__})."


@tool
def extract_links() -> str:
    """Возвращает все ссылки текущей страницы: текст и абсолютный URL.
    Используй, когда пользователь просит собрать или перечислить ссылки."""
    page = page_context.get_page()
    if page is None or not page.html:
        return _PAGE_UNAVAILABLE
    try:
        soup = _clean_html(page.html)
        seen: set[str] = set()
        lines: list[str] = []
        for a in soup.find_all("a", href=True):
            try:
                url = urljoin(page.url, a["href"])
            except ValueError:
                continue  # битый href (например, "http://[bad") — пропускаем
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            text = " ".join(a.get_text(" ", strip=True).split()) or url
            lines.append(f"- [{text[:80]}]({url})")
            if len(lines) >= MAX_LINKS:
                lines.append(f"… и другие (показаны первые {MAX_LINKS}).")
                break
        return "\n".join(lines) if lines else "На странице нет ссылок."
    except Exception as exc:  # noqa: BLE001
        return f"Не удалось разобрать ссылки страницы ({type(exc).__name__})."


FETCH_LIMIT = 8000
FETCH_MAX_BYTES = 2_000_000


@tool
def fetch_url(url: str) -> str:
    """Скачивает страницу по URL и возвращает её содержимое как Markdown.
    Используй, чтобы прочитать ссылку с текущей страницы или из результатов поиска."""
    if not url.startswith(("http://", "https://")):
        return "Поддерживаются только http/https URL."
    try:
        resp = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (AI Page Agent)"},
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return f"Не удалось скачать {url} ({type(exc).__name__})."
    body = resp.content[:FETCH_MAX_BYTES]
    text = body.decode(resp.encoding or "utf-8", errors="replace")
    if "html" in resp.headers.get("content-type", ""):
        try:
            text = markdownify(str(_clean_html(text)), heading_style="ATX")
        except Exception:  # noqa: BLE001
            pass  # отдадим сырой текст
    return text.strip()[:FETCH_LIMIT]
