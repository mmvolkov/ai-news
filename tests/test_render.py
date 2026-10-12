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
