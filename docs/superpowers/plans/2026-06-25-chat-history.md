# История чатов по страницам (закреп + теги) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Постоянная история чатов в SQLite на бэкенде, сгруппированная по нормализованному URL страницы, с закреплением и тегами; новый UI с выезжающим сайдбаром списка чатов.

**Architecture:** Бэкенд хранит чаты/сообщения в SQLite (единственный источник правды) и предоставляет CRUD + эндпоинт сообщений; агент stateless — история берётся из БД, системный промпт со страницей собирается на каждый запрос. Фронт: `App` оркеструет состояние, `Sidebar` — список/закреп/теги/фильтр, `ChatPanel` — активный чат.

**Tech Stack:** Python + FastAPI + sqlite3 + LangGraph; React + TS + Vite + Tailwind + shadcn/ui.

## Global Constraints

- Хранилище — SQLite (`backend/chats.db`), БД — единственный источник правды.
- Привязка чата к странице — нормализованный URL (схема+host+path, без `?query` и `#hash`), нормализация на бэкенде.
- Агент **stateless**: checkpointer убрать; история сообщений берётся из БД; `SystemMessage(build_page_system_message(page))` добавляется свежим на каждый запрос.
- API: `GET /chats?url=`, `POST /chats`, `GET /chats/{id}`, `POST /chats/{id}/messages`, `PATCH /chats/{id}`, `DELETE /chats/{id}`, `GET /health`. Старый `POST /chat` удалить.
- JSON-ключи `ChatMeta`: `id, page_url, page_title, title, pinned, tags, created_at, updated_at, preview` (snake_case). `Message`: `id, role, content, created_at`.
- Список чатов: pinned первыми, затем по `updated_at` desc.
- Ошибка агента → текстовый ответ (не 500). CORS `allow_origins=["*"]`.
- Навигация — выезжающий сайдбар слева; HTML-рендер ответов сохраняется.

---

## Структура файлов

```
backend/app/
  db.py            ← CREATE: SQLite-слой (normalize_url, schema, CRUD)
  config.py        ← MODIFY: поле chats_db_path
  agent.py         ← MODIFY: убрать checkpointer (stateless)
  schemas.py       ← MODIFY: CreateChatRequest, MessageRequest, UpdateChatRequest
  main.py          ← MODIFY: chats CRUD + messages endpoint, убрать /chat
backend/tests/
  test_db.py       ← CREATE
  test_chats_api.py← CREATE
  test_agent.py    ← MODIFY (checkpointer убран)
extension/src/
  lib/chatsApi.ts  ← CREATE: клиент CRUD + типы
  App.tsx          ← CREATE: оркестрация состояния
  Sidebar.tsx      ← CREATE: список чатов, закреп, теги, фильтр
  ChatPanel.tsx    ← MODIFY: презентационный (props), бургер, теги в шапке
  main.tsx         ← MODIFY: рендерит App
README.md          ← MODIFY
```

---

## Task 1: SQLite-слой (db.py) + конфиг

**Files:**
- Create: `backend/app/db.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces (`app.db`):
  - `normalize_url(url: str) -> str`
  - `connect(path: str) -> sqlite3.Connection` (с row_factory, FK on, авто `init_schema`)
  - `create_chat(conn, page_url, page_title) -> dict` (ChatMeta)
  - `get_chat_meta(conn, chat_id) -> dict | None`
  - `list_chats(conn, page_url: str | None) -> {"page": list, "all": list}`
  - `add_message(conn, chat_id, role, content) -> dict`
  - `get_messages(conn, chat_id) -> list[dict]`
  - `update_chat(conn, chat_id, pinned=None, title=None, tags=None) -> dict`
  - `delete_chat(conn, chat_id) -> None`
  - ChatMeta dict ключи: `id, page_url, page_title, title, pinned(bool), tags(list), created_at, updated_at, preview`.
- `app.config.Settings` получает поле `chats_db_path: str` (default `"chats.db"`).

- [ ] **Step 1: Написать падающий тест** — `backend/tests/test_db.py`

```python
from app import db


def test_normalize_url_strips_query_and_hash():
    assert db.normalize_url("https://e.test/wiki/X?lang=ru#sec") == "https://e.test/wiki/X"
    assert db.normalize_url("https://e.test/a") == "https://e.test/a"


