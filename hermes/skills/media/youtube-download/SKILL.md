---
name: youtube-download
description: "Download from YouTube: metadata, timestamped transcript, video (mp4) or audio (m4a); falls back to YouTube Data API + Gemini when YouTube blocks the server."
version: 1.0.0
author: mmvolkov
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [YouTube, Video, Audio, Transcript, Download, yt-dlp, Gemini, Media]
    related_skills: [youtube-content, ai-news-digest]
required_environment_variables:
  - name: GEMINI_API_KEY
    prompt: "Gemini API key (optional, free tier)"
    help: "https://aistudio.google.com/apikey — used for the transcript when YouTube blocks yt-dlp or the video has no subtitles"
    required_for: "transcript fallback"
  - name: YOUTUBE_API_KEY
    prompt: "YouTube Data API v3 key (optional)"
    help: "Google Cloud → APIs & Services → enable YouTube Data API v3 → Credentials → API key"
    required_for: "metadata fallback"
---

# YouTube download

One script, four commands: video metadata, a transcript with timestamps, the video file or the audio track.

## When to Use

- The user shares a YouTube link and wants to **download** the video or audio, get the **transcript** or the
  **description / title / date / chapters**.
- Another skill needs raw material from a YouTube video (e.g. `ai-news-digest`, summaries, clipping).
- For summaries, threads or blog posts built from a video, load `youtube-content` after getting the transcript.

## Quick Reference

| Need | Command |
|---|---|
| Metadata (JSON) | `python ${HERMES_SKILL_DIR}/scripts/yt.py info <url>` |
| Transcript `[MM:SS] text` | `python ${HERMES_SKILL_DIR}/scripts/yt.py transcript <url> [--lang ru,en]` |
| Video mp4 (≤1080p) | `python ${HERMES_SKILL_DIR}/scripts/yt.py video <url> [--max-height 720] [--out DIR]` |
| Audio m4a | `python ${HERMES_SKILL_DIR}/scripts/yt.py audio <url> [--out DIR]` |
| Skip yt-dlp, use Google API | add `--api` to `info` / `transcript` |

`video` and `audio` print `{"files": [...]}` with the saved paths (`<upload_date>_<id>.<ext>`, default folder
`./downloads`).

## Procedure

1. **Dependencies** (once): `python -m pip install -U yt-dlp`. For `video`, `ffmpeg` must be installed —
   yt-dlp merges the separate video and audio tracks with it. `info`/`transcript` via `--api` need only Python.
2. Run the command for what the user asked. Pass the URL in quotes.
3. **If yt-dlp is blocked** («Sign in to confirm you're not a bot», HTTP 429 — typical for cloud servers):
   - `info` and `transcript` switch to the Google APIs automatically when `YOUTUBE_API_KEY` /
     `GEMINI_API_KEY` are set; the script says so on stderr.
   - `video` / `audio` have no API fallback. Options: `YTDLP_COOKIES=/path/to/cookies.txt` exported from a
     browser (separate Google account, export from a private window and close it right after), or run on a
     home machine.
4. **Deliver:** send the downloaded file as a document, the transcript as a `.txt` file if it is long, metadata as a
   short summary (title, channel, date, duration).

## Pitfalls

- **Gemini transcript is a model transcription**, not YouTube captions: rare words and names can be wrong; long
  videos take 1–3 minutes. `HTTP 503 … повтор через N с` on stderr is normal — the script retries itself and then
  tries the next model in `GEMINI_MODEL` (default `gemini-3.8-flash,gemini-3.6-flash`).
- Gemini and the Data API see only **public** videos; private/unlisted videos fail.
- Without subtitles in the requested languages yt-dlp returns nothing — the script then tries Gemini.
- Keep `yt-dlp` up to date (`pip install -U yt-dlp`): YouTube changes often and old versions break.
- Download only content the user has the right to use (own videos, permissive licenses, personal fair use);
  respect YouTube's terms and copyright.
- Never print API keys; the script sends them in a header and never echoes them.

## Verification

- `info` prints JSON with a non-empty `title` and `upload_date` (YYYYMMDD).
- `transcript` prints lines starting with `[MM:SS]` (or `[H:MM:SS]`), timestamps increasing.
- `video`: `ffprobe -v error -show_entries stream=codec_type,width,height -of compact <file>` shows a video and
  an audio stream.
