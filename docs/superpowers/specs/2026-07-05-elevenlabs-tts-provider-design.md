# Дизайн: настраиваемый TTS-провайдер (edge-tts / ElevenLabs)

Дата: 2026-07-05
Статус: утверждён

## Цель

Инструмент `text_to_speech` сейчас озвучивает только через бесплатный edge-tts.
Добавить ElevenLabs как альтернативного провайдера с более естественным
голосом, оставив edge-tts дефолтом и грациозным фолбэком (демо работает без
ключа ElevenLabs). Выбор — через `.env`, по образцу опционального Langfuse.

Проверено вживую (ключ из `backend/.env`, через `PROXY_URL`): ElevenLabs
достижим, TTS-права у ключа есть, синтез русской фразы моделью
`eleven_multilingual_v2` возвращает валидный mp3.

## Конфигурация (`config.py`, всё опционально)

- `TTS_PROVIDER` = `edge` (по умолчанию) | `elevenlabs`.
- `ELEVENLABS_API_KEY` (пусто = провайдер недоступен).
- `ELEVENLABS_VOICE_ID` (по умолчанию `XB0fDUnXU5powFXDhCwa` — голос Charlotte,
  многоязычный; переопределяется).
- `ELEVENLABS_MODEL` (по умолчанию `eleven_multilingual_v2`).
- Существующие `TTS_VOICE` (голос edge-tts) и `audio_dir` — без изменений.

Новые поля в dataclass `Settings` идут после существующих (позиционная
совместимость `Settings("k","u","m","e",100,...)` сохраняется).

## Выбор провайдера (`tools.py`)

`text_to_speech(text)` не меняет сигнатуру и контракт (обрезка до
`TTS_TEXT_LIMIT=3000`, файл `<uuid4>.mp3` в `audio_dir`, возврат ссылки
`http://localhost:8000/audio/<filename>` с инструкцией вставить как есть).

Внутри — диспетчер:

```
provider = config.settings.tts_provider
if provider == "elevenlabs" and config.settings.elevenlabs_api_key:
    _synthesize_elevenlabs(snippet, path)
else:
    _synthesize_edge(snippet, path)
```

То есть при `elevenlabs` без ключа — тихий фолбэк на edge-tts.

- `_synthesize_edge(text, path)` — вынос текущей логики edge-tts
  (`edge_tts.Communicate(...).save` через `asyncio.run`).
- `_synthesize_elevenlabs(text, path)` — синхронный `httpx.post`
  (новых зависимостей нет; httpx уже в стеке):
  `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128`,
  заголовки `xi-api-key`, `Content-Type: application/json`,
  тело `{"text": ..., "model_id": <ELEVENLABS_MODEL>}`, `timeout=60`,
  `resp.raise_for_status()`, тело (`resp.content`, `audio/mpeg`) пишется в `path`.
  Базовый URL — константа `ELEVENLABS_TTS_URL` в модуле (для мока в тестах).

Обе вспомогательные функции только пишут файл по `path`; общий код (имя файла,
каталог, формирование ссылки, единый `try/except` → «Озвучка сейчас недоступна
(ИмяИсключения).») остаётся в `text_to_speech`. Исходящий трафик ElevenLabs
идёт через `PROXY_URL` (httpx читает env-прокси, выставленные `apply_proxy`).

## Обработка ошибок

- Любой сбой синтеза (сеть, 4xx/5xx ElevenLabs, edge-tts) → существующее
  сообщение «Озвучка сейчас недоступна (…)», запрос не роняется.
- Провайдер `elevenlabs` без ключа → фолбэк на edge-tts (не ошибка).
- Неизвестное значение `TTS_PROVIDER` трактуется как `edge` (условие проверяет
  строго `== "elevenlabs"`).

## Тесты (`tests/`, без сети)

- `test_tools.py`:
  - ElevenLabs-путь: `TTS_PROVIDER=elevenlabs` + ключ, `httpx.post` замокан
    (возвращает объект с `.content=b"mp3"`, `.raise_for_status()` — no-op) →
    файл создан, ссылка содержит имя файла; проверить, что post вызван с
    нужным voice_id/model в URL/теле и заголовком `xi-api-key`.
  - Фолбэк: `TTS_PROVIDER=elevenlabs` без ключа → зовётся edge-путь
    (мок `edge_tts.Communicate`), `httpx.post` НЕ вызван.
  - Дефолт `edge`: существующие тесты остаются зелёными.
  - Ошибка ElevenLabs (`httpx.post` кидает) → «Озвучка сейчас недоступна».
- `test_config.py`: дефолты новых настроек и чтение из env.

## Изменения по файлам

- `backend/app/config.py` — новые настройки.
- `backend/app/tools.py` — диспетчер + две функции синтеза + константа URL.
- `backend/.env.example` — `TTS_PROVIDER`, `ELEVENLABS_API_KEY`,
  `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL` с комментариями.
- `backend/tests/test_tools.py`, `backend/tests/test_config.py` — тесты.
- `README.md` — раздел про выбор TTS-провайдера и переменные.
- `CLAUDE.md` — строка про `text_to_speech` дополняется упоминанием провайдеров.

## Живая проверка (нужен ключ, он уже в `.env`)

`pytest` зелёный; запустить бэкенд, задать «озвучь пересказ страницы» при
`TTS_PROVIDER=elevenlabs` → в панели играет mp3, синтезированный ElevenLabs;
переключить на `edge` → играет edge-tts.

## Вне скоупа

- Стриминг аудио, выбор голоса из UI, кэш/дедуп синтеза, автоочистка `audio_dir`.
- Официальный SDK `elevenlabs` (обходимся httpx).
