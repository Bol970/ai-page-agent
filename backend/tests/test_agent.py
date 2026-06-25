from app import agent


def test_build_page_system_message_truncates():
    msg = agent.build_page_system_message("T", "https://x.test", "A" * 100, limit=10)
    assert "T" in msg
    assert "https://x.test" in msg
    assert "A" * 10 in msg
    assert "A" * 11 not in msg


def test_build_agent_has_checkpointer(monkeypatch):
    from app.config import Settings
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    fake = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
    monkeypatch.setattr(agent, "ChatOpenAI", lambda **k: fake)
    s = Settings("k", "https://openrouter.ai/api/v1", "m", "e", 12000)
    g = agent.build_agent(s)
    assert g.checkpointer is not None
    assert hasattr(g, "invoke")  # это пригодный к запуску скомпилированный граф
