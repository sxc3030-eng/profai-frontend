#!/bin/bash
# ── profAI — Déploiement 1-commande Oracle ARM ──────────────────────────────
# 
# 1. Crée une VM Oracle ARM (Ampere, 4 coeurs, 24 GB RAM, Ubuntu 22.04)
# 2. Ouvre le port 8100 dans Oracle Cloud Console (Security List)
# 3. Copie ce script: scp deploy.sh ubuntu@TON_IP:/home/ubuntu/
# 4. Execute: ssh ubuntu@TON_IP "bash deploy.sh"
#
# Temps: ~5 minutes

set -e
echo "========================================"
echo "  profAI - Deploiement Oracle"
echo "========================================"

# 1. Docker
echo "[1/4] Docker..."
sudo apt-get update -qq && sudo apt-get install -y -qq docker.io curl
sudo usermod -aG docker $USER 2>/dev/null || true
echo "OK"

# 2. Cloner le backend
echo "[2/4] Code..."
cd /home/ubuntu
rm -rf profai 2>/dev/null || true
git clone --depth 1 https://github.com/sxc3030-eng/profai-backend.git profai
echo "OK"

# 3. Dockerfile
echo "[3/4] Build..."
cat > /home/ubuntu/profai/Dockerfile << 'EOF'
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir aiohttp aiohttp-cors
WORKDIR /app
COPY src/ ./src/
COPY web/ ./web/
COPY scripts/ ./scripts/
COPY config/ ./config/
RUN mkdir -p courses subscriptions auth_data
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 CMD curl -f http://127.0.0.1:8100/api/health || exit 1
CMD ["python","-u","src/memory_agent/formateur_server.py","--host","0.0.0.0","--port","8100"]
EOF

cd /home/ubuntu/profai
sudo docker build -t profai:latest . 2>&1 | tail -3
echo "OK"

# 4. Run
echo "[4/4] Demarrage..."
sudo docker stop profai 2>/dev/null || true
sudo docker rm profai 2>/dev/null || true
sudo docker run -d --name profai --restart unless-stopped \
  -p 8100:8100 \
  -v /home/ubuntu/profai/courses:/app/courses \
  -v /home/ubuntu/profai/subscriptions:/app/subscriptions \
  -v /home/ubuntu/profai/auth_data:/app/auth_data \
  profai:latest

# Firewall
sudo ufw allow 8100/tcp 2>/dev/null || true

# Anti-reclaim Oracle (empeche la VM d'etre supprimee)
(crontab -l 2>/dev/null; echo "*/10 * * * * curl -sf http://127.0.0.1:8100/api/health > /dev/null 2>&1") | crontab -

# Resultat
IP=$(curl -sf ifconfig.me 2>/dev/null || echo "INCONNUE")
sleep 3
HEALTH=$(curl -sf http://127.0.0.1:8100/api/health 2>/dev/null || echo "EN ATTENTE...")

echo ""
echo "========================================"
echo "  profAI EN LIGNE !"
echo "========================================"
echo "  IP     : $IP"
echo "  API    : http://$IP:8100/api/health"
echo "  Chat   : http://$IP:8100/chat.html"
echo "  Health : $HEALTH"
echo ""
echo "  Pour tester: http://$IP:8100/chat.html"
echo "========================================"