"""Generate FLOWRA Insights visiting card.

Outputs (saved to /app/frontend/public/cards/):
  flowra_card_front.png   — Ankit Sarawgi side, print-ready 300 DPI + bleed
  flowra_card_back.png    — Brand panel side
  flowra_card_combined.png — Side-by-side preview for screen viewing
  flowra_card_print.pdf   — Both sides on a single A4, ready for printer

Card spec (Indian standard):
  Trim size: 90 × 54 mm  (1063 × 638 px @ 300 DPI)
  Bleed:     3 mm all sides → canvas 96 × 60 mm (1134 × 709 px)
  Safe area: 3 mm inside trim (so content stays ≥6 mm from canvas edge)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

OUT = Path("/app/frontend/public/cards")
OUT.mkdir(parents=True, exist_ok=True)

# ───── BRAND ──────────────────────────────────────────────────────────────
NAVY = (15, 27, 76)        # #0F1B4C
BLUE = (37, 99, 235)       # #2563EB
AMBER = (245, 158, 11)     # #f59e0b
PAPER = (255, 255, 255)
SOFT = (240, 244, 255)     # #F0F4FF
GREY = (100, 116, 139)     # #64748B
DARK = (15, 23, 42)        # #0F172A

# ───── GEOMETRY (px @ 300 DPI) ────────────────────────────────────────────
DPI = 300
MM = DPI / 25.4
TRIM_W = int(90 * MM)
TRIM_H = int(54 * MM)
BLEED = int(3 * MM)
CANVAS_W = TRIM_W + 2 * BLEED
CANVAS_H = TRIM_H + 2 * BLEED

# ───── FONTS ──────────────────────────────────────────────────────────────
FONT_DIR = "/usr/share/fonts/truetype/liberation"
F_BOLD = f"{FONT_DIR}/LiberationSans-Bold.ttf"
F_REG = f"{FONT_DIR}/LiberationSans-Regular.ttf"
F_ITAL = f"{FONT_DIR}/LiberationSans-Italic.ttf"


def font(size, weight="regular"):
    path = {"regular": F_REG, "bold": F_BOLD, "italic": F_ITAL}[weight]
    return ImageFont.truetype(path, size)


# ───── HELPERS ────────────────────────────────────────────────────────────
def text(d, xy, s, *, fnt, color, anchor="la"):
    d.text(xy, s, font=fnt, fill=color, anchor=anchor)


def text_width(s, fnt):
    bbox = fnt.getbbox(s)
    return bbox[2] - bbox[0]


def draw_wordmark(d, x, y, *, size=44, primary=NAVY, accent=BLUE):
    """FLOWRA wordmark — uppercase, letter-spaced, with amber dot."""
    f = font(size, "bold")
    # Draw the letters with kerning by hand
    word = "FLOWRA"
    space = int(size * 0.06)
    cx = x
    for i, ch in enumerate(word):
        text(d, (cx, y), ch, fnt=f, color=primary)
        cx += text_width(ch, f) + space
    # Trailing accent dot
    dot_r = int(size * 0.10)
    d.ellipse((cx + space, y + int(size * 0.78) - dot_r,
               cx + space + dot_r * 2, y + int(size * 0.78) + dot_r), fill=accent)
    return cx + space + dot_r * 2


# ───── ICONS (tiny vector dots) ───────────────────────────────────────────
def icon_email(d, x, y, size=22, color=BLUE):
    # Envelope outline
    pad = 1
    d.rectangle((x, y, x + size, y + int(size * 0.7)),
                outline=color, width=2)
    d.line([(x, y), (x + size // 2, y + int(size * 0.45)),
            (x + size, y)], fill=color, width=2)


def icon_phone(d, x, y, size=22, color=BLUE):
    d.rounded_rectangle((x + size * 0.18, y, x + size * 0.82, y + size),
                        radius=int(size * 0.16), outline=color, width=2)
    d.line([(x + size * 0.4, y + size * 0.86),
            (x + size * 0.6, y + size * 0.86)], fill=color, width=2)


def icon_web(d, x, y, size=22, color=BLUE):
    d.ellipse((x, y, x + size, y + size), outline=color, width=2)
    d.line([(x, y + size // 2), (x + size, y + size // 2)], fill=color, width=2)
    d.line([(x + size // 2, y), (x + size // 2, y + size)], fill=color, width=2)
    d.arc((x + size * 0.15, y, x + size * 0.85, y + size), 0, 360, fill=color, width=1)


def icon_pin(d, x, y, size=22, color=BLUE):
    d.ellipse((x + size * 0.18, y, x + size * 0.82, y + size * 0.62),
              outline=color, width=2)
    d.polygon([(x + size * 0.34, y + size * 0.5),
               (x + size * 0.5, y + size),
               (x + size * 0.66, y + size * 0.5)], fill=color)


# ───── FRONT SIDE — Ankit Sarawgi ─────────────────────────────────────────
def render_front(path):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), PAPER)
    d = ImageDraw.Draw(img)

    # Left navy panel (40% width)
    panel_w = int(CANVAS_W * 0.40)
    d.rectangle((0, 0, panel_w, CANVAS_H), fill=NAVY)

    # Diagonal amber accent on the navy panel (subtle)
    accent_h = int(CANVAS_H * 0.08)
    d.rectangle((0, CANVAS_H - BLEED - accent_h,
                 panel_w, CANVAS_H - BLEED - accent_h + int(4 * MM / 1.5)),
                fill=AMBER)

    # Decorative dotted grid on navy panel (apply ONLY inside the panel)
    panel_layer = Image.new("RGBA", (panel_w, CANVAS_H), (15, 27, 76, 255))
    pl_draw = ImageDraw.Draw(panel_layer)
    for gy in range(BLEED + int(8 * MM), CANVAS_H - BLEED, int(8 * MM)):
        for gx in range(BLEED + int(8 * MM), panel_w - int(6 * MM), int(8 * MM)):
            pl_draw.ellipse((gx, gy, gx + 3, gy + 3), fill=(255, 255, 255, 35))
    img.paste(panel_layer, (0, 0))
    d = ImageDraw.Draw(img)
    # Re-paint the amber accent strip on the navy panel
    d.rectangle((0, CANVAS_H - BLEED - accent_h,
                 panel_w, CANVAS_H - BLEED - accent_h + int(4 * MM / 1.5)),
                fill=AMBER)

    # FLOWRA wordmark (white) on navy panel
    wm_x = BLEED + int(6 * MM)
    wm_y = BLEED + int(8 * MM)
    word = "FLOWRA"
    wm_size = int(panel_w * 0.13)
    f = font(wm_size, "bold")
    cx = wm_x
    spacing = int(wm_size * 0.06)
    for ch in word:
        text(d, (cx, wm_y), ch, fnt=f, color=PAPER)
        cx += text_width(ch, f) + spacing
    # Amber dot
    dot_r = int(wm_size * 0.10)
    d.ellipse((cx + spacing,
               wm_y + int(wm_size * 0.78) - dot_r,
               cx + spacing + dot_r * 2,
               wm_y + int(wm_size * 0.78) + dot_r),
              fill=AMBER)

    # "INSIGHTS" tagword
    text(d, (wm_x, wm_y + wm_size + int(2 * MM)), "INSIGHTS",
         fnt=font(int(wm_size * 0.36), "bold"), color=(180, 200, 255))

    # Vertical brand tagline at the bottom of the navy panel
    tag = "Organize. Automate."
    tag2 = "Accelerate."
    tf = font(int(wm_size * 0.40), "italic")
    text(d, (wm_x, CANVAS_H - BLEED - int(20 * MM)), tag,
         fnt=tf, color=(200, 215, 255))
    text(d, (wm_x, CANVAS_H - BLEED - int(20 * MM) + int(wm_size * 0.5)),
         tag2, fnt=tf, color=(200, 215, 255))

    # ─── Right side (white) — Founder card ──────────────────────────────
    cx = panel_w + int(6 * MM)
    cy = BLEED + int(7 * MM)

    # Name
    name_font = font(int(panel_w * 0.13), "bold")
    text(d, (cx, cy), "Ankit Sarawgi", fnt=name_font, color=NAVY)
    cy += int(panel_w * 0.16)

    # Designation
    text(d, (cx, cy), "Founder", fnt=font(int(panel_w * 0.07), "bold"),
         color=BLUE)
    cy += int(panel_w * 0.10)

    # Thin underline
    d.rectangle((cx, cy, cx + int(20 * MM), cy + 2), fill=AMBER)
    cy += int(4 * MM)

    # Core team line (small italic)
    text(d, (cx, cy), "Core Team: Punit · Kritika",
         fnt=font(int(panel_w * 0.05), "italic"), color=GREY)
    cy += int(panel_w * 0.075)

    # Company line
    text(d, (cx, cy), "Jodidar India  ·  Raipur",
         fnt=font(int(panel_w * 0.055), "bold"), color=NAVY)
    cy += int(panel_w * 0.10)

    # Contact block — icons + values
    line_gap = int(panel_w * 0.085)
    icon_size = int(panel_w * 0.055)
    label_font = font(int(panel_w * 0.058), "regular")

    rows = [
        (icon_phone, "+91 81204 70018"),
        (icon_email, "support@flowralive.in"),
        (icon_web, "www.flowralive.in"),
    ]
    for icn, val in rows:
        icn(d, cx, cy, size=icon_size, color=BLUE)
        text(d, (cx + icon_size + int(2.5 * MM), cy + int(icon_size * 0.05)),
             val, fnt=label_font, color=DARK)
        cy += line_gap

    img.save(path, dpi=(DPI, DPI), quality=95)


# ───── BACK SIDE — Brand panel ────────────────────────────────────────────
def render_back(path):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), NAVY)
    d = ImageDraw.Draw(img)

    # Diagonal blue strip (subtle)
    d.polygon([(0, CANVAS_H * 0.55),
               (CANVAS_W, CANVAS_H * 0.30),
               (CANVAS_W, CANVAS_H * 0.42),
               (0, CANVAS_H * 0.67)],
              fill=(25, 50, 115))

    # Dotted texture (sparse)
    for gy in range(BLEED + int(6 * MM), CANVAS_H - BLEED, int(7 * MM)):
        for gx in range(BLEED + int(6 * MM), CANVAS_W - BLEED, int(7 * MM)):
            d.ellipse((gx, gy, gx + 2, gy + 2),
                      fill=(255, 255, 255))
    # Slight darkening overlay
    overlay = Image.new("RGBA", img.size, (15, 27, 76, 215))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)

    # Central FLOWRA wordmark
    word = "FLOWRA"
    wm_size = int(CANVAS_W * 0.11)
    f = font(wm_size, "bold")
    spacing = int(wm_size * 0.08)
    total_w = sum(text_width(ch, f) + spacing for ch in word) + int(wm_size * 0.4)
    cx = (CANVAS_W - total_w) // 2
    cy = int(CANVAS_H * 0.32)
    for ch in word:
        text(d, (cx, cy), ch, fnt=f, color=PAPER)
        cx += text_width(ch, f) + spacing
    dot_r = int(wm_size * 0.10)
    d.ellipse((cx + spacing, cy + int(wm_size * 0.78) - dot_r,
               cx + spacing + dot_r * 2, cy + int(wm_size * 0.78) + dot_r),
              fill=AMBER)

    # INSIGHTS sub-word
    sub_font = font(int(wm_size * 0.38), "bold")
    sub = "INSIGHTS"
    sub_w = text_width(sub, sub_font)
    text(d, ((CANVAS_W - sub_w) // 2, cy + int(wm_size * 1.1)),
         sub, fnt=sub_font, color=(180, 200, 255))

    # Tagline
    tag = "Organize. Automate. Accelerate."
    tagf = font(int(CANVAS_W * 0.038), "italic")
    tw = text_width(tag, tagf)
    text(d, ((CANVAS_W - tw) // 2, cy + int(wm_size * 1.85)),
         tag, fnt=tagf, color=(200, 215, 255))

    # Bottom amber strip
    strip_h = int(7 * MM)
    d.rectangle((0, CANVAS_H - BLEED - strip_h, CANVAS_W, CANVAS_H - BLEED),
                fill=AMBER)
    foot_font = font(int(CANVAS_W * 0.034), "bold")
    foot = "Built for Indian SMEs  ·  flowralive.in"
    fw = text_width(foot, foot_font)
    text(d, ((CANVAS_W - fw) // 2, CANVAS_H - BLEED - strip_h + int(1.8 * MM)),
         foot, fnt=foot_font, color=NAVY)

    img.save(path, dpi=(DPI, DPI), quality=95)


def render_preview(front_path, back_path, out_path):
    """Side-by-side preview at half-resolution for fast on-screen viewing."""
    f = Image.open(front_path)
    b = Image.open(back_path)
    scale = 0.5
    fw, fh = int(f.width * scale), int(f.height * scale)
    f = f.resize((fw, fh), Image.LANCZOS)
    b = b.resize((fw, fh), Image.LANCZOS)
    gap = 30
    canvas = Image.new("RGB", (fw * 2 + gap * 3, fh + gap * 2), (242, 245, 251))
    canvas.paste(f, (gap, gap))
    canvas.paste(b, (gap * 2 + fw, gap))
    canvas.save(out_path, quality=92)


def render_print_pdf(front_path, back_path, out_path):
    """Both sides on a single A4 with crop marks — ready for the printer."""
    c = rl_canvas.Canvas(out_path, pagesize=A4)
    page_w, page_h = A4
    card_w, card_h = 90 * mm, 54 * mm
    # Front placement (top-centre)
    fx = (page_w - card_w) / 2
    fy = page_h - 30 * mm - card_h
    c.drawImage(front_path, fx, fy, width=card_w, height=card_h)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.3)
    _crop_marks(c, fx, fy, card_w, card_h)

    # Back placement (below front)
    bx = (page_w - card_w) / 2
    by = fy - 20 * mm - card_h
    c.drawImage(back_path, bx, by, width=card_w, height=card_h)
    _crop_marks(c, bx, by, card_w, card_h)

    # Labels
    c.setFillColorRGB(0.39, 0.45, 0.55)
    c.setFont("Helvetica", 8)
    c.drawString(fx, fy + card_h + 4 * mm, "FRONT — Ankit Sarawgi")
    c.drawString(bx, by + card_h + 4 * mm, "BACK — Brand panel")
    c.setFont("Helvetica-Oblique", 7)
    c.drawString(20 * mm, 15 * mm,
                 "FLOWRA Insights · Jodidar India · Raipur  —  Print at 300 DPI on 350 gsm matte stock.  Includes 3 mm bleed.")
    c.showPage()
    c.save()


def _crop_marks(c, x, y, w, h, length=4 * mm):
    for cx, cy in [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]:
        c.line(cx - length, cy, cx, cy)
        c.line(cx, cy - length, cx, cy)
        # Outward marks
        c.line(cx, cy, cx + (length if cx == x + w else -length), cy)
        c.line(cx, cy, cx, cy + (length if cy == y + h else -length))


# ────────────────────────────────────────────────────────────────────────────
def main():
    front = OUT / "flowra_card_front.png"
    back = OUT / "flowra_card_back.png"
    preview = OUT / "flowra_card_preview.png"
    pdf = OUT / "flowra_card_print.pdf"

    render_front(str(front))
    print(f"✓ {front}  ({front.stat().st_size:,} bytes)")
    render_back(str(back))
    print(f"✓ {back}  ({back.stat().st_size:,} bytes)")
    render_preview(str(front), str(back), str(preview))
    print(f"✓ {preview}  ({preview.stat().st_size:,} bytes)")
    render_print_pdf(str(front), str(back), str(pdf))
    print(f"✓ {pdf}  ({pdf.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
