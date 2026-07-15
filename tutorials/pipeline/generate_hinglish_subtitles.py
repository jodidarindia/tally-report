"""FLOWRA Academy — Hinglish SRT generator from source scripts.

We chose NOT to use Whisper because it transcribes Hinglish audio into
Devanagari (Hindi script), while the source scripts (and the audience) are
in Hinglish (Roman script). Instead, we split the original manifest text
into sentence-sized caption lines and distribute them across the known
audio duration proportionally to character count — accurate enough for a
90–180 sec tutorial and 100% correct spelling.

Output:
    /app/tutorials/subtitles/lesson-NN.srt
    /app/frontend/public/tutorials/lessons/lesson-NN.srt   (public)
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lessons_manifest import LESSONS

VO_DIR = Path("/app/tutorials/voiceover")
SRT_DIR = Path("/app/tutorials/subtitles")
PUB_DIR = Path("/app/frontend/public/tutorials/lessons")
SRT_DIR.mkdir(parents=True, exist_ok=True)


def _fmt_ts(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    ms = int((secs - int(secs)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _duration_of(mp3: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(mp3)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def _split_into_lines(text: str) -> list:
    """Split at sentence/comma boundaries so each caption is a natural chunk
    of ~5–12 words (comfortable reading pace at TV subtitle standards)."""
    # Break on ! . ?  — then if any chunk still >90 chars, split on em-dash / comma.
    raw = re.split(r"(?<=[\.!?])\s+", text.strip())
    lines = []
    for chunk in raw:
        if not chunk.strip():
            continue
        if len(chunk) <= 90:
            lines.append(chunk.strip())
        else:
            # Sub-split at em-dash or comma boundaries
            parts = re.split(r"\s*[—–,]\s*", chunk)
            buf = ""
            for p in parts:
                if not p.strip():
                    continue
                if len(buf) + len(p) + 2 <= 90:
                    buf = (buf + " " + p).strip() if buf else p.strip()
                else:
                    if buf:
                        lines.append(buf)
                    buf = p.strip()
            if buf:
                lines.append(buf)
    # Guarantee no line ends without punctuation for readability
    return [ln.rstrip(" ,") for ln in lines if ln.strip()]


def build_srt(lines: list, duration: float) -> str:
    """Distribute lines across `duration` proportionally to their length."""
    if not lines:
        return ""
    total_chars = sum(len(ln) for ln in lines) or 1
    out = []
    t = 0.0
    for i, ln in enumerate(lines, start=1):
        share = duration * (len(ln) / total_chars)
        # Enforce a minimum on-screen time so 3-word lines don't flash
        share = max(share, 1.4)
        start = t
        end = min(duration, t + share)
        out.append(f"{i}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{ln}\n")
        t = end
    return "\n".join(out)


def main() -> None:
    for n, slug, title, text, length_hint in LESSONS:
        mp3 = VO_DIR / f"lesson-{n:02d}.mp3"
        if not mp3.exists():
            print(f"  ↷ lesson {n:02d}: mp3 missing")
            continue
        duration = _duration_of(mp3)
        lines = _split_into_lines(text)
        srt = build_srt(lines, duration)

        srt_path = SRT_DIR / f"lesson-{n:02d}.srt"
        srt_path.write_text(srt, encoding="utf-8")
        (PUB_DIR / srt_path.name).write_text(srt, encoding="utf-8")
        print(f"  ✓ lesson {n:02d} — {len(lines)} lines · {duration:.1f} sec · {srt_path.stat().st_size} B")


if __name__ == "__main__":
    main()
