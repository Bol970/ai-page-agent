# AI-агент Chrome (анализ страницы + EXA поиск) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Расширение Chrome с чат-интерфейсом, которое отвечает на вопросы о текущей странице через LangGraph-агента на Python, умеющего искать в интернете через EXA.

**Architecture:** Расширение (React + shadcn/ui) извлекает текст активной вкладки и шлёт его с вопросом на локальный FastAPI-сервер. Сервер запускает LangGraph ReAct-агента (LLM через OpenRouter) с инструментом `exa_search`; текст страницы кладётся в системный промпт, история диалога хранится в checkpointer по `thread_id`.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, LangGraph, langchain-openai, exa-py, pytest. Фронт: React 18 + TypeScript + Vite + Tailwind v4 + shadcn/ui + @crxjs/vite-plugin.

## Global Constraints

- LLM подключается ТОЛЬКО как OpenAI-совместимый клиент к OpenRouter: `base_url=https://openrouter.ai/api/v1`, ключ из `OPENROUTER_API_KEY`, модель из `OPENROUTER_MODEL`.
- Все секреты — в `backend/.env`, в репозиторий не коммитятся; коммитится только `backend/.env.example`.
- Текст страницы обрезается до 12000 символов перед отправкой в модель.
- `thread_id` = идентификатор вкладки (`tab-<tabId>`): одна вкладка = один диалог.
- Backend слушает `http://localhost:8000`. CORS разрешён для всех источников (учебное демо).
- Единственный инструмент агента — `exa_search`. Содержимое страницы передаётся как контекст (системный промпт), а не как инструмент.

---

## Структура файлов

```
backend/
  app/
    __init__.py
    config.py        ← загрузка .env, валидация ключей
    tools.py         ← инструмент exa_search
    agent.py         ← сборка LangGraph-агента
    schemas.py       ← Pydantic-модели запроса/ответа
    main.py          ← FastAPI app, POST /chat, CORS
  tests/
    __init__.py
    test_tools.py    ← тест exa_search (мок сети)
    test_agent.py    ← тест сборки агента
    test_api.py      ← тест эндпоинта /chat (мок агента)
  requirements.txt
  .env.example
  .gitignore

extension/
  manifest.config.ts
  vite.config.ts
  tsconfig.json
  tsconfig.app.json
  tsconfig.node.json
  components.json          ← создаётся `shadcn init`
  index.html
  package.json
  src/
    index.css             ← создаётся `shadcn init` (Tailwind + токены)
    main.tsx
    Popup.tsx             ← чат-интерфейс
    lib/
      utils.ts            ← создаётся `shadcn init`
      page.ts             ← извлечение текста страницы
      api.ts              ← запрос к backend
    components/ui/        ← компоненты shadcn (button, textarea, scroll-area, card)
```

---

## Task 1: Каркас бэкенда и конфигурация

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py` (пустой)
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py` (пустой)
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `app.config.settings` — объект с полями `openrouter_api_key: str`, `openrouter_base_url: str`, `openrouter_model: str`, `exa_api_key: str`, `page_text_limit: int`. Функция `app.config.load_settings() -> Settings`.

- [ ] **Step 1: requirements.txt**

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
langgraph>=0.2.50
langchain-openai>=0.2.0
langchain-core>=0.3.0
exa-py>=1.0.0
python-dotenv>=1.0.0
pydantic>=2.0
pytest>=8.0
httpx>=0.27
```

- [ ] **Step 2: .gitignore и .env.example**

`backend/.gitignore`:
```
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

`backend/.env.example`:
```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-4o-mini
EXA_API_KEY=...
PAGE_TEXT_LIMIT=12000
```

- [ ] **Step 3: Написать падающий тест** — `backend/tests/test_config.py`

```python
import os
from app.config import load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "key1")
    monkeypatch.setenv("EXA_API_KEY", "key2")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    s = load_settings()
    assert s.openrouter_api_key == "key1"
    assert s.exa_api_key == "key2"
    assert s.openrouter_model == "openai/gpt-4o-mini"
    assert s.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert s.page_text_limit == 12000


def test_load_settings_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    import pytest
    with pytest.raises(RuntimeError):
        load_settings()
```

- [ ] **Step 4: Запустить — убедиться, что падает**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.config'`)

- [ ] **Step 5: Реализация** — `backend/app/config.py`

```python
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
    )


settings = None  # ленивая инициализация: заполняется в main.py при старте
```

