# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Senses Scale** — IoT platform for monitoring infectious waste (ขยะติดเชื้อ) weighing compliance in a hospital. Each hospital department has a scale; readings flow through MQTT into PostgreSQL; a FastAPI backend serves both the REST API and the frontend dashboard.

## Infrastructure

Three Docker Compose services. Always use `sudo` for Docker commands (user is not in the docker group).
**Note:** This server runs docker-compose **v1** — use `sudo docker-compose` (hyphen), NOT `docker compose`.

```bash
sudo docker-compose up -d                    # Start all services
sudo docker-compose ps
sudo docker-compose logs -f mqtt             # Follow MQTT broker logs
sudo docker-compose logs -f db               # Follow DB logs
sudo docker-compose down -v                  # Also wipes volumes (resets DB)
```

**Service endpoints:**
- MQTT Broker: `localhost:1883`
- PostgreSQL: `localhost:5432`, database `wastedb`, user `admin`, password `rootpassword`
- pgAdmin: `http://localhost:5050`
- **Dashboard + API: `http://localhost:8000`** (FastAPI serves both)

## Running Application Components

```bash
# 1. Start Docker services first
sudo docker compose up -d

# 2. Initialize database (first time only)
cd database && ./apply_schema.sh

# 3. Backend MQTT subscriber (receives sensor data → writes to DB)
cd backend && /path/to/venv/bin/python3 mqtt_subscriber.py

# 4. IoT device simulator (publishes W-OT and W-SUR2 readings every 10s)
cd simulator && /path/to/venv/bin/python3 iot_device_simulator.py

# 5. Dashboard API (serves frontend + API on :8000)
cd dashboard/api && /path/to/venv/bin/python3 main.py
```

Python venv: `/home/senses/iot-waste-platform/venv/`

**Access the app:** `http://localhost:8000/login.html`

**Login accounts (SHA-256 passwords):**

| Username | Password | Role |
|---|---|---|
| `admin` | `admin` | admin |
| `admin-weightiot` | `admin` | operator |
| `senses-weightiot` | `senses` | admin |

## Architecture

### Data Flow

```
simulator/iot_device_simulator.py
    ↓  MQTT publish: waste/bins/{W-OT|W-SUR2}/sensors  (every 10s)
mosquitto_secure/  (Mosquitto broker, port 1883)
    ↓  subscribe: waste/bins/+/sensors
backend/mqtt_subscriber.py
    ↓  looks up sensor_code in sensors table → inserts sensor_readings → generates alerts
PostgreSQL (wastedb)
    ↓  queried by
dashboard/api/main.py  (FastAPI, port 8000)
    │  also serves static files from dashboard/frontend/ via StaticFiles mount
    ↓
Browser at http://localhost:8000/login.html → index.html
```

The **frontend is NOT a separate server**. FastAPI mounts `dashboard/frontend/` as `StaticFiles` at `/` at the very end of `main.py`, after all API routes are registered. API routes take priority.

### Status/Compliance Model (app.js `cardStatus()`)

Status is based on time since last reading, **not fill level**:

| Status | Colour | Age of last reading |
|--------|--------|---------------------|
| `good` | 🟢 green | < 2 minutes |
| `medium` | 🟡 yellow | 2 min – 24 h |
| `high` | 🩷 pink | 24 h – 48 h |
| `offline` | ⚫ blue-grey | > 48 h |

### Timezone Handling

The DB container runs UTC+7 (`Asia/Bangkok`). The simulator must send timestamps in UTC+7. All API responses call `normalize_row()` which appends `+07:00` to any naive `datetime` values so JavaScript `Date` parsing is correct in any browser.

- `fix_ts(v)` in `main.py` — appends `+07:00` to naive datetimes
- `normalize_row(row)` — wraps a `RealDictRow`; applies `fix_ts` to all timestamp keys
- Simulator uses `datetime.now(TH_TZ)` where `TH_TZ = timezone(timedelta(hours=7))`

If timestamps in the DB look inconsistent (some UTC, some UTC+7), the `MAX(timestamp)` ordering will be wrong — the manual inserts via `psql NOW()` are UTC+7 while old Python inserts may be UTC.

### Key Files

