# FLOWRA — DigitalOcean Droplet Deployment Guide

> One-shot, copy-paste guide to deploy FLOWRA on a fresh Ubuntu 22.04 / 24.04 droplet
> with HTTPS at `https://insights.flowralive.in`. Backend stays at FastAPI on port
> 8001 (proxied by nginx); frontend is served as a static React build by the same
> nginx. MongoDB Atlas is already live, so the droplet only runs API + static files.
>
> **Time to first request:** ~30 minutes including DNS propagation.

---

## 0. Before you start (5 min)

You'll need:
- DO droplet with public IP (you already have one).
- Root or sudo SSH access.
- A laptop with a terminal.
- Your GoDaddy / Cloudflare / wherever-you-registered-flowralive.in DNS panel open
  in a browser tab.

### 0a. Point the DNS record

In your DNS panel, add this A record:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `insights` | `<your droplet public IP>` | 300 |

Save. DNS propagates in 1-10 min globally. Verify from your laptop:

```bash
dig +short insights.flowralive.in
# → should print the droplet IP
```

---

## 1. SSH into the droplet

```bash
ssh root@<your droplet ip>
```

## 2. Install system dependencies (one-time, ~3 min)

```bash
apt update && apt upgrade -y

# Core utilities
apt install -y git curl ufw nginx certbot python3-certbot-nginx \
               build-essential

# Python 3.11 (the version your code targets)
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Node 20 (for the React build)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g yarn

# Firewall (only HTTP/HTTPS + SSH open)
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

## 3. Clone the app

Use DigitalOcean console's GitHub clone, or:

```bash
mkdir -p /opt && cd /opt
git clone https://github.com/<your-username>/<your-repo>.git flowra
cd flowra
```

> If you've already cloned into a different folder, just `cd` there.
> The rest of this guide assumes `/opt/flowra` — adjust paths if different.

## 4. Configure environment variables

### 4a. Backend `.env`

```bash
cat > /opt/flowra/backend/.env <<'EOF'
MONGO_URL="mongodb+srv://jodidarindia_db_user:oTTtFSOrJLz3DdTE@flowra-cluster.cxt8yw1.mongodb.net/?retryWrites=true&w=majority&appName=flowra-cluster"
DB_NAME="Flowra-Insights"
CORS_ORIGINS="https://insights.flowralive.in"
EMERGENT_LLM_KEY=sk-emergent-aC1Cb333033447c9d9
RESEND_API_KEY=re_YwNsMM4h_GSgBpnEQpyBRV1ieR6oeyGFU
SENDER_EMAIL=support@flowralive.in
JWT_SECRET=b49043023b7d21ed66c0d0109ca760872b4f71acd0774edbcef786f72633c55e
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
SUPER_ADMIN_USERNAME=superadmin
SUPER_ADMIN_PASSWORD=superadmin123
ENCRYPTION_KEY=0XxGtFVpZUOUVYtYTt6rI7jsYWsPh2Wc6pgOb3n_PcE=
RECAPTCHA_SECRET_KEY=6LeoJLMsAAAAAJK_oy4L6BE8C3fimRDTNrz677u7
EOF
chmod 600 /opt/flowra/backend/.env
```

> ⚠ Change `ADMIN_PASSWORD` and `SUPER_ADMIN_PASSWORD` before going live!
> Use a 20+ character random string. The current values are demo defaults.

### 4b. Frontend `.env`

```bash
cat > /opt/flowra/frontend/.env <<'EOF'
REACT_APP_BACKEND_URL=https://insights.flowralive.in
REACT_APP_RECAPTCHA_SITE_KEY=6LeoJLMsAAAAANrpgqaHnjBtYTY4ob1dJniDyAlE
EOF
```

## 5. Backend — Python venv + dependencies

```bash
cd /opt/flowra/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Sanity check — should print 51 collections and 7,150+ docs
python -c "
import asyncio, sys
from dotenv import load_dotenv
load_dotenv('.env')
from db import db
async def m():
    cols = await db.list_collection_names()
    print(len(cols), 'collections')
asyncio.run(m())
"
deactivate
```

## 6. Frontend — build the React static files

```bash
cd /opt/flowra/frontend
yarn install
yarn build
# Produces /opt/flowra/frontend/build/ — this is what nginx will serve.
```

## 7. systemd unit for the backend

```bash
cat > /etc/systemd/system/flowra-backend.service <<'EOF'
[Unit]
Description=FLOWRA FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/flowra/backend
EnvironmentFile=/opt/flowra/backend/.env
ExecStart=/opt/flowra/backend/.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 2
Restart=always
RestartSec=5
StandardOutput=append:/var/log/flowra-backend.log
StandardError=append:/var/log/flowra-backend.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable flowra-backend
systemctl start flowra-backend

# Verify
sleep 3 && systemctl status flowra-backend --no-pager | head -15
curl -s http://127.0.0.1:8001/api/health
# → {"ok": true, "db": "connected", "service": "flowra-backend"}
```

## 8. nginx config — serves frontend + proxies API

```bash
cat > /etc/nginx/sites-available/flowra <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name insights.flowralive.in;

    # Increase upload limit for Tally syncs (some manifests can be large)
    client_max_body_size 50M;

    # ── Static frontend ─────────────────────────────────────────────
    root /opt/flowra/frontend/build;
    index index.html;

    # ── API + WebSocket proxy ───────────────────────────────────────
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_buffering off;
        proxy_request_buffering off;
    }
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host       $host;
        proxy_read_timeout 86400s;
    }

    # ── React Router fallback ───────────────────────────────────────
    location / {
        try_files $uri /index.html;
    }

    # Static asset caching
    location ~* \.(?:js|css|woff2?|ttf|png|jpg|jpeg|gif|svg|ico)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    # Plain-text files (PDFs, .exe etc.) — no caching so updates show immediately
    location ~* \.(?:pdf|exe|zip)$ {
        expires 0;
        try_files $uri =404;
    }
}
EOF

