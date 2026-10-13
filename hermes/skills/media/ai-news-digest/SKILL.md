---
name: ai-news-digest
description: "YouTube AI-news episode → Telegram digest (≤1024 chars), Reels script, cover/Veo prompts and an optional 9:16 Reels video."
version: 1.0.0
author: mmvolkov
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [YouTube, Telegram, Reels, Video, Veo, Gemini, Content, Marketing, Russian]
    related_skills: [youtube-content]
    config:
      - key: ai_news.repo_dir
        description: "Local clone of github.com/mmvolkov/ai-news"
        default: "~/ai-news"
        prompt: "Path to the ai-news repository clone"
required_environment_variables:
  - name: GEMINI_API_KEY
    prompt: "Gemini API key (free tier is enough)"
    help: "https://aistudio.google.com/apikey — Gemini opens the YouTube link itself and transcribes it; needed on servers where YouTube blocks yt-dlp"
    required_for: "transcript via Gemini"
  - name: YOUTUBE_API_KEY
    prompt: "YouTube Data API v3 key"
    help: "Google Cloud → APIs & Services → enable YouTube Data API v3 → Credentials → API key (restrict it to that API)"
    required_for: "video title, date and description with source links"
  - name: CLAUDE_CODE_OAUTH_TOKEN
    prompt: "Claude Pro/Max subscription token (`claude setup-token`)"
    help: "Optional: without it Hermes writes the texts itself (Mode B)"
    required_for: "Mode A — texts written by Claude"
  - name: FLOW2API_URL
    prompt: "Flow2API server URL (optional, for the Reels video)"
    help: "Self-hosted github.com/TheSmallHanCat/flow2api; uses Google Flow credits"
    required_for: "Reels video via Flow2API"
  - name: FLOW2API_KEY
    prompt: "Flow2API API key"
    required_for: "Reels video via Flow2API"
  - name: VEO_API_KEY
    prompt: "Gemini API key from a billing-enabled project (optional, paid)"
    help: "Veo has no free tier in the Gemini API: ≈ $0.10/s, ≈ $3 per Reels"
    required_for: "Reels video via Gemini API"
---

# AI-news digest from a YouTube episode

Turns one weekly AI-news episode on YouTube (channel @ProdAdvice by default) into ready-to-publish materials
in Russian: a Telegram caption that fits the 1024-character media-caption limit, a Reels script, prompts for the
cover image and for Veo video, and — on request — a finished 9:16 Reels video.

All work is done by the `ai_news` pipeline in the repository at `ai_news.repo_dir` (default `~/ai-news`).

## When to Use

- The user sends a YouTube link and asks for a digest / post for Telegram / Reels / «материалы по выпуску».
- The user asks to «сделать выпуск AI-новостей», «подпись для Telegram по ролику», «сценарий рилса по видео».
- For a plain summary or transcript of an arbitrary video, use `youtube-content` instead.

## Quick Reference

| Goal | Command (run inside the repo) |
|---|---|
| Full run, texts by Claude | `python -m ai_news <url>` |
| Same + Reels video | `python -m ai_news <url> --reels` |
| Transcript + prompt only (Hermes writes texts) | `python -m ai_news <url> --prompt-only` |
| Schema of `issue.json` | `python ${HERMES_SKILL_DIR}/scripts/render_issue.py --repo <repo> --schema` |
| Render post from `issue.json` | `python ${HERMES_SKILL_DIR}/scripts/render_issue.py --repo <repo> <issue_dir>` |
| Re-render after manual edits | `python -m ai_news <url> --from-json <issue_dir>/issue.json` |

Output folder: `<repo>/issues/<YYYYMMDD>_<video id>/` with `telegram_post.html`, `materials.md`, `issue.json`,
`transcript.txt`, and with `--reels` also `reels.mp4` and `clips/`.

## Procedure

