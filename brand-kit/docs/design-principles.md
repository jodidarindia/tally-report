# FLOWRA Design Principles

The brand goal: **calm confidence**. Every FLOWRA app should feel like talking to a smart, soft-spoken Indian CA who has 20 years of experience and never raises their voice.

## 1. Calm over loud
- Generous whitespace (2–3× more than feels comfortable)
- Single accent color per page; never compete for attention
- No pop-ups, modals, or banners unless action is *required*

## 2. Density when earned
- Inside the apps (post-login), density is fine — power users want it
- Marketing pages stay airy and editorial

## 3. Asymmetric > centered
- Left-aligned hero text reads naturally
- Centered layouts feel generic; use only for confirmation states

## 4. Motion with purpose
- Page enters: stagger reveal (60–90ms apart)
- Hover states: subtle lift (translateY -2px) + shadow grow
- Avoid: spinning, bouncing, or any motion > 500ms unless user-initiated

## 5. Type hierarchy is the layout
- Hero (H1): 56–72px, weight 700, tight tracking
- Section (H2): 32–40px, weight 600
- Body: 16px on mobile, 17px on desktop, 1.6 line-height
- Caption: 13px, color `text-subtle`

## 6. Color rules
- **Primary (#2563EB)** — actions only (buttons, active states, links)
- **Accent (#7C3AED)** — premium / AI features only
- **Success / Warning / Danger** — system feedback only, never decoration
- Backgrounds stay neutral; let content provide color

## 7. Iconography
- Lucide-react throughout (already installed in Insights)
- 16px in dense contexts, 20px in cards, 28–40px in hero illustrations
- Stroke weight always 1.5
- Never mix icon families

## 8. Imagery
- No stock photos with people — they look fake
- Prefer abstract gradients, product screenshots, or hand-drawn illustrations
- All images optimized to ≤ 100kb (WebP > PNG > JPG)

## 9. Forms
- Labels above inputs, never floating
- Error messages: `text-flowra-danger`, below the input, max 1 line
- Required fields marked with red asterisk, never with the word "required"

## 10. Voice (copy)
- Indian English, not American (use "favourable", "organisation")
- Active voice; second-person ("You" not "Users")
- Avoid jargon; if a CA wouldn't say it, don't write it
- Numbers: ₹ prefix, comma per Indian system (1,67,17,990)
- Dates: DD-MMM-YYYY (e.g., 24-Apr-2026)

## Anti-patterns to avoid

- ❌ Purple gradients on white backgrounds (AI-slop signature)
- ❌ Inter on every screen of every product (varied hierarchies > one font monoculture)
- ❌ `transition: all` (breaks transforms; specify properties)
- ❌ Three columns of equal-width centered cards
- ❌ Stock-photo people smiling at laptops
- ❌ "Get started today" / "Unleash" / "Revolutionary" / "Game-changing"

## Reference inspiration

Linear · Stripe · Vercel · Plaid · Notion (recent) · Cred (Indian polish)
