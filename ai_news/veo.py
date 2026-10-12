"""Рилс 9:16 через Veo (Gemini API): клипы по 8 с из issue.video_clips, склейка и текст поверх кадра — ffmpeg.

Veo в Gemini API платный, бесплатного тарифа нет: ключ нужен из проекта Google Cloud с подключённой оплатой
(VEO_API_KEY; если не задан — GEMINI_API_KEY). Модель — VEO_MODEL, по умолчанию veo-3.1-fast-generate-preview
(≈ $0,10 за секунду 720p, рилс из 4 клипов — около $3).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
from pathlib import Path

from .google_api import _request
from .schema import VideoClip

BASE = "https://generativelanguage.googleapis.com/v1beta"
VEO_MODEL = os.environ.get("VEO_MODEL", "veo-3.1-fast-generate-preview")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CLIP_SEC = 8


def generate_clip(prompt: str, key: str, model: str = VEO_MODEL, timeout: int = 900) -> bytes:
    op = _request(f"{BASE}/models/{model}:predictLongRunning", key, {
        "instances": [{"prompt": prompt}],
        "parameters": {"aspectRatio": "9:16", "durationSeconds": CLIP_SEC, "resolution": "720p"},
    })
    deadline = time.monotonic() + timeout
    while not op.get("done"):
        if time.monotonic() > deadline:
            raise RuntimeError(f"Veo не успел за {timeout} с: {op.get('name')}")
        time.sleep(10)
        op = _request(f"{BASE}/{op['name']}", key)
    if "error" in op:
        raise RuntimeError(f"Veo: {op['error']}")
    result = op.get("response", {}).get("generateVideoResponse", {})
    samples = result.get("generatedSamples") or []
    if not samples:
        # Чаще всего клип отклонил фильтр безопасности — причина в raiMediaFilteredReasons
        raise RuntimeError(f"Veo не вернул видео: {result}")
    req = urllib.request.Request(samples[0]["video"]["uri"], headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def _has_audio(path: Path) -> bool:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(probe.stdout.strip())


def assemble_reel(clips: list[Path], texts: list[str], out: Path) -> None:
    """Склеивает клипы в 1080×1920, на каждый — его текст в нижней трети (над интерфейсом Instagram)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("Нужен ffmpeg: sudo apt-get install -y ffmpeg fonts-dejavu-core")
    tmp = Path(tempfile.mkdtemp())
    inputs, filters, concat = [], [], ""
    for i, (clip, text) in enumerate(zip(clips, texts)):
        inputs += ["-i", str(clip)]
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
        if text.strip():
            # Текст — через файл: так не нужно экранировать кавычки, двоеточия и запятые для drawtext
            (tmp / f"t{i}.txt").write_text("\n".join(textwrap.wrap(text.strip(), 20)), encoding="utf-8")
            vf += (f",drawtext=fontfile={FONT}:textfile={tmp / f't{i}.txt'}:fontsize=76:fontcolor=white"
                   ":line_spacing=14:box=1:boxcolor=black@0.55:boxborderw=28"
                   ":x=(w-text_w)/2:y=h*0.64-text_h/2")
        filters.append(f"[{i}:v]{vf}[v{i}]")
        concat += f"[v{i}][a{i}]"
    # У клипа без звуковой дорожки — тишина той же длины, иначе concat не соберёт звук
    for i, clip in enumerate(clips):
        if _has_audio(clip):
            filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        else:
            filters.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{CLIP_SEC}[a{i}]")
    filters.append(f"{concat}concat=n={len(clips)}:v=1:a=1[v][a]")
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)


def make_reel(clips: list[VideoClip], out_dir: Path) -> Path:
    if not clips:
        raise RuntimeError("В выпуске нет video_clips — пересоберите его без --from-json")
    key = os.environ.get("VEO_API_KEY") or os.environ["GEMINI_API_KEY"]
    clip_dir = out_dir / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, clip in enumerate(clips, 1):
        path = clip_dir / f"clip{i}.mp4"
        if not path.exists():  # уже оплаченные клипы при повторном запуске не генерируем заново
            print(f"Veo: клип {i}/{len(clips)}…", file=sys.stderr)
            path.write_bytes(generate_clip(clip.prompt, key))
        paths.append(path)
    reel = out_dir / "reels.mp4"
    assemble_reel(paths, [c.on_screen_text for c in clips], reel)
    return reel