def test_create_and_get_chat(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    c = db.create_chat(conn, "https://e.test/p?x=1", "Заголовок")
    assert c["page_url"] == "https://e.test/p"
    assert c["pinned"] is False
    assert c["tags"] == []
    got = db.get_chat_meta(conn, c["id"])
    assert got["id"] == c["id"]


def test_messages_and_preview(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    c = db.create_chat(conn, "https://e.test/p", "T")
    db.add_message(conn, c["id"], "user", "привет")
    db.add_message(conn, c["id"], "assistant", "ответ ассистента")
    msgs = db.get_messages(conn, c["id"])
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    meta = db.get_chat_meta(conn, c["id"])
    assert meta["preview"] == "ответ ассистента"


def test_list_pinned_first(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    a = db.create_chat(conn, "https://e.test/p", "A")
    b = db.create_chat(conn, "https://e.test/p", "B")
    db.update_chat(conn, b["id"], pinned=True)
    listed = db.list_chats(conn, "https://e.test/p")
    assert listed["all"][0]["id"] == b["id"]  # pinned первым
    assert {m["id"] for m in listed["page"]} == {a["id"], b["id"]}


def test_update_tags_and_delete_cascades(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    c = db.create_chat(conn, "https://e.test/p", "T")
    db.add_message(conn, c["id"], "user", "q")
    upd = db.update_chat(conn, c["id"], tags=["work", "ai"])
    assert upd["tags"] == ["work", "ai"]
    db.delete_chat(conn, c["id"])
    assert db.get_chat_meta(conn, c["id"]) is None
    assert db.get_messages(conn, c["id"]) == []
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.db'`)

- [ ] **Step 3: Реализация** — `backend/app/db.py`

```python
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            page_url TEXT NOT NULL,
            page_title TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            pinned INTEGER NOT NULL DEFAULT 0,
            tags TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def _last_preview(conn: sqlite3.Connection, chat_id: str, limit: int = 80) -> str:
    row = conn.execute(
        "SELECT content FROM messages WHERE chat_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    return row["content"][:limit] if row else ""


def _row_to_meta(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "page_url": row["page_url"],
        "page_title": row["page_title"],
        "title": row["title"],
        "pinned": bool(row["pinned"]),
        "tags": json.loads(row["tags"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "preview": _last_preview(conn, row["id"]),
    }


def create_chat(conn: sqlite3.Connection, page_url: str, page_title: str) -> dict:
    cid = str(uuid.uuid4())
    now = _now()
    conn.execute(
        "INSERT INTO chats (id, page_url, page_title, title, pinned, tags, created_at, updated_at)"
        " VALUES (?,?,?,?,0,'[]',?,?)",
        (cid, normalize_url(page_url), page_title, "", now, now),
    )
    conn.commit()
    return get_chat_meta(conn, cid)


def get_chat_meta(conn: sqlite3.Connection, chat_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
    return _row_to_meta(conn, row) if row else None


def list_chats(conn: sqlite3.Connection, page_url: str | None) -> dict:
    rows = conn.execute(
        "SELECT * FROM chats ORDER BY pinned DESC, updated_at DESC"
    ).fetchall()
    all_metas = [_row_to_meta(conn, r) for r in rows]
    if page_url is None:
        page_metas: list[dict] = []
    else:
        norm = normalize_url(page_url)
        page_metas = [m for m in all_metas if m["page_url"] == norm]
    return {"page": page_metas, "all": all_metas}


def add_message(conn: sqlite3.Connection, chat_id: str, role: str, content: str) -> dict:
    mid = str(uuid.uuid4())
    now = _now()
    conn.execute(
        "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (mid, chat_id, role, content, now),
    )
    conn.execute("UPDATE chats SET updated_at=? WHERE id=?", (now, chat_id))
    conn.commit()
    return {"id": mid, "role": role, "content": content, "created_at": now}


def get_messages(conn: sqlite3.Connection, chat_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, role, content, created_at FROM messages"
        " WHERE chat_id=? ORDER BY created_at ASC, rowid ASC",
        (chat_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_chat(conn, chat_id, pinned=None, title=None, tags=None) -> dict | None:
    if pinned is not None:
        conn.execute("UPDATE chats SET pinned=? WHERE id=?", (1 if pinned else 0, chat_id))
    if title is not None:
        conn.execute("UPDATE chats SET title=? WHERE id=?", (title, chat_id))
    if tags is not None:
        conn.execute("UPDATE chats SET tags=? WHERE id=?", (json.dumps(tags), chat_id))
    conn.execute("UPDATE chats SET updated_at=? WHERE id=?", (_now(), chat_id))
    conn.commit()
    return get_chat_meta(conn, chat_id)


def delete_chat(conn: sqlite3.Connection, chat_id: str) -> None:
    conn.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    conn.commit()
```

- [ ] **Step 4: Добавить поле в конфиг** — `backend/app/config.py`

В классе `Settings` добавить поле последним (с default, чтобы не сломать позиционное создание):
```python
    page_text_limit: int
    chats_db_path: str = "chats.db"
```
В `load_settings(...)` в конструктор `Settings(...)` добавить аргумент:
```python
        page_text_limit=int(os.getenv("PAGE_TEXT_LIMIT", "12000")),
        chats_db_path=os.getenv("CHATS_DB_PATH", "chats.db"),
```

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_db.py tests/test_config.py -v`
Expected: PASS (тесты db + config зелёные)

- [ ] **Step 6: Commit**

```bash
git add backend/app/db.py backend/app/config.py backend/tests/test_db.py
git commit -m "feat(backend): SQLite-слой чатов + chats_db_path"
```

---

## Task 2: API чатов (CRUD + messages) + stateless агент

**Files:**
- Modify: `backend/app/agent.py` (убрать checkpointer)
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py` (полная замена)
- Modify: `backend/tests/test_agent.py` (checkpointer убран)
- Test: `backend/tests/test_chats_api.py`

**Interfaces:**
- Consumes: `app.db.*`, `app.agent.build_agent`, `app.agent.build_page_system_message`, `app.config.settings`.
- Produces: эндпоинты `/health`, `GET/POST /chats`, `GET/PATCH/DELETE /chats/{id}`, `POST /chats/{id}/messages`. `build_agent` теперь без checkpointer (`g.checkpointer is None`).

- [ ] **Step 1: Сделать агент stateless** — `backend/app/agent.py`

Удалить импорт и использование `MemorySaver`. Заменить тело `build_agent`:
```python
def build_agent(settings: Settings) -> CompiledStateGraph:
    model = ChatOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        temperature=0,
    )
    return create_agent(model, tools=[exa_search])
```
И удалить строку `from langgraph.checkpoint.memory import MemorySaver`.

- [ ] **Step 2: Обновить тест агента** — `backend/tests/test_agent.py`

Заменить тело `test_build_agent_has_checkpointer` (агент теперь без checkpointer) на проверку, что граф строится и запускаем:
```python
def test_build_agent_is_runnable(monkeypatch):
    from app.config import Settings
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    fake = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
    monkeypatch.setattr(agent, "ChatOpenAI", lambda **k: fake)
    s = Settings("k", "https://openrouter.ai/api/v1", "m", "e", 12000)
    g = agent.build_agent(s)
    assert hasattr(g, "invoke")
    assert g.checkpointer is None
```
(Тест `test_build_page_system_message_truncates` оставить без изменений.)

- [ ] **Step 3: Схемы** — `backend/app/schemas.py` (полная замена)

```python
from pydantic import BaseModel


class Page(BaseModel):
    title: str = ""
    url: str = ""
    text: str = ""


class CreateChatRequest(BaseModel):
    page_url: str
    page_title: str = ""


class MessageRequest(BaseModel):
    question: str
    page: Page


class UpdateChatRequest(BaseModel):
    pinned: bool | None = None
    title: str | None = None
    tags: list[str] | None = None


class ChatResponse(BaseModel):
    answer: str
```

- [ ] **Step 4: Написать падающий тест** — `backend/tests/test_chats_api.py`

```python
from fastapi.testclient import TestClient


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    from app import main as main_module
    main_module.config.settings.chats_db_path = str(tmp_path / "t.db")
    return main_module, TestClient(main_module.app)


def test_chat_crud_and_pin_tags(monkeypatch, tmp_path):
    _, client = _client(monkeypatch, tmp_path)
    created = client.post("/chats", json={"page_url": "https://e.test/p?x=1", "page_title": "T"}).json()
    cid = created["id"]
    assert created["page_url"] == "https://e.test/p"

    listed = client.get("/chats", params={"url": "https://e.test/p#h"}).json()
    assert any(c["id"] == cid for c in listed["page"])
    assert any(c["id"] == cid for c in listed["all"])

    patched = client.patch(f"/chats/{cid}", json={"pinned": True, "tags": ["work"]}).json()
    assert patched["pinned"] is True and patched["tags"] == ["work"]

    assert client.delete(f"/chats/{cid}").json() == {"ok": True}
    assert client.get(f"/chats/{cid}").status_code == 404


def test_messages_uses_db_history_and_persists(monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage
    main_module, client = _client(monkeypatch, tmp_path)

    calls = []

    class _FakeAgent:
        def invoke(self, payload, *a, **k):
            calls.append([type(m).__name__ for m in payload["messages"]])
            return {"messages": [AIMessage(content="ответ")]}

    monkeypatch.setattr(main_module, "agent", _FakeAgent())

    cid = client.post("/chats", json={"page_url": "https://e.test/p", "page_title": "T"}).json()["id"]
    page = {"title": "T", "url": "https://e.test/p", "text": "контент"}

    r1 = client.post(f"/chats/{cid}/messages", json={"question": "первый", "page": page})
    assert r1.json()["answer"] == "ответ"
    # 1-й ход: System + Human
    assert calls[0] == ["SystemMessage", "HumanMessage"]

    client.post(f"/chats/{cid}/messages", json={"question": "второй", "page": page})
    # 2-й ход: System + история (Human+AI) + новый Human
    assert calls[1] == ["SystemMessage", "HumanMessage", "AIMessage", "HumanMessage"]

    full = client.get(f"/chats/{cid}").json()
    assert [m["role"] for m in full["messages"]] == ["user", "assistant", "user", "assistant"]
    assert full["chat"]["title"] == "первый"  # заголовок из первого вопроса
```

- [ ] **Step 5: Запустить — убедиться, что падает**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_chats_api.py -v`
Expected: FAIL (эндпоинтов `/chats` ещё нет)

- [ ] **Step 6: Реализация** — `backend/app/main.py` (полная замена)

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app import config, db
from app.config import load_settings
from app.agent import build_agent, build_page_system_message
from app.schemas import (
    CreateChatRequest,
    MessageRequest,
    UpdateChatRequest,
    ChatResponse,
)

config.settings = load_settings()
agent = build_agent(config.settings)

app = FastAPI(title="AI Page Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _conn():
    return db.connect(config.settings.chats_db_path)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/chats")
def list_chats(url: str | None = None):
    conn = _conn()
    try:
        return db.list_chats(conn, url)
    finally:
        conn.close()


@app.post("/chats")
def create_chat(req: CreateChatRequest):
    conn = _conn()
    try:
        return db.create_chat(conn, req.page_url, req.page_title)
    finally:
        conn.close()


@app.get("/chats/{chat_id}")
def get_chat(chat_id: str):
    conn = _conn()
    try:
        meta = db.get_chat_meta(conn, chat_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="chat not found")
        return {"chat": meta, "messages": db.get_messages(conn, chat_id)}
    finally:
        conn.close()


@app.patch("/chats/{chat_id}")
def patch_chat(chat_id: str, req: UpdateChatRequest):
    conn = _conn()
    try:
        if db.get_chat_meta(conn, chat_id) is None:
            raise HTTPException(status_code=404, detail="chat not found")
        return db.update_chat(conn, chat_id, pinned=req.pinned, title=req.title, tags=req.tags)
    finally:
        conn.close()


@app.delete("/chats/{chat_id}")
def delete_chat(chat_id: str):
    conn = _conn()
    try:
        db.delete_chat(conn, chat_id)
        return {"ok": True}
    finally:
        conn.close()


@app.post("/chats/{chat_id}/messages", response_model=ChatResponse)
def post_message(chat_id: str, req: MessageRequest):
    conn = _conn()
    try:
        meta = db.get_chat_meta(conn, chat_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="chat not found")

        system_text = build_page_system_message(
            req.page.title, req.page.url, req.page.text, config.settings.page_text_limit
        )
        msgs = [SystemMessage(content=system_text)]
        for m in db.get_messages(conn, chat_id):
            if m["role"] == "user":
                msgs.append(HumanMessage(content=m["content"]))
            else:
                msgs.append(AIMessage(content=m["content"]))
        msgs.append(HumanMessage(content=req.question))

        db.add_message(conn, chat_id, "user", req.question)
        if not meta["title"]:
            db.update_chat(conn, chat_id, title=req.question[:60])

        try:
            result = agent.invoke({"messages": msgs})
            answer = result["messages"][-1].content
        except Exception as exc:  # noqa: BLE001
            answer = f"Ошибка при обращении к агенту: {exc}"

        db.add_message(conn, chat_id, "assistant", answer)
        return ChatResponse(answer=answer)
    finally:
        conn.close()
```

- [ ] **Step 7: Запустить весь набор бэкенда**

Run: `cd backend && source .venv/bin/activate && python -m pytest -v`
Expected: PASS (db + config + agent + chats_api; старый test_api.py удалён — см. ниже)

- [ ] **Step 8: Удалить устаревший тест старого /chat**

Старый `backend/tests/test_api.py` тестировал удалённый `POST /chat`. Удалить его:
```bash
git rm backend/tests/test_api.py
```
Run: `cd backend && source .venv/bin/activate && python -m pytest -q`
Expected: PASS, вывод чистый.

- [ ] **Step 9: Commit**

```bash
git add backend/app/agent.py backend/app/schemas.py backend/app/main.py backend/tests/test_agent.py backend/tests/test_chats_api.py
git commit -m "feat(backend): API чатов (CRUD + messages), stateless агент"
```

---

## Task 3: Клиент API чатов (chatsApi.ts)

**Files:**
- Create: `extension/src/lib/chatsApi.ts`

**Interfaces:**
- Produces (`@/lib/chatsApi`):
  - типы `ChatMeta`, `Message`, `PagePayload`
  - `listChats(url: string): Promise<{ page: ChatMeta[]; all: ChatMeta[] }>`
  - `createChat(page_url: string, page_title: string): Promise<ChatMeta>`
  - `getChat(id: string): Promise<{ chat: ChatMeta; messages: Message[] }>`
  - `sendMessage(id: string, question: string, page: PagePayload): Promise<{ answer: string }>`
  - `updateChat(id: string, patch: { pinned?: boolean; title?: string; tags?: string[] }): Promise<ChatMeta>`
  - `deleteChat(id: string): Promise<void>`

- [ ] **Step 1: Реализация** — `extension/src/lib/chatsApi.ts`

```ts
const BASE = "http://localhost:8000";

export interface ChatMeta {
  id: string;
  page_url: string;
  page_title: string;
  title: string;
  pinned: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
  preview: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface PagePayload {
  title: string;
  url: string;
  text: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new Error("Не удалось подключиться к серверу. Запущен ли backend на :8000?");
  }
  if (!resp.ok) throw new Error(`Сервер вернул ошибку ${resp.status}`);
  return (await resp.json()) as T;
}

export function listChats(url: string): Promise<{ page: ChatMeta[]; all: ChatMeta[] }> {
  return req(`/chats?url=${encodeURIComponent(url)}`);
}

export function createChat(page_url: string, page_title: string): Promise<ChatMeta> {
  return req("/chats", { method: "POST", body: JSON.stringify({ page_url, page_title }) });
}

export function getChat(id: string): Promise<{ chat: ChatMeta; messages: Message[] }> {
  return req(`/chats/${id}`);
}

export function sendMessage(
  id: string,
  question: string,
  page: PagePayload
): Promise<{ answer: string }> {
  return req(`/chats/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ question, page }),
  });
}

