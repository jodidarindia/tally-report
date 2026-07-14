"""Build YouTube copy-paste pack for all 30 lessons.

Output:
    /app/tutorials/youtube-metadata/all-lessons.md   (one big markdown file
                                                      for you to copy from)
    /app/tutorials/youtube-metadata/lesson-NN.txt    (per-lesson plain text)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lessons_manifest import LESSONS

OUT_DIR = Path("/app/tutorials/youtube-metadata")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_TAGS = [
    "flowra", "tally to cloud", "busy to cloud", "tally software",
    "business dashboard", "hindi tutorial", "hinglish", "sme software",
    "indian business", "sales report", "customer outstanding",
    "inventory management", "business automation",
]


def title_case_smart(s: str) -> str:
    """Sensible YouTube title capitalisation — first word cap, keep known
    brand words as-is."""
    fixed = {"flowra": "FLOWRA", "tally": "Tally", "busy": "Busy", "ca": "CA",
             "gst": "GST", "abc": "ABC", "pdf": "PDF", "kpi": "KPI"}
    out = []
    for i, word in enumerate(s.split()):
        lw = word.lower().strip(",.")
        if lw in fixed:
            out.append(fixed[lw])
        elif i == 0:
            out.append(word[0].upper() + word[1:])
        else:
            out.append(word)
    return " ".join(out)


LINES_PER_LESSON = []
big = ["# FLOWRA Academy — YouTube upload pack\n\nCopy-paste for every lesson.\n\n---\n"]

for n, slug, title, text, length_hint in LESSONS:
    yt_title = f"{title_case_smart(title)} | FLOWRA Academy Lesson {n}"
    if len(yt_title) > 100:
        yt_title = yt_title[:97] + "..."

    hashtags = "#FLOWRA #Tally #Busy #Hinglish"
    desc = (
        f"Lesson {n} of the FLOWRA Academy series — 30 short Hinglish tutorials "
        f"for owners, ops managers, salesmen aur CAs.\n\n"
        f"Is video mein: {title}\n\n"
        f"Aage ke videos: subscribe kar dijiye aur bell icon dabaayein.\n\n"
        f"—\n"
        f"FLOWRA: apne Tally/Busy data ko cloud pe le jaakar mobile pe access karein.\n"
        f"Website: https://flowralive.in\n"
        f"WhatsApp support: +91-XXXXX-XXXXX\n\n"
        f"{hashtags} #BusinessTutorial #SME #IndianBusiness"
    )

    tags = BASE_TAGS + [slug.replace("-", " "), f"lesson {n}"]
    tags_line = ", ".join(tags)

    block = (
        f"## Lesson {n:02d} — {title}\n"
        f"**Slug:** `{slug}`  ·  **Length:** {length_hint}\n\n"
        f"**Title (copy):**\n```\n{yt_title}\n```\n\n"
        f"**Description (copy):**\n```\n{desc}\n```\n\n"
        f"**Tags (copy):**\n```\n{tags_line}\n```\n\n"
        f"---\n"
    )
    big.append(block)

    per_path = OUT_DIR / f"lesson-{n:02d}.txt"
    per_path.write_text(
        f"=== TITLE ===\n{yt_title}\n\n=== DESCRIPTION ===\n{desc}\n\n=== TAGS ===\n{tags_line}\n"
    )

(OUT_DIR / "all-lessons.md").write_text("\n".join(big))
print(f"✅ Wrote {OUT_DIR / 'all-lessons.md'} and 30 per-lesson txt files")
