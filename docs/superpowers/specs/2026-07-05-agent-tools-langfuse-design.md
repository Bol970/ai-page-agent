# Дизайн: мультитул-агент + наблюдаемость Langfuse

Дата: 2026-07-05
Статус: утверждён

## Цель

Домашнее задание l7 (две части):

1. Добавить агенту дополнительные инструменты: `page_to_markdown`, `extract_links`,
   `fetch_url`, `calculator`, `current_datetime`, `text_to_speech` (edge-tts).
2. Встроить анализ запросов через **Langfuse Cloud** (трейсы агента: LLM-вызовы,
   инструменты, токены, стоимость; группировка по чатам).

## Ключевые архитектурные решения

### HTML страницы — через request-scoped контекст (не через LLM)

`page_to_markdown` и `extract_links` требуют HTML текущей страницы. Передавать его
через аргументы инструмента нельзя — LLM пришлось бы «перепечатать» мегабайт HTML.

- Расширение дополнительно снимает `document.body.outerHTML` (обрезка до 800 000
  символов) и шлёт в поле `html` пейлоада страницы. Поле опционально (default `""`).
- Новый модуль `backend/app/page_context.py`: `contextvars.ContextVar` со словарём
  `{title, url, html}`. `main.py` заполняет его перед `agent.invoke` и сбрасывает
  в `finally`. Инструменты читают контекст напрямую.
- Отвергнутая альтернатива: инструмент сам скачивает страницу по URL — ломается
  на страницах за логином и на динамическом контенте.

### Аудио TTS — файл на бэкенде + ссылка в ответе (не base64)

Инструмент возвращает результат LLM-у, а не UI, поэтому:

- `text_to_speech` генерирует mp3 через edge-tts, сохраняет в каталог аудио на
  бэкенде (`<каталог chats.db>/audio/`, имя `<uuid4>.mp3`) и возвращает агенту
  готовую ссылку `http://localhost:8000/audio/<uuid>.mp3` с инструкцией вставить
  её в ответ.
- Новый эндпоинт `GET /audio/{filename}` отдаёт файл через `FileResponse`.
  Валидация имени: строго `<uuid>.mp3` (regex), никакого path traversal.
- `ChatPanel.tsx`: если в тексте сообщения ассистента встречается ссылка на
  `http://localhost:8000/audio/*.mp3` — под сообщением рендерится нативный
  React-элемент `<audio controls>`. DOMPurify не трогаем.
- Отвергнутая альтернатива: base64-аудио в тексте ответа — мегабайтные записи
  в истории чата и в промптах следующих запросов.

## Инструменты (backend/app/tools.py)

Все — `@tool`-функции по образцу `exa_search`: любая внутренняя ошибка
возвращается агенту коротким текстом («инструмент недоступен, ответь по
странице»), никогда не роняет запрос.

| Инструмент | Аргументы | Поведение |
|---|---|---|
| `page_to_markdown` | — | HTML из контекста → очистка (`script`, `style`, `noscript`, `svg` удаляются через BeautifulSoup) → `markdownify` → Markdown, обрезка до 20 000 символов. Пустой контекст → текст «содержимое страницы недоступно». |
| `extract_links` | — | Из HTML контекста: `a[href]` → список `- [текст](URL)`, URL приводятся к абсолютным через `urljoin` с URL страницы, дедупликация по URL, максимум 100 ссылок. |
| `fetch_url` | `url: str` | Только `http/https`. `httpx.get` (timeout 15 c, follow_redirects, лимит тела 2 МБ). HTML → та же очистка + markdownify; иное — как текст. Обрезка до 8 000 символов. |
| `calculator` | `expression: str` | Разбор через `ast`: числа, `+ - * / // % **`, унарный минус, скобки. Всё прочее (имена, вызовы) → отказ текстом. Никакого `eval`. |
| `current_datetime` | — | Локальные дата, время, день недели (ISO + читаемая строка на русском). |
| `text_to_speech` | `text: str` | Обрезка текста до 3 000 символов, голос из `TTS_VOICE` (default `ru-RU-SvetlanaNeural`), edge-tts асинхронный — внутри инструмента `asyncio.run`. Возвращает ссылку на mp3. |