1. **Prepare the repository** (once):
   ```bash
   git clone https://github.com/mmvolkov/ai-news ~/ai-news   # skip if it exists
   cd ~/ai-news && git pull && python -m pip install -r requirements.txt
   ```
   Mode A also needs Claude Code: `npm install -g @anthropic-ai/claude-code`. `--reels` needs `ffmpeg`
   and the DejaVu fonts (`apt-get install -y ffmpeg fonts-dejavu-core`).

2. **Choose the mode.**
   - `CLAUDE_CODE_OAUTH_TOKEN` (or `ANTHROPIC_API_KEY`) is set → **Mode A**.
   - Otherwise → **Mode B**: you write the texts yourself.

3. **Mode A — whole pipeline in one command:**
   ```bash
   cd ~/ai-news && python -m ai_news "<url>"
   ```
   It takes 2–5 minutes. Gemini answering `HTTP 503 … повтор через 15 с` is normal — the pipeline retries itself.

4. **Mode B — Hermes writes the texts:**
   1. `cd ~/ai-news && python -m ai_news "<url>" --prompt-only` → prints the issue folder; it contains
      `prompt.md` (editorial rules + video metadata + timestamped transcript) and `transcript.txt`.
   2. Get the schema: `python ${HERMES_SKILL_DIR}/scripts/render_issue.py --repo ~/ai-news --schema`.
   3. Read `prompt.md` in full and follow it exactly: only news actually said in the video, 5–8 items,
      `headline` ≤ 55 chars, `summary` ≤ 70 chars, `timestamp_sec` from the transcript, `source_url` only from
      the video description, `video_clips` — 4 self-contained English Veo prompts with Russian `on_screen_text`.
   4. Write the JSON object to `<issue_dir>/issue.json` (UTF-8, valid against the schema).
   5. `python ${HERMES_SKILL_DIR}/scripts/render_issue.py --repo ~/ai-news <issue_dir>` — on a validation error,
      fix `issue.json` and run it again.

5. **Reels video (only if the user asked, it spends credits or money):** add `--reels` in Mode A; in Mode B run
   `python -m ai_news "<url>" --from-json <issue_dir>/issue.json --reels`. With `FLOW2API_URL` the clips come from
   the user's Flow2API (Google Flow credits: 10 per clip, 40 per Reels); otherwise from the paid Gemini API (≈ $3).
   Already generated clips in `clips/` are reused on a re-run.

6. **Deliver:** send the content of `telegram_post.html` as the Telegram post (it is HTML for `parse_mode=HTML`),
   attach `materials.md`, and `reels.mp4` if it was made. Report the caption length the pipeline printed.

## Pitfalls

- **YouTube «Sign in to confirm you're not a bot»** on servers: set `GEMINI_API_KEY` — the transcript then comes
  from Gemini, not yt-dlp. Optional fallback for yt-dlp: `YTDLP_COOKIES=/path/cookies.txt`.
- **No `YOUTUBE_API_KEY`:** no title, date or description → no source links in the digest; date falls back to today.
- **Gemini answer without transcript:** the error prints the raw response; the pipeline already tries the fallback
  model from `GEMINI_MODEL` (`gemini-3.8-flash,gemini-3.6-flash`).
- **Claude subscription token** works only via Claude Code (`claude -p`), never in the raw Anthropic SDK.
  Personal use only; a service for clients must use `ANTHROPIC_API_KEY`.
- **Do not paste the Telegram caption through Markdown** — it is HTML; links and `&amp;` must stay intact.
- **Flow2API** is an unofficial wrapper over Google Flow: the Google account may be limited, use a separate one.
- Never print or echo API keys and tokens; they come from the environment.

## Verification

- The pipeline prints `Готово: issues/<…>/ (подпись Telegram: N симв.)` with N ≤ 1024.
- `telegram_post.html` has 5–8 `<a href=…>` items, the date and hashtags; every news item exists in `transcript.txt`.
- With `--reels`: `ffprobe -v error -show_entries stream=width,height:format=duration reels.mp4` shows 1080×1920
  and ≈ 32 s.
