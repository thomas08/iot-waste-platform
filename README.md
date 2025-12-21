# IoT Waste Management Platform

ระบบจัดการขยะอัจฉริยะด้วย IoT sensors สำหรับติดตามระดับขยะแบบ real-time และเพิ่มประสิทธิภาพการเก็บขยะ

## 🎯 Features

- ✅ **Real-time Monitoring**: ติดตามระดับขยะในถังขยะแบบ real-time
- ✅ **Smart Alerts**: แจ้งเตือนอัตโนมัติเมื่อถังขยะเต็ม หรือมีปัญหา
- ✅ **MQTT Protocol**: ใช้ MQTT สำหรับการสื่อสารกับ IoT devices
- ✅ **Database Storage**: บันทึกข้อมูล time-series ใน PostgreSQL
- ✅ **IoT Simulator**: จำลอง IoT devices สำหรับทดสอบ
- ✅ **Web Dashboard**: แสดงข้อมูลและสถิติแบบ real-time พร้อมกราฟ
- ✅ **REST API**: FastAPI backend สำหรับเข้าถึงข้อมูล
- ✅ **Route Optimization**: วางแผนเส้นทางการเก็บขยะ (planned)

## 🏗️ Architecture

```
┌─────────────────┐
│  IoT Devices    │ ─┐
│   (Sensors)     │  │
└─────────────────┘  │
                     │ MQTT Publish
┌─────────────────┐  │  (waste/bins/+/sensors)
│   Simulator     │ ─┘
│   (Testing)     │
└─────────────────┘
         │
         v
┌─────────────────────────────────┐
│      MQTT Broker (Mosquitto)    │
│         Port: 1883, 9001        │
└─────────────────────────────────┘
         │
         │ MQTT Subscribe
         v
┌─────────────────────────────────┐
│   Backend Service (Python)      │
│   - MQTT Subscriber              │
│   - Data Processing              │
│   - Alert Generation             │
└─────────────────────────────────┘
         │
         v
┌─────────────────────────────────┐
│   PostgreSQL Database            │
│   - sensor_readings              │
│   - waste_bins                   │
│   - alerts                       │
│   - collections                  │
└─────────────────────────────────┘
         │
         ├──────────────────────┐
         v                      v
┌──────────────────────┐  ┌──────────────────────┐
│  pgAdmin (Web UI)     │  │  Dashboard API       │
│  http://localhost:5050│  │  (FastAPI)           │
└──────────────────────┘  │  http://localhost:8000│
                          └──────────────────────┘
                                   │
                                   v
                          ┌──────────────────────┐
                          │  Web Dashboard       │
                          │  (HTML/CSS/JS)       │
                          │  http://localhost:8080│
                          └──────────────────────┘
```

## 📁 Project Structure

```
iot-waste-platform/
├── backend/                    # Backend MQTT services
│   ├── mqtt_subscriber.py     # MQTT subscriber service
│   └── README.md
├── database/                   # Database schemas and scripts
│   ├── schema.sql             # PostgreSQL schema
│   ├── apply_schema.sh        # Schema deployment script
│   └── README.md
├── dashboard/                  # Web Dashboard
│   ├── api/
│   │   └── main.py            # FastAPI REST API
│   ├── frontend/
│   │   ├── index.html         # Dashboard HTML
│   │   ├── style.css          # Custom styles
│   │   └── app.js             # Dashboard JavaScript
│   ├── start_dashboard.sh     # Dashboard launcher script
│   └── README.md
├── simulator/                  # IoT device simulator
│   ├── iot_device_simulator.py
│   └── README.md
├── mosquitto/                  # MQTT broker configuration
│   ├── config/
│   │   └── mosquitto.conf
│   ├── data/                  # Persistence data
│   └── log/                   # Broker logs
├── docker-compose.yml         # Docker services configuration
├── requirements.txt           # Python dependencies
├── CLAUDE.md                  # Claude Code guidance
├── DEPLOYMENT_LOG.md          # Deployment history
└── README.md                  # This file
```

## 🚀 Quick Start

### 1. เริ่มต้น Infrastructure

```bash
# Start all Docker services
cd /home/tossaporn/iot-waste-platform
sudo docker compose up -d

# ตรวจสอบสถานะ
sudo docker compose ps
```

### 2. ติดตั้ง Database Schema

```bash
cd database
./apply_schema.sh
```

### 3. ติดตั้ง Python Dependencies

```bash
# สร้าง virtual environment (แนะนำ)
python3 -m venv venv
source venv/bin/activate

# ติดตั้ง packages
pip install -r requirements.txt
```

### 4. เริ่มต้น Backend Service

```bash
# Terminal 1: MQTT Subscriber
cd backend
python3 mqtt_subscriber.py
```

### 5. เริ่มต้น IoT Simulator

```bash
# Terminal 2: IoT Device Simulator
cd simulator
python3 iot_device_simulator.py
```

### 6. เริ่มต้น Web Dashboard

```bash
# Terminal 3: Dashboard (API + Frontend)
cd dashboard
./start_dashboard.sh
```

หรือเริ่มแยก:

```bash
# Terminal 3: API Backend
cd dashboard/api
python3 main.py

# Terminal 4: Frontend
cd dashboard/frontend
python3 -m http.server 8080
```

**เปิด Dashboard:** http://localhost:8080

**API Docs:** http://localhost:8000/docs

