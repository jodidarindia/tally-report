# Tally Reports - Self-Hosting Guide

## Prerequisites
- Docker & Docker Compose installed
- 2GB+ RAM, 10GB disk space
- Port 80 (web), 8001 (API), 27017 (MongoDB) available

## Quick Start (Linux/Mac)
```bash
# 1. Copy the project folder to your server
# 2. Create environment config
cp .env.example .env
# Edit .env with your EMERGENT_LLM_KEY

# 3. Deploy
chmod +x deploy.sh
./deploy.sh
```

## Quick Start (Windows)
```
1. Copy the project folder to your machine
2. Copy .env.example to .env, edit with your keys
3. Double-click deploy.bat
```

## Configuration (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `EMERGENT_LLM_KEY` | Yes | Emergent Universal Key for AI features |
| `RESEND_API_KEY` | No | Resend.com API key for real OTP emails |
| `SENDER_EMAIL` | No | Email sender address |
| `APP_URL` | No | Your domain (default: http://localhost) |

## Access
- **Web App**: http://localhost (or your domain)
- **Login**: Enter any email, use OTP `123456` (dev mode without Resend key)

## Desktop Sync Agent
The Desktop Agent runs on your local machine (where Tally is installed) and pushes data to the cloud/server.

```bash
cd desktop-agent
pip install -r requirements.txt
# Edit tally_sync_agent.py to set CLOUD_API_URL to your server
python tally_sync_agent.py
```

## Management Commands
```bash
# View logs
docker compose logs -f

# Stop all services
docker compose down

# Restart
docker compose restart

# Update (after pulling new code)
docker compose up -d --build

# Backup MongoDB
docker exec tally-mongodb mongodump --out /data/backup
docker cp tally-mongodb:/data/backup ./backup
```

## Production Tips
1. Use HTTPS with a reverse proxy (Nginx/Caddy) in front
2. Set `APP_URL` to your real domain
3. Configure a real Resend API key for email OTP
4. Enable MongoDB authentication for security
5. Set up automated backups for the `mongo_data` volume
