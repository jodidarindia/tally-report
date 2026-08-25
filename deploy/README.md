# FLOWRA · One-click deploy to DigitalOcean Droplet

Everything under `deploy/` gives you a **push-to-deploy** and a **click-to-republish** pipeline for your existing DO Droplet. Zero-touch after first setup.

```
deploy/
├── setup-droplet.sh          # run ONCE on a fresh Ubuntu 22.04 droplet
├── deploy.sh                 # runs on every push (from GitHub Actions)
├── env.backend.example       # copy → backend/.env, fill in real keys
├── env.frontend.example      # copy → frontend/.env, fill in real keys
├── systemd/flowra-backend.service
└── nginx/flowra.conf
```

The workflow file lives at `.github/workflows/deploy.yml` (already committed).

---

## One-time setup (≈ 15 minutes)

### 1. Push code to GitHub
In the Emergent chat input, click **Save → Save to GitHub**, choose a repo (e.g. `jodidar-india/flowra`), branch `main`.

### 2. Bootstrap your Droplet

SSH into your Droplet as `root`, then:

```bash
export REPO_URL=https://github.com/<your-org>/flowra.git
export DOMAIN=insights.flowralive.in
curl -fsSL https://raw.githubusercontent.com/<your-org>/flowra/main/deploy/setup-droplet.sh | bash
```

The script installs Python 3.11, Node 20, nginx, certbot, MongoDB tools, clones your repo into `/opt/flowra`, creates a `flowra` deploy user, opens the firewall, and issues a Let's Encrypt cert.

### 3. Fill in real secrets

```bash
sudo -u flowra nano /opt/flowra/backend/.env    # MONGO_URL, RESEND_API_KEY, EMERGENT_LLM_KEY, etc.
sudo -u flowra nano /opt/flowra/frontend/.env   # REACT_APP_BACKEND_URL, REACT_APP_RECAPTCHA_SITE_KEY, ...
sudo systemctl restart flowra-backend
```

### 4. Wire GitHub Actions to your Droplet

**On your laptop**, generate an SSH key just for CI/CD:

```bash
ssh-keygen -t ed25519 -f flowra_deploy_key -N ""       # produces flowra_deploy_key + flowra_deploy_key.pub
```

**On the Droplet**, add the public key to the deploy user:

```bash
sudo bash -c 'cat flowra_deploy_key.pub >> /home/flowra/.ssh/authorized_keys'
sudo chown flowra:flowra /home/flowra/.ssh/authorized_keys
sudo chmod 600 /home/flowra/.ssh/authorized_keys
```

**On GitHub**, open your repo → **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Value |
|---|---|
| `DO_HOST` | your droplet's IP or `insights.flowralive.in` |
| `DO_USER` | `flowra` |
| `DO_SSH_KEY` | full contents of the **private** key file `flowra_deploy_key` (paste including `-----BEGIN` and `-----END` lines) |

### 5. First auto-deploy

Push anything to `main` OR go to **Actions → Deploy to DigitalOcean → Run workflow**. Watch the log:

- ✅ Checkout · Set up SSH · SSH → build → restart · Smoke test

The smoke test hits `/api/health` — if it doesn't return `{"ok":true}` the workflow fails, so you know instantly.

---

## Daily use — the "one click" you asked for

**Auto (default):** every push to `main` deploys.

**Manual button:** GitHub → your repo → **Actions** tab → **Deploy to DigitalOcean** in the left sidebar → **Run workflow** (green button, top-right). Options:
- `restart_only=false` → full rebuild (git pull, `yarn build`, `pip install`, restart) — ~2 min
- `restart_only=true` → just restart services (env-var change / hot config swap) — ~10 sec

---

## Rollback in 30 seconds

```bash
ssh flowra@<droplet>
cd /opt/flowra && git log --oneline -10       # find the good commit
git reset --hard <commit-sha>
./deploy/deploy.sh false
```

Or just re-run the last-good GitHub Actions run: **Actions → past successful run → Re-run all jobs**.

---

## What the automation covers

| Thing | Handled? |
|---|---|
| React build + minification | ✅ |
| Backend deps + emergentintegrations SDK | ✅ |
| Frontend copy to `/var/www/flowra` | ✅ |
| Systemd restart (backend) | ✅ |
| nginx reload | ✅ |
| Health-check smoke test | ✅ |
| Zero-downtime? | ~2-second blip during `systemctl restart` — fine for a SaaS at your stage. Add a second app node + haproxy when you hit 500+ concurrent users |
| MongoDB migrations | Handled inside the app on startup (indexes are `ensure_indexes()`) |
| SSL renewal | certbot's systemd timer, installed by `setup-droplet.sh` |
| Secrets in git? | **No** — `.env` files live only on the Droplet |

---

## Troubleshooting

```bash
# Live backend logs
journalctl -u flowra-backend -f

# nginx error log
tail -n 100 /var/log/nginx/error.log

# Confirm health from the droplet
curl -s http://127.0.0.1:8001/api/health

# Confirm health from the internet
curl -s https://insights.flowralive.in/api/health
```

Common gotchas:
- **502 Bad Gateway** → uvicorn crashed. `journalctl -u flowra-backend -f` will show the traceback.
- **Frontend loads but API 404s** → `frontend/.env` has the wrong `REACT_APP_BACKEND_URL`. Rebuild with the correct value: `./deploy/deploy.sh false`.
- **Login says "reCAPTCHA failed"** → your `RECAPTCHA_SECRET` (backend) doesn't match `REACT_APP_RECAPTCHA_SITE_KEY` (frontend).

---

## Node sizing recap (from iter-125 chat)

| Tenants | Concurrent users | Droplet size |
|---|---|---|
| 1-20 | 1-5 | Basic 1 vCPU / 2 GB |
| **20-100** (current) | **5-20** | **CPU-Optimized 2 vCPU / 4 GB** ← you're here |
| 100-500 | 20-75 | CPU-Optimized 4 vCPU / 8 GB |
| 500+ | 75+ | 2 nodes + haproxy + Redis |

For a 2-vCPU / 4-GB Droplet, keep `--workers 4` in the systemd unit. Bump to 8 workers when you move to a 4-vCPU node.