export function updateChat(
  id: string,
  patch: { pinned?: boolean; title?: string; tags?: string[] }
): Promise<ChatMeta> {
  return req(`/chats/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export async function deleteChat(id: string): Promise<void> {
  await req(`/chats/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Проверка типов**

Run: `cd extension && npx tsc -b`
Expected: без ошибок типов.

- [ ] **Step 3: Commit**

```bash
git add extension/src/lib/chatsApi.ts
git commit -m "feat(extension): клиент API чатов"
```

---

## Task 4: UI — App + Sidebar + ChatPanel (рефактор)

**Files:**
- Create: `extension/src/App.tsx`
- Create: `extension/src/Sidebar.tsx`
- Modify: `extension/src/ChatPanel.tsx` (презентационный, props)
- Modify: `extension/src/main.tsx`

**Interfaces:**
- Consumes: `@/lib/chatsApi`, `@/lib/page`, `@/lib/markdown`, shadcn `Button/Textarea/ScrollArea`.
- Produces: `App` (default-рендерится из main.tsx); `ChatPanel` экспортирует тип `DisplayMsg`.

- [ ] **Step 1: ChatPanel.tsx (полная замена — презентационный)**

```tsx
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { renderMarkdown } from "@/lib/markdown";
import type { ChatMeta } from "@/lib/chatsApi";

export interface DisplayMsg {
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
}

interface ChatPanelProps {
  chat: ChatMeta | null;
  messages: DisplayMsg[];
  loading: boolean;
  onSend: (question: string) => void;
  onToggleSidebar: () => void;
  onAddTag: (tag: string) => void;
  onRemoveTag: (tag: string) => void;
}

export function ChatPanel({
  chat,
  messages,
  loading,
  onSend,
  onToggleSidebar,
  onAddTag,
  onRemoveTag,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [tagInput, setTagInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function submit() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    onSend(q);
  }
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }
  function commitTag() {
    const t = tagInput.trim();
    if (!t) return;
    setTagInput("");
    onAddTag(t);
  }

  return (
    <div className="flex h-full w-full flex-col bg-background text-foreground">
      <header className="flex items-center gap-2 border-b px-3 py-2">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onToggleSidebar}>
          ☰
        </Button>
        <span className="flex-1 truncate text-sm font-semibold">
          {chat?.title || "Новый чат"}
        </span>
      </header>

      {chat && (
        <div className="flex flex-wrap items-center gap-1 border-b px-3 py-2">
          {chat.tags.map((t) => (
            <span
              key={t}
              className="flex items-center gap-1 rounded bg-secondary px-1.5 py-0.5 text-[10px] text-secondary-foreground"
            >
              #{t}
              <button onClick={() => onRemoveTag(t)} className="opacity-70 hover:opacity-100">
                ✕
              </button>
            </span>
          ))}
          <input
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commitTag();
              }
            }}
            placeholder="+ тег"
            className="w-16 bg-transparent text-[11px] outline-none placeholder:text-muted-foreground"
          />
        </div>
      )}

      <ScrollArea className="flex-1">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Спросите что-нибудь об этой странице. Например: «О чём эта страница?»
              или «Найди свежие новости по теме».
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
            onClick={submit}
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

- [ ] **Step 2: Sidebar.tsx**

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatMeta } from "@/lib/chatsApi";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  pageChats: ChatMeta[];
  allChats: ChatMeta[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onTogglePin: (chat: ChatMeta) => void;
  onDelete: (chat: ChatMeta) => void;
}

export function Sidebar({
  open,
  onClose,
  pageChats,
  allChats,
  currentId,
  onSelect,
  onNew,
  onTogglePin,
  onDelete,
}: SidebarProps) {
  const [tagFilter, setTagFilter] = useState<string | null>(null);

  const allTags = Array.from(new Set(allChats.flatMap((c) => c.tags))).sort();
  const applyFilter = (list: ChatMeta[]) =>
    tagFilter ? list.filter((c) => c.tags.includes(tagFilter)) : list;

  function Row({ c }: { c: ChatMeta }) {
    return (
      <div
        className={
          "group flex cursor-pointer items-start gap-2 rounded-lg px-2 py-2 text-sm hover:bg-accent " +
          (c.id === currentId ? "bg-accent" : "")
        }
        onClick={() => onSelect(c.id)}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1">
            {c.pinned && <span>📌</span>}
            <span className="truncate font-medium">{c.title || "Без названия"}</span>
          </div>
          {c.preview && (
            <div className="truncate text-xs text-muted-foreground">{c.preview}</div>
          )}
          {c.tags.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {c.tags.map((t) => (
                <span
                  key={t}
                  className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-secondary-foreground"
                >
                  #{t}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex shrink-0 gap-1 opacity-0 group-hover:opacity-100">
          <button
            title={c.pinned ? "Открепить" : "Закрепить"}
            onClick={(e) => {
              e.stopPropagation();
              onTogglePin(c);
            }}
          >
            📌
          </button>
          <button
            title="Удалить"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(c);
            }}
          >
            🗑
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      {open && (
        <div className="absolute inset-0 z-10 bg-black/40" onClick={onClose} />
      )}
      <aside
        className={
          "absolute left-0 top-0 z-20 flex h-full w-72 flex-col border-r bg-background transition-transform " +
          (open ? "translate-x-0" : "-translate-x-full")
        }
      >
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-sm font-semibold">Чаты</span>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ✕
          </Button>
        </div>
        <div className="px-3 py-2">
          <Button className="w-full" size="sm" onClick={onNew}>
            ＋ Новый чат
          </Button>
        </div>
        {allTags.length > 0 && (
          <div className="flex flex-wrap gap-1 px-3 pb-2">
            {allTags.map((t) => (
              <button
                key={t}
                onClick={() => setTagFilter((f) => (f === t ? null : t))}
                className={
                  "rounded px-1.5 py-0.5 text-[10px] " +
                  (tagFilter === t
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground")
                }
              >
                #{t}
              </button>
            ))}
          </div>
        )}
        <ScrollArea className="flex-1">
          <div className="px-2 pb-4">
            <div className="px-2 pt-2 text-xs font-semibold text-muted-foreground">
              Эта страница
            </div>
            {applyFilter(pageChats).length === 0 && (
              <div className="px-2 py-1 text-xs text-muted-foreground">Нет чатов</div>
            )}
            {applyFilter(pageChats).map((c) => (
              <Row key={c.id} c={c} />
            ))}
            <div className="px-2 pt-3 text-xs font-semibold text-muted-foreground">
              Все чаты
            </div>
            {applyFilter(allChats).map((c) => (
              <Row key={c.id} c={c} />
            ))}
          </div>
        </ScrollArea>
      </aside>
    </>
  );
}
```

- [ ] **Step 3: App.tsx**

```tsx
import { useCallback, useEffect, useState } from "react";
import { ChatPanel, type DisplayMsg } from "@/ChatPanel";
import { Sidebar } from "@/Sidebar";
import { getPageContent, type PageContent } from "@/lib/page";
import * as api from "@/lib/chatsApi";
import type { ChatMeta } from "@/lib/chatsApi";

export function App() {
  const [page, setPage] = useState<PageContent | null>(null);
  const [pageChats, setPageChats] = useState<ChatMeta[]>([]);
  const [allChats, setAllChats] = useState<ChatMeta[]>([]);
  const [chat, setChat] = useState<ChatMeta | null>(null);
  const [messages, setMessages] = useState<DisplayMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const refresh = useCallback(async (url: string) => {
    const data = await api.listChats(url);
    setPageChats(data.page);
    setAllChats(data.all);
    return data;
  }, []);

  async function selectChat(id: string) {
    const { chat, messages } = await api.getChat(id);
    setChat(chat);
    setMessages(messages.map((m) => ({ role: m.role, content: m.content })));
    setSidebarOpen(false);
  }

  function newChat() {
    setChat(null);
    setMessages([]);
    setSidebarOpen(false);
  }

  useEffect(() => {
    (async () => {
      const p = await getPageContent();
      setPage(p);
      try {
        const data = await refresh(p.url);
        if (data.page.length > 0) {
          const { chat, messages } = await api.getChat(data.page[0].id);
          setChat(chat);
          setMessages(messages.map((m) => ({ role: m.role, content: m.content })));
        }
      } catch {
        setMessages([
          {
            role: "assistant",
            content: "⚠️ Бэкенд недоступен. Запустите сервер на :8000.",
            isError: true,
          },
        ]);
      }
    })();
  }, [refresh]);

  async function send(question: string) {
    if (!page) return;
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    try {
      let active = chat;
      if (!active) {
        active = await api.createChat(page.url, page.title);
        setChat(active);
      }
      const { answer } = await api.sendMessage(active.id, question, {
        title: page.title,
        url: page.url,
        text: page.text,
      });
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
      const fresh = await api.getChat(active.id);
      setChat(fresh.chat);
      await refresh(page.url);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `⚠️ ${(e as Error).message}`, isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function setTags(tags: string[]) {
    if (!chat) return;
    const updated = await api.updateChat(chat.id, { tags });
    setChat(updated);
    if (page) await refresh(page.url);
  }
  const addTag = (t: string) =>
    setTags(Array.from(new Set([...(chat?.tags ?? []), t])));
  const removeTag = (t: string) => setTags((chat?.tags ?? []).filter((x) => x !== t));

  async function togglePin(c: ChatMeta) {
    const updated = await api.updateChat(c.id, { pinned: !c.pinned });
    if (chat?.id === c.id) setChat(updated);
    if (page) await refresh(page.url);
  }

  async function remove(c: ChatMeta) {
    if (!confirm(`Удалить чат «${c.title || "Без названия"}»?`)) return;
    await api.deleteChat(c.id);
    if (chat?.id === c.id) newChat();
    if (page) await refresh(page.url);
  }

  return (
    <div className="relative h-screen w-full overflow-hidden">
      <ChatPanel
        chat={chat}
        messages={messages}
        loading={loading}
        onSend={send}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        onAddTag={addTag}
        onRemoveTag={removeTag}
      />
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        pageChats={pageChats}
        allChats={allChats}
        currentId={chat?.id ?? null}
        onSelect={selectChat}
        onNew={newChat}
        onTogglePin={togglePin}
        onDelete={remove}
      />
    </div>
  );
}
```

- [ ] **Step 4: main.tsx (рендерить App)**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "@/App";
import "@/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 5: Сборка**

Run: `cd extension && npm run build`
Expected: `tsc -b` 0 ошибок, vite build успешен, `dist/` создан.

- [ ] **Step 6: Commit**

```bash
git add extension/src/App.tsx extension/src/Sidebar.tsx extension/src/ChatPanel.tsx extension/src/main.tsx
git commit -m "feat(extension): UI истории чатов (App + Sidebar + ChatPanel)"
```

---

## Task 5: README + сквозная проверка

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Дополнить раздел «Использование» в README.md**

После существующего списка примеров добавить абзац:
```markdown
### История чатов

Кнопка **☰** в шапке открывает список чатов. Чаты сохраняются на бэкенде
(SQLite, `backend/chats.db`) и группируются по странице (URL без параметров):
секции «Эта страница» и «Все чаты». Чат можно **закрепить** (📌 — наверху списка),
пометить **тегами** (поле «+ тег» в шапке чата) и фильтровать список по тегу.
Кнопка «＋ Новый чат» создаёт новый чат для текущей страницы.
```

- [ ] **Step 2: Полный прогон тестов бэкенда**

Run: `cd backend && source .venv/bin/activate && python -m pytest -q`
Expected: все тесты зелёные, вывод чистый.

- [ ] **Step 3: Сборка расширения**

Run: `cd extension && npm run build`
Expected: успешная сборка, `dist/manifest.json` присутствует.

- [ ] **Step 4: Ручная проверка №1 — история и переключение**

Запустить бэкенд, перезагрузить расширение, открыть панель на странице. Задать вопрос
(создастся чат), затем «＋ Новый чат», задать другой. Открыть ☰.
Expected: в «Эта страница» два чата с заголовками из первых вопросов; переключение между ними показывает их историю.

- [ ] **Step 5: Ручная проверка №2 — закреп и теги**

Закрепить один чат (📌), добавить тег в шапке активного чата, кликнуть тег в сайдбаре.
Expected: закреплённый — наверху; список фильтруется по тегу; повторный клик по тегу сбрасывает фильтр.

- [ ] **Step 6: Ручная проверка №3 — память и удаление**

В существующем чате задать уточняющий вопрос (агент помнит контекст из БД). Удалить чат (🗑, с подтверждением).
Expected: агент учитывает прошлые сообщения; удалённый чат исчезает из списка.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: README — история чатов"
```

---

## Self-Review (выполнено при написании плана)

- **Покрытие спека:** SQLite-слой + нормализация URL (Task 1); CRUD + messages + stateless агент (Task 2); клиент API (Task 3); UI сайдбар/закреп/теги/фильтр + история (Task 4); README + ручная проверка (Task 5). Все разделы спека покрыты.
- **Плейсхолдеры:** отсутствуют — везде реальный код/команды.
- **Согласованность типов:** `ChatMeta`/`Message` JSON-ключи (snake_case) совпадают между бэкендом (Task 1/2) и `chatsApi.ts` (Task 3); `DisplayMsg` экспортируется из `ChatPanel` и импортируется в `App` (Task 4); сигнатуры `chatsApi` (listChats/createChat/getChat/sendMessage/updateChat/deleteChat) одинаковы в Task 3 и Task 4; `build_agent` без checkpointer согласован между agent.py и тестом (Task 2).
- **Замечание по поведению:** ответ-ошибка агента сохраняется в БД как assistant-сообщение (попадёт в историю следующего хода) — осознанное упрощение для демо, отмечено для финального ревью.
