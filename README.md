# AI Page Agent

AI-агент в виде расширения Chrome: отвечает на вопросы о текущей странице
и умеет искать в интернете через EXA. «Мозг» агента — на **LangGraph** (Python),
интерфейс — расширение на React + **shadcn/ui**.

```
[Расширение Chrome]  --innerText + вопрос-->  [FastAPI :8000]
  React + shadcn/ui                             LangGraph-агент (create_agent)
  popup-чат                                      ├─ LLM через OpenRouter
  content (chrome.scripting)                     ├─ инструмент exa_search (EXA)
                                                 └─ память диалога (checkpointer)
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
- Уточняющие вопросы подряд — агент помнит диалог в рамках вкладки (один tab = один тред).

## Конфигурация

`backend/.env`:

| Переменная | Назначение |
|---|---|
| `OPENROUTER_API_KEY` | ключ OpenRouter (обязателен) |
| `OPENROUTER_MODEL` | модель, напр. `openai/gpt-4o-mini` |
| `OPENROUTER_BASE_URL` | по умолчанию `https://openrouter.ai/api/v1` |
| `EXA_API_KEY` | ключ EXA для веб-поиска (обязателен) |
| `PAGE_TEXT_LIMIT` | сколько символов страницы слать модели (по умолчанию 12000) |
