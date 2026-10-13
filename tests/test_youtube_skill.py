import importlib.util
import json
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "yt", Path(__file__).parent.parent / "hermes/skills/media/youtube-download/scripts/yt.py")
yt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(yt)

BLOCKED = RuntimeError("ERROR: [youtube] x: Sign in to confirm you're not a bot")


def run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["yt.py", *argv])
    yt.main()
    return capsys.readouterr().out


def test_video_id_and_parse():
    for url in ("https://youtu.be/aC9p1eld0tA", "https://www.youtube.com/watch?v=aC9p1eld0tA&t=5",
                "https://youtube.com/shorts/aC9p1eld0tA"):
        assert yt.video_id(url) == "aC9p1eld0tA"
    assert yt.parse_timestamped("Вот:\n**[00:05]** Привет\nещё\n[1:02:03] Позже") == [(5, "Привет ещё"), (3723, "Позже")]


def test_info_falls_back_to_youtube_data_api(monkeypatch, capsys):
    def blocked(url):
        raise BLOCKED

    def fake_google(url, key, body=None, timeout=60):
        assert "youtube/v3/videos" in url and key == "yt-key"
        return {"items": [{"snippet": {"title": "Выпуск", "publishedAt": "2026-10-09T10:00:00Z",
                                       "channelTitle": "ProdAdvice", "description": "ссылки"},
                           "contentDetails": {"duration": "PT1H2M3S"}}]}

    monkeypatch.setenv("YOUTUBE_API_KEY", "yt-key")
    monkeypatch.setattr(yt, "info_ytdlp", blocked)
    monkeypatch.setattr(yt, "_google", fake_google)
    info = json.loads(run(monkeypatch, capsys, "info", "https://youtu.be/aC9p1eld0tA"))
    assert (info["title"], info["upload_date"], info["duration_sec"]) == ("Выпуск", "20261009", 3723)


def test_transcript_falls_back_to_gemini(monkeypatch, capsys):
    def blocked(url, langs):
        raise BLOCKED

    def fake_google(url, key, body=None, timeout=60):
        assert "gemini-3.8-flash:generateContent" in url
        assert body["contents"][0]["parts"][0]["file_data"]["file_uri"].endswith("v=aC9p1eld0tA")
        return {"candidates": [{"content": {"parts": [{"text": "[00:05] Первая\n[01:10] Вторая"}]}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setattr(yt, "transcript_ytdlp", blocked)
    monkeypatch.setattr(yt, "_google", fake_google)
    assert run(monkeypatch, capsys, "transcript", "https://youtu.be/aC9p1eld0tA") == "[00:05] Первая\n[01:10] Вторая\n"


def test_fallback_without_key_explains(monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(yt, "transcript_ytdlp", lambda url, langs: (_ for _ in ()).throw(BLOCKED))
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        run(monkeypatch, capsys, "transcript", "https://youtu.be/aC9p1eld0tA")
