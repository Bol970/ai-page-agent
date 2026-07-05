import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app import config, db
from app.config import load_settings, apply_proxy
from app.agent import build_agent, build_page_system_message
from app.schemas import (
    CreateChatRequest,
    MessageRequest,
    UpdateChatRequest,
    ChatResponse,
)

config.settings = load_settings()
apply_proxy(config.settings.proxy_url)  # до создания клиентов, чтобы они подхватили прокси
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


_AUDIO_NAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.mp3$"
)


@app.get("/audio/{filename}")
def get_audio(filename: str):
    # только имена, которые генерирует text_to_speech — никакого path traversal
    if not _AUDIO_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="not found")
    path = os.path.join(config.settings.audio_dir, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="audio/mpeg")


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