- [ ] **Step 6: Запустить — убедиться, что проходит**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat(backend): каркас и загрузка конфигурации"
```

---

## Task 2: Инструмент EXA

**Files:**
- Create: `backend/app/tools.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: `app.config` (читает `EXA_API_KEY` из окружения внутри функции).
- Produces: `app.tools.exa_search` — LangChain-инструмент (`@tool`), сигнатура `exa_search(query: str) -> str`. Вызов в тестах: `exa_search.invoke({"query": "..."})`. Класс `Exa` импортируется как `app.tools.Exa` (для мока).

- [ ] **Step 1: Написать падающий тест** — `backend/tests/test_tools.py`

```python
from app import tools


class _FakeResult:
    def __init__(self, title, url, text):
        self.title = title
        self.url = url
        self.text = text


class _FakeResponse:
    def __init__(self, results):
        self.results = results


class _FakeExa:
    def __init__(self, api_key=None):
        self.api_key = api_key

    def search_and_contents(self, query, **kwargs):
        return _FakeResponse([
            _FakeResult("Заголовок 1", "https://a.test", "Текст один " * 50),
            _FakeResult("Заголовок 2", "https://b.test", "Текст два"),
        ])


def test_exa_search_formats_results(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(tools, "Exa", _FakeExa)
    out = tools.exa_search.invoke({"query": "погода"})
    assert "Заголовок 1" in out
    assert "https://a.test" in out
    assert "Заголовок 2" in out
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd backend && python -m pytest tests/test_tools.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.tools'`)

- [ ] **Step 3: Реализация** — `backend/app/tools.py`

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd backend && python -m pytest tests/test_tools.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools.py backend/tests/test_tools.py
git commit -m "feat(backend): инструмент exa_search"
```

---

## Task 3: Сборка LangGraph-агента

**Files:**
- Create: `backend/app/agent.py`
- Test: `backend/tests/test_agent.py`

**Interfaces:**
- Consumes: `app.tools.exa_search`, `app.config.Settings`.
- Produces:
  - `app.agent.build_agent(settings: Settings)` → скомпилированный граф (`CompiledStateGraph`) с подключённым `MemorySaver` и инструментом `exa_search`.
  - `app.agent.SYSTEM_BASE: str` — базовый системный промпт.
  - `app.agent.build_page_system_message(title, url, text, limit) -> str` — собирает системный промпт с содержимым страницы (обрезка до `limit`).

- [ ] **Step 1: Написать падающий тест** — `backend/tests/test_agent.py`

```python
from app import agent


def test_build_page_system_message_truncates():
    msg = agent.build_page_system_message("T", "https://x.test", "A" * 100, limit=10)
    assert "T" in msg
    assert "https://x.test" in msg
    assert "A" * 10 in msg
    assert "A" * 11 not in msg


def test_build_agent_has_checkpointer(monkeypatch):
    from app.config import Settings

    class _FakeModel:
        def bind_tools(self, *a, **k):
            return self

    monkeypatch.setattr(agent, "ChatOpenAI", lambda **k: _FakeModel())
    s = Settings("k", "https://openrouter.ai/api/v1", "m", "e", 12000)
    g = agent.build_agent(s)
    assert g.checkpointer is not None
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd backend && python -m pytest tests/test_agent.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.agent'`)

- [ ] **Step 3: Реализация** — `backend/app/agent.py`

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
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
    return create_react_agent(model, tools=[exa_search], checkpointer=checkpointer)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd backend && python -m pytest tests/test_agent.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent.py backend/tests/test_agent.py
git commit -m "feat(backend): сборка LangGraph-агента"
```

---

## Task 4: FastAPI-эндпоинт /chat

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `app.agent.build_agent`, `app.agent.build_page_system_message`, `app.config.load_settings`.
- Produces: FastAPI-приложение `app.main.app` с `POST /chat`.
  - Запрос: `{ "thread_id": str, "question": str, "page": { "title": str, "url": str, "text": str } }`
  - Ответ: `{ "answer": str }`
  - Эндпоинт `GET /health` → `{ "status": "ok" }`.

- [ ] **Step 1: Pydantic-схемы** — `backend/app/schemas.py`

```python
from pydantic import BaseModel


class Page(BaseModel):
    title: str = ""
    url: str = ""
    text: str = ""


class ChatRequest(BaseModel):
    thread_id: str
    question: str
    page: Page


class ChatResponse(BaseModel):
    answer: str
```

- [ ] **Step 2: Написать падающий тест** — `backend/tests/test_api.py`

```python
from fastapi.testclient import TestClient


