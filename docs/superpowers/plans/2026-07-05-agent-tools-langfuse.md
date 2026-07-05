# Мультитул-агент + Langfuse — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить агенту шесть инструментов (page_to_markdown, extract_links, fetch_url, calculator, current_datetime, text_to_speech) и трейсинг запросов через Langfuse Cloud.

**Architecture:** HTML текущей страницы передаётся расширением в пейлоаде и кладётся в request-scoped `contextvars.ContextVar` — инструменты страницы читают его напрямую, минуя LLM. TTS сохраняет mp3 на бэкенде и возвращает агенту ссылку на новый эндпоинт `GET /audio/{filename}`; панель рендерит `<audio>` по таким ссылкам. Langfuse подключается опциональным `CallbackHandler` в `agent.invoke` с `langfuse_session_id = chat_id`.

**Tech Stack:** FastAPI, LangGraph/LangChain, markdownify + BeautifulSoup, httpx, edge-tts, langfuse (Python SDK v3), React 18 + Vite/CRXJS.

Спек: `docs/superpowers/specs/2026-07-05-agent-tools-langfuse-design.md`.

## Global Constraints

- Python 3.11+; тесты — pytest, **без сети** (все внешние вызовы мокаются monkeypatch).
- Каждый инструмент ловит все исключения и возвращает агенту короткий русский текст — никогда не роняет запрос (паттерн `exa_search`).
- Тексты пользовательских сообщений и docstring-и инструментов — на русском.
- Лимиты (точные значения): HTML со страницы ≤ 800 000 символов; Markdown страницы ≤ 20 000; `fetch_url` ≤ 8 000 символов текста и ≤ 2 000 000 байт тела; ссылок ≤ 100; текст TTS ≤ 3 000 символов.
- Голос TTS по умолчанию: `ru-RU-SvetlanaNeural` (env `TTS_VOICE`).
- Langfuse строго опционален: без `LANGFUSE_PUBLIC_KEY`+`LANGFUSE_SECRET_KEY` приложение и тесты работают как раньше. Дефолт `LANGFUSE_HOST` — `https://cloud.langfuse.com` (в локальном `.env` пользователя — `https://us.cloud.langfuse.com`).
- Рабочая директория бэкенд-команд: `backend/`, с активированным `.venv` (`source .venv/bin/activate`).
- Команды расширения — из `extension/`. Проверка: `npx tsc -b && npm run build`.

---

### Task 1: Зависимости и конфигурация

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: существующий `Settings` (dataclass) и `load_settings()`.
- Produces: поля `Settings.tts_voice: str`, `Settings.audio_dir: str`, `Settings.langfuse_public_key: str`, `Settings.langfuse_secret_key: str`, `Settings.langfuse_host: str`. Позиционный порядок первых пяти полей не меняется: `Settings("k", "url", "model", "exa", 12000)` продолжает работать.

- [ ] **Step 1: Добавить зависимости**

В конец `backend/requirements.txt` добавить:

```
markdownify>=0.13
beautifulsoup4>=4.12
edge-tts>=6.1
langfuse>=3.0
```

- [ ] **Step 2: Установить зависимости**

Run: `cd backend && source .venv/bin/activate && pip install -r requirements.txt`
Expected: успешная установка, в конце `Successfully installed ... langfuse-3.x ...`

- [ ] **Step 3: Написать падающие тесты на новые настройки**

Добавить в конец `backend/tests/test_config.py`:

```python
def test_load_settings_new_defaults(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    for var in ("TTS_VOICE", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "CHATS_DB_PATH"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings()
    assert s.tts_voice == "ru-RU-SvetlanaNeural"
    assert s.audio_dir == os.path.join(".", "audio")  # рядом с chats.db
    assert s.langfuse_public_key == ""
    assert s.langfuse_secret_key == ""
    assert s.langfuse_host == "https://cloud.langfuse.com"


def test_load_settings_langfuse_and_audio_dir(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    monkeypatch.setenv("TTS_VOICE", "ru-RU-DmitryNeural")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-1")
    monkeypatch.setenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
    monkeypatch.setenv("CHATS_DB_PATH", "/data/db/chats.db")
    s = load_settings()
    assert s.tts_voice == "ru-RU-DmitryNeural"
    assert s.langfuse_public_key == "pk-lf-1"
    assert s.langfuse_secret_key == "sk-lf-1"
    assert s.langfuse_host == "https://us.cloud.langfuse.com"
    assert s.audio_dir == "/data/db/audio"
```

И добавить импорт `os` в начало файла (после `import pytest`):

```python
import os
```

- [ ] **Step 4: Убедиться, что тесты падают**

Run: `python -m pytest tests/test_config.py -v`
Expected: два новых теста FAIL с `AttributeError: 'Settings' object has no attribute 'tts_voice'` (или `TypeError`), старые пять — PASS.

- [ ] **Step 5: Реализовать настройки**

В `backend/app/config.py` заменить dataclass и `load_settings` целиком на:

