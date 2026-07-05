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


# --- calculator ---

def test_calculator_basic():
    assert "= 6" in tools.calculator.invoke({"expression": "2 + 2 * 2"})


def test_calculator_power_and_parens():
    assert "= 1048576" in tools.calculator.invoke({"expression": "2**20"})
    assert "= 9" in tools.calculator.invoke({"expression": "(1 + 2) * 3"})


def test_calculator_division_by_zero():
    assert "деление на ноль" in tools.calculator.invoke({"expression": "1/0"})


def test_calculator_rejects_evil_expressions():
    for evil in ("__import__('os')", "abs(-1)", "x + 1", "2**999999", "'a'*3"):
        out = tools.calculator.invoke({"expression": evil})
        assert "Не удалось вычислить" in out, evil


# --- current_datetime ---

def test_current_datetime_mentions_current_year():
    from datetime import datetime
    out = tools.current_datetime.invoke({})
    assert str(datetime.now().year) in out
