"""FLOWRA Academy — female-voice sample generator.

Produces short Hinglish samples for the 3 best female TTS voices so the
user can pick before we mass-produce all 30 lessons.

Voices sampled:
  • coral   — warm, friendly       (candidate for Owner track)
  • nova    — energetic, upbeat    (candidate for Salesman track)
  • shimmer — bright, cheerful     (candidate for Getting-Started)

Usage:
    python /app/tutorials/pipeline/generate_voice_samples.py
Output:
    /app/tutorials/voice-samples/{coral,nova,shimmer}.mp3
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.openai import OpenAITextToSpeech

load_dotenv("/app/backend/.env")

OUT = Path("/app/tutorials/voice-samples")
OUT.mkdir(parents=True, exist_ok=True)

# ~15 sec Hinglish script — same for every voice so comparison is fair.
SAMPLE_TEXT = (
    "Namaste! FLOWRA mein aapka swagat hai. "
    "Yeh video mein hum dekhenge ki apne business ko phone se kaise chalayen. "
    "Sales report, customer outstanding, aur inventory — sab kuch ek jagah. "
    "Chaliye shuru karte hain!"
)

# Only female voices per user's confirmed pick.
VOICES = ["coral", "nova", "shimmer"]


async def main() -> None:
    key = os.getenv("EMERGENT_LLM_KEY")
    if not key:
        sys.exit("EMERGENT_LLM_KEY missing in /app/backend/.env")

    tts = OpenAITextToSpeech(api_key=key)
    for voice in VOICES:
        print(f"→ Generating '{voice}' sample …", end=" ", flush=True)
        audio = await tts.generate_speech(
            text=SAMPLE_TEXT,
            model="tts-1-hd",       # HD for production quality (YouTube upload)
            voice=voice,
            speed=1.0,
            response_format="mp3",
        )
        path = OUT / f"{voice}.mp3"
        path.write_bytes(audio)
        print(f"{path}  ({len(audio) // 1024} KB)")

    print("\nDone.  Play the three files, tell me your pick.")


if __name__ == "__main__":
    asyncio.run(main())