```python
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
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


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
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        langfuse_host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
```

Функция `apply_proxy` и строка `settings = None` в конце файла остаются без изменений.

- [ ] **Step 6: Прогнать тесты конфига**

Run: `python -m pytest tests/test_config.py -v`
Expected: 7 passed.

- [ ] **Step 7: Обновить .env.example**

В конец `backend/.env.example` добавить:

```
# Голос озвучки edge-tts (инструмент text_to_speech)
TTS_VOICE=ru-RU-SvetlanaNeural
# Langfuse (наблюдаемость, опционально): ключи проекта с cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
# Регион: https://cloud.langfuse.com (EU) или https://us.cloud.langfuse.com (US)
LANGFUSE_HOST=https://cloud.langfuse.com
```

- [ ] **Step 8: Полный прогон и коммит**

Run: `python -m pytest -v`
Expected: все тесты PASS (12 старых + 2 новых).

```bash
git add backend/requirements.txt backend/app/config.py backend/.env.example backend/tests/test_config.py
git commit -m "feat(backend): настройки TTS, каталога аудио и Langfuse"
```

---

### Task 2: Request-scoped контекст страницы

**Files:**
- Create: `backend/app/page_context.py`
- Test: `backend/tests/test_page_context.py`

**Interfaces:**
- Consumes: ничего.
- Produces: `page_context.PageContext` (dataclass: `title: str`, `url: str`, `html: str`); `set_page(title: str, url: str, html: str) -> Token`; `reset_page(token) -> None`; `get_page() -> PageContext | None`. Их используют Task 4 (инструменты) и Task 7 (main.py).

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_page_context.py`:

```python
from app import page_context


def test_get_page_default_none():
    assert page_context.get_page() is None


def test_set_and_reset_page():
    token = page_context.set_page("T", "https://e.test", "<p>x</p>")
    page = page_context.get_page()
    assert page.title == "T"
    assert page.url == "https://e.test"
    assert page.html == "<p>x</p>"
    page_context.reset_page(token)
    assert page_context.get_page() is None
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `python -m pytest tests/test_page_context.py -v`
Expected: FAIL c `ModuleNotFoundError: No module named 'app.page_context'`.

- [ ] **Step 3: Реализовать модуль**

Создать `backend/app/page_context.py`:

```python
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
```

- [ ] **Step 4: Прогнать тесты**

Run: `python -m pytest tests/test_page_context.py -v`
Expected: 2 passed.

- [ ] **Step 5: Коммит**

```bash
git add backend/app/page_context.py backend/tests/test_page_context.py
git commit -m "feat(backend): request-scoped контекст страницы для инструментов"
```

---

### Task 3: Инструменты calculator и current_datetime

**Files:**
- Modify: `backend/app/tools.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: декоратор `@tool` из `langchain_core.tools` (уже импортирован в tools.py).
- Produces: `tools.calculator` (аргумент `expression: str`), `tools.current_datetime` (без аргументов) — LangChain-инструменты, подключаются в Task 7.

- [ ] **Step 1: Написать падающие тесты**

Добавить в конец `backend/tests/test_tools.py`:

```python
# --- calculator ---

def test_calculator_basic():
    assert "= 6" in tools.calculator.invoke({"expression": "2 + 2 * 2"})


def test_calculator_power_and_parens():
    assert "= 1048576" in tools.calculator.invoke({"expression": "2**20"})
    assert "= 9" in tools.calculator.invoke({"expression": "(1 + 2) * 3"})


def test_calculator_division_by_zero():
    assert "деление на ноль" in tools.calculator.invoke({"expression": "1/0"})


def test_calculator_rejects_evil_expressions():
    for evil in ("__import__('os')", "abs(-1)", "x + 1", "2**999999", "'a'*3"):
        out = tools.calculator.invoke({"expression": evil})
        assert "Не удалось вычислить" in out, evil


# --- current_datetime ---

def test_current_datetime_mentions_current_year():
    from datetime import datetime
    out = tools.current_datetime.invoke({})
    assert str(datetime.now().year) in out
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `python -m pytest tests/test_tools.py -v`
Expected: новые тесты FAIL с `AttributeError: module 'app.tools' has no attribute 'calculator'`; `test_exa_search_formats_results` — PASS.

- [ ] **Step 3: Реализовать инструменты**

В начало `backend/app/tools.py` добавить импорты (к существующим):

```python
import ast
import operator
from datetime import datetime
```

В конец файла добавить:

```python
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
    now = datetime.now().astimezone()
    return f"Сейчас {now.isoformat(timespec='seconds')}, {_WEEKDAYS[now.weekday()]}."
```

- [ ] **Step 4: Прогнать тесты**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 6 passed.

- [ ] **Step 5: Коммит**

```bash
git add backend/app/tools.py backend/tests/test_tools.py
git commit -m "feat(backend): инструменты calculator и current_datetime"
```

---

### Task 4: Инструменты page_to_markdown и extract_links

