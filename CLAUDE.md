# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

AI Page Agent — Chrome-расширение (боковая панель) для вопросов о текущей странице.
Две независимые части, общаются по HTTP на `localhost:8000`:

- `backend/` — FastAPI + LangGraph-агент (Python 3.11+), LLM через OpenRouter, веб-поиск через EXA, история чатов в SQLite (`chats.db`).
- `extension/` — Chrome MV3 расширение: React 18 + shadcn/ui + Tailwind v4, собирается Vite + `@crxjs/vite-plugin` (манифест генерируется из `manifest.config.ts`).

Документация и общение в проекте — на русском.

## Команды

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # обязательны OPENROUTER_API_KEY и EXA_API_KEY
uvicorn app.main:app --reload --port 8000
```

Тесты (сеть не нужна — LLM подменяется fake-моделью):

```bash
cd backend && source .venv/bin/activate
python -m pytest -v                          # все
python -m pytest tests/test_db.py -v         # один файл
python -m pytest -k test_create_chat -v      # один тест
```

### Extension

```bash
cd extension
npm install
npm run build        # tsc -b && vite build → dist/
```

Быстрая проверка типов без сборки: `npx tsc -b`. Линтера в проекте нет.
Загрузка в Chrome: `chrome://extensions` → режим разработчика → «Загрузить распакованное» → `extension/dist`.
Node 20+ (на Node 18 сборка работает, но CLI `shadcn` — нет; компоненты shadcn уже закоммичены в `src/components/ui/`).

## Архитектура

Поток запроса: панель читает `innerText` активной вкладки через `chrome.scripting.executeScript` (`extension/src/lib/page.ts`) → `POST /chats/{id}/messages` c вопросом и содержимым страницы → бэкенд собирает промпт и вызывает агента → ответ сохраняется в SQLite и рендерится как markdown (`marked` + `DOMPurify` в `lib/markdown.ts`).

### Backend (`backend/app/`)

- `main.py` — все эндпоинты (CRUD чатов + `/chats/{id}/messages`). Соединение с SQLite открывается на каждый запрос (`_conn()`), закрывается в `finally`.
- **Агент stateless** (`create_agent` без checkpointer, `agent.py`): история диалога НЕ живёт в LangGraph — на каждый запрос она заново собирается из БД в список `HumanMessage`/`AIMessage` (`main.py:post_message`). System-message с содержимым страницы строится каждый раз заново (`build_page_system_message`, обрезка до `PAGE_TEXT_LIMIT`).
- `config.py` — `settings` инициализируется лениво в `main.py` при старте; `apply_proxy()` выставляет env-переменные прокси и должен вызываться **до** создания LLM/EXA-клиентов.
- `tools.py` — семь инструментов агента: `exa_search`, `page_to_markdown`, `extract_links` (HTML — из request-контекста `page_context.py`), `fetch_url`, `calculator` (ast, без eval), `current_datetime`, `text_to_speech` (провайдер по `TTS_PROVIDER`: `edge`-tts или `elevenlabs` через httpx, фолбэк на edge без ключа; mp3 в `audio_dir`, отдаётся через `GET /audio/{filename}`). Ошибки инструментов не роняют ответ, а возвращаются агенту текстом.
- `db.py` — схема создаётся в `connect()` (`init_schema`), id — uuid4, теги хранятся JSON-строкой. Тесты API подменяют `config.settings` и модуль `agent` через monkeypatch.
- `observability.py` — опциональный Langfuse `CallbackHandler` (без ключей — None); `main.py` передаёт его в `agent.invoke` с `langfuse_session_id = chat_id`.

### Extension (`extension/src/`)

- `App.tsx` — вся state-логика: синхронизация с активной вкладкой (`chrome.tabs.onActivated`/`onUpdated`), память «вкладка → чат» (`tabChat`), создание чата при первом сообщении. На нечитаемых страницах (chrome:// и т.п.) ввод блокируется (`pageReadable`).
- `ChatPanel.tsx` / `Sidebar.tsx` — презентация; `background.ts` только открывает side panel по клику на иконку.
- `lib/chatsApi.ts` — типизированный клиент бэкенда (BASE = `http://localhost:8000`).
- Alias `@` → `src/` (vite.config.ts + tsconfig).

### Инвариант нормализации URL

Чаты группируются по URL без query/hash. Нормализация **продублирована** в двух местах и должна совпадать: `normalize_url` в `backend/app/db.py` и `normalizeUrl` в `extension/src/App.tsx`. Меняешь одну — меняй вторую.

### Инвариант адреса бэкенда

`http://localhost:8000` захардкожен в трёх местах, которые должны совпадать:
`text_to_speech` в `backend/app/tools.py` (ссылка на mp3), `BASE` в
`extension/src/lib/chatsApi.ts` и `AUDIO_URL_RE` в `extension/src/ChatPanel.tsx`.
Меняешь порт — меняй все три.

## Проектные документы

- `docs/superpowers/specs/` и `docs/superpowers/plans/` — дизайн-доки и планы реализованных фич (side panel, история чатов).
- `.superpowers/sdd/progress.md` — журнал subagent-driven разработки с итогами ревью.
