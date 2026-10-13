"""Собирает подпись Telegram и materials.md из issue.json, который написал сам агент.

Нужен, когда тексты пишет модель Hermes, а не Claude из пайплайна (`python -m ai_news … --prompt-only`).

    render_issue.py --repo ~/ai-news --schema            # JSON-схема issue.json
    render_issue.py --repo ~/ai-news issues/20261009_aC9p1eld0tA
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path.home() / "ai-news", help="Клон github.com/mmvolkov/ai-news")
    p.add_argument("--schema", action="store_true", help="Напечатать JSON-схему issue.json и выйти")
    p.add_argument("issue_dir", type=Path, nargs="?", help="Папка выпуска <YYYYMMDD>_<id ролика> с issue.json")
    args = p.parse_args()
    sys.path.insert(0, str(args.repo.expanduser().resolve()))

    from pydantic import ValidationError

    from ai_news.fetch import Source
    from ai_news.render import materials_md, telegram_caption, visible_len
    from ai_news.schema import Issue

    if args.schema:
        print(json.dumps(Issue.model_json_schema(), ensure_ascii=False, indent=2))
        return
    if not args.issue_dir:
        p.error("укажите папку выпуска")

    out = args.issue_dir
    date, _, vid = out.name.partition("_")  # имя папки пайплайн задаёт сам: <дата>_<id ролика>
    try:
        issue = Issue.model_validate_json((out / "issue.json").read_text(encoding="utf-8"))
    except ValidationError as e:
        sys.exit(f"issue.json не соответствует схеме — исправьте и запустите снова:\n{e}")
    src = Source(video_id=vid, url=f"https://youtu.be/{vid}", upload_date=date)
    caption = telegram_caption(issue, src)
    (out / "telegram_post.html").write_text(caption, encoding="utf-8")
    (out / "materials.md").write_text(materials_md(issue, src, caption), encoding="utf-8")
    print(f"Готово: {out}/ (подпись Telegram: {visible_len(caption)} симв.)")


if __name__ == "__main__":
    main()
