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
