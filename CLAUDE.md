# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IoT Waste Management Platform - A system for monitoring and managing waste collection using IoT sensors and MQTT protocol.

## Infrastructure

The project uses Docker Compose to run core services:

### Running Services

- **MQTT Broker (Mosquitto)** - Message broker for IoT device communication
- **PostgreSQL** - Main database for storing waste data
- **pgAdmin** - Database management interface

### Common Commands

**Start all services:**
```bash
sudo docker compose up -d
```

**Check service status:**
```bash
sudo docker compose ps
```

**View logs:**
```bash
sudo docker compose logs [service-name]
# Examples:
sudo docker compose logs mqtt
sudo docker compose logs db
sudo docker compose logs pgadmin
```

**Stop services:**
```bash
sudo docker compose stop
```

**Restart services:**
```bash
sudo docker compose restart
```

**Stop and remove containers:**
```bash
sudo docker compose down
```

**Stop and remove containers with volumes:**
```bash
sudo docker compose down -v
```

## Service Endpoints

- **MQTT Broker**: `mqtt://localhost:1883` (anonymous allowed for development)
- **PostgreSQL**: `localhost:5432`
  - Database: `wastedb`
  - User: `admin`
  - Password: `rootpassword`
- **pgAdmin**: `http://localhost:5050`
  - Email: `admin@admin.com`
  - Password: `rootpassword`

## Architecture

### MQTT Configuration

Located in `mosquitto/config/mosquitto.conf`:
- Persistence enabled at `/mosquitto/data/`
- Logs at `/mosquitto/log/mosquitto.log`
- Anonymous access allowed (development only)

### Data Flow

1. IoT devices (or simulator) publish sensor data to MQTT topics: `waste/bins/{bin_code}/sensors`
2. Backend service (`mqtt_subscriber.py`) subscribes to MQTT topics
3. Data is validated and stored in PostgreSQL `sensor_readings` table
4. System automatically generates alerts when needed (bin full, low battery, high temp)
5. Dashboard displays real-time waste management data (planned)

### MQTT Topics

- **Publish**: `waste/bins/{BIN_CODE}/sensors`
  - Example: `waste/bins/BIN001/sensors`
- **Subscribe**: `waste/bins/+/sensors` (wildcard for all bins)

## Application Components

### Database Setup

```bash
# Apply database schema
cd database
./apply_schema.sh

# Or manually
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb < schema.sql
```

**Key Tables:**
- `waste_bins` - Waste bin master data
- `sensors` - IoT sensor information
- `sensor_readings` - Time-series sensor data
- `alerts` - Automated alerts
- `collections` - Collection history
- `users` - System users

### Backend Service (MQTT Subscriber)

```bash
# Install dependencies first
pip install -r requirements.txt

# Run the subscriber service
cd backend
python3 mqtt_subscriber.py
```

**Features:**
- Subscribes to MQTT broker for sensor data
- Stores readings in PostgreSQL
- Auto-generates alerts for:
  - Bin full (>75% = high, >90% = critical)
  - Low battery (<20%)
  - High temperature (>45°C)

### IoT Device Simulator

```bash
# Run the simulator (for testing)
cd simulator
python3 iot_device_simulator.py
```

**Features:**
- Simulates 5 waste bins with sensors
- Publishes data every 10 seconds (configurable)
- Gradually increases fill level
- Simulates automatic collection when >85% full

## Development Workflow

### Full System Test

```bash
# Terminal 1: Start infrastructure
sudo docker compose up -d
sudo docker compose ps

# Terminal 2: Apply database schema (first time only)
cd database
./apply_schema.sh

# Terminal 3: Start backend service
cd backend
python3 mqtt_subscriber.py

# Terminal 4: Start simulator
cd simulator
python3 iot_device_simulator.py
```

### Testing MQTT Manually

```bash
# Install MQTT client tools
sudo apt-get install mosquitto-clients

# Subscribe to all topics
mosquitto_sub -h localhost -t "waste/bins/#" -v

# Publish test message
mosquitto_pub -h localhost -t "waste/bins/TEST/sensors" -m '{"bin_code": "TEST", "fill_level": 85.5}'
```

### Database Queries

```bash
# Connect to database
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb

# View current bin status
SELECT * FROM v_bin_current_status;

# View recent readings
SELECT bin_code, fill_level, temperature_c, battery_level, timestamp
FROM sensor_readings sr
JOIN waste_bins wb ON sr.bin_id = wb.bin_id
ORDER BY timestamp DESC LIMIT 20;

# View open alerts
SELECT * FROM alerts WHERE status = 'open' ORDER BY triggered_at DESC;
```

### Web Dashboard

```bash
# Quick start (starts both API and frontend)
cd dashboard
./start_dashboard.sh

# Or start separately:
# Terminal 1: API Backend
cd dashboard/api
python3 main.py  # Runs on http://localhost:8000

# Terminal 2: Frontend
cd dashboard/frontend
python3 -m http.server 8080  # Runs on http://localhost:8080
```

**Dashboard Features:**
- Real-time bin monitoring with auto-refresh (10 seconds)
- Statistics overview (total bins, alerts, fill levels)
- Interactive charts (fill level timeline, status distribution)
- Bins grid view with color-coded status
- Active alerts panel

**API Endpoints:**
- `GET /api/bins` - All bins with current status
- `GET /api/bins/{bin_id}` - Specific bin details
- `GET /api/sensors` - All sensors
- `GET /api/readings` - Sensor readings (query: bin_id, hours)
- `GET /api/alerts` - Alerts (query: status)
- `GET /api/stats` - Overall statistics
- `GET /api/stats/timeline` - Timeline data for charts
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation (FastAPI Swagger)

## Development Notes

- Always use `sudo` for docker commands (user not in docker group)
- MQTT broker allows anonymous connections - change for production
- Default credentials are for development only - rotate for production
- Python virtual environment recommended: `python3 -m venv venv && source venv/bin/activate`
- Dashboard runs on port 8000 (API) and 8080 (Frontend)
- See `DEPLOYMENT_LOG.md` for detailed setup history
- Each component has its own README in its directory
