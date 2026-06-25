# Боковая панель ChatGPT-стиль + HTML-рендер — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить popup-расширение в боковую панель Chrome (Side Panel API) в стиле ChatGPT, где ответы ассистента рендерятся как HTML, а не как сырой markdown.

**Architecture:** Тот же React-апп (`index.html`) рендерится в боковой панели вместо popup. Фоновый service worker открывает панель по клику на иконку. Ответы прогоняются через `marked` (md→html) + `DOMPurify` (санитайзинг) и вставляются через `dangerouslySetInnerHTML`. Бэкенд не меняется.

**Tech Stack:** React 18 + TS + Vite + Tailwind v4 + shadcn/ui + @crxjs/vite-plugin; marked, dompurify.

## Global Constraints

- Панель — через Chrome **Side Panel API**: manifest `side_panel.default_path = "index.html"`, разрешение `sidePanel`, фоновый `background.service_worker`. `action.default_popup` УБРАТЬ.
- Клик по иконке открывает панель: `chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })`.
- Ответы ассистента рендерятся как **очищенный HTML** (`marked.parse` → `DOMPurify.sanitize`). Сообщения пользователя — как обычный текст (без HTML-рендера).
- Ссылки в HTML-ответах открываются в новой вкладке (`target="_blank" rel="noreferrer noopener"`).
- `thread_id = "tab-<tabId>"`, извлечение страницы через активную вкладку — без изменений.
- Вид как ChatGPT: тёмная тема, лента на всю высоту панели, крупное поле ввода внизу, индикатор «печатает».

---

## Структура файлов

```
extension/
  manifest.config.ts        ← MODIFY: side_panel + sidePanel + background, убрать popup
  index.html                ← MODIFY: root на всю ширину/высоту
  src/
    background.ts           ← CREATE: поведение открытия панели
    lib/markdown.ts         ← CREATE: renderMarkdown (marked + DOMPurify)
    ChatPanel.tsx           ← CREATE: UI в стиле ChatGPT (заменяет Popup.tsx)
    Popup.tsx               ← DELETE
    main.tsx                ← MODIFY: рендерить ChatPanel
    index.css              ← MODIFY: высота + стили HTML-ответов
  package.json              ← MODIFY: marked, dompurify, @types/dompurify
```

---

## Task 1: Боковая панель (manifest + background)

**Files:**
- Modify: `extension/manifest.config.ts`
- Create: `extension/src/background.ts`

**Interfaces:**
- Produces: собранное расширение, где клик по иконке открывает side panel; `dist/manifest.json` содержит `side_panel` и разрешение `sidePanel`, без `default_popup`.

- [ ] **Step 1: Переписать manifest.config.ts**

```ts
import { defineManifest } from "@crxjs/vite-plugin";

export default defineManifest({
  manifest_version: 3,
  name: "AI Page Agent",
  version: "0.1.0",
  description: "AI-агент, отвечающий на вопросы о текущей странице",
  action: { default_title: "AI Page Agent" },
  background: { service_worker: "src/background.ts", type: "module" },
  side_panel: { default_path: "index.html" },
  permissions: ["activeTab", "scripting", "tabs", "sidePanel"],
  host_permissions: ["http://localhost:8000/*"],
});
```

- [ ] **Step 2: Создать src/background.ts**

```ts
// Клик по иконке расширения открывает боковую панель справа.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error(error));
```

- [ ] **Step 3: Собрать и проверить манифест**

Run: `cd extension && npm run build`
Expected: сборка успешна.

Run: `cd extension && grep -E '"side_panel"|"sidePanel"' dist/manifest.json && ! grep -q '"default_popup"' dist/manifest.json && echo OK`
Expected: печатает строки с `side_panel`/`sidePanel` и `OK` (popup отсутствует).

- [ ] **Step 4: Commit**

```bash
git add extension/manifest.config.ts extension/src/background.ts
git commit -m "feat(extension): боковая панель через Side Panel API"
```

---

## Task 2: Рендер markdown → HTML

**Files:**
- Modify: `extension/package.json` (добавить зависимости)
- Create: `extension/src/lib/markdown.ts`

