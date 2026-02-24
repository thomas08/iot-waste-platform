#!/bin/bash
# =============================================================
# IoT Waste Platform — Production Setup Script
# Domain: tus.maker-hub.net  (via Cloudflare Tunnel)
# Run once as user with sudo access: bash setup_production.sh
# =============================================================
set -e

DOMAIN="tus.maker-hub.net"
TUNNEL_NAME="iot-waste"
PROJECT_DIR="/home/senses/iot-waste-platform"
USER="senses"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo "============================================================"
echo "  IoT Waste Platform — Production Setup"
echo "  Domain: ${DOMAIN}"
echo "============================================================"
echo ""

# ─────────────────────────────────────────────────────────────
# STEP 1: Stop existing processes
# ─────────────────────────────────────────────────────────────
info "Stopping existing processes..."
pkill -f "iot_device_simulator.py" 2>/dev/null || true
pkill -f "mqtt_subscriber.py"      2>/dev/null || true
pkill -f "dashboard/api/main.py"   2>/dev/null || true
pkill -f "main.py"                 2>/dev/null || true
sleep 2
log "Existing processes stopped"

# ─────────────────────────────────────────────────────────────
# STEP 2: Install cloudflared
# ─────────────────────────────────────────────────────────────
if command -v cloudflared &>/dev/null; then
    log "cloudflared already installed: $(cloudflared --version)"
else
    info "Installing cloudflared..."
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
    echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' \
        | sudo tee /etc/apt/sources.list.d/cloudflared.list
    sudo apt-get update -qq
    sudo apt-get install -y cloudflared
    log "cloudflared installed: $(cloudflared --version)"
fi

# ─────────────────────────────────────────────────────────────
# STEP 3: Cloudflare Tunnel login
# ─────────────────────────────────────────────────────────────
if [ -f ~/.cloudflared/cert.pem ]; then
    log "Already authenticated with Cloudflare"
else
    echo ""
    warn "Opening browser for Cloudflare login..."
    warn "Please click 'Authorize' for the domain: maker-hub.net"
    echo ""
    cloudflared tunnel login
    log "Cloudflare authentication complete"
fi

# ─────────────────────────────────────────────────────────────
# STEP 4: Create tunnel
# ─────────────────────────────────────────────────────────────
EXISTING=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}' || true)

if [ -n "$EXISTING" ]; then
    TUNNEL_ID="$EXISTING"
    log "Tunnel '$TUNNEL_NAME' already exists: $TUNNEL_ID"
else
    info "Creating tunnel: $TUNNEL_NAME"
    cloudflared tunnel create "$TUNNEL_NAME"
    TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
    log "Tunnel created: $TUNNEL_ID"
fi

# ─────────────────────────────────────────────────────────────
# STEP 5: Write cloudflared config
# ─────────────────────────────────────────────────────────────
info "Writing cloudflared config..."
mkdir -p ~/.cloudflared

cat > ~/.cloudflared/config.yml << EOF
tunnel: ${TUNNEL_ID}
credentials-file: /home/${USER}/.cloudflared/${TUNNEL_ID}.json
logfile: /var/log/cloudflared.log
loglevel: info

ingress:
  - hostname: ${DOMAIN}
    service: http://127.0.0.1:8000
    originRequest:
      connectTimeout: 30s
      noTLSVerify: false
  - service: http_status:404
EOF

log "Config written: ~/.cloudflared/config.yml"

# ─────────────────────────────────────────────────────────────
# STEP 6: Route DNS
# ─────────────────────────────────────────────────────────────
info "Routing DNS: ${DOMAIN} → tunnel..."
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" || \
    warn "DNS route may already exist — continuing"
log "DNS routed (Cloudflare CNAME set automatically)"

# ─────────────────────────────────────────────────────────────
# STEP 7: Install systemd services
# ─────────────────────────────────────────────────────────────
info "Installing systemd services..."

sudo cp "${PROJECT_DIR}/deploy/iot-waste-api.service"        /etc/systemd/system/
sudo cp "${PROJECT_DIR}/deploy/iot-waste-sim.service"        /etc/systemd/system/
sudo cp "${PROJECT_DIR}/deploy/iot-waste-subscriber.service" /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable iot-waste-api iot-waste-sim iot-waste-subscriber
log "systemd services installed and enabled"

# ─────────────────────────────────────────────────────────────
# STEP 8: Install cloudflared as system service
# ─────────────────────────────────────────────────────────────
info "Installing cloudflared as system service..."
sudo cloudflared service install
sudo systemctl enable cloudflared 2>/dev/null || true
log "cloudflared service installed"

# ─────────────────────────────────────────────────────────────
# STEP 9: Make sure Docker is up (MQTT + DB)
# ─────────────────────────────────────────────────────────────
info "Ensuring Docker services are running..."
cd "${PROJECT_DIR}"
sudo docker compose up -d
sleep 3
log "Docker services running"

# ─────────────────────────────────────────────────────────────
# STEP 10: Start all services
# ─────────────────────────────────────────────────────────────
info "Starting all services..."
sudo systemctl start iot-waste-api
sleep 3
sudo systemctl start iot-waste-subscriber
sudo systemctl start iot-waste-sim
sudo systemctl start cloudflared

log "All services started"

# ─────────────────────────────────────────────────────────────
# STATUS CHECK
# ─────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Status"
echo "============================================================"
for svc in iot-waste-api iot-waste-subscriber iot-waste-sim cloudflared; do
    STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "active" ]; then
        echo -e "  ${GREEN}●${NC} $svc — active"
    else
        echo -e "  ${RED}●${NC} $svc — $STATUS"
    fi
done

echo ""
echo "============================================================"
echo -e "  ${GREEN}Done!${NC}"
echo "  Dashboard: https://${DOMAIN}"
echo "  API docs:  https://${DOMAIN}/docs"
echo ""
echo "  Logs:"
echo "    sudo journalctl -u iot-waste-api -f"
echo "    sudo journalctl -u cloudflared -f"
echo "============================================================"
echo ""
