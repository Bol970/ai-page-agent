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