**Files:**
- Modify: `backend/app/tools.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: `page_context.get_page() -> PageContext | None` (Task 2, поля `title`, `url`, `html`).
- Produces: `tools.page_to_markdown` (без аргументов), `tools.extract_links` (без аргументов), приватный помощник `tools._clean_html(html: str) -> BeautifulSoup` (переиспользуется в Task 5). Константы `PAGE_MD_LIMIT = 20000`, `MAX_LINKS = 100`.

- [ ] **Step 1: Написать падающие тесты**

Добавить в конец `backend/tests/test_tools.py`:

```python
# --- инструменты страницы (HTML из page_context) ---

from app import page_context

PAGE_HTML = """
<html><body>
  <script>var secret = 1;</script>
  <style>.a { color: red }</style>
  <h1>Заголовок</h1>
  <p>Абзац с <a href="/rel">относительной ссылкой</a> и
     <a href="https://abs.test/page">абсолютной</a>.</p>
  <a href="https://abs.test/page">дубль</a>
  <a href="mailto:a@b.c">почта</a>
</body></html>
"""


def _with_page(html):
    return page_context.set_page("T", "https://site.test/dir/page", html)


def test_page_to_markdown_converts_and_strips_noise():
    token = _with_page(PAGE_HTML)
    try:
        out = tools.page_to_markdown.invoke({})
    finally:
        page_context.reset_page(token)
    assert "Заголовок" in out
    assert "Абзац" in out
    assert "var secret" not in out
    assert "color: red" not in out


def test_page_to_markdown_without_context():
    assert "недоступно" in tools.page_to_markdown.invoke({})


def test_page_to_markdown_respects_limit():
    token = _with_page("<p>" + "ы" * 50000 + "</p>")
    try:
        out = tools.page_to_markdown.invoke({})
    finally:
        page_context.reset_page(token)
    assert len(out) <= tools.PAGE_MD_LIMIT


def test_extract_links_absolute_dedup_and_filters():
    token = _with_page(PAGE_HTML)
    try:
        out = tools.extract_links.invoke({})
    finally:
        page_context.reset_page(token)
    assert "https://site.test/rel" in out           # относительная стала абсолютной
    assert out.count("https://abs.test/page") == 1  # дедупликация
    assert "mailto:" not in out                     # не-http отфильтрованы


def test_extract_links_without_context():
    assert "недоступно" in tools.extract_links.invoke({})
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `python -m pytest tests/test_tools.py -v`
Expected: новые тесты FAIL с `AttributeError: module 'app.tools' has no attribute 'page_to_markdown'`.

- [ ] **Step 3: Реализовать инструменты**

В `backend/app/tools.py` добавить импорты (к существующим):

```python
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify

from app import page_context
```

В конец файла добавить:

```python
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
    except Exception as exc:  # noqa: BLE001
        return f"Не удалось сконвертировать страницу ({type(exc).__name__})."
    md = "\n".join(line.rstrip() for line in md.splitlines())
    while "\n\n\n" in md:
        md = md.replace("\n\n\n", "\n\n")
    return md.strip()[:PAGE_MD_LIMIT]


@tool
def extract_links() -> str:
    """Возвращает все ссылки текущей страницы: текст и абсолютный URL.
    Используй, когда пользователь просит собрать или перечислить ссылки."""
    page = page_context.get_page()
    if page is None or not page.html:
        return _PAGE_UNAVAILABLE
    soup = _clean_html(page.html)
    seen: set[str] = set()
    lines: list[str] = []
    for a in soup.find_all("a", href=True):
        url = urljoin(page.url, a["href"])
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        text = " ".join(a.get_text(" ", strip=True).split()) or url
        lines.append(f"- [{text[:80]}]({url})")
        if len(lines) >= MAX_LINKS:
            lines.append(f"… и другие (показаны первые {MAX_LINKS}).")
            break
    return "\n".join(lines) if lines else "На странице нет ссылок."
```

- [ ] **Step 4: Прогнать тесты**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 11 passed.

- [ ] **Step 5: Коммит**

```bash
git add backend/app/tools.py backend/tests/test_tools.py
git commit -m "feat(backend): инструменты page_to_markdown и extract_links"
```

---

### Task 5: Инструмент fetch_url

**Files:**
- Modify: `backend/app/tools.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: `tools._clean_html` (Task 4), `markdownify` (Task 4).
- Produces: `tools.fetch_url` (аргумент `url: str`). Константы `FETCH_LIMIT = 8000`, `FETCH_MAX_BYTES = 2_000_000`.

- [ ] **Step 1: Написать падающие тесты**

Добавить в конец `backend/tests/test_tools.py`:

```python
# --- fetch_url (httpx мокается, сети нет) ---

class _FakeHttpxResponse:
    def __init__(self, content=b"", ctype="text/html; charset=utf-8"):
        self.content = content
        self.headers = {"content-type": ctype}
        self.encoding = "utf-8"

    def raise_for_status(self):
        pass


