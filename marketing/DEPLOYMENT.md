# FLOWRA — Step-by-Step Deployment Guide for `flowralive.in`

This is the complete, tested path to getting the FLOWRA Suite marketing landing page
live at **https://flowralive.in** and **https://www.flowralive.in** with SSL, in under
30 minutes, using **free** services only.

---

## Recommended path: Cloudflare Pages

**Why Cloudflare Pages over Vercel/Netlify for this site:**
- Free with unlimited bandwidth (others throttle at 100 GB/mo)
- Free SSL with Cloudflare's own root certs (best in class)
- Free DDoS protection, WAF, bot mitigation
- Built-in analytics (privacy-friendly, no cookies)
- Best-of-class Indian edge POPs (Mumbai, Delhi, Chennai, Bangalore)

If you already use Vercel — same steps work. Skip to Section B.

---

## Prerequisites (5 min)

1. **A GitHub account** — free at github.com
2. **The `flowralive.in` domain** registered with any registrar (GoDaddy, Namecheap,
   Hostinger, Cloudflare Registrar, etc.)
3. **A Cloudflare account** — free at cloudflare.com
4. **Git installed** on your computer (or use GitHub web UI)

---

## Section A — Cloudflare Pages deployment

### Step 1 — Push the marketing site to GitHub (5 min)

```bash
# In your local machine, copy the /app/marketing folder out of Emergent
# (Use Emergent's "Save to GitHub" button OR download/upload manually.)

# Then on your local machine:
cd flowra-marketing/
git init
git add .
git commit -m "Initial FLOWRA marketing landing"

# Create a new repo at https://github.com/new (e.g., 'flowra-marketing'),
# then push:
git branch -M main
git remote add origin https://github.com/<your-username>/flowra-marketing.git
git push -u origin main
```

### Step 2 — Connect Cloudflare Pages to the repo (3 min)

1. Login to **dash.cloudflare.com**
2. Left sidebar → **Workers & Pages** → **Create application** → **Pages** tab
3. Click **Connect to Git** → authorize GitHub → select `flowra-marketing` repo
4. **Set up builds and deployments**:
   - **Project name**: `flowra-marketing` (this becomes the *.pages.dev URL)
   - **Production branch**: `main`
   - **Framework preset**: **None**
   - **Build command**: leave **empty**
   - **Build output directory**: `/` (root) — or leave empty
5. Click **Save and Deploy**

In about 60 seconds you'll see your site live at:
`https://flowra-marketing.pages.dev`

### Step 3 — Add Cloudflare as your DNS provider (10 min, one-time)

> Skip this step if your domain is already on Cloudflare. Most registrars charge for SSL
> separately; Cloudflare gives it free, so it's worth migrating DNS even if you keep your
> registrar elsewhere.

1. dash.cloudflare.com → **+ Add a site** → enter `flowralive.in` → **Free plan**
2. Cloudflare scans existing DNS records → click **Continue**
3. Cloudflare gives you 2 nameservers (e.g., `ada.ns.cloudflare.com`, `bob.ns.cloudflare.com`)
4. Login to **your registrar** (GoDaddy/Namecheap/etc.) → DNS settings → change nameservers to
   the 2 Cloudflare nameservers → save
5. Wait 10–60 minutes for DNS propagation. Cloudflare auto-emails you when done.
6. While waiting, in Cloudflare → **SSL/TLS** → set mode to **Full (strict)**

### Step 4 — Point the domain to Cloudflare Pages (2 min)

1. Cloudflare Pages → your `flowra-marketing` project → **Custom domains** tab
2. **Set up a custom domain** → enter `flowralive.in` → **Continue**
3. Cloudflare auto-creates the CNAME record. Click **Activate domain**
4. Repeat for `www.flowralive.in`
5. SSL cert auto-provisions in 30 seconds. Done.

### Step 5 — Verify (2 min)

```bash
# DNS check
dig flowralive.in
dig www.flowralive.in

# Should resolve to Cloudflare IPs (e.g., 172.67.x.x or 104.x.x.x)

# Curl check (HTTP → HTTPS redirect)
curl -I http://flowralive.in
# → Should 301 to https://flowralive.in

curl -I https://flowralive.in
# → Should 200 OK with security headers
```

Open **https://flowralive.in** in your browser. You should see the FLOWRA Suite landing page.

### Step 6 — SEO + Search Console (5 min)

1. Go to **search.google.com/search-console**
2. **Add property** → **URL prefix** → enter `https://flowralive.in/`
3. Verify via **Google Analytics** (if you have it) or **HTML tag** method
4. Submit sitemap: `https://flowralive.in/sitemap.xml`
5. Optional: add to **Bing Webmaster Tools** (bing.com/webmasters) for ~25% of Indian search traffic

### Step 7 — Going forward

Every time you push to the `main` branch on GitHub:
- Cloudflare automatically rebuilds and deploys
- Live in ~60 seconds
- Previous deployment is preserved (rollback in 1 click if anything breaks)

---

## Section B — Vercel deployment (alternative)

```bash
# Install Vercel CLI once
npm i -g vercel

# In the marketing folder
cd /path/to/marketing
vercel login
vercel --prod
```

Then:
1. Vercel dashboard → Project → **Domains** → add `flowralive.in`
2. Vercel gives you DNS records (A/CNAME) → add to your registrar
3. Done in ~2 min.

---

## Section C — DigitalOcean App Platform Static (alternative)

Apps → Create App → GitHub source → resource type **Static Site** →
build command: empty → output dir: `/` → custom domain `flowralive.in`.

---

## Post-deploy checklist

| Item | Status |
|------|--------|
| `https://flowralive.in/` returns 200 | □ |
| `https://www.flowralive.in/` redirects/serves correctly | □ |
| SSL cert valid (green padlock) | □ |
| `/sitemap.xml` accessible | □ |
| `/robots.txt` accessible | □ |
| Security headers present (use https://securityheaders.com — target A grade) | □ |
| Lighthouse scores ≥ 95 on all 4 axes (https://pagespeed.web.dev/) | □ |
| Submitted to Google Search Console | □ |
| Submitted to Bing Webmaster Tools | □ |
| Replace `hello@flowralive.in` with real inbox (Resend or Zoho free tier) | □ |
| Add `og-cover.png` (1200×630) to `/assets/` for nicer social previews | □ |
| Replace placeholder Twitter handle `@flowralive` if different | □ |

---

## Troubleshooting

**"My site shows the Cloudflare placeholder, not my page"**
→ DNS hasn't propagated yet. Wait up to 1 hour. Use https://dnschecker.org to track.

**"SSL error / NET::ERR_CERT_COMMON_NAME_INVALID"**
→ Custom domain not yet activated in Pages settings. Re-check Section 4.

**"www.flowralive.in doesn't redirect to root"**
→ In Cloudflare → Rules → Page Rules → add `www.flowralive.in/*` → Forwarding URL 301 to `https://flowralive.in/$1`

**"My GitHub push didn't trigger a build"**
→ Cloudflare Pages → Settings → check the production branch is `main` (not `master`).

---

## Cost summary (always free for the marketing site)

- Cloudflare Pages: **₹0/month** — unlimited bandwidth, unlimited builds
- Cloudflare DNS: **₹0/month**
- SSL: **₹0/month** (auto-renews every 90 days)
- Domain: ~₹999/year (whatever you paid the registrar)

**Total ongoing: ₹999/year for the domain. Hosting and bandwidth are free for life.**