| File | Role |
|------|------|
| `dashboard/api/main.py` | FastAPI: all API routes, auth, `normalize_row`, `StaticFiles` mount |
| `dashboard/frontend/app.js` | Polls API every 15s; compliance status logic; improved detail modal (fetches `/api/bins/{id}`) |
| `dashboard/frontend/login.html` | Login page; `const API = ''` (relative URL); class-based loading state |
| `dashboard/frontend/style.css` | All dashboard styles; Senses Scale colour palette defined in `:root` |
| `backend/mqtt_subscriber.py` | `DatabaseManager` + `MQTTSubscriber`; alert deduplication |
| `simulator/iot_device_simulator.py` | `WasteBinSensor` + `IoTSimulator`; simulates **W-OT** (bin_id=6) and **W-SUR2** (bin_id=12); weight = `random.uniform(0.5, 5.0)` |
| `simulator/esp32c3_waste_sensor/esp32c3_waste_sensor.ino` | Arduino sketch v2.0 — ESP32-C3/S3 sends all 10 departments via MQTT over WSS |
| `database/schema.sql` | Full schema; views `v_bin_current_status`, `v_collection_stats` |
| `deploy/*.service` | systemd unit files for production (api, subscriber, simulator) |
| `setup_production.sh` | One-time production setup script (cloudflared + systemd + docker) |

### Auth System (`/api/auth/*`)

In-memory session store `_sessions: dict` in `main.py` — tokens are lost when the API restarts. Passwords stored as SHA-256 hex digest. Sessions expire after 8 hours.

Endpoints: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/verify`

Frontend auth guard in `app.js`: checks `sessionStorage.getItem('ss_token')` on load; redirects to `login.html` if missing. Token is stored in `sessionStorage` (cleared on browser tab close).

### API Endpoints

```
GET  /api/bins                  — all active departments (status='active')
GET  /api/bins/{bin_id}         — detail + last 10 readings + collection history
GET  /api/stats/daily-weight    — 24h rolling weight totals per department
GET  /api/alerts?status=open    — open alerts
GET  /api/readings?hours=N      — raw readings for export
GET  /api/stats                 — summary statistics
GET  /api/stats/timeline        — data for charts
POST /api/auth/login            — {username, password} → {token, role, display_name}
POST /api/auth/logout           — Bearer token in Authorization header
GET  /api/auth/verify           — verify Bearer token
GET  /health                    — DB connectivity check
```

### Database

Core tables: `waste_bins`, `sensors`, `sensor_readings`, `alerts`, `collections`, `users`.

**Active departments:** W-OT, W-ER, W-ICU, W-MED1, W-MED2, W-SUR1, W-SUR2, W-OB, W-PED, W-OPD (bin_ids 6–15). BIN001–BIN005 (bin_ids 1–5) are `inactive`.

MQTT subscriber matches incoming data via `sensor_code` (e.g. `SENS006`, `SENS012`) + `bin_id` integer from the MQTT payload.

```bash
# Connect to DB (from host)
docker exec -it waste_db psql -U admin -d wastedb

# Useful queries
SELECT bin_code, location, last_reading FROM v_bin_current_status WHERE bin_status='active';
SELECT * FROM alerts WHERE status='open' ORDER BY triggered_at DESC;

# Insert a fresh reading to make a department green (< 2 min)
INSERT INTO sensor_readings (bin_id, fill_level, weight_kg, temperature_c, battery_level, signal_strength, timestamp)
SELECT bin_id, 0, 3.5, 24.0, 85, -65, NOW()
FROM waste_bins WHERE bin_code = 'W-OT';
```

### MQTT

Three roles defined in `mosquitto_secure/config/acl.conf`: `iot_device` (publish), `backend_service` (subscribe), `mqtt_admin` (full). Update passwords with `mosquitto_secure/setup_mqtt_auth_docker.sh`.

Mosquitto listens on two ports:
- `1883` — plain MQTT (local/internal use)
- `9001` — MQTT over WebSocket (used by ESP32 via Cloudflare Tunnel)

```bash
mosquitto_sub -h localhost -t "waste/bins/#" -v -u iot_user -P iotpassword
mosquitto_pub -h localhost -t "waste/bins/W-OT/sensors" \
  -m '{"bin_id":"6","bin_code":"W-OT","sensor_code":"SENS006","fill_level":20,"weight_kg":2.5,"temperature_c":24,"battery_level":85,"signal_strength":-60,"timestamp":"2026-02-24T02:00:00+07:00"}' \
  -u iot_user -P iotpassword