## 🔧 Services & Ports

| Service | Port | URL/Endpoint | Credentials |
|---------|------|--------------|-------------|
| MQTT Broker | 1883, 9001 | mqtt://localhost:1883 | anonymous |
| PostgreSQL | 5432 | localhost:5432 | admin / rootpassword |
| pgAdmin | 5050 | http://localhost:5050 | admin@admin.com / rootpassword |
| **Dashboard API** | **8000** | **http://localhost:8000** | - |
| **Web Dashboard** | **8080** | **http://localhost:8080** | - |

## 📊 Database Schema

### Main Tables

- **waste_bins**: ข้อมูลถังขยะทั้งหมด
- **sensors**: IoT sensors ที่ติดตั้ง
- **sensor_readings**: Time-series data จาก sensors
- **collections**: ประวัติการเก็บขยะ
- **alerts**: การแจ้งเตือนอัตโนมัติ
- **users**: ผู้ใช้งานระบบ
- **collection_routes**: เส้นทางการเก็บขยะ

### Views

- **v_bin_current_status**: สถานะปัจจุบันของถังขยะ
- **v_collection_stats**: สถิติการเก็บขยะ

ดูรายละเอียดเพิ่มเติมใน [database/README.md](database/README.md)

## 🧪 Testing

### ทดสอบ MQTT Broker

```bash
# ติดตั้ง mosquitto clients
sudo apt-get install mosquitto-clients

# Subscribe to all bin topics
mosquitto_sub -h localhost -t "waste/bins/#" -v

# Publish test message
mosquitto_pub -h localhost -t "waste/bins/TEST/sensors" -m '{"test": true}'
```

### ตรวจสอบข้อมูลใน Database

```bash
# เชื่อมต่อ PostgreSQL
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb

# ดูข้อมูลล่าสุด
SELECT * FROM v_bin_current_status;

# ดู sensor readings ล่าสุด
SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 10;

# ดู alerts ที่เปิดอยู่
SELECT * FROM alerts WHERE status = 'open';
```

## 📚 Documentation

### Quick Start & Testing
- [**Quick Start Guide**](quick_start.md) - 🚀 วิธีเริ่มต้นระบบแบบครบ
- [**System Test Guide**](SYSTEM_TEST_GUIDE.md) - 🧪 วิธีทดสอบระบบ

### Component Guides
- [**Dashboard**](dashboard/README.md) - Web dashboard และ REST API
- [Backend Service](backend/README.md) - MQTT subscriber และ data processing
- [Database](database/README.md) - Schema และการติดตั้ง
- [Simulator](simulator/README.md) - IoT device simulator

### Reference
- [CLAUDE.md](CLAUDE.md) - สำหรับ Claude Code
- [DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md) - ประวัติการติดตั้ง

## 🛠️ Development

### จัดการ Docker Services

```bash
# ดู logs
sudo docker compose logs -f [service-name]

# Restart service
sudo docker compose restart [service-name]

# Stop all services
sudo docker compose stop

# Stop and remove containers
sudo docker compose down

# Stop and remove with volumes (⚠️ ลบข้อมูลทั้งหมด)
sudo docker compose down -v
```

### Virtual Environment

```bash
# สร้าง venv
python3 -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
# หรือ
venv\Scripts\activate     # Windows

# Deactivate
deactivate
```

## 📈 Future Enhancements

- [x] REST API สำหรับเข้าถึงข้อมูล ✅
- [x] Web Dashboard ✅
- [ ] User Authentication & Authorization
- [ ] WebSocket สำหรับ real-time updates
- [ ] Mobile App สำหรับ operators
- [ ] Map View สำหรับแสดงตำแหน่งถังขยะ
- [ ] Route Optimization Algorithm
- [ ] Machine Learning สำหรับทำนายการเต็มของถังขยะ
- [ ] Notification System (Email, LINE, SMS)
- [ ] Export Reports (PDF, Excel)
- [ ] Historical Data Analysis & Trends

## ⚙️ Configuration

### Environment Variables (Future)

สร้างไฟล์ `.env`:

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=wastedb
DB_USER=admin
DB_PASSWORD=rootpassword

# MQTT
MQTT_BROKER=localhost
MQTT_PORT=1883

# Application
LOG_LEVEL=INFO
```

## 🔒 Security Notes

⚠️ **สำคัญ**: Configuration ปัจจุบันเป็นแบบ development

สำหรับ production ควร:
- ✅ เปลี่ยน passwords และ credentials ทั้งหมด
- ✅ ปิด anonymous access ของ MQTT broker
- ✅ เพิ่ม authentication ให้ MQTT
- ✅ ใช้ HTTPS/TLS สำหรับ connections
- ✅ ตั้งค่า firewall rules
- ✅ ใช้ environment variables สำหรับ secrets
- ✅ Regular security updates

## 📝 License

This project is for educational and development purposes.

## 👥 Contributors

- DevOps Engineer - Infrastructure Setup
- Backend Developer - Services Development
- IoT Engineer - Device Integration

## 📞 Support

สำหรับคำถามหรือปัญหา:
- ดู [DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md) สำหรับประวัติการติดตั้ง
- ตรวจสอบ logs: `sudo docker compose logs [service-name]`
- ดู individual README files ในแต่ละ directory

---

**Last Updated**: 2025-12-19
**Status**: ✅ Infrastructure Ready, Backend Services Implemented
