#!/bin/bash
# ── profAI — Déploiement rapide Oracle ARM (Ubuntu 22.04) ────────────────────
# Copie ce script sur ta VM Oracle et exécute-le.
#
# 1. Crée une VM Oracle ARM (Ampere, 4 cœurs, 24 GB RAM) sur Ubuntu 22.04
# 2. Copie ce script: scp deploy.sh ubuntu@TON_IP:/home/ubuntu/
# 3. Exécute: ssh ubuntu@TON_IP "bash deploy.sh"
#
# Temps total: ~10 minutes

set -e

echo "========================================"
echo "  profAI — Déploiement Oracle"
echo "========================================"

# ── 1. Docker ────────────────────────────────────────────────────────────
echo "[1/5] Installation Docker..."
sudo apt-get update -qq
sudo apt-get install -y -qq docker.io docker-compose-v2 curl
sudo usermod -aG docker $USER
echo "Docker OK"

# ── 2. Code ──────────────────────────────────────────────────────────────
echo "[2/5] Téléchargement du code..."
cd /home/ubuntu
git clone https://github.com/sxc3030-eng/profai-frontend.git profai 2>/dev/null || (cd profai && git pull)
mkdir -p profai/src/memory_agent profai/web profai/scripts profai/config profai/courses profai/subscriptions profai/auth_data

# Télécharger les fichiers backend depuis le repo
curl -sL https://raw.githubusercontent.com/sxc3030-eng/profai-frontend/master/index.html -o profai/web/chat.html

echo "Code OK"

# ── 3. Dockerfile minimal ────────────────────────────────────────────────
echo "[3/5] Création du Dockerfile..."
cat > profai/Dockerfile << 'DOCKERFILE'
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
CMD ["python", "-u", "src/memory_agent/formateur_server.py", "--host", "0.0.0.0", "--port", "8100"]
DOCKERFILE

# ── 4. Build & Run ───────────────────────────────────────────────────────
echo "[4/5] Build de l'image Docker..."
cd profai
sudo docker build -t profai:latest . 2>&1 | tail -5

echo "[5/5] Démarrage..."
sudo docker stop profai 2>/dev/null || true
sudo docker rm profai 2>/dev/null || true
sudo docker run -d --name profai --restart unless-stopped \
  -p 8100:8100 \
  -v /home/ubuntu/profai/courses:/app/courses \
  -v /home/ubuntu/profai/subscriptions:/app/subscriptions \
  -v /home/ubuntu/profai/auth_data:/app/auth_data \
  profai:latest

# ── Firewall ─────────────────────────────────────────────────────────────
sudo ufw allow 8100/tcp 2>/dev/null || true

# ── Anti-reclaim Oracle ──────────────────────────────────────────────────
(crontab -l 2>/dev/null; echo "*/10 * * * * curl -sf http://127.0.0.1:8100/api/health > /dev/null 2>&1") | crontab -

# ── Résultat ─────────────────────────────────────────────────────────────
IP=$(curl -sf ifconfig.me 2>/dev/null || echo "INCONNUE")
echo ""
echo "========================================"
echo "  ✅ profAI DÉPLOYÉ !"
echo "========================================"
echo "  API  : http://$IP:8100/api/health"
echo "  Chat : http://$IP:8100/chat.html"
echo ""
echo "  ⚠️  Ouvre le port 8100 dans Oracle Cloud Console"
echo "     (Réseau → Security Lists → Ingress Rules)"
echo "========================================"