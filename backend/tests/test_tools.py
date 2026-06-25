from app import tools


class _FakeResult:
    def __init__(self, title, url, text):
        self.title = title
        self.url = url
        self.text = text


class _FakeResponse:
    def __init__(self, results):
        self.results = results


class _FakeExa:
    def __init__(self, api_key=None):
        self.api_key = api_key

    def search_and_contents(self, query, **kwargs):
        return _FakeResponse([
            _FakeResult("Заголовок 1", "https://a.test", "Текст один " * 50),
            _FakeResult("Заголовок 2", "https://b.test", "Текст два"),
        ])


def test_exa_search_formats_results(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(tools, "Exa", _FakeExa)
    out = tools.exa_search.invoke({"query": "погода"})
    assert "Заголовок 1" in out
    assert "https://a.test" in out
    assert "Заголовок 2" in out