```

### Sensor Code Map (all 10 active departments)

| bin_id | bin_code | sensor_code   |
|--------|----------|---------------|
| 6      | W-OT     | SENS006       |
| 7      | W-ER     | SNS-W-ER      |
| 8      | W-ICU    | SNS-W-ICU     |
| 9      | W-MED1   | SNS-W-MED1    |
| 10     | W-MED2   | SNS-W-MED2    |
| 11     | W-SUR1   | SNS-W-SUR1    |
| 12     | W-SUR2   | SENS012       |
| 13     | W-OB     | SNS-W-OB      |
| 14     | W-PED    | SNS-W-PED     |
| 15     | W-OPD    | SNS-W-OPD     |

The `sensor_code` in MQTT payload must exactly match the `sensors` table — lookup fails silently if mismatched.

---

## Production Deployment

### Infrastructure

- **Server:** Ubuntu, user `senses`, project at `/home/senses/iot-waste-platform/`
- **Public dashboard:** `https://tuh.maker-hub.net`
- **MQTT WebSocket endpoint (for ESP32):** `wss://mqtt-tuh.maker-hub.net:443`
- **Cloudflare Tunnel ID:** `687700ec-8e5e-4885-8a2e-df93e6485ae0`
- **Tunnel config:** `/home/senses/.cloudflared/config.yml` (also copied to `/etc/cloudflared/config.yml`)

### Cloudflare Tunnel Architecture

ESP32/IoT devices cannot use raw TCP through Cloudflare Tunnel (requires Enterprise plan).
Solution: **MQTT over WebSocket (WSS port 443)** routed via Cloudflare Tunnel.

```
ESP32  ──wss://mqtt-tuh.maker-hub.net:443──►  Cloudflare Edge
                                                    │ (QUIC/HTTP)
                                               Cloudflare Tunnel
                                                    │
                                             Server localhost:9001
                                             (Mosquitto WebSocket)
                                                    │
                                          Mosquitto broker (1883/9001)
                                                    │
                                        backend/mqtt_subscriber.py
                                                    │
                                              PostgreSQL (wastedb)
```

The domain `mqtt-tuh.maker-hub.net` is covered by the wildcard SSL cert `*.maker-hub.net`.
**Do NOT use** `mqtt.tuh.maker-hub.net` — that's a 3rd-level subdomain not covered by the wildcard cert.

### systemd Services

Four services managed by systemd:

| Service | Description | Source |
|---------|-------------|--------|
| `iot-waste-api` | FastAPI dashboard + API on port 8000 | `deploy/iot-waste-api.service` |
| `iot-waste-subscriber` | MQTT subscriber → PostgreSQL | `deploy/iot-waste-subscriber.service` |
| `iot-waste-sim` | IoT simulator (W-OT + W-SUR2 every 10s) | `deploy/iot-waste-sim.service` |
| `cloudflared` | Cloudflare Tunnel (dashboard + MQTT WS) | system-installed |

```bash
# Check all service statuses
sudo systemctl status iot-waste-api iot-waste-subscriber iot-waste-sim cloudflared

# View live logs
sudo journalctl -u iot-waste-api -f
sudo journalctl -u iot-waste-subscriber -f
sudo journalctl -u iot-waste-sim -f
sudo journalctl -u cloudflared -f
```

### First-Time Production Setup

Run `setup_production.sh` once after cloning on a new server:

```bash
bash setup_production.sh
```

If `sudo cloudflared service install` fails with "cannot determine config path":

```bash
sudo cloudflared --config /home/senses/.cloudflared/config.yml service install
sudo cp /home/senses/.cloudflared/config.yml /etc/cloudflared/config.yml
sudo systemctl restart cloudflared
```

---

## Recovery Procedures (เมื่อเว็บพัง)

### Quick Status Check

```bash
# 1. Check all services at once
sudo systemctl status iot-waste-api iot-waste-subscriber iot-waste-sim cloudflared --no-pager

# 2. Check Docker containers (MQTT broker + PostgreSQL)
sudo docker-compose ps

# 3. Check if dashboard responds
curl -s http://localhost:8000/health
```

### Website/Dashboard Down

**Symptom:** `https://tuh.maker-hub.net` not loading or 502/504 error.

```bash
# Step 1: Check cloudflared tunnel
sudo systemctl status cloudflared
sudo journalctl -u cloudflared -n 30

# Step 2: Restart cloudflared if needed
sudo systemctl restart cloudflared

# Step 3: Check API service
sudo systemctl status iot-waste-api
sudo journalctl -u iot-waste-api -n 30

# Step 4: Restart API if needed
sudo systemctl restart iot-waste-api

# Step 5: Verify API is listening on port 8000
curl http://localhost:8000/health
```

### MQTT Data Not Flowing (departments showing offline)

**Symptom:** All departments showing offline/pink/yellow, no new readings in DB.

