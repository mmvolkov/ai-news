"""Загрузка метаданных и транскрипта YouTube-ролика (yt-dlp) или из локального файла."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SUB_LANGS = ("ru", "ru-orig", "en", "en-orig")
_VTT_TIME = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->")


@dataclass
class Source:
    video_id: str
    url: str
    title: str = ""
    upload_date: str = ""  # YYYYMMDD
    description: str = ""
    chapters: list[dict] = field(default_factory=list)
    # Список (секунда, текст), сгруппированный примерно по 20 секунд
    transcript: list[tuple[int, str]] = field(default_factory=list)

    def transcript_text(self) -> str:
        return "\n".join(f"[{fmt_ts(sec)} | {sec}s] {text}" for sec, text in self.transcript)

    def timestamp_url(self, sec: int) -> str:
        return f"https://youtu.be/{self.video_id}?t={max(sec, 0)}"


def fmt_ts(sec: int) -> str:
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def video_id_from_url(url: str) -> str:
    m = re.search(r"(?:youtu\.be/|v=|shorts/|live/)([\w-]{11})", url)
    if not m:
        raise ValueError(f"Не удалось извлечь id видео из ссылки: {url}")
    return m.group(1)


def _group(cues: list[tuple[int, str]], window: int = 20) -> list[tuple[int, str]]:
    """Склеивает короткие реплики субтитров в блоки по ~window секунд и убирает повторы автосубтитров."""
    out: list[tuple[int, str]] = []
    last_line = ""
    for sec, text in cues:
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text == last_line:
            continue
        last_line = text
        if out and sec - out[-1][0] < window:
            out[-1] = (out[-1][0], f"{out[-1][1]} {text}")
        else:
            out.append((sec, text))
    return out


def parse_json3(data: dict) -> list[tuple[int, str]]:
    cues = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs)
        cues.append((int(ev.get("tStartMs", 0)) // 1000, text))
    return _group(cues)


def parse_vtt_or_srt(raw: str) -> list[tuple[int, str]]:
    cues = []
    sec = None
    for line in raw.splitlines():
        m = _VTT_TIME.search(line)
        if m:
            h, mi, s = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
            sec = h * 3600 + mi * 60 + s
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if sec is None or not line or line.isdigit() or line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        cues.append((sec, line))
    return _group(cues)


def load_transcript_file(path: Path) -> list[tuple[int, str]]:
    """Локальный транскрипт: .vtt/.srt, .json3 или обычный текст (таймкоды «12:34 текст» поддерживаются)."""
    raw = path.read_text(encoding="utf-8")
    if path.suffix in (".vtt", ".srt"):
        return parse_vtt_or_srt(raw)
    if path.suffix in (".json", ".json3"):
        return parse_json3(json.loads(raw))
    cues = []
    for line in raw.splitlines():
        m = re.match(r"\s*\[?(?:(\d+):)?(\d{1,2}):(\d{2})\]?\s*(.*)", line)
        if m:
            sec = int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            cues.append((sec, m.group(4)))
        elif line.strip():
            cues.append((cues[-1][0] if cues else 0, line))
    return _group(cues)


def fetch_youtube(url: str) -> Source:
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        src = Source(
            video_id=info["id"],
            url=f"https://youtu.be/{info['id']}",
            title=info.get("title", ""),
            upload_date=info.get("upload_date", ""),
            description=info.get("description", ""),
            chapters=[
                {"start": int(c["start_time"]), "title": c["title"]} for c in info.get("chapters") or []
            ],
        )
        tracks = {**(info.get("automatic_captions") or {}), **(info.get("subtitles") or {})}
        for lang in SUB_LANGS:
            fmt = next((f for f in tracks.get(lang, []) if f.get("ext") == "json3"), None)
            if fmt:
                data = json.loads(ydl.urlopen(fmt["url"]).read().decode("utf-8"))
                src.transcript = parse_json3(data)
                break
    return src
