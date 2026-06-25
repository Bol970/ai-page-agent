# Дизайн: боковая панель в стиле ChatGPT + HTML-рендер ответов

Дата: 2026-06-25
Статус: утверждён
Базируется на: [2026-06-25-chrome-ai-agent-design.md](2026-06-25-chrome-ai-agent-design.md)

## Цель

Переделать UI расширения:
1. Вместо popup — **выезжающая боковая панель справа** (Chrome Side Panel API).
2. Вид **как у ChatGPT** (тёмная тема, лента сообщений, крупное поле ввода).
3. Ответы ассистента рендерить **как HTML**, а не как сырой markdown
   (сейчас видно `**текст**` вместо жирного).

Бэкенд не меняется.

## 1. Механизм панели (Chrome Side Panel API)

- `manifest.config.ts`: убрать `action.default_popup`; добавить
  `"side_panel": { "default_path": "index.html" }` и разрешение `sidePanel`;
  добавить `background.service_worker`.
- Новый `src/background.ts`:
  `chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })` —
  клик по иконке открывает боковую панель справа.
- Тот же React-апп (`index.html`) рендерится в side-panel. Layout — на всю
  высоту панели (`h-screen`), ширину панели контролирует Chrome.
- Извлечение страницы (`getPageContent`) и `thread_id = tab-<id>` — без
  изменений: активная вкладка берётся в момент отправки сообщения.

## 2. Рендер ответов: markdown → HTML

- Зависимости: `marked` (markdown→HTML), `dompurify` (санитайзинг от XSS),
  `@types/dompurify`.
- Новый `src/lib/markdown.ts`: `renderMarkdown(md: string): string` — парсит
  markdown через `marked` и пропускает результат через `DOMPurify.sanitize`.
- Ответы ассистента рендерятся через `dangerouslySetInnerHTML` уже как
  очищенный HTML (жирный, списки, ссылки, инлайн-код).
- Сообщения пользователя выводятся как обычный текст (без HTML-рендера) —
  безопасно и соответствует поведению ChatGPT.
- Ссылки в ответах открываются в новой вкладке (`target="_blank"
  rel="noreferrer"`), добавляется при постобработке/через стили.

## 3. Вид «как ChatGPT»

- Тёмная тема (уже включена `class="dark"`).
- Лента: каждое сообщение — строка на всю ширину. Ассистент — строка с лёгким
  фоном и маленькой иконкой «AI»; пользователь — пузырь, прижатый вправо.
- Поле ввода внизу: крупное, скруглённое, кнопка-стрелка отправки внутри/рядом;
  Enter — отправка, Shift+Enter — перенос строки.
- Индикатор «печатает…» — три анимированные точки.
- Шапка: заголовок + кнопка «Очистить».
- Компоненты shadcn те же (`Button`, `Textarea`, `ScrollArea`) + prose-стили
  для HTML-ответов в `src/index.css`.

## 4. Файлы

| Файл | Изменение |
|---|---|
| `extension/manifest.config.ts` | side_panel + sidePanel + background; убрать popup |
| `extension/src/background.ts` | новый — поведение открытия панели |
| `extension/src/lib/markdown.ts` | новый — renderMarkdown + санитайзинг |
| `extension/src/Popup.tsx` → `src/ChatPanel.tsx` | вёрстка в стиле ChatGPT + HTML-рендер |
| `extension/src/main.tsx` | импорт ChatPanel вместо Popup |
| `extension/src/index.css` | prose-стили для HTML-ответов |
| `extension/package.json` | marked, dompurify, @types/dompurify |

## 5. Обработка ошибок

- Ошибки агента/сети — как раньше: показываются в ленте как сообщение
  ассистента с пометкой (текст, без HTML-рендера, чтобы не сломать вёрстку).
- `renderMarkdown` при сбое парсинга возвращает экранированный исходный текст.

## 6. Тестирование

- JS-тест-раннера в проекте нет; `renderMarkdown` — чистая функция, проверяется
  при сборке (`npm run build`, tsc) и вручную. Тест-раннер не добавляем (YAGNI).
- Ручная проверка: иконка открывает панель справа; ответы рендерятся как HTML
  (жирный/списки/ссылки); вид как ChatGPT; память диалога работает.

## Принятые решения

- Панель: Chrome Side Panel API (нативная правая панель; без конфликтов с CSS сайта).
- Рендер: marked + DOMPurify на фронте (модель надёжно выдаёт markdown).
