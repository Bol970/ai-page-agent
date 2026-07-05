import ipaddress
import socket

import pytest

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


# --- инструменты страницы (HTML из page_context) ---

from app import page_context

PAGE_HTML = """
<html><body>
  <script>var secret = 1;</script>
  <style>.a { color: red }</style>
  <h1>Заголовок</h1>
  <p>Абзац с <a href="/rel">относительной ссылкой</a> и
     <a href="https://abs.test/page">абсолютной</a>.</p>
  <a href="https://abs.test/page">дубль</a>
  <a href="mailto:a@b.c">почта</a>
</body></html>
"""


def _with_page(html):
    return page_context.set_page("T", "https://site.test/dir/page", html)


def test_page_to_markdown_converts_and_strips_noise():
    token = _with_page(PAGE_HTML)
    try:
        out = tools.page_to_markdown.invoke({})
    finally:
        page_context.reset_page(token)
    assert "Заголовок" in out
    assert "Абзац" in out
    assert "var secret" not in out
    assert "color: red" not in out


def test_page_to_markdown_without_context():
    assert "недоступно" in tools.page_to_markdown.invoke({})


def test_page_to_markdown_respects_limit():
    token = _with_page("<p>" + "ы" * 50000 + "</p>")
    try:
        out = tools.page_to_markdown.invoke({})
    finally:
        page_context.reset_page(token)
    assert len(out) <= tools.PAGE_MD_LIMIT


def test_extract_links_absolute_dedup_and_filters():
    token = _with_page(PAGE_HTML)
    try:
        out = tools.extract_links.invoke({})
    finally:
        page_context.reset_page(token)
    assert "https://site.test/rel" in out           # относительная стала абсолютной
    assert out.count("https://abs.test/page") == 1  # дедупликация
    assert "mailto:" not in out                     # не-http отфильтрованы


def test_extract_links_without_context():
    assert "недоступно" in tools.extract_links.invoke({})


def test_extract_links_survives_malformed_href():
    html = '<a href="http://[bad">битая</a><a href="https://ok.test/a">ок</a>'
    token = _with_page(html)
    try:
        out = tools.extract_links.invoke({})
    finally:
        page_context.reset_page(token)
    assert "https://ok.test/a" in out
    assert "http://[bad" not in out


# --- fetch_url (httpx мокается, сети нет) ---

@pytest.fixture(autouse=True)
def _no_real_dns(monkeypatch):
    """Тесты без сети: числовые IP «резолвятся» сами в себя, имена — не резолвятся."""
    def fake_getaddrinfo(host, *args, **kwargs):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise socket.gaierror(f"тестовый резолвер: {host}")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, 0))]

    monkeypatch.setattr(tools.socket, "getaddrinfo", fake_getaddrinfo)


class _FakeHttpxResponse:
    def __init__(self, content=b"", ctype="text/html; charset=utf-8"):
        self.content = content
        self.headers = {"content-type": ctype}
        self.encoding = "utf-8"
        self.status_code = 200

    def raise_for_status(self):
        pass


def test_fetch_url_html_to_markdown(monkeypatch):
    resp = _FakeHttpxResponse(b"<h1>Hi</h1><script>var s=1;</script>")
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: resp)
    out = tools.fetch_url.invoke({"url": "https://e.test"})
    assert "Hi" in out
    assert "var s" not in out


def test_fetch_url_plain_text_passthrough(monkeypatch):
    resp = _FakeHttpxResponse(b"plain body", ctype="text/plain")
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: resp)
    assert "plain body" in tools.fetch_url.invoke({"url": "https://e.test"})


def test_fetch_url_rejects_non_http():
    out = tools.fetch_url.invoke({"url": "ftp://e.test"})
    assert "http" in out


def test_fetch_url_network_error_is_text(monkeypatch):
    def boom(*a, **k):
        raise tools.httpx.ConnectError("no route")

    monkeypatch.setattr(tools.httpx, "get", boom)
    out = tools.fetch_url.invoke({"url": "https://e.test"})
    assert "Не удалось скачать" in out


def test_fetch_url_unknown_encoding_survives(monkeypatch):
    resp = _FakeHttpxResponse(b"<p>ok</p>")
    resp.encoding = "koi8-super-charset"  # неизвестная кодировка от сервера
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: resp)
    out = tools.fetch_url.invoke({"url": "https://e.test"})
    assert "ok" in out


def test_fetch_url_truncates_to_limit(monkeypatch):
    resp = _FakeHttpxResponse(("x" * 20000).encode(), ctype="text/plain")
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: resp)
    out = tools.fetch_url.invoke({"url": "https://e.test"})
    assert len(out) <= tools.FETCH_LIMIT


def test_fetch_url_blocks_private_hosts(monkeypatch):
    called = []
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: called.append(1))
    out = tools.fetch_url.invoke({"url": "http://127.0.0.1:8000/health"})
    assert "внутренн" in out
    assert not called  # до сетевого запроса дело не дошло


def test_fetch_url_blocks_redirect_to_private_host(monkeypatch):
    resp = _FakeHttpxResponse(b"")
    resp.headers["location"] = "http://192.168.0.1/admin"
    resp.status_code = 302
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: resp)
    out = tools.fetch_url.invoke({"url": "https://e.test"})
    assert "внутренн" in out


def test_fetch_url_location_without_redirect_status_returns_body(monkeypatch):
    resp = _FakeHttpxResponse(b"real body", ctype="text/plain")
    resp.headers["location"] = "https://other.test/x"  # 200 + Location — не редирект
    monkeypatch.setattr(tools.httpx, "get", lambda *a, **k: resp)
    out = tools.fetch_url.invoke({"url": "https://e.test"})
    assert "real body" in out


# --- text_to_speech (edge_tts мокается) ---

def _tts_settings(tmp_path):
    from app import config
    from app.config import Settings

    config.settings = Settings("k", "u", "m", "e", 100, audio_dir=str(tmp_path))
    return config


class _FakeCommunicate:
    def __init__(self, text, voice):
        self.text = text
        self.voice = voice

    async def save(self, path):
        with open(path, "wb") as f:
            f.write(b"mp3-bytes")


def test_text_to_speech_saves_file_and_returns_link(monkeypatch, tmp_path):
    _tts_settings(tmp_path)
    monkeypatch.setattr(tools.edge_tts, "Communicate", _FakeCommunicate)
    out = tools.text_to_speech.invoke({"text": "привет"})
    assert "http://localhost:8000/audio/" in out
    files = list(tmp_path.glob("*.mp3"))
    assert len(files) == 1
    assert files[0].read_bytes() == b"mp3-bytes"
    assert files[0].name in out


def test_text_to_speech_error_is_text(monkeypatch, tmp_path):
    _tts_settings(tmp_path)

    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("edge-tts недоступен")

    monkeypatch.setattr(tools.edge_tts, "Communicate", _Boom)
    out = tools.text_to_speech.invoke({"text": "привет"})
    assert "Озвучка сейчас недоступна" in out
    assert list(tmp_path.glob("*.mp3")) == []
