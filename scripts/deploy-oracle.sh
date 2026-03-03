#!/usr/bin/env bash
# =============================================================================
# Orion - Manual Deploy Script for Oracle VM
# =============================================================================
# Run this directly on the Oracle VM via SSH:
#   ssh opc@<VM_IP> 'bash -s' < scripts/deploy-oracle.sh
#
# Or copy it to the VM and run:
#   chmod +x deploy-oracle.sh && ./deploy-oracle.sh
# =============================================================================

set -euo pipefail

DEPLOY_DIR=~/Orion-AI_Personal-Assistant
REPO_URL="${ORION_REPO_URL:-https://github.com/mayank29malhotra/Orion-AI_Personal-Assistant.git}"

echo "=========================================="
echo "  Orion Manual Deploy — $(date)"
echo "=========================================="

# -----------------------------------------------
# 1. Setup swap (2GB) if not present
# -----------------------------------------------
if [ ! -f /swapfile ]; then
  echo "📦 Creating 2GB swap..."
  sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
  sudo swapon /swapfile 2>/dev/null || true
fi
echo "RAM + Swap:"; free -h

# -----------------------------------------------
# 2. Stop old container
# -----------------------------------------------
echo "🛑 Stopping old container..."
podman stop orion 2>/dev/null || true
podman rm   orion 2>/dev/null || true
podman rmi  orion 2>/dev/null || true
podman image prune -f 2>/dev/null || true

# -----------------------------------------------
# 3. Backup .env + data, wipe old code
# -----------------------------------------------
echo "🧹 Cleaning old deployment..."
mkdir -p ~/orion-data
[ -d "$DEPLOY_DIR/data" ] && cp -a "$DEPLOY_DIR/data/." ~/orion-data/ 2>/dev/null || true
[ -f "$DEPLOY_DIR/.env" ] && cp "$DEPLOY_DIR/.env" ~/orion-env-backup 2>/dev/null || true

rm -rf "$DEPLOY_DIR"

# -----------------------------------------------
# 4. Clone fresh
# -----------------------------------------------
echo "📥 Cloning fresh from $REPO_URL ..."
git clone --depth 1 "$REPO_URL" "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# Restore .env and data
[ -f ~/orion-env-backup ] && cp ~/orion-env-backup .env
cp -a ~/orion-data/. data/ 2>/dev/null || true

# -----------------------------------------------
# 5. Build
# -----------------------------------------------
echo "🔨 Building container (multi-stage, no browser)..."
podman build --build-arg INSTALL_BROWSER=0 --jobs 1 -t orion .

# -----------------------------------------------
# 6. Run with memory limits
# -----------------------------------------------
echo "🚀 Starting Orion..."
podman run -d --name orion \
  --env-file .env \
  -v "$(pwd)/data:/app/data:Z" \
  --memory=900m \
  --memory-swap=2g \
  --restart=always \
  orion

# -----------------------------------------------
# 6b. Install Playwright Chromium inside container
# (post-start to avoid OOM during build on low-RAM VMs)
# -----------------------------------------------
echo "🌐 Installing Playwright Chromium..."
podman exec orion playwright install --with-deps chromium
podman restart orion
echo "✅ Playwright installed, container restarted"

# Commit so Playwright persists across restarts
podman commit orion orion:latest

# -----------------------------------------------
# 7. Verify
# -----------------------------------------------
sleep 20
echo "=========================================="
echo "  Container status:"
podman ps --filter name=orion --format "table {{.Names}} {{.Status}}"
echo ""
echo "  Recent logs:"
podman logs --tail 20 orion
echo ""
echo "✅ Deploy complete at $(date)"
echo "=========================================="
