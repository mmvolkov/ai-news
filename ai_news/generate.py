"""Генерация дайджеста и промптов через Claude API (структурированный вывод)."""

from pathlib import Path

import anthropic

from .fetch import Source, fmt_ts
from .schema import Issue

MODEL = "claude-opus-5-5"
SYSTEM_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.md").read_text(
    encoding="utf-8"
)


def build_user_message(src: Source) -> str:
    chapters = "\n".join(f"{fmt_ts(c['start'])} ({c['start']}s) {c['title']}" for c in src.chapters)
    return (
        f"Ссылка на ролик: {src.url}\n"
        f"Название: {src.title}\n"
        f"Дата публикации: {src.upload_date}\n\n"
        f"<description>\n{src.description}\n</description>\n\n"
        f"<chapters>\n{chapters or 'нет'}\n</chapters>\n\n"
        f"<transcript>\n{src.transcript_text()}\n</transcript>"
    )


def generate_issue(src: Source, model: str = MODEL) -> Issue:
    if not src.transcript and not src.chapters:
        raise ValueError("Нет ни транскрипта, ни глав ролика — генерировать не из чего.")
    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(src)}],
        output_format=Issue,
        # Если классификатор безопасности отклонит запрос, API сам повторит его на рекомендованной модели
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Модель отказалась отвечать: {response.stop_details}")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError(f"Ответ модели не разобран (stop_reason={response.stop_reason})")
    return response.parsed_output
