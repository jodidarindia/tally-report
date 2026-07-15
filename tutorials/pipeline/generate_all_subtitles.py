"""FLOWRA Academy — generate SRT subtitle files for all 30 lessons.

Runs OpenAI Whisper on each voiceover MP3 to get segment-level timestamps,
then writes an SRT file per lesson. Output SRT files are served publicly so
they can be uploaded to YouTube as subtitles (users toggle CC).

Output:
    /app/tutorials/subtitles/lesson-NN.srt
    /app/frontend/public/tutorials/lessons/lesson-NN.srt   (public serving)
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.openai import OpenAISpeechToText

sys.path.insert(0, str(Path(__file__).parent))
from lessons_manifest import LESSONS

load_dotenv("/app/backend/.env")

VO_DIR = Path("/app/tutorials/voiceover")
SRT_DIR = Path("/app/tutorials/subtitles")
PUB_DIR = Path("/app/frontend/public/tutorials/lessons")
SRT_DIR.mkdir(parents=True, exist_ok=True)


def _fmt_ts(secs: float) -> str:
    """SRT timestamp format: HH:MM:SS,ms."""
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    ms = int((secs - int(secs)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt(segments) -> str:
    """Convert Whisper segments → SRT text."""
    out = []
    for i, seg in enumerate(segments, start=1):
        # segment can be a dict (json response) or an object
        start = seg["start"] if isinstance(seg, dict) else seg.start
        end = seg["end"] if isinstance(seg, dict) else seg.end
        text = (seg["text"] if isinstance(seg, dict) else seg.text).strip()
        out.append(f"{i}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{text}\n")
    return "\n".join(out)


async def transcribe_one(stt: OpenAISpeechToText, mp3_path: Path) -> str:
    """Run Whisper with segment timestamps and return SRT text."""
    # Whisper transcribe expects a file-like object or bytes, not a path.
    with open(mp3_path, "rb") as fp:
        audio_bytes = fp.read()
    resp = await stt.transcribe(
        file=(mp3_path.name, audio_bytes, "audio/mpeg"),
        model="whisper-1",
        response_format="verbose_json",
        timestamp_granularities=["segment"],
    )
    # resp shape may be pydantic-like or dict. Support both.
    if hasattr(resp, "segments"):
        segments = resp.segments
    elif isinstance(resp, dict):
        segments = resp.get("segments", [])
    else:
        # As a last resort, parse .json()
        segments = getattr(resp, "json", lambda: {})().get("segments", [])
    return _segments_to_srt(segments)


async def main() -> None:
    key = os.getenv("EMERGENT_LLM_KEY")
    if not key:
        sys.exit("EMERGENT_LLM_KEY missing")

    stt = OpenAISpeechToText(api_key=key)
    for n, slug, title, text, length_hint in LESSONS:
        mp3 = VO_DIR / f"lesson-{n:02d}.mp3"
        if not mp3.exists():
            print(f"  ↷ lesson {n:02d}: mp3 missing, skipping")
            continue
        srt_path = SRT_DIR / f"lesson-{n:02d}.srt"
        if srt_path.exists() and srt_path.stat().st_size > 200:
            print(f"  ↷ lesson {n:02d}: srt already exists ({srt_path.stat().st_size} B)")
            (PUB_DIR / srt_path.name).write_bytes(srt_path.read_bytes())
            continue
        print(f"  → lesson {n:02d}: transcribing …", end=" ", flush=True)
        try:
            srt = await transcribe_one(stt, mp3)
            srt_path.write_text(srt, encoding="utf-8")
            (PUB_DIR / srt_path.name).write_text(srt, encoding="utf-8")
            print(f"{len(srt)} chars")
        except Exception as e:
            print(f"FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(main())