ln -sf /etc/nginx/sites-available/flowra /etc/nginx/sites-enabled/flowra
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

## 9. HTTPS — free SSL via Let's Encrypt

```bash
certbot --nginx -d insights.flowralive.in \
        --non-interactive --agree-tos -m support@flowralive.in --redirect
```

Certbot rewrites the nginx config to add the HTTPS server block and a 80→443
redirect. Auto-renewal is set up automatically (twice-daily systemd timer).

Verify:
```bash
curl -s https://insights.flowralive.in/api/health
# → {"ok": true, "db": "connected", "service": "flowra-backend"}
```

## 10. Smoke test

Open `https://insights.flowralive.in/` in a browser.

Log in with:
- `admin / admin123` (replace with your new password from step 4a)
- or `demo@flowralive.in / demo2026` (the pre-seeded demo tenant)

If you see the dashboard with ₹39.82L total sales → you're live. 🎉

---

## 11. Tally Sync Agent — what URL to feed it?

After deploy, when distributing the agent EXE:

- The agent's pre-filled URL (`DEFAULT_BACKEND_URL` constant) is **already**
  `https://insights.flowralive.in` as of v9.8.19.
- End-users do NOT need to type a URL — Settings tab pre-fills it.
- Existing v9.8.18 agents already in the field: tell users to go to
  **Settings → Advanced → FLOWRA Server URL** and replace the old preview URL
  with `https://insights.flowralive.in`, then click **Save & Start Sync**.

Just upload the new `FlowraTallyAgent_v9.8.19.exe` to
`/opt/flowra/frontend/build/FlowraTallyAgent.exe` (nginx serves it from the
build folder), and customers downloading from the Setup page will get the
correctly-configured binary.

---

## 12. Day-2 ops cheat sheet

| Need to do | Command |
|---|---|
| Backend logs | `journalctl -u flowra-backend -f`  *or*  `tail -f /var/log/flowra-backend.log` |
| Backend restart | `systemctl restart flowra-backend` |
| Nginx restart | `systemctl restart nginx` |
| Re-pull from GitHub | `cd /opt/flowra && git pull && cd backend && source .venv/bin/activate && pip install -r requirements.txt && deactivate && cd ../frontend && yarn install && yarn build && systemctl restart flowra-backend && systemctl reload nginx` |
| Renew certs (auto) | `certbot renew --dry-run` — should say "Congratulations" |
| Check Atlas connection | `curl https://insights.flowralive.in/api/health` |

---

## 13. Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `/api/health` returns 502 | Backend down | `systemctl status flowra-backend` → check logs |
| `db: disconnected` in health | Atlas IP allowlist | Add droplet IP (or 0.0.0.0/0) to Atlas → Network Access |
| Login works but dashboard empty | Frontend rebuilt with wrong URL | Rebuild frontend after fixing `frontend/.env` |
| Agent says "Cannot reach FLOWRA" | DNS not propagated yet | `dig insights.flowralive.in` — wait 5-10 min |
| reCAPTCHA fails on login | Site key restricted to localhost in Google console | Add `insights.flowralive.in` to allowed domains in https://www.google.com/recaptcha/admin |
| EXE 404 | Build folder doesn't contain it | `cp /opt/flowra/frontend/public/FlowraTallyAgent.exe /opt/flowra/frontend/build/` then `systemctl reload nginx` |

---

## 14. What's left to harden post-launch

- **Database snapshots**: Atlas → Backup → enable daily snapshot retention (free tier = 2/day).
- **Off-server log rotation**: `apt install -y logrotate` (already installed); add a `/etc/logrotate.d/flowra-backend` if logs grow large.
- **Password rotation**: change `ADMIN_PASSWORD` and `SUPER_ADMIN_PASSWORD` to 20-char random strings.
- **WhatsApp + GST integrations**: still on the roadmap — don't block production launch waiting for these.
- **Monitor uptime**: free option = https://uptimerobot.com → add `https://insights.flowralive.in/api/health` and get an email if it ever goes down.

---

## 15. Dev / Prod database isolation (already configured)

Two databases live on the same Atlas cluster — no extra cost, full data isolation:

| Environment | `DB_NAME` value | Used by |
|---|---|---|
| **Emergent preview** (development sandbox) | `Flowra-Insights-Dev` | Feature work, regression tests, demo seeds |
| **DigitalOcean droplet** (production) | `Flowra-Insights` | Live customer data |

The same code runs on both. The `.env` file (which is git-ignored, see `.gitignore`)
is the only thing that differs. As a result:

- Any change made on Emergent — schema migrations, demo re-seeds, broken
  deployments — touches **only** `Flowra-Insights-Dev`.
- `git pull` on the droplet pulls only the *code* (the droplet's `.env` is
  never overwritten), so production data is untouched by any development.

To refresh the dev database from production at any time, run
`python3 /tmp/split_dev_db.py` from inside the Emergent container — it re-clones
`Flowra-Insights` → `Flowra-Insights-Dev` in ~30 seconds.

Last updated: May 2026 · FLOWRA v9.8.19 / Agent v9.8.19
