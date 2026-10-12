"""Генерация дайджеста и промптов через Claude (структурированный вывод).

По умолчанию — через Claude Code (`claude -p`) по подписке Pro/Max: локально после `claude login`,
в CI — с токеном `claude setup-token` в переменной CLAUDE_CODE_OAUTH_TOKEN.
Если задан ANTHROPIC_API_KEY — напрямую через Claude API.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

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
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _generate_api(src, model)
    return _generate_cli(src, model)


def _generate_cli(src: Source, model: str) -> Issue:
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError(
            "Не найден Claude Code: npm install -g @anthropic-ai/claude-code, затем `claude login` "
            "(или токен `claude setup-token` в CLAUDE_CODE_OAUTH_TOKEN)."
        )
    cmd = [
        claude, "-p",
        "--model", model,
        "--system-prompt", SYSTEM_PROMPT,
        # Чистый вызов модели: без инструментов, настроек, MCP и истории сессий
        "--tools", "",
        "--setting-sources", "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format", "json",
        "--json-schema", json.dumps(Issue.model_json_schema(), ensure_ascii=False),
    ]
    # Транскрипт идёт через stdin: в аргументе командной строки он может не поместиться
    proc = subprocess.run(cmd, input=build_user_message(src), capture_output=True, text=True,
                          encoding="utf-8", cwd=tempfile.gettempdir(), timeout=1800)
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude -p завершился с кодом {proc.returncode}: {(proc.stderr or proc.stdout)[-2000:]}")
    if result.get("is_error") or result.get("structured_output") is None:
        raise RuntimeError(f"claude -p: {result.get('subtype')}: {str(result.get('result'))[-2000:]}")
    return Issue.model_validate(result["structured_output"])


def _generate_api(src: Source, model: str) -> Issue:
    import anthropic

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
