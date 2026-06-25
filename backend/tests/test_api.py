from fastapi.testclient import TestClient


def test_chat_returns_answer(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")

    from langchain_core.messages import AIMessage
    from app import main as main_module

    class _FakeAgent:
        def invoke(self, payload, config):
            # система+вопрос на первом ходу
            assert config["configurable"]["thread_id"] == "tab-1"
            return {"messages": [AIMessage(content="Это страница про котов.")]}

    monkeypatch.setattr(main_module, "agent", _FakeAgent())

    client = TestClient(main_module.app)
    resp = client.post("/chat", json={
        "thread_id": "tab-1",
        "question": "О чём страница?",
        "page": {"title": "Коты", "url": "https://cats.test", "text": "Про котов"},
    })
    assert resp.status_code == 200
    assert resp.json()["answer"] == "Это страница про котов."


def test_health(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    from app import main as main_module
    client = TestClient(main_module.app)
    assert client.get("/health").json() == {"status": "ok"}