Системный промпт `SYSTEM_BASE` дополняется: перечень инструментов и когда их
звать; правило «результат `page_to_markdown` выводить дословно внутри fenced
code block»; правило «ссылку из `text_to_speech` вставлять в ответ как есть».

## Langfuse Cloud

- Новые настройки в `Settings` (все опциональны): `langfuse_public_key`,
  `langfuse_secret_key`, `langfuse_host` (default `https://cloud.langfuse.com`).
- Если оба ключа заданы — при старте создаётся `CallbackHandler`
  (`langfuse.langchain`); иначе трейсинг **молча выключен** — тесты и клоны
  репозитория без регистрации работают как раньше.
- Хендлер передаётся в каждый `agent.invoke(...)`:
  `config={"callbacks": [handler], "metadata": {"langfuse_session_id": chat_id}}` —
  трейсы в Langfuse группируются по чатам (Sessions).
- Исходящий трафик Langfuse идёт через существующий механизм `PROXY_URL`
  (`apply_proxy` выставляет `HTTPS_PROXY`; SDK Langfuse на httpx его уважает).

## Изменения по файлам

Backend:

- `requirements.txt`: + `markdownify`, `beautifulsoup4`, `edge-tts`, `langfuse`.
- `app/config.py`: + `tts_voice`, `langfuse_public_key`, `langfuse_secret_key`,
  `langfuse_host`, `audio_dir` (вычисляется от каталога БД).
- `app/page_context.py` (новый): ContextVar + set/reset/get помощники.
- `app/tools.py`: шесть новых инструментов.
- `app/agent.py`: расширенный `SYSTEM_BASE`, `build_agent` подключает все инструменты.
- `app/main.py`: заполнение page-контекста вокруг `agent.invoke`, Langfuse-хендлер,
  `GET /audio/{filename}`.
- `app/schemas.py`: `PagePayload.html: str = ""`.
- `.env.example`: + `TTS_VOICE`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
  `LANGFUSE_HOST`.

Extension:

- `src/lib/page.ts`: снимать `outerHTML` с лимитом 800 000 символов.
- `src/lib/chatsApi.ts`: `PagePayload.html`.
- `src/App.tsx`: передавать `p.html` в `sendMessage`.
- `src/ChatPanel.tsx`: аудиоплеер под сообщением при наличии ссылки на `/audio/*.mp3`.

Документация: README — новые инструменты, переменные окружения, скриншот-инструкция
по Langfuse (регистрация, ключи).

## Обработка ошибок

- Каждый инструмент ловит все исключения и возвращает агенту короткий текст
  (паттерн `exa_search`).
- `fetch_url`: не-http(s) схемы, таймауты, слишком большие ответы → текст ошибки.
- `/audio/{filename}`: имя не по формату `<uuid>.mp3` или файла нет → 404.
- Отсутствие ключей Langfuse — штатный режим, не ошибка.
- Пустой/отсутствующий `html` в пейлоаде (старый клиент) → инструменты страницы
  отвечают «содержимое недоступно», остальное работает.

## Тестирование

pytest (без сети, по образцу существующих тестов):

- `calculator`: арифметика, приоритеты, деление на ноль, злые выражения
  (`__import__`, имена, вызовы) → отказ.
- `page_to_markdown` / `extract_links`: фикстурный HTML в контексте; пустой
  контекст → «недоступно».
- `fetch_url`: httpx замокан (monkeypatch), схемы `ftp://` → отказ.
- `text_to_speech`: edge-tts замокан, проверка создания файла и формата ссылки.
- `current_datetime`: формат ответа.
- `/audio`: 200 для существующего файла, 404 для отсутствующего и для
  `../`-имён.
- Конфиг: настройки Langfuse опциональны; `build_agent` включает 7 инструментов.
- Приложение стартует и отвечает без ключей Langfuse.

Extension: `npx tsc -b` и `npm run build` проходят.

Живое демо: «скопируй страницу в markdown», «собери все ссылки», «сколько будет
2**20», «который час», «открой первую ссылку и перескажи», «озвучь ответ» +
трейсы видны в Langfuse UI (Sessions = чаты).

## Вне скоупа

- Стриминг ответов и аудио.
- Очистка старых mp3 (каталог живёт до ручного удаления).
- UI-кнопка «скопировать markdown» (копирование — штатно из code block).
- Самостоятельный хостинг Langfuse.