def test_chat_returns_answer(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")

    from langchain_core.messages import AIMessage
    from app import main as main_module

    class _FakeAgent:
        def invoke(self, payload, config):
            # система+вопрос на первом ходу
            assert config["configurable"]["thread_id"] == "tab-1"
            return {"messages": [AIMessage(content="Это страница про котов.")]}

    monkeypatch.setattr(main_module, "agent", _FakeAgent())

    client = TestClient(main_module.app)
    resp = client.post("/chat", json={
        "thread_id": "tab-1",
        "question": "О чём страница?",
        "page": {"title": "Коты", "url": "https://cats.test", "text": "Про котов"},
    })
    assert resp.status_code == 200
    assert resp.json()["answer"] == "Это страница про котов."


def test_health(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    from app import main as main_module
    client = TestClient(main_module.app)
    assert client.get("/health").json() == {"status": "ok"}
```

- [ ] **Step 3: Запустить — убедиться, что падает**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.main'`)

- [ ] **Step 4: Реализация** — `backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import SystemMessage, HumanMessage

from app import config
from app.config import load_settings
from app.agent import build_agent, build_page_system_message
from app.schemas import ChatRequest, ChatResponse

config.settings = load_settings()
agent = build_agent(config.settings)

app = FastAPI(title="AI Page Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_seen_threads: set[str] = set()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    cfg = {"configurable": {"thread_id": req.thread_id}}
    messages = []
    if req.thread_id not in _seen_threads:
        sys = build_page_system_message(
            req.page.title, req.page.url, req.page.text,
            config.settings.page_text_limit,
        )
        messages.append(SystemMessage(content=sys))
        _seen_threads.add(req.thread_id)
    messages.append(HumanMessage(content=req.question))

    try:
        result = agent.invoke({"messages": messages}, cfg)
        answer = result["messages"][-1].content
    except Exception as exc:  # noqa: BLE001
        answer = f"Ошибка при обращении к агенту: {exc}"
    return ChatResponse(answer=answer)
```

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Прогнать все тесты бэкенда**

Run: `cd backend && python -m pytest -v`
Expected: PASS (все тесты зелёные)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/main.py backend/tests/test_api.py
git commit -m "feat(backend): эндпоинт /chat и /health"
```

---

## Task 5: Каркас расширения (Vite + React + Tailwind + shadcn + crxjs)

**Files:**
- Create: `extension/package.json`
- Create: `extension/vite.config.ts`
- Create: `extension/manifest.config.ts`
- Create: `extension/tsconfig.json`, `extension/tsconfig.app.json`, `extension/tsconfig.node.json`
- Create: `extension/index.html`
- Create: `extension/src/main.tsx`, `extension/src/Popup.tsx` (заглушка)
- Generated by shadcn init: `extension/components.json`, `extension/src/index.css`, `extension/src/lib/utils.ts`

**Interfaces:**
- Produces: рабочая сборка `npm run build` → `extension/dist/`, которую можно загрузить в Chrome. Путь-алиас `@/` указывает на `extension/src`.

- [ ] **Step 1: package.json**

```json
{
  "name": "ai-page-agent-extension",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.0",
    "lucide-react": "^0.450.0"
  },
  "devDependencies": {
    "@crxjs/vite-plugin": "^2.0.0-beta.28",
    "@types/chrome": "^0.0.270",
    "@types/node": "^22.0.0",
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.1",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }
}
```

- [ ] **Step 2: tsconfig-файлы** (нужны алиас `@/` и типы chrome/node)

`extension/tsconfig.json`:
```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ],
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

`extension/tsconfig.app.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] },
    "types": ["chrome", "node"]
  },
  "include": ["src"]
}
```

`extension/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "types": ["node"]
  },
  "include": ["vite.config.ts", "manifest.config.ts"]
}
```

- [ ] **Step 3: manifest.config.ts**

```ts
import { defineManifest } from "@crxjs/vite-plugin";

export default defineManifest({
  manifest_version: 3,
  name: "AI Page Agent",
  version: "0.1.0",
  description: "AI-агент, отвечающий на вопросы о текущей странице",
  action: { default_popup: "index.html", default_title: "AI Page Agent" },
  permissions: ["activeTab", "scripting", "tabs"],
  host_permissions: ["http://localhost:8000/*"],
});
```

- [ ] **Step 4: vite.config.ts**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { crx } from "@crxjs/vite-plugin";
import path from "node:path";
import manifest from "./manifest.config";

