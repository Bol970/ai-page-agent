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