```bash
# Step 1: Check subscriber service
sudo systemctl status iot-waste-subscriber
sudo journalctl -u iot-waste-subscriber -n 50

# Step 2: Check Docker (MQTT broker must be running)
sudo docker-compose ps
sudo docker-compose logs mqtt | tail -20

# Step 3: Test MQTT locally
mosquitto_sub -h localhost -t "waste/bins/#" -v -u iot_user -P iotpassword &
mosquitto_pub -h localhost -t "waste/bins/W-OT/sensors" \
  -m '{"bin_id":"6","bin_code":"W-OT","sensor_code":"SENS006","fill_level":20,"weight_kg":2.5,"temperature_c":24,"battery_level":85,"signal_strength":-60}' \
  -u iot_user -P iotpassword

# Step 4: Restart subscriber
sudo systemctl restart iot-waste-subscriber

# Step 5: If Docker containers are down, restart them
sudo docker-compose up -d
sleep 5
sudo systemctl restart iot-waste-subscriber
```

### Full System Restart (everything broken)

```bash
# Stop all services
sudo systemctl stop iot-waste-api iot-waste-subscriber iot-waste-sim cloudflared

# Restart Docker (MQTT + DB)
sudo docker-compose down
sudo docker-compose up -d
sleep 5

# Start services in order
sudo systemctl start iot-waste-api
sleep 3
sudo systemctl start iot-waste-subscriber
sudo systemctl start iot-waste-sim
sudo systemctl start cloudflared

# Verify
sudo systemctl status iot-waste-api iot-waste-subscriber iot-waste-sim cloudflared --no-pager
curl http://localhost:8000/health
```

### Force a Department Green (for testing)

```bash
docker exec -it waste_db psql -U admin -d wastedb -c "
INSERT INTO sensor_readings (bin_id, fill_level, weight_kg, temperature_c, battery_level, signal_strength, timestamp)
SELECT bin_id, 0, 3.5, 24.0, 85, -65, NOW()
FROM waste_bins WHERE bin_code = 'W-OT';"
```

### Database Issues

```bash
# Connect to database
sudo docker exec -it waste_db psql -U admin -d wastedb

# Check recent readings
SELECT bin_code, MAX(timestamp) as last_seen FROM sensor_readings sr
JOIN waste_bins wb ON sr.bin_id = wb.bin_id GROUP BY bin_code ORDER BY last_seen DESC;

# Check current bin status
SELECT bin_code, last_reading FROM v_bin_current_status WHERE bin_status='active';

# If DB is completely corrupted — DANGER: wipes all data
sudo docker-compose down -v
sudo docker-compose up -d
sleep 5
cd /home/senses/iot-waste-platform/database && ./apply_schema.sh
```

---

## ESP32 Arduino Setup (MQTT over WebSocket)

### Required Library

Install via Arduino IDE Library Manager:
- **WebSockets** by Markus Sattler (links2004) — version 2.x

### Board Settings

- Board: **ESP32C3 Dev Module** (for ESP32-C3) or **ESP32S3 Dev Module** (for ESP32-S3)
- Upload Speed: 115200 or 921600
- USB CDC On Boot: Enabled (for Serial monitor)

### Sketch: `simulator/esp32c3_waste_sensor/esp32c3_waste_sensor.ino`

Current version: **2.0** — sends all 10 departments, one every 2s, repeats every 60s.

Key constants to change when deploying to a new network:
```cpp
const char* WIFI_SSID = "MakerHub_2.4G";       // WiFi network name
const char* WIFI_PASS = "makerhubhome";         // WiFi password
const char* WS_HOST   = "mqtt-tuh.maker-hub.net"; // MQTT WebSocket host (do not change)
const int   WS_PORT   = 443;                    // WSS port (do not change)
const char* MQTT_USER = "iot_user";             // MQTT username
const char* MQTT_PASS = "iotpassword";          // MQTT password
```

The sketch uses **manual MQTT packet framing** (no MQTT library) — connects via WebSocket SSL,
sends CONNECT packet, waits for CONNACK (`0x20`), then publishes sensor readings.
Topic format: `waste/bins/{bin_code}/sensors`

### Expected Serial Output

```
=== Waste Bin Multi-Dept Test v2.0 ===
จำนวนแผนก: 10

WiFi OK: 192.168.x.x
NTP sync OK
[WS] Connected → MQTT CONNECT
[MQTT] Connected OK! เริ่มส่งข้อมูลทุกแผนก...

[1/10] W-OT     fill=15% weight=1.2kg @ 2026-02-24T10:30:00+07:00
[2/10] W-ER     fill=72% weight=4.8kg @ 2026-02-24T10:30:02+07:00
...
✓ ส่งครบทุกแผนกแล้ว! ส่งซ้ำทุก 60 วินาที
```
