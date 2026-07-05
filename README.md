# AI Page Agent

AI-агент в виде расширения Chrome: отвечает на вопросы о текущей странице
и умеет искать в интернете через EXA. «Мозг» агента — на **LangGraph** (Python),
интерфейс — расширение на React + **shadcn/ui**.

```
[Расширение Chrome]  --innerText + вопрос-->  [FastAPI :8000]
  React + shadcn/ui                             LangGraph-агент (create_agent)
  боковая панель (Side Panel)                    ├─ LLM через OpenRouter
  content (chrome.scripting)                     ├─ инструменты: exa_search, page_to_markdown,
                                                 │   extract_links, fetch_url, calculator,
                                                 │   current_datetime, text_to_speech (edge-tts)
                                                 ├─ трейсинг: Langfuse (опционально)
                                                 └─ история диалога из SQLite
```

## Требования

- **Python 3.11+**
- **Node.js 20+** рекомендуется. На Node 18 проект собирается, но CLI `shadcn`
  не работает (использует Web `File` API), а нативный биндинг Tailwind v4
  (`@tailwindcss/oxide`) ставится только под текущую платформу. Компоненты
  shadcn уже добавлены в репозиторий, так что для сборки CLI не нужен.

## Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # заполнить OPENROUTER_API_KEY, EXA_API_KEY, OPENROUTER_MODEL
uvicorn app.main:app --reload --port 8000
```

Проверка, что сервер поднялся: `curl http://localhost:8000/health` → `{"status":"ok"}`.

Тесты бэкенда: `cd backend && source .venv/bin/activate && python -m pytest -v`.

## Extension

```bash
cd extension
npm install
npm run build
```

Затем в Chrome: `chrome://extensions` → включить «Режим разработчика» →
«Загрузить распакованное расширение» → выбрать папку `extension/dist`.

## Использование

Нажмите иконку расширения — справа откроется **боковая панель** (Side Panel)
в стиле чата. Ответы отображаются как форматированный HTML (жирный, списки,
кликабельные ссылки), а не как сырой markdown. Задавайте вопросы:

- «О чём эта страница?» — ответ из содержимого страницы.
- «Найди свежие новости по теме» — агент вызовет инструмент EXA и сошлётся на источники.
- Уточняющие вопросы подряд — агент помнит диалог (история берётся из БД).
- «Скопируй страницу в markdown» — агент вернёт Markdown-версию страницы в code block.
- «Собери все ссылки со страницы» — список ссылок с абсолютными URL.
- «Открой первую ссылку и перескажи» — агент прочитает страницу по ссылке (fetch_url).
- «Сколько будет 2**20?» — точный расчёт через инструмент calculator.
- «Озвучь ответ» — агент сгенерирует mp3 (edge-tts), в чате появится аудиоплеер.

### История чатов

Кнопка **☰** в шапке открывает список чатов. Чаты сохраняются на бэкенде
(SQLite, `backend/chats.db`) и группируются по странице (URL без параметров):
секции «Эта страница» и «Все чаты». Чат можно **закрепить** (📌 — наверху списка),
пометить **тегами** (поле «+ тег» в шапке чата) и фильтровать список по тегу.
Кнопка «＋ Новый чат» создаёт новый чат для текущей страницы.

## Наблюдаемость (Langfuse)

Трейсы агента (LLM-вызовы, инструменты, токены, стоимость) отправляются в
[Langfuse Cloud](https://cloud.langfuse.com), если в `backend/.env` заданы ключи:
зарегистрируйтесь, создайте проект, скопируйте `LANGFUSE_PUBLIC_KEY` и
`LANGFUSE_SECRET_KEY` (регион US — `LANGFUSE_HOST=https://us.cloud.langfuse.com`).
Трейсы группируются по чатам (Sessions, `session_id` = id чата).
Без ключей приложение работает как обычно, трейсинг молча выключен.

## Конфигурация

`backend/.env`:

| Переменная | Назначение |
|---|---|
| `OPENROUTER_API_KEY` | ключ OpenRouter (обязателен) |
| `OPENROUTER_MODEL` | модель, напр. `openai/gpt-4o-mini` |
| `OPENROUTER_BASE_URL` | по умолчанию `https://openrouter.ai/api/v1` |
| `EXA_API_KEY` | ключ EXA для веб-поиска (обязателен) |
| `PAGE_TEXT_LIMIT` | сколько символов страницы слать модели (по умолчанию 12000) |
| `CHATS_DB_PATH` | путь к файлу SQLite с историей чатов (по умолчанию `chats.db`) |
| `PROXY_URL` | прокси для исходящих запросов к LLM/EXA (пусто = напрямую), напр. `http://127.0.0.1:8118` |
| `TTS_VOICE` | голос edge-tts для text_to_speech (по умолчанию `ru-RU-SvetlanaNeural`) |
| `LANGFUSE_PUBLIC_KEY` | публичный ключ Langfuse (пусто = трейсинг выключен) |
| `LANGFUSE_SECRET_KEY` | секретный ключ Langfuse |
| `LANGFUSE_HOST` | регион Langfuse, по умолчанию `https://cloud.langfuse.com` |