def test_fetch_url_html_to_markdown(monkeypatch):
    resp = _FakeHttpxResponse(b"<h1>Hi</h1><script>var s=1;</script>")
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: resp)
    out = tools.fetch_url.invoke({"url": "https://e.test"})
    assert "Hi" in out
    assert "var s" not in out


def test_fetch_url_plain_text_passthrough(monkeypatch):
    resp = _FakeHttpxResponse(b"plain body", ctype="text/plain")
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: resp)
    assert "plain body" in tools.fetch_url.invoke({"url": "https://e.test"})


def test_fetch_url_rejects_non_http():
    out = tools.fetch_url.invoke({"url": "ftp://e.test"})
    assert "http" in out


def test_fetch_url_network_error_is_text(monkeypatch):
    def boom(*a, **k):
        raise tools.httpx.ConnectError("no route")

    monkeypatch.setattr(tools.httpx, "get", boom)
    out = tools.fetch_url.invoke({"url": "https://e.test"})
    assert "Не удалось скачать" in out
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `python -m pytest tests/test_tools.py -v`
Expected: новые тесты FAIL с `AttributeError: module 'app.tools' has no attribute 'fetch_url'` (и/или `has no attribute 'httpx'`).

- [ ] **Step 3: Реализовать инструмент**

В `backend/app/tools.py` добавить импорт (к существующим):

```python
import httpx
```

В конец файла добавить:

```python
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
```

- [ ] **Step 4: Прогнать тесты**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 15 passed.

- [ ] **Step 5: Коммит**

```bash
git add backend/app/tools.py backend/tests/test_tools.py
git commit -m "feat(backend): инструмент fetch_url"
```

---

### Task 6: Инструмент text_to_speech и эндпоинт GET /audio

**Files:**
- Modify: `backend/app/tools.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_tools.py`
- Test: `backend/tests/test_audio_api.py` (новый)

**Interfaces:**
- Consumes: `config.settings.audio_dir`, `config.settings.tts_voice` (Task 1).
- Produces: `tools.text_to_speech` (аргумент `text: str`) — сохраняет `<uuid4>.mp3` в `config.settings.audio_dir`, возвращает строку со ссылкой `http://localhost:8000/audio/<uuid>.mp3`; эндпоинт `GET /audio/{filename}` (только имена вида `<uuid>.mp3`, иначе 404).

- [ ] **Step 1: Написать падающие тесты инструмента**

Добавить в конец `backend/tests/test_tools.py`:

```python
# --- text_to_speech (edge_tts мокается) ---

def _tts_settings(tmp_path):
    from app import config
    from app.config import Settings

    config.settings = Settings("k", "u", "m", "e", 100, audio_dir=str(tmp_path))
    return config


class _FakeCommunicate:
    def __init__(self, text, voice):
        self.text = text
        self.voice = voice

    async def save(self, path):
        with open(path, "wb") as f:
            f.write(b"mp3-bytes")


def test_text_to_speech_saves_file_and_returns_link(monkeypatch, tmp_path):
    _tts_settings(tmp_path)
    monkeypatch.setattr(tools.edge_tts, "Communicate", _FakeCommunicate)
    out = tools.text_to_speech.invoke({"text": "привет"})
    assert "http://localhost:8000/audio/" in out
    files = list(tmp_path.glob("*.mp3"))
    assert len(files) == 1
    assert files[0].read_bytes() == b"mp3-bytes"
    assert files[0].name in out


def test_text_to_speech_error_is_text(monkeypatch, tmp_path):
    _tts_settings(tmp_path)

    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("edge-tts недоступен")

    monkeypatch.setattr(tools.edge_tts, "Communicate", _Boom)
    out = tools.text_to_speech.invoke({"text": "привет"})
    assert "Озвучка сейчас недоступна" in out
    assert list(tmp_path.glob("*.mp3")) == []
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `python -m pytest tests/test_tools.py -v`
Expected: новые тесты FAIL с `AttributeError: module 'app.tools' has no attribute 'text_to_speech'`.

- [ ] **Step 3: Реализовать инструмент**

В `backend/app/tools.py` добавить импорты (к существующим):

```python
import asyncio
import uuid

import edge_tts

from app import config
```

В конец файла добавить:

```python
TTS_TEXT_LIMIT = 3000


@tool
def text_to_speech(text: str) -> str:
    """Озвучивает текст и возвращает ссылку на mp3-файл. Используй, когда
    пользователь просит озвучить, прочитать вслух или сделать аудио из текста."""
    snippet = text[:TTS_TEXT_LIMIT]
    filename = f"{uuid.uuid4()}.mp3"
    path = os.path.join(config.settings.audio_dir, filename)
    try:
        os.makedirs(config.settings.audio_dir, exist_ok=True)
        communicate = edge_tts.Communicate(snippet, voice=config.settings.tts_voice)
        asyncio.run(communicate.save(path))
    except Exception as exc:  # noqa: BLE001
        return f"Озвучка сейчас недоступна ({type(exc).__name__})."
    return (
        f"Аудио готово: http://localhost:8000/audio/{filename}\n"
        "Вставь эту ссылку в ответ пользователю как есть."
    )