**Interfaces:**
- Produces: `renderMarkdown(md: string): string` из `@/lib/markdown` — возвращает очищенный HTML; ссылки получают `target="_blank"`.

- [ ] **Step 1: Установить зависимости**

Run: `cd extension && npm install marked dompurify && npm install -D @types/dompurify`
Expected: пакеты установлены, `package.json` обновлён.

- [ ] **Step 2: Создать src/lib/markdown.ts**

```ts
import { marked } from "marked";
import DOMPurify from "dompurify";

// Ссылки в ответах открываем в новой вкладке.
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noreferrer noopener");
  }
});

/** Превращает markdown в безопасный HTML. При сбое — экранированный текст. */
export function renderMarkdown(md: string): string {
  try {
    const html = marked.parse(md, { async: false }) as string;
    return DOMPurify.sanitize(html);
  } catch {
    return md
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
}
```

- [ ] **Step 3: Проверка типов**

Run: `cd extension && npx tsc -b`
Expected: без ошибок типов. (Рантайм-проверка — при сборке Task 3, где функция используется; `DOMPurify` требует DOM, который есть в контексте боковой панели браузера.)

- [ ] **Step 4: Commit**

```bash
git add extension/package.json extension/package-lock.json extension/src/lib/markdown.ts
git commit -m "feat(extension): renderMarkdown (marked + DOMPurify)"
```

---

## Task 3: UI в стиле ChatGPT + HTML-рендер

**Files:**
- Create: `extension/src/ChatPanel.tsx`
- Delete: `extension/src/Popup.tsx`
- Modify: `extension/src/main.tsx`
- Modify: `extension/index.html`
- Modify: `extension/src/index.css`

**Interfaces:**
- Consumes: `getPageContent` (`@/lib/page`), `askAgent` (`@/lib/api`), `renderMarkdown` (`@/lib/markdown`), shadcn `Button`/`Textarea`/`ScrollArea`.
- Produces: компонент `ChatPanel` (именованный экспорт), рендерится из `main.tsx`.

- [ ] **Step 1: Создать src/ChatPanel.tsx**

```tsx
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getPageContent } from "@/lib/page";
import { askAgent } from "@/lib/api";
import { renderMarkdown } from "@/lib/markdown";

interface Msg {
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
}

export function ChatPanel() {
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
        { role: "assistant", content: `⚠️ ${(e as Error).message}`, isError: true },
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
    <div className="flex h-screen w-full flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <span className="text-sm font-semibold">AI Page Agent</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setMessages([])}
          disabled={loading}
        >
          Очистить
        </Button>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Спросите что-нибудь об этой странице. Например: «О чём эта
              страница?» или «Найди свежие новости по теме».
            </p>
          )}

          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2 text-sm text-primary-foreground">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={i} className="flex gap-3">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-semibold text-secondary-foreground">
                  AI
                </div>
                {m.isError ? (
                  <div className="pt-0.5 text-sm text-destructive">{m.content}</div>
                ) : (
                  <div
                    className="assistant-html min-w-0 flex-1 pt-0.5"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                  />
                )}
              </div>
            )
          )}

          {loading && (
            <div className="flex gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-semibold text-secondary-foreground">
                AI
              </div>
              <div className="flex items-center gap-1 pt-2">
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </ScrollArea>

      <div className="border-t px-4 py-3">
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border bg-card px-3 py-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Спросите об этой странице…"
            className="max-h-40 min-h-[40px] flex-1 resize-none border-0 bg-transparent text-sm shadow-none focus-visible:ring-0"
          />
          <Button
            size="icon"
            className="h-9 w-9 shrink-0 rounded-full"
            onClick={send}
            disabled={loading || !input.trim()}
          >
            ➤
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Обновить src/main.tsx**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { ChatPanel } from "@/ChatPanel";
import "@/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ChatPanel />
  </React.StrictMode>
);
```

- [ ] **Step 3: Удалить старый Popup.tsx**

Run: `git rm extension/src/Popup.tsx`
Expected: файл удалён из индекса.

- [ ] **Step 4: Обновить index.html (панель на всю ширину/высоту)**

