"""Convert SRT subtitle files into ASS with proper PlayResX/Y headers.

libass's `subtitles=` filter defaults PlayRes to 384×288 when the source
lacks a [Script Info] block, which throws off MarginV/Alignment in
force_style overrides. Producing proper ASS files avoids this class of bug.

Output:
    /app/tutorials/subtitles/lesson-NN.ass
Two flavours: horizontal (16:9) and vertical (9:16) styles.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lessons_manifest import LESSONS

SRT_DIR = Path("/app/tutorials/subtitles")

# Two style variants — horizontal (1920×1080) and vertical (1080×1920).
STYLES = {
    "horizontal": {
        "res_x": 1920, "res_y": 1080,
        "fontname": "DejaVu Sans", "fontsize": 42,
        "margin_v": 60,
    },
    "vertical": {
        "res_x": 1080, "res_y": 1920,
        "fontname": "DejaVu Sans", "fontsize": 44,
        "margin_v": 260,
    },
}


def _ts_srt_to_ass(ts: str) -> str:
    """00:00:01,399 → 0:00:01.39 (ASS)"""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    cs = int(round(int(ms) / 10))
    return f"{int(h)}:{int(m):02d}:{int(s):02d}.{cs:02d}"


def _parse_srt(text: str) -> list:
    """Return [(start, end, text)]"""
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for b in blocks:
        lines = [ln for ln in b.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        # First line is index, second is timing
        try:
            timing = next(ln for ln in lines if "-->" in ln)
        except StopIteration:
            continue
        start_ts, end_ts = [t.strip() for t in timing.split("-->")]
        text_lines = [ln for ln in lines if "-->" not in ln and not ln.strip().isdigit()]
        out.append((_ts_srt_to_ass(start_ts), _ts_srt_to_ass(end_ts), " ".join(text_lines)))
    return out


def _build_ass(cues: list, style: dict) -> str:
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {style['res_x']}\n"
        f"PlayResY: {style['res_y']}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{style['fontname']},{style['fontsize']},&H00FFFFFF,"
        f"&H000000FF,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,3,2,0,2,"
        f"60,60,{style['margin_v']},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    events = "\n".join(
        f"Dialogue: 0,{start},{end},Default,,0,0,0,,{txt}"
        for (start, end, txt) in cues
    )
    return header + events + "\n"


def main() -> None:
    for n, *_ in LESSONS:
        srt = SRT_DIR / f"lesson-{n:02d}.srt"
        if not srt.exists():
            continue
        cues = _parse_srt(srt.read_text(encoding="utf-8"))
        for variant, style in STYLES.items():
            ass = _build_ass(cues, style)
            (SRT_DIR / f"lesson-{n:02d}-{variant}.ass").write_text(ass, encoding="utf-8")
        print(f"  ✓ lesson {n:02d}: {len(cues)} cues → horizontal.ass + vertical.ass")


if __name__ == "__main__":
    main()
