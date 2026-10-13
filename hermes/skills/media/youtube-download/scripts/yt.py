"""Загрузка с YouTube: метаданные, транскрипт с таймкодами, видео, аудио.

    yt.py info URL                       # JSON: id, название, дата, длительность, канал, описание, главы
    yt.py transcript URL [--lang ru,en]  # строки «[MM:SS] текст» (или [H:MM:SS])
    yt.py video URL [--max-height 1080] [--out DIR]
    yt.py audio URL [--out DIR]

Основной путь — yt-dlp. С серверов YouTube часто отвечает «Sign in to confirm you're not a bot», тогда:
- info берётся из YouTube Data API (YOUTUBE_API_KEY);
- transcript — из Gemini, который сам открывает ролик по ссылке (GEMINI_API_KEY, модели — GEMINI_MODEL);
- для video/audio обхода через API нет — помогает только cookies.txt браузера (YTDLP_COOKIES) или запуск
  с домашнего IP.
Ключи передаются в заголовке, не в адресе, и в вывод не попадают.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GEMINI_MODELS = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash,gemini-3.6-flash").split(",")
TRANSCRIPT_PROMPT = (
    "Сделай дословную расшифровку всей речи в этом видео на языке оригинала, от начала до конца, без пропусков, "
    "пересказа и комментариев. Формат — только строки вида «[MM:SS] текст», новая строка каждые 10–20 секунд; "
    "для видео длиннее часа — [H:MM:SS]."
)


def video_id(url: str) -> str:
    m = re.search(r"(?:youtu\.be/|v=|shorts/|live/|embed/)([\w-]{11})", url)
    if not m:
        sys.exit(f"Не удалось извлечь id видео из ссылки: {url}")
    return m.group(1)


def fmt_ts(sec: int) -> str:
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------- yt-dlp ----------

def _ydl(extra: dict | None = None):
    try:
        import yt_dlp
    except ImportError:
        sys.exit("Нужен yt-dlp: python -m pip install -U yt-dlp")
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, **(extra or {})}
    if os.environ.get("YTDLP_COOKIES"):
        opts["cookiefile"] = os.environ["YTDLP_COOKIES"]
    return yt_dlp.YoutubeDL(opts)


def info_ytdlp(url: str) -> dict:
    with _ydl({"skip_download": True}) as ydl:
        i = ydl.extract_info(url, download=False)
    return {
        "id": i["id"], "url": f"https://youtu.be/{i['id']}", "title": i.get("title", ""),
        "upload_date": i.get("upload_date", ""), "duration_sec": i.get("duration"),
        "channel": i.get("channel") or i.get("uploader", ""), "description": i.get("description", ""),
        "chapters": [{"start": int(c["start_time"]), "title": c["title"]} for c in i.get("chapters") or []],
    }


def transcript_ytdlp(url: str, langs: list[str]) -> list[tuple[int, str]]:
    with _ydl({"skip_download": True}) as ydl:
        i = ydl.extract_info(url, download=False)
        tracks = {**(i.get("automatic_captions") or {}), **(i.get("subtitles") or {})}
        for lang in langs:
            for code in (lang, f"{lang}-orig"):
                fmt = next((f for f in tracks.get(code, []) if f.get("ext") == "json3"), None)
                if fmt:
                    data = json.loads(ydl.urlopen(fmt["url"]).read().decode("utf-8"))
                    cues = []
                    for ev in data.get("events", []):
                        text = "".join(s.get("utf8", "") for s in ev.get("segs") or []).strip()
                        if text:
                            cues.append((int(ev.get("tStartMs", 0)) // 1000, text))
                    return cues
    return []


def download(url: str, out: Path, audio: bool, max_height: int) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    fmt = ("bestaudio[ext=m4a]/bestaudio" if audio else
           f"bv*[height<=?{max_height}][ext=mp4]+ba[ext=m4a]/b[height<=?{max_height}][ext=mp4]/b[height<=?{max_height}]")
    opts = {"format": fmt, "outtmpl": str(out / "%(upload_date)s_%(id)s.%(ext)s"), "noplaylist": True}
    if not audio:
        opts["merge_output_format"] = "mp4"  # склейка дорожек видео и звука — нужен ffmpeg
    with _ydl(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    # Итоговые пути после склейки yt-dlp кладёт в requested_downloads
    return [d["filepath"] for d in info.get("requested_downloads") or [] if d.get("filepath")]


# ---------- Google API (запасной путь) ----------

def _google(url: str, key: str, body: dict | None = None, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    for delay in (15, 45, 90, None):  # Gemini нередко отвечает 503 «high demand»
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:1000]
            if e.code in (429, 500, 502, 503, 504) and delay is not None:
                print(f"{url.split('?')[0]}: HTTP {e.code}, повтор через {delay} с", file=sys.stderr)
                time.sleep(delay)
                continue
            raise RuntimeError(f"{url.split('?')[0]}: HTTP {e.code}: {detail}") from None


def info_api(vid: str) -> dict:
    data = _google(f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={vid}",
                   os.environ["YOUTUBE_API_KEY"])
    if not data.get("items"):
        raise RuntimeError(f"YouTube Data API: ролик {vid} не найден (приватный или удалён?)")
    sn, cd = data["items"][0]["snippet"], data["items"][0].get("contentDetails", {})
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", cd.get("duration", "")) if cd else None
    duration = int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0) if m else None
    return {"id": vid, "url": f"https://youtu.be/{vid}", "title": sn.get("title", ""),
            "upload_date": sn.get("publishedAt", "")[:10].replace("-", ""), "duration_sec": duration,
            "channel": sn.get("channelTitle", ""), "description": sn.get("description", ""), "chapters": []}


def transcript_gemini(vid: str) -> list[tuple[int, str]]:
    body = {"contents": [{"parts": [{"file_data": {"file_uri": f"https://www.youtube.com/watch?v={vid}"}},
                                    {"text": TRANSCRIPT_PROMPT}]}],
            "generationConfig": {"mediaResolution": "MEDIA_RESOLUTION_LOW", "maxOutputTokens": 65536,
                                 "temperature": 0}}
    errors = []
    for model in GEMINI_MODELS:
        try:
            data = _google(f"https://generativelanguage.googleapis.com/v1beta/models/{model.strip()}:generateContent",
                           os.environ["GEMINI_API_KEY"], body, timeout=900)
        except RuntimeError as e:
            errors.append(str(e))
            continue
        cand = (data.get("candidates") or [{}])[0]
        text = "\n".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
        cues = parse_timestamped(text)
        if cues:
            return cues
        errors.append(f"{model}: ответ без транскрипта: {json.dumps(data, ensure_ascii=False)[:1000]}")
    raise RuntimeError("Gemini не вернул транскрипт:\n" + "\n".join(errors))


def parse_timestamped(raw: str) -> list[tuple[int, str]]:
    cues: list[tuple[int, str]] = []
    for line in raw.splitlines():
        line = line.strip().lstrip("*-• ").replace("**", "")
        m = re.match(r"\[?(?:(\d+):)?(\d{1,2}):(\d{2})\]?\s*(.*)", line)
        if m:
            cues.append((int(m[1] or 0) * 3600 + int(m[2]) * 60 + int(m[3]), m[4].strip()))
        elif line and cues:
            cues[-1] = (cues[-1][0], f"{cues[-1][1]} {line}")
    return [c for c in cues if c[1]]


# ---------- CLI ----------

def _blocked(e: Exception) -> bool:
    return any(s in str(e) for s in ("Sign in to confirm", "not a bot", "HTTP Error 429", "Unable to download"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["info", "transcript", "video", "audio"])
    p.add_argument("url")
    p.add_argument("--lang", default="ru,en", help="Языки субтитров по приоритету (для yt-dlp)")
    p.add_argument("--max-height", type=int, default=1080, help="Максимальная высота видео")
    p.add_argument("--out", type=Path, default=Path("downloads"), help="Папка для файлов")
    p.add_argument("--api", action="store_true", help="Сразу через Google API, без yt-dlp")
    args = p.parse_args()
    vid = video_id(args.url)

    if args.command in ("video", "audio"):
        files = download(args.url, args.out, args.command == "audio", args.max_height)
        print(json.dumps({"files": files}, ensure_ascii=False, indent=2))
        return

    use_api = args.api
    if not use_api:
        try:
            if args.command == "info":
                print(json.dumps(info_ytdlp(args.url), ensure_ascii=False, indent=2))
                return
            cues = transcript_ytdlp(args.url, args.lang.split(","))
            if not cues:
                print("У ролика нет субтитров на этих языках — пробую Gemini", file=sys.stderr)
                use_api = True
        except Exception as e:  # noqa: BLE001 — yt-dlp бросает много разных типов
            if not _blocked(e):
                raise
            print(f"yt-dlp заблокирован YouTube ({str(e)[:120]}…) — перехожу на Google API", file=sys.stderr)
            use_api = True

    need = "YOUTUBE_API_KEY" if args.command == "info" else "GEMINI_API_KEY"
    if use_api and not os.environ.get(need):
        sys.exit(f"Для запасного пути нужен {need}")
    if args.command == "info":
        print(json.dumps(info_api(vid), ensure_ascii=False, indent=2))
        return
    if use_api:
        cues = transcript_gemini(vid)
    print("\n".join(f"[{fmt_ts(sec)}] {text}" for sec, text in cues))


if __name__ == "__main__":
    main()
