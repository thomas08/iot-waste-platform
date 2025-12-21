#!/bin/bash

# ===========================================
# MQTT Authentication Setup Script
# IoT Waste Management Platform
# ===========================================
#
# This script creates the Mosquitto password file
# using credentials from .env file
#
# Usage:
#   ./setup_mqtt_auth.sh
#
# Requirements:
#   - mosquitto_passwd command (install: apt-get install mosquitto-clients)
#   - .env file with MQTT credentials
#
# ===========================================

set -e

echo "=========================================="
echo "MQTT Authentication Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file from .env.example first"
    exit 1
fi

# Load environment variables
source ../.env

# Check if mosquitto_passwd is installed
if ! command -v mosquitto_passwd &> /dev/null; then
    echo "❌ Error: mosquitto_passwd command not found!"
    echo ""
    echo "Please install mosquitto-clients:"
    echo "  Ubuntu/Debian: sudo apt-get install mosquitto-clients"
    echo "  MacOS: brew install mosquitto"
    exit 1
fi

# Password file location
PASSWD_FILE="config/passwd"

echo "Creating MQTT password file..."
echo ""

# Create password file for each user
# Note: -c creates new file (only use for first user)
# Without -c, it appends to existing file

# 1. Admin user (create new file)
echo "Adding user: mqtt_admin"
mosquitto_passwd -c -b "$PASSWD_FILE" "$MQTT_ADMIN_USERNAME" "$MQTT_ADMIN_PASSWORD"

# 2. IoT Device user (append)
echo "Adding user: iot_device"
mosquitto_passwd -b "$PASSWD_FILE" "$MQTT_USERNAME" "$MQTT_PASSWORD"

# 3. Backend Service user (append)
echo "Adding user: backend_service"
mosquitto_passwd -b "$PASSWD_FILE" "backend_service" "$MQTT_PASSWORD"

# 4. Dashboard Service user (append)
echo "Adding user: dashboard_service"
mosquitto_passwd -b "$PASSWD_FILE" "dashboard_service" "$MQTT_PASSWORD"

echo ""
echo "✅ Password file created successfully!"
echo ""
echo "File location: $PASSWD_FILE"
echo "Users created:"
echo "  - mqtt_admin (full access)"
echo "  - iot_device (publish sensors data)"
echo "  - backend_service (subscribe all data)"
echo "  - dashboard_service (read data + send commands)"
echo ""
echo "Next steps:"
echo "1. Update docker-compose.yml to use mosquitto_secure folder"
echo "2. Restart MQTT broker: docker compose up -d mqtt"
echo "3. Update backend, simulator, and API to use credentials"
echo ""
echo "=========================================="
