"""Request-scoped контекст текущей страницы.

HTML страницы слишком велик, чтобы гонять его через аргументы инструментов
(LLM пришлось бы его перепечатывать). main.py кладёт страницу сюда перед
agent.invoke, инструменты читают напрямую."""
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass
class PageContext:
    title: str = ""
    url: str = ""
    html: str = ""


_page_ctx: ContextVar[PageContext | None] = ContextVar("page_ctx", default=None)


def set_page(title: str, url: str, html: str) -> Token:
    return _page_ctx.set(PageContext(title=title, url=url, html=html))


def reset_page(token: Token) -> None:
    _page_ctx.reset(token)


def get_page() -> PageContext | None:
    return _page_ctx.get()
