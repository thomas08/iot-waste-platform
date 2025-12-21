#!/bin/bash

# ===========================================
# MQTT Authentication Setup Script (Docker version)
# IoT Waste Management Platform
# ===========================================
#
# This script creates the Mosquitto password file
# using Docker container and credentials from .env file
#
# Usage:
#   ./setup_mqtt_auth_docker.sh
#
# Requirements:
#   - Docker and docker-compose installed
#   - MQTT container must be running
#   - .env file with MQTT credentials
#
# ===========================================

set -e

echo "=========================================="
echo "MQTT Authentication Setup (Docker)"
echo "=========================================="
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file from .env.example first"
    exit 1
fi

# Load environment variables
source .env

# Check if MQTT container is running
if ! docker compose ps mqtt | grep -q "Up"; then
    echo "⚠️  MQTT container is not running. Starting it..."
    docker compose up -d mqtt
    echo "Waiting for MQTT container to be ready..."
    sleep 5
fi

CONTAINER_NAME="waste_mqtt"

echo "Creating MQTT password file in container..."
echo ""

# Password file location inside container
PASSWD_FILE="/mosquitto/config/passwd"

# Create password file for each user
# Note: -c creates new file (only use for first user)

# 1. Admin user (create new file)
echo "Adding user: $MQTT_ADMIN_USERNAME"
docker exec $CONTAINER_NAME mosquitto_passwd -c -b $PASSWD_FILE "$MQTT_ADMIN_USERNAME" "$MQTT_ADMIN_PASSWORD"

# 2. IoT Device user (append)
echo "Adding user: $MQTT_USERNAME"
docker exec $CONTAINER_NAME mosquitto_passwd -b $PASSWD_FILE "$MQTT_USERNAME" "$MQTT_PASSWORD"

# 3. Backend Service user (append)
echo "Adding user: backend_service"
docker exec $CONTAINER_NAME mosquitto_passwd -b $PASSWD_FILE "backend_service" "$MQTT_PASSWORD"

# 4. Dashboard Service user (append)
echo "Adding user: dashboard_service"
docker exec $CONTAINER_NAME mosquitto_passwd -b $PASSWD_FILE "dashboard_service" "$MQTT_PASSWORD"

echo ""
echo "✅ Password file created successfully in container!"
echo ""
echo "File location (in container): $PASSWD_FILE"
echo "Users created:"
echo "  - $MQTT_ADMIN_USERNAME (full access)"
echo "  - $MQTT_USERNAME (publish sensor data)"
echo "  - backend_service (subscribe all data)"
echo "  - dashboard_service (read data + send commands)"
echo ""
echo "Next steps:"
echo "1. MQTT authentication is now enabled"
echo "2. Update backend, simulator, and API to use these credentials"
echo "3. Test connection with: mosquitto_pub -h localhost -u $MQTT_USERNAME -P [password] -t test -m 'hello'"
echo ""
echo "=========================================="