```

Примечание: sync-эндпоинты FastAPI выполняются в тредпуле, поэтому `asyncio.run`
внутри инструмента безопасен (активного event loop в этом потоке нет).

- [ ] **Step 4: Прогнать тесты инструмента**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 17 passed.

- [ ] **Step 5: Написать падающий тест эндпоинта**

Создать `backend/tests/test_audio_api.py`:

```python
import uuid

from fastapi.testclient import TestClient


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    from app import main as main_module

    main_module.config.settings.audio_dir = str(tmp_path)
    return TestClient(main_module.app)


def test_audio_serves_existing_file(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    name = f"{uuid.uuid4()}.mp3"
    (tmp_path / name).write_bytes(b"mp3-bytes")
    resp = client.get(f"/audio/{name}")
    assert resp.status_code == 200
    assert resp.content == b"mp3-bytes"
    assert resp.headers["content-type"] == "audio/mpeg"


def test_audio_missing_file_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.get(f"/audio/{uuid.uuid4()}.mp3").status_code == 404


def test_audio_rejects_non_uuid_names(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    (tmp_path / "evil.mp3").write_bytes(b"x")
    assert client.get("/audio/evil.mp3").status_code == 404
    assert client.get("/audio/..%2Fsecret.mp3").status_code == 404
```

- [ ] **Step 6: Убедиться, что тест падает**

Run: `python -m pytest tests/test_audio_api.py -v`
Expected: FAIL — `404` есть у всех, но `test_audio_serves_existing_file` падает (эндпоинта нет → 404 вместо 200).

- [ ] **Step 7: Реализовать эндпоинт**

В `backend/app/main.py` добавить импорты (к существующим):

```python
import os
import re

from fastapi.responses import FileResponse
```

После функции `health()` добавить:

```python
_AUDIO_NAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.mp3$"
)


@app.get("/audio/{filename}")
def get_audio(filename: str):
    # только имена, которые генерирует text_to_speech — никакого path traversal
    if not _AUDIO_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="not found")
    path = os.path.join(config.settings.audio_dir, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="audio/mpeg")
```

- [ ] **Step 8: Прогнать тесты и закоммитить**

Run: `python -m pytest -v`
Expected: все PASS (в т.ч. 3 новых в test_audio_api.py).

```bash
git add backend/app/tools.py backend/app/main.py backend/tests/test_tools.py backend/tests/test_audio_api.py
git commit -m "feat(backend): инструмент text_to_speech и эндпоинт GET /audio"
```

---

### Task 7: Подключение инструментов к агенту, HTML в схеме, контекст в main

**Files:**
- Modify: `backend/app/agent.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_agent.py`
- Test: `backend/tests/test_chats_api.py`

**Interfaces:**
- Consumes: все семь инструментов из `app.tools`; `page_context.set_page/reset_page` (Task 2); `Page` (pydantic-модель в schemas.py).
- Produces: `agent.TOOLS: list` (7 инструментов), обновлённый `SYSTEM_BASE`; `Page.html: str = ""`; `post_message` оборачивает `agent.invoke` в set/reset контекста страницы.

- [ ] **Step 1: Написать падающие тесты**

Добавить в конец `backend/tests/test_agent.py`:

```python
def test_agent_has_seven_tools():
    names = {t.name for t in agent.TOOLS}
    assert names == {
        "exa_search",
        "page_to_markdown",
        "extract_links",
        "fetch_url",
        "calculator",
        "current_datetime",
        "text_to_speech",
    }


def test_system_base_mentions_tools():
    for name in ("exa_search", "page_to_markdown", "extract_links",
                 "fetch_url", "calculator", "current_datetime", "text_to_speech"):
        assert name in agent.SYSTEM_BASE
