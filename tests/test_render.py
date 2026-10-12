from ai_news.fetch import Source, parse_vtt_or_srt, video_id_from_url
from ai_news.render import CAPTION_LIMIT, telegram_caption, visible_len
from ai_news.schema import Digest, Issue, NewsItem, Reels, Scene


def make_issue(n_items: int, headline_len: int = 50, summary_len: int = 65) -> Issue:
    items = [
        NewsItem(emoji="🧠", headline="Н" * headline_len, summary="о" * summary_len,
                 timestamp_sec=60 * i, source_url="https://example.com/a?b=1&c=2" if i % 2 else "")
        for i in range(n_items)
    ]
    return Issue(
        digest=Digest(title="AI-новости недели", items=items, outro="Полный выпуск на YouTube",
                      hashtags=["AI", "#нейросети"]),
        image_prompt="p", image_text_overlay="t",
        reels=Reels(hook="h", scenes=[Scene(time="0–3 с", visual="v", on_screen_text="o", voiceover="vo")],
                    music="m", caption="c"),
        video_prompt="v", voiceover_full="vo",
    )


SRC = Source(video_id="rc1MGVebM-4", url="https://youtu.be/rc1MGVebM-4", upload_date="20261004")


def test_caption_fits_and_links():
    cap = telegram_caption(make_issue(8), SRC)
    assert visible_len(cap) <= CAPTION_LIMIT
    assert 'href="https://youtu.be/rc1MGVebM-4?t=0"' in cap      # нет источника -> таймкод ролика
    assert 'href="https://example.com/a?b=1&amp;c=2"' in cap      # источник экранирован
    assert "4 октября" in cap and "#AI #нейросети" in cap


def test_caption_drops_items_when_too_long():
    cap = telegram_caption(make_issue(12), SRC)
    assert visible_len(cap) <= CAPTION_LIMIT
    assert cap.count("🧠") < 12


def test_visible_len_ignores_markup_counts_utf16():
    assert visible_len('<a href="https://very.long/url"><b>AI</b></a> &amp;') == 4
    assert visible_len("⚡️") == 2 and visible_len("🧠") == 2


def test_parsers():
    assert video_id_from_url("https://youtu.be/rc1MGVebM-4") == "rc1MGVebM-4"
    assert video_id_from_url("https://www.youtube.com/watch?v=rc1MGVebM-4&t=5") == "rc1MGVebM-4"
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nпривет\n\n00:01:05.000 --> 00:01:07.000\n<c>мир</c>\n"
    assert parse_vtt_or_srt(vtt) == [(1, "привет"), (65, "мир")]


def test_generate_via_claude_cli(monkeypatch):
    import json
    import subprocess

    from ai_news import generate

    issue = make_issue(2)
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        out = {"type": "result", "is_error": False, "structured_output": issue.model_dump()}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(out), stderr="")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(generate.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    src = Source(video_id="x", url="https://youtu.be/x", transcript=[(5, "привет")])
    assert generate.generate_issue(src) == issue
    cmd, kw = calls[0]
    assert cmd[:2] == ["/usr/bin/claude", "-p"] and "--json-schema" in cmd
    assert "привет" in kw["input"]


def test_parse_timestamped_text():
    from ai_news.fetch import parse_timestamped_text

    raw = "Вот расшифровка:\n**[00:05]** Привет\n[1:02:03] Позже\nпродолжение"
    assert parse_timestamped_text(raw) == [(0, "Вот расшифровка: Привет"), (3723, "Позже продолжение")]


def test_fetch_google(monkeypatch):
    from ai_news import google_api

    def fake_request(url, key, body=None, timeout=60):
        if "youtube/v3" in url:
            assert key == "yt-key"
            return {"items": [{"snippet": {"title": "AI-новости", "description": "https://example.com",
                                           "publishedAt": "2026-10-04T10:00:00Z"}}]}
        assert key == "gem-key" and "rc1MGVebM-4" in body["contents"][0]["parts"][0]["file_data"]["file_uri"]
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "думаю", "thought": True}, {"text": "[00:05] Первая новость\n[00:40] Вторая"}]}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    monkeypatch.setenv("YOUTUBE_API_KEY", "yt-key")
    monkeypatch.setattr(google_api, "_request", fake_request)
    src = google_api.fetch_google("https://youtu.be/rc1MGVebM-4")
    assert (src.title, src.upload_date, src.description) == ("AI-новости", "20261004", "https://example.com")
    assert src.transcript == [(5, "Первая новость"), (40, "Вторая")]


def test_gemini_retries_and_falls_back(monkeypatch):
    import io
    import urllib.error

    from ai_news import google_api

    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:  # первая модель перегружена: 503, после повтора — пустой ответ
            raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO(b'{"error": "high demand"}'))
        text = "" if "3.8" in req.full_url else "[00:05] Привет"
        payload = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}
        return io.BytesIO(google_api.json.dumps(payload).encode())

    monkeypatch.setattr(google_api.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(google_api.time, "sleep", lambda _: None)
    assert google_api.gemini_transcript("x", "k", ["gemini-3.8-flash", "gemini-3.6-flash"]) == [(5, "Привет")]
    assert [u.split("/")[-1] for u in calls] == ["gemini-3.8-flash:generateContent"] * 2 + ["gemini-3.6-flash:generateContent"]


def test_veo_generate_clip_polls_and_downloads(monkeypatch):
    import io

    from ai_news import veo

    requests = []

    def fake_request(url, key, body=None, timeout=60):
        requests.append((url, body))
        if body is not None:
            assert body["parameters"] == {"aspectRatio": "9:16", "durationSeconds": 8, "resolution": "720p"}
            return {"name": "models/veo/operations/op1"}
        if len(requests) == 2:
            return {"name": "models/veo/operations/op1", "done": False}
        return {"done": True, "response": {"generateVideoResponse": {
            "generatedSamples": [{"video": {"uri": "https://example.com/v.mp4"}}]}}}

    def fake_urlopen(req, timeout):
        assert req.full_url == "https://example.com/v.mp4" and req.get_header("X-goog-api-key") == "k"
        return io.BytesIO(b"mp4")

    monkeypatch.setattr(veo, "_request", fake_request)
    monkeypatch.setattr(veo.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(veo.time, "sleep", lambda _: None)
    assert veo.generate_clip("a cat", "k") == b"mp4"
    assert requests[1][0].endswith("/v1beta/models/veo/operations/op1") and len(requests) == 3
