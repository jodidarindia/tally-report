"""Batch-render voiceovers for ALL 30 lessons in the locked Onyx voice.

Reads lessons_manifest.LESSONS and writes:
    /app/tutorials/voiceover/lesson-NN.mp3
    /app/frontend/public/tutorials/lessons/lesson-NN.mp3    (public serving)

Also writes a small progress JSON so the frontend can auto-discover which
lessons have audio ready:
    /app/frontend/public/tutorials/manifest.json
    { "voice": "onyx", "generated_at": "...", "lessons": [{n, slug, audio_url, duration_hint}] }
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.openai import OpenAITextToSpeech

sys.path.insert(0, str(Path(__file__).parent))
from lessons_manifest import LESSONS, VOICE, MODEL

load_dotenv("/app/backend/.env")

VO_DIR = Path("/app/tutorials/voiceover")
PUB_DIR = Path("/app/frontend/public/tutorials/lessons")
MANIFEST_PATH = Path("/app/frontend/public/tutorials/manifest.json")


async def render_one(tts: OpenAITextToSpeech, n: int, slug: str, text: str) -> Path:
    audio = await tts.generate_speech(
        text=text,
        model=MODEL,
        voice=VOICE,
        speed=1.0,
        response_format="mp3",
    )
    fname = f"lesson-{n:02d}.mp3"
    (VO_DIR / fname).write_bytes(audio)
    (PUB_DIR / fname).write_bytes(audio)
    return VO_DIR / fname


async def main() -> None:
    key = os.getenv("EMERGENT_LLM_KEY")
    if not key:
        sys.exit("EMERGENT_LLM_KEY missing")

    VO_DIR.mkdir(parents=True, exist_ok=True)
    PUB_DIR.mkdir(parents=True, exist_ok=True)

    tts = OpenAITextToSpeech(api_key=key)
    entries = []
    for n, slug, title, text, length_hint in LESSONS:
        # Skip if audio already exists AND is >= 20 KB (guard against stubs)
        target = VO_DIR / f"lesson-{n:02d}.mp3"
        if target.exists() and target.stat().st_size > 20_000:
            print(f"  ↷ Lesson {n:02d} — {slug}  (skipped, already exists {target.stat().st_size//1024} KB)")
        else:
            print(f"  → Lesson {n:02d} — {slug} ({len(text)} chars) ...", end=" ", flush=True)
            path = await render_one(tts, n, slug, text)
            print(f"{path.stat().st_size//1024} KB")
        entries.append({
            "n": n,
            "slug": slug,
            "title": title,
            "audio_url": f"/tutorials/lessons/lesson-{n:02d}.mp3",
            "duration_hint": length_hint,
        })

    manifest = {
        "voice": VOICE,
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lessons": entries,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"\n✅ Manifest written: {MANIFEST_PATH}")
    print(f"   {len(entries)} lessons  ·  voice={VOICE}")


if __name__ == "__main__":
    asyncio.run(main())
