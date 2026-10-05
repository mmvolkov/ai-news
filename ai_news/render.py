"""Рендер материалов выпуска: подпись Telegram (HTML) с контролем лимита и markdown с промптами."""

import html
import re
from datetime import date

from .fetch import Source
from .schema import Issue

# Лимит подписи к фото/видео в Telegram (для Premium-аккаунтов — 2048, ботам всегда 1024).
# Считается по видимому тексту без HTML-разметки и адресов ссылок, в UTF-16 code units.
CAPTION_LIMIT = 1024
MIN_ITEMS = 3

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]


def visible_len(tg_html: str) -> int:
    text = html.unescape(re.sub(r"<[^>]+>", "", tg_html))
    return len(text.encode("utf-16-le")) // 2


def human_date(yyyymmdd: str) -> str:
    if not yyyymmdd:
        return ""
    d = date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    return f"{d.day} {MONTHS[d.month - 1]}"


def item_url(src: Source, url: str, sec: int) -> str:
    return url if url.startswith("http") else src.timestamp_url(sec)


def _caption(issue: Issue, src: Source, n_items: int) -> str:
    d = issue.digest
    e = html.escape
    when = human_date(src.upload_date)
    lines = [f"⚡️ <b>{e(d.title)}{' · ' + when if when else ''}</b>", ""]
    for it in d.items[:n_items]:
        href = e(item_url(src, it.source_url, it.timestamp_sec), quote=True)
        lines.append(f'{it.emoji} <a href="{href}"><b>{e(it.headline)}</b></a> — {e(it.summary)}')
    lines += ["", f'▶️ <a href="{e(src.url, quote=True)}">{e(d.outro)}</a>']
    if d.hashtags:
        lines.append(" ".join(e(h if h.startswith("#") else f"#{h}") for h in d.hashtags))
    return "\n".join(lines)


def telegram_caption(issue: Issue, src: Source, limit: int = CAPTION_LIMIT) -> str:
    """Собирает подпись; если не влезает в лимит — отбрасывает последние новости."""
    for n in range(len(issue.digest.items), MIN_ITEMS - 1, -1):
        caption = _caption(issue, src, n)
        if visible_len(caption) <= limit:
            return caption
    raise ValueError(
        f"Даже {MIN_ITEMS} новости не влезают в {limit} символов — сократите заголовки/описания."
    )


def materials_md(issue: Issue, src: Source, caption: str) -> str:
    r = issue.reels
    scenes = "\n".join(
        f"| {s.time} | {s.visual} | {s.on_screen_text} | {s.voiceover} |" for s in r.scenes
    )
    return f"""# Материалы выпуска: {src.title}

Источник: {src.url}

## 1. Пост для Telegram (подпись к фото/видео)

Видимых символов: **{visible_len(caption)} / {CAPTION_LIMIT}**. Отправлять с `parse_mode=HTML`
(готовый файл — `telegram_post.html`).

```html
{caption}
```

## 2. Иллюстрация — первый кадр Reels 9:16 (ChatGPT)

Текст на обложку (добавить при монтаже): **{issue.image_text_overlay}**

```text
{issue.image_prompt}
```

## 3. Сценарий Reels

**Хук:** {r.hook}

| Время | Что в кадре | Текст на экране | Закадровый текст |
|---|---|---|---|
{scenes}

**Музыка:** {r.music}

**Подпись к Reels:**

```text
{r.caption}
```

## 4. Задание для генерации видео — Google Gemini (Veo) / Omni

```text
{issue.video_prompt}
```

### Полный закадровый текст (для озвучки)

{issue.voiceover_full}
"""