```

Добавить в конец `backend/tests/test_chats_api.py`:

```python
def test_messages_set_page_context_for_tools(monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage
    from app import page_context

    main_module, client = _client(monkeypatch, tmp_path)
    seen = []

    class _FakeAgent:
        def invoke(self, payload, *a, **k):
            seen.append(page_context.get_page())
            return {"messages": [AIMessage(content="ответ")]}

    monkeypatch.setattr(main_module, "agent", _FakeAgent())
    cid = client.post("/chats", json={"page_url": "https://e.test/p", "page_title": "T"}).json()["id"]
    page = {"title": "T", "url": "https://e.test/p", "text": "x", "html": "<p>тело</p>"}
    client.post(f"/chats/{cid}/messages", json={"question": "q", "page": page})

    assert seen[0] is not None
    assert seen[0].html == "<p>тело</p>"
    assert seen[0].url == "https://e.test/p"


def test_messages_page_html_optional(monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage

    main_module, client = _client(monkeypatch, tmp_path)

    class _FakeAgent:
        def invoke(self, payload, *a, **k):
            return {"messages": [AIMessage(content="ответ")]}

    monkeypatch.setattr(main_module, "agent", _FakeAgent())
    cid = client.post("/chats", json={"page_url": "https://e.test/p", "page_title": "T"}).json()["id"]
    page = {"title": "T", "url": "https://e.test/p", "text": "x"}  # без html — старый клиент
    r = client.post(f"/chats/{cid}/messages", json={"question": "q", "page": page})
    assert r.status_code == 200
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `python -m pytest tests/test_agent.py tests/test_chats_api.py -v`
Expected: `test_agent_has_seven_tools` и `test_system_base_mentions_tools` FAIL (`no attribute 'TOOLS'`); `test_messages_set_page_context_for_tools` FAIL (`seen[0] is None`); `test_messages_page_html_optional` PASS (html и так опционален — фиксируем поведение); старые тесты PASS.

- [ ] **Step 3: Обновить agent.py**

Заменить в `backend/app/agent.py` блок импортов, `SYSTEM_BASE` и `build_agent`:

```python
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
```

Функция `build_page_system_message` не меняется. В `build_agent` заменить последнюю строку:

```python
    return create_agent(model, tools=TOOLS)
```

- [ ] **Step 4: Добавить html в схему**

В `backend/app/schemas.py` в модель `Page` добавить поле:

```python
class Page(BaseModel):
    title: str = ""
    url: str = ""
    text: str = ""
    html: str = ""
```

- [ ] **Step 5: Обернуть invoke в контекст страницы**

В `backend/app/main.py`: добавить импорт `page_context` (строка с `from app import config, db` становится):

```python
from app import config, db, page_context
```

В `post_message` заменить блок вызова агента:

```python
        try:
            result = agent.invoke({"messages": msgs})
            answer = result["messages"][-1].content
        except Exception as exc:  # noqa: BLE001
            answer = f"Ошибка при обращении к агенту: {exc}"
```

на:

```python
        token = page_context.set_page(req.page.title, req.page.url, req.page.html)
        try:
            result = agent.invoke({"messages": msgs})
            answer = result["messages"][-1].content
        except Exception as exc:  # noqa: BLE001
            answer = f"Ошибка при обращении к агенту: {exc}"
        finally:
            page_context.reset_page(token)
```

- [ ] **Step 6: Прогнать все тесты**

Run: `python -m pytest -v`
Expected: все PASS. Особо проверить: `test_build_agent_is_runnable` (агент собирается с 7 инструментами и fake-моделью).

- [ ] **Step 7: Коммит**

```bash
git add backend/app/agent.py backend/app/schemas.py backend/app/main.py backend/tests/test_agent.py backend/tests/test_chats_api.py
git commit -m "feat(backend): агент с семью инструментами, HTML страницы в контексте запроса"
```

---

### Task 8: Интеграция Langfuse

**Files:**
- Create: `backend/app/observability.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_observability.py` (новый)
- Test: `backend/tests/test_chats_api.py`

**Interfaces:**
- Consumes: `Settings.langfuse_public_key/langfuse_secret_key/langfuse_host` (Task 1).
- Produces: `observability.build_langfuse_handler(settings) -> CallbackHandler | None`; `main.langfuse_handler` (module-level); `agent.invoke(..., config={"callbacks": [...], "metadata": {"langfuse_session_id": chat_id}})`.

- [ ] **Step 1: Написать падающие тесты**

Создать `backend/tests/test_observability.py`:

```python
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
```

Добавить в конец `backend/tests/test_chats_api.py`:

```python
def test_messages_pass_langfuse_session_metadata(monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage

    main_module, client = _client(monkeypatch, tmp_path)
    seen_configs = []

    class _FakeAgent:
        def invoke(self, payload, config=None, **k):
            seen_configs.append(config)
            return {"messages": [AIMessage(content="ответ")]}

    monkeypatch.setattr(main_module, "agent", _FakeAgent())
    cid = client.post("/chats", json={"page_url": "https://e.test/p", "page_title": "T"}).json()["id"]
    page = {"title": "T", "url": "https://e.test/p", "text": "x"}
    client.post(f"/chats/{cid}/messages", json={"question": "q", "page": page})

    assert seen_configs[0]["metadata"]["langfuse_session_id"] == cid
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `python -m pytest tests/test_observability.py tests/test_chats_api.py -v`
Expected: test_observability FAIL с `ModuleNotFoundError: No module named 'app.observability'`; `test_messages_pass_langfuse_session_metadata` FAIL (`config is None`).

- [ ] **Step 3: Реализовать observability.py**

Создать `backend/app/observability.py`:

```python
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
```

- [ ] **Step 4: Подключить в main.py**

В `backend/app/main.py` добавить импорт:

```python
from app.observability import build_langfuse_handler
```

После строки `agent = build_agent(config.settings)` добавить:

```python
langfuse_handler = build_langfuse_handler(config.settings)
```

В `post_message` заменить блок вызова агента (из Task 7) на:

```python
        invoke_config = {"metadata": {"langfuse_session_id": chat_id}}
        if langfuse_handler is not None:
            invoke_config["callbacks"] = [langfuse_handler]

        token = page_context.set_page(req.page.title, req.page.url, req.page.html)
        try:
            result = agent.invoke({"messages": msgs}, config=invoke_config)
            answer = result["messages"][-1].content
        except Exception as exc:  # noqa: BLE001
            answer = f"Ошибка при обращении к агенту: {exc}"
        finally:
            page_context.reset_page(token)
```

- [ ] **Step 5: Прогнать все тесты**

Run: `python -m pytest -v`
Expected: все PASS. Тесты идут без ключей Langfuse — это подтверждает опциональность.

- [ ] **Step 6: Коммит**

```bash
git add backend/app/observability.py backend/app/main.py backend/tests/test_observability.py backend/tests/test_chats_api.py
git commit -m "feat(backend): трейсинг агента через Langfuse (опционально, session=chat)"
```

---

### Task 9: Расширение — HTML страницы в пейлоаде

**Files:**
- Modify: `extension/src/lib/page.ts`
- Modify: `extension/src/lib/chatsApi.ts:22-26`
- Modify: `extension/src/App.tsx:162-166`

**Interfaces:**
- Consumes: `PagePayload` в chatsApi.ts, `getPageContent()` в page.ts.
- Produces: `PageContent.html: string` и `PagePayload.html: string` — бэкенд (Task 7) уже принимает поле `html`.

- [ ] **Step 1: Добавить html в page.ts**

Заменить содержимое `extension/src/lib/page.ts` на:

```typescript
export interface PageContent {
  tabId: number;
  title: string;
  url: string;
  text: string;
  html: string;
}

export async function getPageContent(): Promise<PageContent> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("Не удалось определить активную вкладку");
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    // func сериализуется и выполняется на странице — замыкания недоступны,
    // поэтому лимит HTML (800 000 символов) прописан числом внутри.
    func: () => ({
      title: document.title,
      url: location.href,
      text: document.body?.innerText ?? "",
      html: (document.body?.outerHTML ?? "").slice(0, 800_000),
    }),
  });
  return {
    tabId: tab.id,
    ...(result as { title: string; url: string; text: string; html: string }),
  };
}
```

- [ ] **Step 2: Добавить html в PagePayload**

В `extension/src/lib/chatsApi.ts` заменить интерфейс:

```typescript
export interface PagePayload {
  title: string;
  url: string;
  text: string;
  html: string;
}
```

- [ ] **Step 3: Передавать html при отправке**

В `extension/src/App.tsx`, в функции `send`, заменить вызов `api.sendMessage`:

```typescript
      const { answer } = await api.sendMessage(active.id, question, {
        title: p.title,
        url: p.url,
        text: p.text,
        html: p.html,
      });
