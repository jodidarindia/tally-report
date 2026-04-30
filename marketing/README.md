# FLOWRA Marketing Site (`flowralive.in`)

The static landing page for the FLOWRA Suite. Deployed at the apex domain
`flowralive.in` (and `www.flowralive.in`).

## Stack

- **Pure HTML + Tailwind CDN + Google Fonts** — single file (`index.html`), no build step
- **Imports `tokens.css`** from the brand-kit so design always matches the apps
- **Total size**: ~30 KB HTML + ~70 KB Tailwind CDN script + fonts → loads under 1 s on 4G
- **Lighthouse target**: 100/100/100/100

## File map

```
marketing/
├── index.html             # The landing page (single source of truth)
├── assets/
│   ├── favicon.svg        # Brand favicon
│   └── tokens.css         # Copy of @flowra/brand-kit/tokens.css
├── vercel.json            # Vercel deploy config (headers + redirects)
├── _headers               # Cloudflare Pages headers
├── _redirects             # Cloudflare Pages redirects (also valid for Netlify)
└── README.md              # This file
```

## Local preview

```bash
cd /app/marketing
python3 -m http.server 8080
# → http://localhost:8080
```

Or any static-file server: `npx serve` / `php -S localhost:8080` etc.

## Deployment options (recommended order)

### 1. Cloudflare Pages — FREE, unlimited bandwidth (recommended)
1. Push `marketing/` to a GitHub repo (e.g., `flowra-marketing`)
2. Cloudflare → Pages → Create project → Connect repo
3. Build settings: **none** (it's a static site, no build step)
4. Output directory: `/` (root)
5. Add custom domain `flowralive.in` and `www.flowralive.in` in project settings
6. Cloudflare auto-issues SSL certs and points DNS — done in <5 min

### 2. Vercel — FREE for the Hobby tier
1. Push to GitHub
2. Vercel → Import Project → pick the repo
3. Framework preset: **Other** (no build)
4. `vercel.json` already configured for headers + redirects
5. Add `flowralive.in` in Domains → follow DNS instructions

### 3. DigitalOcean App Platform Static Site — ₹0 (free static plan)
1. Apps → Create App → GitHub source
2. Resource type: **Static Site**, no build command
3. Add `flowralive.in` as custom domain

## DNS records to set (any registrar)

If using Cloudflare Pages:
```
flowralive.in       CNAME  flowra-marketing.pages.dev   (Cloudflare auto-creates)
www.flowralive.in   CNAME  flowralive.in
```

If using Vercel:
```
flowralive.in       A      76.76.21.21
www.flowralive.in   CNAME  cname.vercel-dns.com
```

## What to update later

| When you launch | Update |
|----------------|--------|
| Insights paid tier | Add pricing card section |
| Tasks app | Change "Coming soon" → "Live" badge in tool card |
| Loyalty app | Same |
| New tool | Duplicate a tool-card block in `index.html`, update icon/colors/copy |

## Updating the brand kit

The landing page imports `assets/tokens.css`. When the brand kit changes:
```bash
cp /app/brand-kit/tokens.css /app/marketing/assets/tokens.css
```
(Will be automated once we publish `@flowra/brand-kit` to npm.)

## Mandatory before going live

- [ ] Replace `hello@flowralive.in` with the real support inbox (Resend / Zoho / Gmail)
- [ ] Add `og-cover.png` (1200×630) to `assets/` for social sharing previews
- [ ] Privacy & Terms pages (use templates from `brand-kit/legal/`)
- [ ] Verify SSL certs after DNS pointed
- [ ] Run Lighthouse — target 100 across the board
