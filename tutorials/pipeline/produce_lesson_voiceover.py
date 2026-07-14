"""Produce Lesson 01 voiceover — final production audio.

Reads the Hinglish script from /app/tutorials/scripts/lesson-01-flowra-kya-hai.md,
extracts the VOICEOVER SCRIPT block, and renders it via OpenAI tts-1-hd
using the currently-locked voice (default: echo).

Output:
    /app/tutorials/voiceover/lesson-01.mp3
"""
import asyncio
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.openai import OpenAITextToSpeech

load_dotenv("/app/backend/.env")

SCRIPT_PATH = Path("/app/tutorials/scripts/lesson-01-flowra-kya-hai.md")
OUT_PATH = Path("/app/tutorials/voiceover/lesson-01.mp3")
VOICE = os.getenv("FLOWRA_ACADEMY_VOICE", "echo")   # male voice locked
MODEL = "tts-1-hd"


def _extract_voiceover(md: str) -> str:
    """Grab the block between '## VOICEOVER SCRIPT' and the next H2."""
    m = re.search(r"## VOICEOVER SCRIPT.*?\n(.*?)\n## ", md, re.DOTALL)
    if not m:
        sys.exit("Could not find VOICEOVER SCRIPT section in Lesson-01 MD")
    raw = m.group(1)
    # Strip markdown blockquote markers and collapse to a single flowing block
    lines = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith(">"):
            ln = ln[1:].strip()
        if ln.startswith("(") and ln.endswith(")"):
            continue    # skip parenthetical stage-directions
        lines.append(ln)
    return " ".join(lines)


async def main() -> None:
    key = os.getenv("EMERGENT_LLM_KEY")
    if not key:
        sys.exit("EMERGENT_LLM_KEY missing in /app/backend/.env")
    md = SCRIPT_PATH.read_text()
    text = _extract_voiceover(md)
    print(f"Voice: {VOICE}   Model: {MODEL}")
    print(f"Script length: {len(text)} chars  (~{len(text) / 15:.0f} sec at 15 chars/sec)")
    print(f"Preview: {text[:150]}…\n")

    tts = OpenAITextToSpeech(api_key=key)
    audio = await tts.generate_speech(
        text=text,
        model=MODEL,
        voice=VOICE,
        speed=1.0,
        response_format="mp3",
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_bytes(audio)
    print(f"✅ Wrote {OUT_PATH}  ({len(audio) // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())