```

- [ ] **Step 4: Проверить типы и сборку**

Run: `cd extension && npx tsc -b && npm run build`
Expected: без ошибок, `dist/` пересобран.

- [ ] **Step 5: Коммит**

```bash
git add extension/src/lib/page.ts extension/src/lib/chatsApi.ts extension/src/App.tsx
git commit -m "feat(extension): передавать HTML страницы для инструментов агента"
```

---

### Task 10: Расширение — аудиоплеер для ссылок TTS

**Files:**
- Modify: `extension/src/ChatPanel.tsx:126-148`

**Interfaces:**
- Consumes: `DisplayMsg.content` (текст ответа ассистента), ссылки вида `http://localhost:8000/audio/<uuid>.mp3` из Task 6.
- Produces: `<audio controls>` под сообщением ассистента, если в тексте есть такие ссылки.

- [ ] **Step 1: Добавить извлечение аудиоссылок**

В `extension/src/ChatPanel.tsx` после блока `QUICK_PROMPTS` (после строки 19) добавить:

```typescript
// Ссылки на mp3, которые генерирует инструмент text_to_speech бэкенда.
const AUDIO_URL_RE = /http:\/\/localhost:8000\/audio\/[0-9a-f-]+\.mp3/g;

function extractAudioUrls(content: string): string[] {
  return Array.from(new Set(content.match(AUDIO_URL_RE) ?? []));
}
```

- [ ] **Step 2: Рендерить плеер под сообщением**

В том же файле заменить ветку рендера обычного (не error) сообщения ассистента:

```tsx
                {m.isError ? (
                  <div className="pt-0.5 text-sm text-destructive">{m.content}</div>
                ) : (
                  <div
                    className="assistant-html min-w-0 flex-1 pt-0.5"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                  />
                )}
```

на:

```tsx
                {m.isError ? (
                  <div className="pt-0.5 text-sm text-destructive">{m.content}</div>
                ) : (
                  <div className="min-w-0 flex-1">
                    <div
                      className="assistant-html pt-0.5"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                    />
                    {extractAudioUrls(m.content).map((src) => (
                      <audio key={src} controls src={src} className="mt-2 w-full" />
                    ))}
                  </div>
                )}
```

