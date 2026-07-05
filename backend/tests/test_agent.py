from app import agent


def test_build_page_system_message_truncates():
    msg = agent.build_page_system_message("T", "https://x.test", "A" * 100, limit=10)
    assert "T" in msg
    assert "https://x.test" in msg
    assert "A" * 10 in msg
    assert "A" * 11 not in msg


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


def test_agent_has_seven_tools():
    names = {t.name for t in agent.TOOLS}
    assert names == {
        "exa_search",
        "page_to_markdown",
        "extract_links",
        "fetch_url",
        "calculator",
        "current_datetime",
        "text_to_speech",
    }


def test_system_base_mentions_tools():
    for name in ("exa_search", "page_to_markdown", "extract_links",
                 "fetch_url", "calculator", "current_datetime", "text_to_speech"):
        assert name in agent.SYSTEM_BASE
