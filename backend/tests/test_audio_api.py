import uuid

from fastapi.testclient import TestClient


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("EXA_API_KEY", "e")
    from app import main as main_module

    main_module.config.settings.audio_dir = str(tmp_path)
    return TestClient(main_module.app)


def test_audio_serves_existing_file(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    name = f"{uuid.uuid4()}.mp3"
    (tmp_path / name).write_bytes(b"mp3-bytes")
    resp = client.get(f"/audio/{name}")
    assert resp.status_code == 200
    assert resp.content == b"mp3-bytes"
    assert resp.headers["content-type"] == "audio/mpeg"


def test_audio_missing_file_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.get(f"/audio/{uuid.uuid4()}.mp3").status_code == 404


def test_audio_rejects_non_uuid_names(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    (tmp_path / "evil.mp3").write_bytes(b"x")
    assert client.get("/audio/evil.mp3").status_code == 404
    assert client.get("/audio/..%2Fsecret.mp3").status_code == 404