- [ ] **Step 3: Проверить типы и сборку**

Run: `cd extension && npx tsc -b && npm run build`
Expected: без ошибок.

- [ ] **Step 4: Коммит**

```bash
git add extension/src/ChatPanel.tsx
git commit -m "feat(extension): аудиоплеер для озвучки text_to_speech"
```

---

### Task 11: README и сквозная проверка

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md` (раздел про инструменты агента)

**Interfaces:**
- Consumes: всё реализованное в Tasks 1–10.
- Produces: обновлённая документация; подтверждённый живой прогон.

- [ ] **Step 1: Обновить README**

1. В шапке README обновить ASCII-схему: строку `├─ инструмент exa_search (EXA)` заменить на:

```
  боковая панель (Side Panel)                    ├─ инструменты: exa_search, page_to_markdown,
  content (chrome.scripting)                     │   extract_links, fetch_url, calculator,
                                                 │   current_datetime, text_to_speech (edge-tts)
                                                 ├─ трейсинг: Langfuse (опционально)
                                                 └─ история диалога из SQLite
```

2. В раздел «Использование» добавить примеры после существующего списка:

```markdown
- «Скопируй страницу в markdown» — агент вернёт Markdown-версию страницы в code block.
- «Собери все ссылки со страницы» — список ссылок с абсолютными URL.
- «Открой первую ссылку и перескажи» — агент прочитает страницу по ссылке (fetch_url).
- «Сколько будет 2**20?» — точный расчёт через инструмент calculator.
- «Озвучь ответ» — агент сгенерирует mp3 (edge-tts), в чате появится аудиоплеер.
```

3. Добавить раздел перед «Конфигурация»:

```markdown
## Наблюдаемость (Langfuse)

Трейсы агента (LLM-вызовы, инструменты, токены, стоимость) отправляются в
[Langfuse Cloud](https://cloud.langfuse.com), если в `backend/.env` заданы ключи:
зарегистрируйтесь, создайте проект, скопируйте `LANGFUSE_PUBLIC_KEY` и
`LANGFUSE_SECRET_KEY` (регион US — `LANGFUSE_HOST=https://us.cloud.langfuse.com`).
Трейсы группируются по чатам (Sessions, `session_id` = id чата).
Без ключей приложение работает как обычно, трейсинг молча выключен.
```

4. В таблицу переменных окружения добавить строки:

```markdown
| `TTS_VOICE` | голос edge-tts для text_to_speech (по умолчанию `ru-RU-SvetlanaNeural`) |
| `LANGFUSE_PUBLIC_KEY` | публичный ключ Langfuse (пусто = трейсинг выключен) |
| `LANGFUSE_SECRET_KEY` | секретный ключ Langfuse |
| `LANGFUSE_HOST` | регион Langfuse, по умолчанию `https://cloud.langfuse.com` |
```

- [ ] **Step 2: Обновить CLAUDE.md**

В разделе «Backend» CLAUDE.md заменить строку про `tools.py`:

```markdown
- `tools.py` — семь инструментов агента: `exa_search`, `page_to_markdown`, `extract_links` (HTML — из request-контекста `page_context.py`), `fetch_url`, `calculator` (ast, без eval), `current_datetime`, `text_to_speech` (edge-tts → mp3 в `audio_dir`, отдаётся через `GET /audio/{filename}`). Ошибки инструментов не роняют ответ, а возвращаются агенту текстом.
```

И добавить в тот же раздел:

```markdown
- `observability.py` — опциональный Langfuse `CallbackHandler` (без ключей — None); `main.py` передаёт его в `agent.invoke` с `langfuse_session_id = chat_id`.
```

- [ ] **Step 3: Полный прогон тестов и сборки**

Run: `cd backend && source .venv/bin/activate && python -m pytest -v`
Expected: все PASS.

Run: `cd extension && npx tsc -b && npm run build`
Expected: без ошибок.

- [ ] **Step 4: Живой smoke-тест (нужны реальные ключи в .env)**

1. `cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000`
2. `curl http://localhost:8000/health` → `{"status":"ok"}`
3. Перезагрузить распакованное расширение из `extension/dist` в Chrome, открыть любую статью.
4. Проверить в панели: «скопируй страницу в markdown» (code block с Markdown), «собери все ссылки» (список), «сколько будет 2**20» (1048576), «который час» (текущее время), «озвучь короткое резюме страницы» (появился аудиоплеер, звук играет), «открой первую ссылку и перескажи» (пересказ другой страницы).
5. Открыть Langfuse UI (`https://us.cloud.langfuse.com`) → Traces: видны трейсы с вызовами инструментов; Sessions: трейсы сгруппированы по чату.

- [ ] **Step 5: Коммит**

```bash
git add README.md CLAUDE.md
git commit -m "docs: инструменты агента и наблюдаемость Langfuse"
```