export default defineConfig({
  plugins: [react(), tailwindcss(), crx({ manifest })],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
```

- [ ] **Step 5: index.html + точки входа**

`extension/index.html`:
```html
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Page Agent</title>
  </head>
  <body>
    <div id="root" style="width: 380px"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`extension/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { Popup } from "@/Popup";
import "@/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Popup />
  </React.StrictMode>
);
```

`extension/src/Popup.tsx` (временная заглушка):
```tsx
export function Popup() {
  return <div className="p-4 text-sm">AI Page Agent</div>;
}
```

- [ ] **Step 6: Установить зависимости**

Run: `cd extension && npm install`
Expected: установка без ошибок, появляется `node_modules/`.

- [ ] **Step 7: Инициализировать shadcn/ui**

Run: `cd extension && npx shadcn@latest init -d -b neutral`
Expected: создаются `components.json`, `src/index.css` (с `@import "tailwindcss"` и токенами темы), `src/lib/utils.ts`. На вопросы согласиться с дефолтами (`-d`).

> Если CLI спросит про путь алиаса — указать `@/*` → `./src/*` (уже настроено в tsconfig).

- [ ] **Step 8: Добавить нужные компоненты shadcn**

Run: `cd extension && npx shadcn@latest add button textarea scroll-area card`
Expected: появляются `src/components/ui/button.tsx`, `textarea.tsx`, `scroll-area.tsx`, `card.tsx`.

- [ ] **Step 9: Включить тёмную тему** — добавить класс `dark` в `extension/index.html`

Заменить `<html lang="ru">` на:
```html
<html lang="ru" class="dark">
```

- [ ] **Step 10: Собрать**

Run: `cd extension && npm run build`
Expected: сборка успешна, появляется `extension/dist/` с `manifest.json` и `index.html`.

- [ ] **Step 11: .gitignore для расширения** — `extension/.gitignore`

```
node_modules/
dist/
```

- [ ] **Step 12: Commit**

```bash
git add extension/ -- ':!extension/node_modules' ':!extension/dist'
git commit -m "feat(extension): каркас Vite+React+Tailwind+shadcn+crxjs"
```

---

## Task 6: Извлечение содержимого страницы и клиент API

**Files:**
- Create: `extension/src/lib/page.ts`
- Create: `extension/src/lib/api.ts`

**Interfaces:**
- Produces:
  - `getPageContent(): Promise<{ tabId: number; title: string; url: string; text: string }>` — извлекает текст активной вкладки через `chrome.scripting.executeScript`.
  - `askAgent(threadId: string, question: string, page: { title: string; url: string; text: string }): Promise<string>` — POST на `http://localhost:8000/chat`, возвращает `answer`.

- [ ] **Step 1: page.ts**

```ts
export interface PageContent {
  tabId: number;
  title: string;
  url: string;
  text: string;
}

export async function getPageContent(): Promise<PageContent> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("Не удалось определить активную вкладку");
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => ({
      title: document.title,
      url: location.href,
      text: document.body?.innerText ?? "",
    }),
  });
  return { tabId: tab.id, ...(result as { title: string; url: string; text: string }) };
}
```

- [ ] **Step 2: api.ts**

```ts
const BACKEND_URL = "http://localhost:8000/chat";

export interface PagePayload {
  title: string;
  url: string;
  text: string;
}

export async function askAgent(
  threadId: string,
  question: string,
  page: PagePayload
): Promise<string> {
  let resp: Response;
  try {
    resp = await fetch(BACKEND_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, question, page }),
    });
  } catch {
    throw new Error("Не удалось подключиться к серверу. Запущен ли backend на :8000?");
  }
  if (!resp.ok) throw new Error(`Сервер вернул ошибку ${resp.status}`);
  const data = (await resp.json()) as { answer: string };
  return data.answer;
}
```

- [ ] **Step 3: Проверка типов**

Run: `cd extension && npx tsc -b`
Expected: без ошибок типов.

- [ ] **Step 4: Commit**

```bash
git add extension/src/lib/page.ts extension/src/lib/api.ts
git commit -m "feat(extension): извлечение страницы и клиент API"
```

---

## Task 7: Чат-интерфейс на shadcn/ui

**Files:**
- Modify: `extension/src/Popup.tsx` (полная замена заглушки)

**Interfaces:**
- Consumes: `getPageContent` из `@/lib/page`, `askAgent` из `@/lib/api`, компоненты `@/components/ui/{button,textarea,scroll-area,card}`.

- [ ] **Step 1: Реализация Popup.tsx**

```tsx
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import { getPageContent } from "@/lib/page";
import { askAgent } from "@/lib/api";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

export function Popup() {
  const [threadId, setThreadId] = useState<string>("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
      if (tab?.id) setThreadId(`tab-${tab.id}`);
    });
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send() {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    try {
      const page = await getPageContent();
      const answer = await askAgent(threadId, question, {
        title: page.title,
        url: page.url,
        text: page.text,
      });
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `⚠️ ${(e as Error).message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="flex h-[500px] w-[380px] flex-col bg-background text-foreground">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-semibold">AI Page Agent</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setMessages([])}
          disabled={loading}
        >
          Очистить
        </Button>
      </div>

      <ScrollArea className="flex-1 px-3 py-2">
        <div className="flex flex-col gap-2">
          {messages.length === 0 && (
            <p className="text-xs text-muted-foreground">
              Спросите что-нибудь об этой странице. Например: «О чём эта страница?»
              или «Найди свежие новости по теме».
            </p>
          )}
          {messages.map((m, i) => (
            <Card
              key={i}
              className={
                "max-w-[90%] whitespace-pre-wrap px-3 py-2 text-sm " +
                (m.role === "user"
                  ? "self-end bg-primary text-primary-foreground"
                  : "self-start")
              }
            >
              {m.content}
            </Card>
          ))}
          {loading && (
            <Card className="self-start px-3 py-2 text-sm text-muted-foreground">
              Думаю…
            </Card>
          )}
          <div ref={endRef} />
        </div>
      </ScrollArea>

      <div className="flex gap-2 border-t p-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ваш вопрос…"
          className="min-h-[40px] resize-none text-sm"
        />
        <Button onClick={send} disabled={loading || !input.trim()}>
          ➤
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Сборка и проверка типов**

Run: `cd extension && npm run build`
Expected: сборка успешна, ошибок типов нет.

- [ ] **Step 3: Commit**

```bash
git add extension/src/Popup.tsx
git commit -m "feat(extension): чат-интерфейс на shadcn/ui"
```

---

## Task 8: Сквозная проверка и README

**Files:**
- Create: `README.md`

**Interfaces:** —

- [ ] **Step 1: README.md** (инструкция запуска)

````markdown
# AI Page Agent

AI-агент в виде расширения Chrome: отвечает на вопросы о текущей странице
и умеет искать в интернете через EXA. Агент — на LangGraph (Python).

## Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить OPENROUTER_API_KEY, EXA_API_KEY, OPENROUTER_MODEL
uvicorn app.main:app --reload --port 8000
```

## Extension

```bash
cd extension
npm install
npm run build
```

Затем в Chrome: `chrome://extensions` → включить «Режим разработчика» →
«Загрузить распакованное расширение» → выбрать папку `extension/dist`.

## Использование

Откройте любую страницу, нажмите иконку расширения, задайте вопрос.
- «О чём эта страница?» — ответ из содержимого.
- «Найди свежие новости по теме» — агент вызовет инструмент EXA.
````

- [ ] **Step 2: Запустить backend вручную**

Run: `cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000`
Expected: сервер стартует без ошибок; `curl http://localhost:8000/health` → `{"status":"ok"}`.

- [ ] **Step 3: Сквозная проверка №1 — ответ по странице**

Загрузить `extension/dist` в Chrome, открыть статью (например, Wikipedia),
нажать иконку, спросить «О чём эта страница?».
Expected: осмысленный ответ по содержимому страницы.

- [ ] **Step 4: Сквозная проверка №2 — инструмент EXA**

Спросить «Найди свежие новости по теме этой страницы».
Expected: ответ со ссылками на внешние источники (агент вызвал `exa_search`).
Проверить в логах uvicorn, что был вызов инструмента.

- [ ] **Step 5: Сквозная проверка №3 — память диалога**

Задать уточняющий вопрос («а подробнее про второй пункт?») без повтора контекста.
Expected: агент помнит предыдущий ответ (работает checkpointer по thread_id).

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: README с инструкцией запуска"
```

---

## Self-Review (выполнено при написании плана)

- **Покрытие спека:** расширение+чат (Task 5,7), извлечение страницы (Task 6), Python+FastAPI+LangGraph агент (Task 3,4), инструмент EXA (Task 2), OpenRouter LLM (Task 1,3), память диалога через checkpointer (Task 3,4 + проверка Task 8.5), обработка ошибок (Task 4 try/except, Task 6 api.ts), тесты (Task 1–4 pytest + Task 8 ручные). Все разделы спека покрыты.
- **Плейсхолдеры:** не обнаружены — во всех шагах приведён реальный код/команды.
- **Согласованность типов:** `ChatRequest`/`Page` (schemas.py) ↔ тело запроса в `api.ts`; `build_agent`/`build_page_system_message`/`SYSTEM_BASE` согласованы между Task 3 и Task 4; `thread_id` формата `tab-<id>` одинаков в Popup.tsx и main.py.
