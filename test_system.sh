#!/bin/bash

# IoT Waste Platform - Full System Test Script
# This script tests all components of the system

set -e  # Exit on error

echo "========================================================================"
echo "   IoT Waste Platform - Full System Test"
echo "========================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# ====================
# Step 1: Check Docker Services
# ====================
print_step "Checking Docker services..."
echo ""

if sudo docker compose ps | grep -q "waste_mqtt.*Up"; then
    print_success "MQTT Broker is running"
    ((TESTS_PASSED++))
else
    print_error "MQTT Broker is not running"
    ((TESTS_FAILED++))
fi

if sudo docker compose ps | grep -q "waste_db.*Up"; then
    print_success "PostgreSQL is running"
    ((TESTS_PASSED++))
else
    print_error "PostgreSQL is not running"
    ((TESTS_FAILED++))
fi

if sudo docker compose ps | grep -q "waste_pgadmin.*Up"; then
    print_success "pgAdmin is running"
    ((TESTS_PASSED++))
else
    print_error "pgAdmin is not running"
    ((TESTS_FAILED++))
fi

echo ""

# ====================
# Step 2: Check Database Connection
# ====================
print_step "Testing database connection..."
echo ""

if PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "SELECT 1" > /dev/null 2>&1; then
    print_success "Database connection successful"
    ((TESTS_PASSED++))
else
    print_error "Cannot connect to database"
    ((TESTS_FAILED++))
fi

echo ""

# ====================
# Step 3: Check Database Schema
# ====================
print_step "Checking database schema..."
echo ""

# Check if main tables exist
TABLES=("waste_bins" "sensors" "sensor_readings" "alerts" "collections" "users")
for table in "${TABLES[@]}"; do
    if PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "\dt $table" 2>/dev/null | grep -q "$table"; then
        print_success "Table '$table' exists"
        ((TESTS_PASSED++))
    else
        print_error "Table '$table' not found"
        ((TESTS_FAILED++))
        SCHEMA_MISSING=1
    fi
done

if [ ! -z "$SCHEMA_MISSING" ]; then
    print_warning "Some tables are missing. Run: cd database && ./apply_schema.sh"
fi

echo ""

# ====================
# Step 4: Check Sample Data
# ====================
print_step "Checking sample data..."
echo ""

BIN_COUNT=$(PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -t -c "SELECT COUNT(*) FROM waste_bins" 2>/dev/null || echo "0")
BIN_COUNT=$(echo $BIN_COUNT | tr -d '[:space:]')

if [ "$BIN_COUNT" -gt 0 ]; then
    print_success "Found $BIN_COUNT waste bins in database"
    ((TESTS_PASSED++))
else
    print_warning "No waste bins found in database"
    print_warning "Schema may need to be applied: cd database && ./apply_schema.sh"
fi

echo ""

# ====================
# Step 5: Check MQTT Broker
# ====================
print_step "Testing MQTT broker connectivity..."
echo ""

# Check if mosquitto clients are installed
if command -v mosquitto_pub > /dev/null 2>&1; then
    # Try to publish a test message
    if timeout 2 mosquitto_pub -h localhost -t "test/connection" -m "test" > /dev/null 2>&1; then
        print_success "MQTT broker is accessible"
        ((TESTS_PASSED++))
    else
        print_error "Cannot publish to MQTT broker"
        ((TESTS_FAILED++))
    fi
else
    print_warning "mosquitto-clients not installed (optional for testing)"
    print_warning "Install with: sudo apt-get install mosquitto-clients"
fi

echo ""

# ====================
# Step 6: Check Python Dependencies
# ====================
print_step "Checking Python dependencies..."
echo ""

REQUIRED_PACKAGES=("paho.mqtt" "psycopg2" "fastapi" "uvicorn")
PACKAGE_NAMES=("paho-mqtt" "psycopg2" "fastapi" "uvicorn")

for i in "${!REQUIRED_PACKAGES[@]}"; do
    PACKAGE="${REQUIRED_PACKAGES[$i]}"
    NAME="${PACKAGE_NAMES[$i]}"

    if python3 -c "import ${PACKAGE}" 2>/dev/null; then
        print_success "Python package '$NAME' installed"
        ((TESTS_PASSED++))
    else
        print_error "Python package '$NAME' not installed"
        ((TESTS_FAILED++))
        DEPS_MISSING=1
    fi
done

if [ ! -z "$DEPS_MISSING" ]; then
    print_warning "Some dependencies are missing. Run: pip install -r requirements.txt"
fi

echo ""

# ====================
# Step 7: Check File Structure
# ====================
print_step "Checking project file structure..."
echo ""

FILES=(
    "docker-compose.yml"
    "requirements.txt"
    "database/schema.sql"
    "database/apply_schema.sh"
    "backend/mqtt_subscriber.py"
    "simulator/iot_device_simulator.py"
    "dashboard/api/main.py"
    "dashboard/frontend/index.html"
    "dashboard/start_dashboard.sh"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "File exists: $file"
        ((TESTS_PASSED++))
    else
        print_error "File missing: $file"
        ((TESTS_FAILED++))
    fi
done

echo ""

# ====================
# Step 8: Check Ports
# ====================
print_step "Checking port availability..."
echo ""

PORTS=(1883 5432 5050 8000 8080)
PORT_NAMES=("MQTT" "PostgreSQL" "pgAdmin" "Dashboard API" "Dashboard Frontend")

for i in "${!PORTS[@]}"; do
    PORT="${PORTS[$i]}"
    NAME="${PORT_NAMES[$i]}"

    if netstat -tuln 2>/dev/null | grep -q ":${PORT} "; then
        print_success "Port $PORT ($NAME) is in use"
        ((TESTS_PASSED++))
    else
        print_warning "Port $PORT ($NAME) is not in use"
    fi
done

echo ""

# ====================
# Summary
# ====================
echo "========================================================================"
echo "   Test Summary"
echo "========================================================================"
echo ""
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    print_success "All critical tests passed!"
    echo ""
    echo "========================================================================"
    echo "   System is ready to use!"
    echo "========================================================================"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Start Backend MQTT Subscriber (Terminal 1):"
    echo "   cd backend && python3 mqtt_subscriber.py"
    echo ""
    echo "2. Start IoT Simulator (Terminal 2):"
    echo "   cd simulator && python3 iot_device_simulator.py"
    echo ""
    echo "3. Start Dashboard (Terminal 3):"
    echo "   cd dashboard && ./start_dashboard.sh"
    echo ""
    echo "4. Open Dashboard in browser:"
    echo "   http://localhost:8080"
    echo ""
else
    print_error "Some tests failed. Please fix the issues above."
    echo ""
    echo "Common fixes:"
    echo "- Apply database schema: cd database && ./apply_schema.sh"
    echo "- Install Python dependencies: pip install -r requirements.txt"
    echo "- Start Docker services: sudo docker compose up -d"
    exit 1
fi
