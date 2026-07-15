"""FLOWRA Academy — 9:16 vertical Shorts renderer.

Builds a 1080×1920 vertical version of any lesson for
Instagram Reels / YouTube Shorts / WhatsApp Status.

Usage:
    python /app/tutorials/pipeline/render_shorts.py 1
    python /app/tutorials/pipeline/render_shorts.py all
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from lessons_manifest import LESSONS
from compose_all_videos import LOGO_PATH, VO_DIR, SRT_DIR, _font, _vertical_gradient, _wrap, BG_TOP, BG_BOT, ACCENT, WHITE, MUTED

SHORTS_W, SHORTS_H = 1080, 1920
SHORTS_DIR = Path("/app/tutorials/shorts")
PUB_SHORTS_DIR = Path("/app/frontend/public/tutorials/lessons")
SHORTS_DIR.mkdir(parents=True, exist_ok=True)


def build_vertical_slide(n: int, title: str, out_path: Path) -> None:
    """1080×1920 branded slide optimised for vertical viewing."""
    img = _vertical_gradient(SHORTS_W, SHORTS_H, BG_TOP, BG_BOT)
    draw = ImageDraw.Draw(img)

    # Faint gridlines
    for x in range(0, SHORTS_W, 80):
        draw.line([(x, 0), (x, SHORTS_H)], fill=(255, 255, 255, 8), width=1)

    # Logo top-center — reduced size + placed higher to leave room for wordmark
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        r = 280 / logo.width
        logo = logo.resize((280, int(logo.height * r)), Image.LANCZOS)
        lx = (SHORTS_W - logo.width) // 2
        img.paste(logo, (lx, 90), logo)
        logo_bottom = 90 + logo.height
    except Exception as e:
        print(f"  ⚠ Logo not loaded: {e}")
        logo_bottom = 300

    # Wordmark — sit BELOW logo, never overlap
    wm = _font(40, bold=True)
    text = "FLOWRA ACADEMY"
    tw = wm.getbbox(text)[2]
    draw.text(((SHORTS_W - tw) // 2, logo_bottom + 30), text, fill=WHITE, font=wm)
    sf = _font(28)
    st = f"Lesson {n:02d} of 30"
    stw = sf.getbbox(st)[2]
    draw.text(((SHORTS_W - stw) // 2, logo_bottom + 90), st, fill=ACCENT, font=sf)

    # Large lesson-number badge, centered
    cx, cy, rad = SHORTS_W // 2, 820, 130
    draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad),
                 outline=ACCENT, width=8)
    num_font = _font(120, bold=True)
    ntxt = f"{n:02d}"
    nw, nh = num_font.getbbox(ntxt)[2], num_font.getbbox(ntxt)[3]
    draw.text((cx - nw // 2, cy - nh // 2 - 12), ntxt, fill=WHITE, font=num_font)

    # Title wrapped
    title_font = _font(76, bold=True)
    lines = _wrap(title, title_font, max_w=SHORTS_W - 120)
    y = 1090
    for line in lines:
        lw = title_font.getbbox(line)[2]
        draw.text(((SHORTS_W - lw) // 2, y), line, fill=WHITE, font=title_font)
        y += 90

    # Bottom copyright block
    strip_h = 220
    draw.rectangle((0, SHORTS_H - strip_h, SHORTS_W, SHORTS_H), fill=(0, 0, 0, 120))
    ff = _font(30)
    draw.text((60, SHORTS_H - strip_h + 40), "flowralive.in", fill=MUTED, font=ff)
    cta_font = _font(34, bold=True)
    cta = "▶ Full tutorial in bio"
    cw = cta_font.getbbox(cta)[2]
    draw.text((SHORTS_W - cw - 60, SHORTS_H - strip_h + 40), cta, fill=ACCENT, font=cta_font)
    cop_font = _font(22)
    draw.text((60, SHORTS_H - strip_h + 130),
              "© 2026 FLOWRA. All rights reserved. Unauthorised re-upload prohibited.",
              fill=(148, 163, 184), font=cop_font)

    img.convert("RGB").save(out_path, "PNG", optimize=True)


def render_shorts_video(n: int, slide_path: Path, audio_path: Path, srt_path: Path, out_path: Path) -> None:
    """1080×1920 h264 + burned captions + persistent watermark, uses lesson audio."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    duration = float(r.stdout.strip())
    total_frames = max(60, int(duration * 30))

    zoom = (
        f"zoompan=z='min(zoom+0.0006,1.02)':x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={SHORTS_W}x{SHORTS_H}:fps=30"
    )
    watermark = (
        f"drawtext=text='© FLOWRA':fontsize=28:fontcolor=white@0.65:"
        f"x=w-tw-30:y=40"
    )
    filters = [zoom, watermark]
    # Prefer the ASS file (has proper PlayResX/Y + Alignment=2 baked in).
    ass_path = srt_path.with_name(srt_path.stem + "-vertical.ass") if srt_path else None
    if ass_path and ass_path.exists():
        ass_arg = str(ass_path).replace(":", r"\:")
        filters.append(f"ass='{ass_arg}'")
    elif srt_path and srt_path.exists():
        srt_arg = str(srt_path).replace(":", r"\:")
        filters.append(f"subtitles='{srt_arg}'")
    vf = ",".join(filters)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-loop", "1", "-framerate", "30", "-i", str(slide_path),
        "-i", str(audio_path),
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-t", f"{duration:.2f}",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def render_one(n: int) -> None:
    match = next((l for l in LESSONS if l[0] == n), None)
    if not match:
        print(f"Lesson {n} not in manifest")
        return
    _, slug, title, _text, _length = match
    slide = SHORTS_DIR / f"lesson-{n:02d}-shorts.png"
    out = SHORTS_DIR / f"lesson-{n:02d}-shorts.mp4"
    pub_out = PUB_SHORTS_DIR / f"lesson-{n:02d}-shorts.mp4"
    build_vertical_slide(n, title, slide)
    render_shorts_video(n, slide, VO_DIR / f"lesson-{n:02d}.mp3",
                        SRT_DIR / f"lesson-{n:02d}.srt", out)
    pub_out.write_bytes(out.read_bytes())
    print(f"  ✓ Lesson {n:02d} Shorts — {out.stat().st_size // 1024} KB")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: render_shorts.py <lesson-n | all>")
        sys.exit(1)
    arg = sys.argv[1]
    if arg == "all":
        for n, *_ in LESSONS:
            render_one(n)
    else:
        render_one(int(arg))


if __name__ == "__main__":
    main()
