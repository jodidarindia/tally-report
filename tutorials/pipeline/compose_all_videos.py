"""FLOWRA Academy — batch video composer.

Produces 1920×1080 MP4s for all 30 lessons using:
  • FLOWRA-branded slide (title + subtitle + logo + lesson number badge)
  • Voiceover audio (Onyx, from previous pipeline step)
  • Subtle Ken-Burns zoom (2%) so the video isn't static
  • Optional 2-sec intro card + 2-sec outro card with logo

Design decision: v1 uses branded slides (podcast-with-visual style) rather
than full Playwright screencasts because it lets us ship all 30 uploadable
videos in a single batch. v2 (future) can replace individual lesson slides
with recorded screencasts of the actual app UI — the audio track stays
identical so no re-narration needed.

Output:
    /app/tutorials/final/lesson-NN.mp4
    /app/frontend/public/tutorials/lessons/lesson-NN.mp4     (public)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from lessons_manifest import LESSONS

# ─────────────────── Paths ────────────────────
LOGO_PATH = Path("/app/frontend/public/flowra-logo.png")
VO_DIR = Path("/app/tutorials/voiceover")
SLIDES_DIR = Path("/app/tutorials/slides")
OUT_DIR = Path("/app/tutorials/final")
PUB_DIR = Path("/app/frontend/public/tutorials/lessons")

SLIDES_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)
PUB_DIR.mkdir(parents=True, exist_ok=True)
SRT_DIR = Path("/app/tutorials/subtitles")

# ─────────────────── Design constants ─────────
W, H = 1920, 1080
BG_TOP = (15, 27, 76)       # #0F1B4C — FLOWRA navy
BG_BOT = (37, 99, 235)      # #2563EB — FLOWRA blue
ACCENT = (56, 189, 248)     # sky-400
WHITE = (255, 255, 255)
MUTED = (191, 219, 254)     # blue-200

# Try DejaVu (already used elsewhere in the app) — fall back to bundled if not.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).exists():
            if bold and "Bold" not in candidate and any("Bold" in c for c in _FONT_CANDIDATES if Path(c).exists()):
                continue
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _vertical_gradient(w: int, h: int, top, bot) -> Image.Image:
    base = Image.new("RGB", (w, h), top)
    for y in range(h):
        blend = y / max(1, h - 1)
        r = int(top[0] * (1 - blend) + bot[0] * blend)
        g = int(top[1] * (1 - blend) + bot[1] * blend)
        b = int(top[2] * (1 - blend) + bot[2] * blend)
        ImageDraw.Draw(base).line([(0, y), (w, y)], fill=(r, g, b))
    return base


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list:
    """Simple word-wrap so long lesson titles don't run off the slide."""
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        w = font.getbbox(test)[2]
        if w <= max_w or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def build_slide(n: int, title: str, out_path: Path) -> None:
    """Compose the branded slide PNG for one lesson."""
    img = _vertical_gradient(W, H, BG_TOP, BG_BOT)
    draw = ImageDraw.Draw(img)

    # Faint decorative gridlines (very subtle)
    for x in range(0, W, 120):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 8), width=1)

    # Top-left logo (48% opacity feel via paste with alpha)
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        # Scale to 240 wide
        ratio = 240 / logo.width
        logo = logo.resize((240, int(logo.height * ratio)), Image.LANCZOS)
        img.paste(logo, (100, 80), logo)
    except Exception as e:
        print(f"  ⚠ Logo not loaded: {e}")

    # Top-right: FLOWRA Academy wordmark
    wm_font = _font(28, bold=True)
    text = "FLOWRA ACADEMY"
    w = wm_font.getbbox(text)[2]
    draw.text((W - w - 100, 100), text, fill=MUTED, font=wm_font)
    sub_font = _font(18)
    sub_text = f"Lesson {n:02d} of 30"
    sw = sub_font.getbbox(sub_text)[2]
    draw.text((W - sw - 100, 140), sub_text, fill=ACCENT, font=sub_font)

    # Lesson number circle badge — center-left
    circle_x, circle_y, radius = 220, H // 2, 90
    draw.ellipse((circle_x - radius, circle_y - radius,
                  circle_x + radius, circle_y + radius),
                 outline=ACCENT, width=6)
    num_font = _font(78, bold=True)
    ntext = f"{n:02d}"
    nw, nh = num_font.getbbox(ntext)[2], num_font.getbbox(ntext)[3]
    draw.text((circle_x - nw // 2, circle_y - nh // 2 - 8), ntext, fill=WHITE, font=num_font)

    # Title (wrapped) — right of the badge
    title_font = _font(72, bold=True)
    lines = _wrap(title, title_font, max_w=W - 470)
    y = circle_y - (len(lines) * 90) // 2
    for line in lines:
        draw.text((360, y), line, fill=WHITE, font=title_font)
        y += 90

    # Subtitle strip at bottom
    strip_h = 100
    draw.rectangle((0, H - strip_h, W, H), fill=(0, 0, 0, 90))
    footer_font = _font(24)
    # iter-126: shortened footer to make room for the copyright line —
    # helps discourage clone-uploads to competing YouTube channels.
    draw.text((100, H - strip_h + 22),
              "FLOWRA Academy  •  Voice: Onyx  •  flowralive.in",
              fill=MUTED, font=footer_font)
    copyright_font = _font(18)
    draw.text((100, H - strip_h + 58),
              "© 2026 FLOWRA. All rights reserved. Unauthorised re-upload prohibited.",
              fill=(148, 163, 184), font=copyright_font)
    # Bottom right — YouTube-style call-out
    cta_font = _font(24, bold=True)
    cta = "▶ Subscribe for more"
    cw = cta_font.getbbox(cta)[2]
    draw.text((W - cw - 100, H - strip_h + 34), cta, fill=ACCENT, font=cta_font)

    img.convert("RGB").save(out_path, "PNG", optimize=True)


def compose_video(n: int, slide_path: Path, audio_path: Path, out_path: Path,
                  srt_path: Path = None) -> None:
    """Combine slide + voiceover into MP4 with subtle Ken-Burns zoom.

    iter-126:
      - Burns SRT captions if provided (Hinglish, bottom of frame).
      - Adds a persistent © FLOWRA watermark bottom-right so re-uploads
        anywhere else are visibly branded — an IP-protection measure.
    """
    # ffprobe to get audio duration
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    duration = float(r.stdout.strip())
    total_frames = max(60, int(duration * 30))

    # Ken-Burns: subtle 2% zoom in over duration
    zoom_filter = (
        f"zoompan=z='min(zoom+0.0006,1.02)':x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={W}x{H}:fps=30"
    )
    # Persistent watermark drawtext (small, top-right, alpha 0.65)
    watermark = (
        f"drawtext=text='© FLOWRA · flowralive.in':"
        f"fontsize=22:fontcolor=white@0.65:x=w-tw-40:y=40"
    )

    filters = [zoom_filter, watermark]
    # Prefer the ASS file (proper PlayResX/Y + Alignment=2 baked in).
    ass_path = srt_path.with_name(srt_path.stem + "-horizontal.ass") if srt_path else None
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


def main() -> None:
    if not LOGO_PATH.exists():
        print(f"⚠ FLOWRA logo missing at {LOGO_PATH} — will render slides without logo")

    for n, slug, title, text, length_hint in LESSONS:
        audio = VO_DIR / f"lesson-{n:02d}.mp3"
        if not audio.exists():
            print(f"  ↷ Lesson {n:02d} — audio missing at {audio}, skipping")
            continue

        slide = SLIDES_DIR / f"lesson-{n:02d}.png"
        final = OUT_DIR / f"lesson-{n:02d}.mp4"
        public = PUB_DIR / f"lesson-{n:02d}.mp4"
        srt = SRT_DIR / f"lesson-{n:02d}.srt"

        # iter-126: always re-render — we now bake in captions + watermark.
        # (Cache guard removed: prior rendered files predate IP protection.)
        print(f"  → Lesson {n:02d} — {title[:60]}")
        build_slide(n, title, slide)
        try:
            compose_video(n, slide, audio, final, srt_path=srt if srt.exists() else None)
            public.write_bytes(final.read_bytes())
            print(f"     ✓ {final.stat().st_size // 1024} KB")
        except subprocess.CalledProcessError as e:
            print(f"     ✗ ffmpeg failed: {e.stderr.decode()[:400]}")

    print("\n✅ Batch complete.")


if __name__ == "__main__":
    main()
