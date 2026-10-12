"""CLI: python -m ai_news <ссылка на ролик> [опции]

Примеры:
  python -m ai_news https://youtu.be/rc1MGVebM-4
  python -m ai_news https://youtu.be/rc1MGVebM-4 --transcript subs.ru.vtt --description desc.txt --date 20261004
  python -m ai_news https://youtu.be/rc1MGVebM-4 --prompt-only     # без API: собрать промпт для ручной вставки
  python -m ai_news https://youtu.be/rc1MGVebM-4 --from-json issues/.../issue.json   # перерендер
"""

import argparse
import json
from datetime import date
from pathlib import Path

from .fetch import Source, fetch_youtube, load_transcript_file, video_id_from_url
from .render import materials_md, telegram_caption, visible_len
from .schema import Issue


def main() -> None:
    p = argparse.ArgumentParser(prog="ai_news", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url", help="Ссылка на YouTube-ролик с выпуском")
    p.add_argument("--transcript", type=Path, help="Локальный транскрипт (.vtt/.srt/.json3/.txt) вместо загрузки с YouTube")
    p.add_argument("--description", type=Path, help="Файл с описанием ролика (таймкоды, ссылки на источники)")
    p.add_argument("--title", default="", help="Название ролика (если не загружается с YouTube)")
    p.add_argument("--date", default="", help="Дата публикации YYYYMMDD (если не загружается с YouTube)")
    p.add_argument("--out", type=Path, default=Path("issues"), help="Папка для выпусков")
    p.add_argument("--prompt-only", action="store_true", help="Только собрать prompt.md для ручной вставки в Claude/ChatGPT")
    p.add_argument("--from-json", type=Path, help="Готовый issue.json — только перерендерить материалы")
    args = p.parse_args()

    vid = video_id_from_url(args.url)
    if args.transcript:
        src = Source(video_id=vid, url=f"https://youtu.be/{vid}", transcript=load_transcript_file(args.transcript))
    else:
        src = fetch_youtube(args.url)
    if args.description:
        src.description = args.description.read_text(encoding="utf-8")
    src.title = args.title or src.title
    src.upload_date = args.date or src.upload_date

    out = args.out / f"{src.upload_date or date.today().strftime('%Y%m%d')}_{vid}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.txt").write_text(src.transcript_text(), encoding="utf-8")

    if args.prompt_only:
        from .generate import SYSTEM_PROMPT, build_user_message

        (out / "prompt.md").write_text(f"{SYSTEM_PROMPT}\n\n---\n\n{build_user_message(src)}", encoding="utf-8")
        print(f"Промпт сохранён: {out / 'prompt.md'}")
        return

    if args.from_json:
        issue = Issue.model_validate_json(args.from_json.read_text(encoding="utf-8"))
    else:
        from .generate import generate_issue

        issue = generate_issue(src)

    (out / "issue.json").write_text(json.dumps(issue.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    caption = telegram_caption(issue, src)
    (out / "telegram_post.html").write_text(caption, encoding="utf-8")
    (out / "materials.md").write_text(materials_md(issue, src, caption), encoding="utf-8")
    print(f"Готово: {out}/ (подпись Telegram: {visible_len(caption)} симв.)")


if __name__ == "__main__":
    main()
