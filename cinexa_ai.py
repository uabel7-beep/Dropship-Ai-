"""Cinexa AI - story/script to narrated vertical video.

Provider: OpenAI-compatible API for story planning, image generation and TTS.
Rendering: ffmpeg/ffprobe installed on the host.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from config import OPENAI_API_KEY, CINEXA_TEXT_MODEL, CINEXA_IMAGE_MODEL, CINEXA_TTS_MODEL

try:
    from openai import OpenAI
except ImportError:  # optional until Cinexa is used
    OpenAI = None

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = Path(os.getenv("CINEXA_OUTPUT_DIR", str(BASE_DIR / "cinexa_output")))
WORK_DIR.mkdir(parents=True, exist_ok=True)

STYLE_DEFAULT = "cinématique réaliste, narration storytelling, éclairage dramatique, détails naturels"


def _client():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY manquante. Ajoute-la dans token.env ou .env.")
    if OpenAI is None:
        raise RuntimeError("Le paquet openai n'est pas installé. Lance: pip install openai")
    return OpenAI(api_key=OPENAI_API_KEY)


def _json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _plan_story(story: str, style: str = STYLE_DEFAULT) -> dict[str, Any]:
    client = _client()
    prompt = f"""Tu es le directeur créatif de Cinexa AI.
Transforme l'histoire/script ci-dessous en plan de vidéo verticale 9:16.
Le texte peut être une histoire très courte, un scénario ou des notes brutes.
Tu dois tout comprendre sans demander de précisions.

OBJECTIFS:
- narration française naturelle, au présent ou au passé selon le texte;
- 3 à 8 scènes maximum selon la longueur;
- chaque scène doit faire avancer l'histoire;
- conserver une continuité stricte des personnages, vêtements, lieux et époque;
- créer une Bible des personnages et une Bible du monde AVANT les scènes;
- chaque scène doit avoir un texte de narration réellement prononçable;
- durée estimée en secondes par scène, total entre 20 et 90 secondes sauf si l'histoire impose plus;
- style visuel: {style}.

RETOURNE UNIQUEMENT DU JSON valide avec exactement cette structure:
{{
  "title": "...",
  "visual_style": "...",
  "characters": [{{"id":"...","name":"...","locked_description":"..."}}],
  "locations": [{{"id":"...","name":"...","locked_description":"..."}}],
  "scenes": [{{
    "id":"scene_01",
    "duration": 6,
    "narration":"...",
    "visual_prompt":"...",
    "camera":"...",
    "mood":"..."
  }}]
}}

RÈGLE IMPORTANTE: dans chaque visual_prompt, réutilise les descriptions verrouillées pertinentes des personnages/lieux. Ne change jamais arbitrairement leur apparence.

HISTOIRE/SCRIPT:
{story}
"""
    response = client.responses.create(model=CINEXA_TEXT_MODEL, input=prompt)
    return _json_from_text(response.output_text)


def _generate_image(prompt: str, output: Path) -> None:
    client = _client()
    result = client.images.generate(
        model=CINEXA_IMAGE_MODEL,
        prompt=prompt,
        size="1024x1536",
        quality="medium",
    )
    item = result.data[0]
    if getattr(item, "b64_json", None):
        output.write_bytes(base64.b64decode(item.b64_json))
        return
    url = getattr(item, "url", None)
    if url:
        import requests
        r = requests.get(url, timeout=90)
        r.raise_for_status()
        output.write_bytes(r.content)
        return
    raise RuntimeError("Le fournisseur d'image n'a retourné ni base64 ni URL.")


def _generate_tts(text: str, output: Path, voice: str = "marin") -> None:
    client = _client()
    with client.audio.speech.with_streaming_response.create(
        model=CINEXA_TTS_MODEL,
        voice=voice,
        input=text,
        response_format="mp3",
    ) as response:
        response.stream_to_file(output)


def _duration(path: Path) -> float:
    if not shutil.which("ffprobe"):
        return 5.0
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(p.stdout.strip())


def _render_scene(image: Path, audio: Path, output: Path, duration: float) -> None:
    # Gentle Ken-Burns motion keeps static generated images from feeling like a slideshow.
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"zoompan=z='min(zoom+0.0008,1.08)':d={max(1, int(duration*25))}:s=1080x1920:fps=25,"
        "format=yuv420p"
    )
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(image), "-i", str(audio),
        "-t", f"{duration:.3f}", "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(output)
    ], check=True)


def _concat(parts: list[Path], output: Path) -> None:
    manifest = output.with_suffix(".txt")
    manifest.write_text("".join(f"file '{p.as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in parts), encoding="utf-8")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", str(output)], check=True)
    finally:
        manifest.unlink(missing_ok=True)


def _add_subtitles(video: Path, plan: dict[str, Any], scene_durations: list[float], output: Path) -> None:
    if not shutil.which("ffmpeg"):
        shutil.copy2(video, output)
        return
    srt = output.with_suffix(".srt")
    elapsed = 0.0
    blocks = []
    for i, (scene, dur) in enumerate(zip(plan["scenes"], scene_durations), 1):
        start = _srt_time(elapsed)
        end = _srt_time(elapsed + dur)
        blocks.append(f"{i}\n{start} --> {end}\n{scene['narration'].strip()}\n")
        elapsed += dur
    srt.write_text("\n".join(blocks), encoding="utf-8")
    # Keep subtitle styling deliberately simple for compatibility with hosted ffmpeg builds.
    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
            "-vf", f"subtitles={srt.as_posix()}:force_style='FontSize=18,Outline=2,Alignment=2,MarginV=90'",
            "-c:a", "copy", str(output)
        ], check=True)
    finally:
        srt.unlink(missing_ok=True)


def _srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    total, ms = divmod(total_ms, 1000)
    h, rem = divmod(total, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def generate_video(story: str, user_id: int, style: str = STYLE_DEFAULT, voice: str = "marin") -> tuple[Path, dict[str, Any]]:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg est requis pour assembler la vidéo. Installe FFmpeg sur le serveur.")
    plan = _plan_story(story, style)
    job = WORK_DIR / f"{user_id}_{int(time.time()*1000)}"
    job.mkdir(parents=True, exist_ok=True)
    (job / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    parts: list[Path] = []
    durations: list[float] = []
    continuity = "\n".join(f"{c['name']}: {c['locked_description']}" for c in plan.get("characters", []))
    locations = "\n".join(f"{l['name']}: {l['locked_description']}" for l in plan.get("locations", []))
    for idx, scene in enumerate(plan["scenes"], 1):
        image = job / f"scene_{idx:02d}.png"
        audio = job / f"scene_{idx:02d}.mp3"
        part = job / f"scene_{idx:02d}.mp4"
        image_prompt = (
            f"{plan.get('visual_style', style)}. FORMAT VERTICAL 9:16.\n"
            f"CONTINUITY CHARACTERS:\n{continuity}\nLOCATIONS:\n{locations}\n"
            f"SCENE: {scene['visual_prompt']}\nCAMERA: {scene.get('camera','cinematic')}\n"
            "No text, no subtitles, no watermark. Preserve exact identity and clothing of recurring characters."
        )
        _generate_image(image_prompt, image)
        _generate_tts(scene["narration"], audio, voice)
        actual = max(_duration(audio), float(scene.get("duration", 5)))
        durations.append(actual)
        _render_scene(image, audio, part, actual)
        parts.append(part)

    raw = job / "cinexa_raw.mp4"
    final = job / "cinexa_final.mp4"
    _concat(parts, raw)
    _add_subtitles(raw, plan, durations, final)
    return final, plan
