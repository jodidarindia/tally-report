#!/usr/bin/env bash
#
# FLOWRA — Droplet bootstrap (run ONCE on a fresh Ubuntu 22.04 Droplet).
#
#   curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy/setup-droplet.sh | sudo bash
#
# What it does:
#   - installs Python 3.11, Node 20, yarn, nginx, certbot, git, mongo-tools
#   - creates a `flowra` deploy user
#   - clones the repo into /opt/flowra
#   - installs your systemd unit + nginx vhost
#   - opens ports 80/443 + fetches a Let's Encrypt cert
#   - creates a Python venv + installs backend deps
#   - builds the React frontend
#   - starts the FastAPI service under systemd
#
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/your-org/flowra.git}"     # override before running
DOMAIN="${DOMAIN:-insights.flowralive.in}"
DEPLOY_USER="flowra"
APP_DIR="/opt/flowra"

echo "🔧  Installing OS packages…"
apt update -y
apt install -y python3.11 python3.11-venv python3-pip \
                git nginx certbot python3-certbot-nginx \
                curl build-essential mongodb-clients ufw

echo "🔧  Installing Node 20 + Yarn…"
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g yarn

echo "🔧  Creating deploy user…"
if ! id "$DEPLOY_USER" &>/dev/null; then
  useradd -m -s /bin/bash "$DEPLOY_USER"
  mkdir -p /home/$DEPLOY_USER/.ssh
  chmod 700 /home/$DEPLOY_USER/.ssh
  # Paste your GitHub Actions public key into /home/flowra/.ssh/authorized_keys AFTER this script.
  touch /home/$DEPLOY_USER/.ssh/authorized_keys
  chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
fi
# Let the deploy user restart the backend service without a password.
cat >/etc/sudoers.d/flowra-deploy <<'EOF'
flowra ALL=(root) NOPASSWD: /bin/systemctl restart flowra-backend
flowra ALL=(root) NOPASSWD: /bin/systemctl reload nginx
EOF
chmod 440 /etc/sudoers.d/flowra-deploy

echo "🔧  Cloning repo → $APP_DIR"
mkdir -p "$APP_DIR"
chown "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u "$DEPLOY_USER" git clone "$REPO_URL" "$APP_DIR"
fi

echo "🔧  Placing systemd unit + nginx vhost"
install -o root -g root -m 644 "$APP_DIR/deploy/systemd/flowra-backend.service" /etc/systemd/system/flowra-backend.service
install -o root -g root -m 644 "$APP_DIR/deploy/nginx/flowra.conf"             /etc/nginx/sites-available/flowra
ln -sf /etc/nginx/sites-available/flowra /etc/nginx/sites-enabled/flowra
rm -f /etc/nginx/sites-enabled/default

echo "🔧  Firewall"
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true
ufw --force enable

echo "🔧  Env files — copy the templates and edit them NOW"
[ -f "$APP_DIR/backend/.env" ] || sudo -u "$DEPLOY_USER" cp "$APP_DIR/deploy/env.backend.example"  "$APP_DIR/backend/.env"
[ -f "$APP_DIR/frontend/.env" ] || sudo -u "$DEPLOY_USER" cp "$APP_DIR/deploy/env.frontend.example" "$APP_DIR/frontend/.env"
chmod 600 "$APP_DIR/backend/.env" "$APP_DIR/frontend/.env"
echo "    → Edit $APP_DIR/backend/.env  (MONGO_URL, RESEND_API_KEY, EMERGENT_LLM_KEY, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, SUPER_ADMIN_EMAIL, JWT_SECRET, RECAPTCHA_SECRET)"
echo "    → Edit $APP_DIR/frontend/.env (REACT_APP_BACKEND_URL=https://$DOMAIN)"

echo "🔧  First-time build"
sudo -u "$DEPLOY_USER" bash -c "cd $APP_DIR && ./deploy/deploy.sh false"

echo "🔧  Reload nginx + start backend"
systemctl daemon-reload
systemctl enable --now flowra-backend
nginx -t && systemctl reload nginx

echo "🔧  Let's Encrypt cert for $DOMAIN"
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "ops@flowralive.in" || \
  echo "⚠️   cert issuance failed — run 'certbot --nginx -d $DOMAIN' manually"

echo ""
echo "✅ Bootstrap complete."
echo "   Next steps:"
echo "   1. Paste your GitHub Actions public key into /home/$DEPLOY_USER/.ssh/authorized_keys"
echo "   2. Add repo secrets DO_HOST, DO_USER=$DEPLOY_USER, DO_SSH_KEY (private key)"
echo "   3. Push to main OR click Actions → Deploy to DigitalOcean → Run workflow"
