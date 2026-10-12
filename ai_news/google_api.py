"""Ролик без yt-dlp: метаданные из YouTube Data API, транскрипт — от Gemini, который сам открывает ролик по ссылке.

С серверов (GitHub Actions и т. п.) YouTube отвечает yt-dlp «Sign in to confirm you're not a bot», а официальный
API и Gemini не блокирует. Ключи: GEMINI_API_KEY (aistudio.google.com/apikey) и YOUTUBE_API_KEY (Google Cloud,
YouTube Data API v3) — без него не будет названия, даты и описания со ссылками на источники.
"""

import json
import os
import sys
import urllib.error
import urllib.request

from .fetch import Source, parse_timestamped_text, video_id_from_url

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
TRANSCRIPT_PROMPT = (
    "Сделай дословную расшифровку всей речи в этом видео на языке оригинала, от начала до конца, без пропусков, "
    "пересказа и комментариев. Формат — только строки вида:\n"
    "[MM:SS] текст\n"
    "Новая строка — каждые 10–20 секунд или при смене темы; для видео длиннее часа — [H:MM:SS]. "
    "Названия компаний, продуктов и моделей пиши так, как они пишутся в оригинале (OpenAI, Claude, Gemini)."
)


def _request(url: str, key: str, body: dict | None = None, timeout: int = 60) -> dict:
    # Ключ — в заголовке, а не в адресе: адрес может попасть в лог ошибки
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:1500]
        raise RuntimeError(f"{url.split('?')[0]}: HTTP {e.code}: {detail}") from None


def youtube_metadata(src: Source, key: str) -> None:
    data = _request(f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={src.video_id}", key)
    if not data.get("items"):
        raise RuntimeError(f"YouTube Data API: ролик {src.video_id} не найден (приватный или удалён?)")
    snippet = data["items"][0]["snippet"]
    src.title = snippet.get("title", "")
    src.description = snippet.get("description", "")
    src.upload_date = snippet.get("publishedAt", "")[:10].replace("-", "")


def gemini_transcript(video_id: str, key: str, model: str = GEMINI_MODEL) -> list[tuple[int, str]]:
    body = {
        "contents": [{"parts": [
            {"file_data": {"file_uri": f"https://www.youtube.com/watch?v={video_id}"}},
            {"text": TRANSCRIPT_PROMPT},
        ]}],
        # Для речи хватает низкого разрешения кадров: втрое меньше токенов, длинный выпуск влезает в бесплатный лимит
        "generationConfig": {"mediaResolution": "MEDIA_RESOLUTION_LOW", "maxOutputTokens": 65536, "temperature": 0},
    }
    data = _request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    key, body, timeout=900)
    cand = (data.get("candidates") or [{}])[0]
    parts = cand.get("content", {}).get("parts", [])
    transcript = parse_timestamped_text("\n".join(p.get("text", "") for p in parts if not p.get("thought")))
    if not transcript:
        # Ответ без самого текста: показываем его целиком (ключа в нём нет), иначе причину не найти
        raise RuntimeError(f"Gemini не вернул транскрипт: {json.dumps(data, ensure_ascii=False)[:3000]}")
    if cand.get("finishReason") == "MAX_TOKENS":
        print("Внимание: транскрипт Gemini обрезан по лимиту длины ответа", file=sys.stderr)
    return transcript


def fetch_google(url: str) -> Source:
    vid = video_id_from_url(url)
    src = Source(video_id=vid, url=f"https://youtu.be/{vid}")
    if os.environ.get("YOUTUBE_API_KEY"):
        youtube_metadata(src, os.environ["YOUTUBE_API_KEY"])
    src.transcript = gemini_transcript(vid, os.environ["GEMINI_API_KEY"])
    return src
