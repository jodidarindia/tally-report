"""FLOWRA Academy — final composer for real screencast lessons.

Combines:
  • WebM screencast (Playwright)           /app/tutorials/recordings/lesson-NN.webm
  • Onyx voiceover                          /app/tutorials/voiceover/lesson-NN.mp3
  • Vertical/horizontal ASS captions        /app/tutorials/subtitles/lesson-NN-horizontal.ass
  • Persistent © FLOWRA watermark
  • End-cap that freezes the last frame if the video is shorter than audio

Output:
    /app/tutorials/final/lesson-NN.mp4
    /app/frontend/public/tutorials/lessons/lesson-NN.mp4    (public)
"""
import subprocess
import sys
from pathlib import Path

REC = Path("/app/tutorials/recordings")
VO = Path("/app/tutorials/voiceover")
ASS = Path("/app/tutorials/subtitles")
OUT = Path("/app/tutorials/final")
PUB = Path("/app/frontend/public/tutorials/lessons")


def _dur(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def compose(n: int) -> Path:
    webm = REC / f"lesson-{n:02d}.webm"
    mp3 = VO / f"lesson-{n:02d}.mp3"
    ass = ASS / f"lesson-{n:02d}-horizontal.ass"
    out = OUT / f"lesson-{n:02d}.mp4"

    if not (webm.exists() and mp3.exists()):
        raise SystemExit(f"Missing inputs for lesson {n}")

    vdur = _dur(webm)
    adur = _dur(mp3)
    pad = max(0.0, adur - vdur + 0.5)  # freeze-hold to cover audio tail
    total = max(vdur + pad, adur)

    watermark = (
        "drawtext=text='© FLOWRA · flowralive.in':fontsize=22:"
        "fontcolor=white@0.85:box=1:boxcolor=black@0.35:boxborderw=8:"
        "x=w-tw-30:y=30"
    )
    # tpad freezes the last frame to fill audio duration
    tpad = f"tpad=stop_mode=clone:stop_duration={pad:.2f}"
    ass_arg = str(ass).replace(":", r"\:")
    ass_filter = f"ass='{ass_arg}'" if ass.exists() else "null"

    vf = f"scale=1920:1080,{tpad},{watermark},{ass_filter}"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-i", str(webm),
        "-i", str(mp3),
        "-vf", vf,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total:.2f}",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / out.name).write_bytes(out.read_bytes())
    print(f"✓ Lesson {n:02d}: {out.stat().st_size // 1024} KB · "
          f"video {vdur:.1f}s + freeze {pad:.1f}s = audio {adur:.1f}s")
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: compose_screencast.py <lesson-n | all>")
        sys.exit(1)
    if sys.argv[1] == "all":
        for f in sorted(REC.glob("lesson-*.webm")):
            n = int(f.stem.split("-")[1])
            compose(n)
    else:
        compose(int(sys.argv[1]))


if __name__ == "__main__":
    main()