Заменить строку `<div id="root" style="width: 380px"></div>` на:
```html
    <div id="root"></div>
```

- [ ] **Step 5: Добавить стили в конец src/index.css**

```css
html,
body,
#root {
  height: 100%;
}

.assistant-html {
  font-size: 0.875rem;
  line-height: 1.6;
}
.assistant-html > :first-child {
  margin-top: 0;
}
.assistant-html p {
  margin: 0.5rem 0;
}
.assistant-html ul,
.assistant-html ol {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
}
.assistant-html ul {
  list-style: disc;
}
.assistant-html ol {
  list-style: decimal;
}
.assistant-html li {
  margin: 0.25rem 0;
}
.assistant-html a {
  color: var(--primary);
  text-decoration: underline;
}
.assistant-html strong {
  font-weight: 600;
}
.assistant-html h1,
.assistant-html h2,
.assistant-html h3 {
  font-weight: 600;
  margin: 0.75rem 0 0.4rem;
}
.assistant-html code {
  background: var(--muted);
  padding: 0.1rem 0.3rem;
  border-radius: 0.25rem;
  font-size: 0.85em;
}
.assistant-html pre {
  background: var(--muted);
  padding: 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 0.5rem 0;
}
.assistant-html pre code {
  background: transparent;
  padding: 0;
}
```

- [ ] **Step 6: Сборка и проверка типов**

Run: `cd extension && npm run build`
Expected: `tsc -b` без ошибок, vite build успешен, `dist/` создан.

- [ ] **Step 7: Commit**

```bash
git add extension/src/ChatPanel.tsx extension/src/main.tsx extension/index.html extension/src/index.css
git commit -m "feat(extension): UI в стиле ChatGPT + HTML-рендер ответов"
```

---

## Task 4: Сквозная проверка и README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Обновить раздел использования в README.md**

Заменить абзац про загрузку/использование на:
```markdown
Затем в Chrome: `chrome://extensions` → включить «Режим разработчика» →
«Загрузить распакованное расширение» → выбрать папку `extension/dist`.

## Использование

Нажмите иконку расширения — справа откроется **боковая панель** (Side Panel)
в стиле чата. Ответы отображаются как форматированный HTML (жирный, списки,
ссылки). Задавайте вопросы:

- «О чём эта страница?» — ответ из содержимого страницы.
- «Найди свежие новости по теме» — агент вызовет инструмент EXA и сошлётся на источники.
- Уточняющие вопросы подряд — агент помнит диалог в рамках вкладки.
```

- [ ] **Step 2: Сборка для свежего dist**

Run: `cd extension && npm run build`
Expected: успешная сборка, `dist/manifest.json` присутствует.

- [ ] **Step 3: Ручная проверка №1 — панель открывается справа**

Загрузить `extension/dist` в `chrome://extensions`, нажать иконку.
Expected: справа открывается боковая панель с чатом (не popup).

- [ ] **Step 4: Ручная проверка №2 — HTML-рендер**

Запустить бэкенд, спросить «О чём эта страница?».
Expected: ответ форматирован (жирный текст, списки, кликабельные ссылки), `**` не видны как сырой markdown.

- [ ] **Step 5: Ручная проверка №3 — стиль и память**

Проверить вид (тёмная тема, пузыри пользователя справа, ответы ассистента слева с иконкой «AI», индикатор «печатает»), задать уточняющий вопрос.
Expected: вид как у ChatGPT; агент помнит контекст.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: README — боковая панель и HTML-ответы"
```

---

## Self-Review (выполнено при написании плана)

- **Покрытие спека:** Side Panel API (Task 1), markdown→HTML с санитайзингом и target=_blank (Task 2), UI в стиле ChatGPT + HTML-рендер + полная высота (Task 3), README + ручная проверка (Task 4). Все разделы спека покрыты.
- **Плейсхолдеры:** отсутствуют — везде реальный код/команды.
- **Согласованность типов:** `renderMarkdown(md: string): string` определён в Task 2 и используется в Task 3; `ChatPanel` (именованный экспорт) определён в Task 3 и импортируется в `main.tsx` там же; `getPageContent`/`askAgent` — существующие интерфейсы из предыдущего плана, не меняются.
