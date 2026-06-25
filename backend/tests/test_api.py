import pytest
from fastapi.testclient import TestClient


def test_chat_returns_answer(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")

    from langchain_core.messages import AIMessage
    from app import main as main_module

    monkeypatch.setattr(main_module, "_seen_threads", set())

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


def test_chat_second_turn_no_system_message(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")

    from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
    from app import main as main_module

    monkeypatch.setattr(main_module, "_seen_threads", set())

    calls = []

    class _RecordingAgent:
        def invoke(self, payload, config):
            calls.append([type(m).__name__ for m in payload["messages"]])
            return {"messages": [AIMessage(content="ok")]}

    monkeypatch.setattr(main_module, "agent", _RecordingAgent())

    client = TestClient(main_module.app)
    payload = {
        "thread_id": "tab-9",
        "question": "О чём страница?",
        "page": {"title": "Коты", "url": "https://cats.test", "text": "Про котов"},
    }

    client.post("/chat", json=payload)
    client.post("/chat", json={**payload, "question": "Расскажи подробнее?"})

    assert calls[0] == ["SystemMessage", "HumanMessage"]
    assert calls[1] == ["HumanMessage"]


def test_health(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    from app import main as main_module
    client = TestClient(main_module.app)
    assert client.get("/health").json() == {"status": "ok"}
