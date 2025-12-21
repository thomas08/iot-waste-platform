# IoT Waste Platform - Quick Start Guide

## 🚀 วิธีเริ่มต้นระบบแบบครบ (Full System)

### ขั้นตอนที่ 1: ตรวจสอบระบบ

```bash
# รัน test script เพื่อตรวจสอบว่าทุกอย่างพร้อม
./test_system.sh
```

หาก test ผ่านทั้งหมด ให้ดำเนินการต่อ ❌ หาก test ไม่ผ่าน ให้แก้ไขตามที่ script แนะนำ

---

### ขั้นตอนที่ 2: เตรียมข้อมูล (First Time Only)

```bash
# ติดตั้ง Python dependencies
pip install -r requirements.txt

# Apply database schema
cd database
./apply_schema.sh
cd ..
```

---

### ขั้นตอนที่ 3: เริ่มต้นระบบ

คุณจะต้องเปิด **3 terminals** เพื่อรันระบบทั้งหมด:

#### **Terminal 1: Backend MQTT Subscriber**
```bash
cd /home/tossaporn/iot-waste-platform/backend
python3 mqtt_subscriber.py
```

**Output ที่คาดหวัง:**
```
✅ Connected to database at localhost
🔌 Connecting to MQTT broker localhost:1883...
✅ Connected to MQTT Broker at localhost:1883
📡 Subscribed to topic: waste/bins/+/sensors
🚀 MQTT Subscriber service started
📊 Waiting for sensor data...
```

---

#### **Terminal 2: IoT Device Simulator**
```bash
cd /home/tossaporn/iot-waste-platform/simulator
python3 iot_device_simulator.py
```

**Output ที่คาดหวัง:**
```
🔌 Connecting to MQTT broker localhost:1883...
✅ Connected to MQTT Broker
➕ Added bin: BIN001 at Building A - Floor 1
➕ Added bin: BIN002 at Building A - Floor 2
...
🚀 Starting simulation with 5 bins
```

ใน Terminal 1 (Backend) คุณจะเห็น:
```
🟢 Received from BIN001: Fill=35.2% | Temp=25.3°C | Battery=95.2%
💾 Saved reading for BIN001
```

---

#### **Terminal 3: Web Dashboard**
```bash
cd /home/tossaporn/iot-waste-platform/dashboard
./start_dashboard.sh
```

**Output ที่คาดหวัง:**
```
🚀 Starting API backend on http://localhost:8000...
✅ API backend started
🌐 Starting frontend server on http://localhost:8080...
✅ Frontend server started

========================================
✅ Dashboard is running!
========================================

🌐 Open your browser and navigate to:
   👉 http://localhost:8080
```

---

### ขั้นตอนที่ 4: เปิด Dashboard

เปิด browser แล้วไปที่:
- **Dashboard**: http://localhost:8080
- **API Docs**: http://localhost:8000/docs
- **pgAdmin**: http://localhost:5050

---

## 📊 สิ่งที่คุณจะเห็นใน Dashboard

### หลังจาก 10-30 วินาที:

1. **Statistics Cards** จะอัพเดทด้วย:
   - Total Bins: 5
   - Bins Need Attention: 0-2 (ขึ้นอยู่กับ fill level)
   - Active Alerts: 0-3
   - Avg Fill Level: 30-60%

2. **Fill Level Timeline Chart**
   - กราฟเส้นแสดงการเพิ่มขึ้นของ fill level

3. **Bin Status Distribution (Pie Chart)**
   - แสดงจำนวน bins แต่ละสถานะ

4. **Bins Grid**
   - 5 cards แสดงถังขยะ BIN001-BIN005
   - แต่ละ card แสดง:
     - Fill level (progress bar)
     - Temperature
     - Battery level
     - Bin type
     - Status badge (color-coded)

5. **Active Alerts Panel**
   - เมื่อถังขยะเริ่มเต็ม (>75%) จะมี alert แสดง

### การทำงานของระบบ:

```
Simulator → MQTT Broker → Backend Subscriber → PostgreSQL Database
                                                        ↓
                                                  Dashboard API
                                                        ↓
                                                  Web Dashboard
```

---

## 🧪 ทดสอบ Features

### 1. ทดสอบ Auto-refresh
- Dashboard จะ refresh ทุก 10 วินาทีอัตโนมัติ
- Fill level จะเพิ่มขึ้นเรื่อยๆ

### 2. ทดสอบ Alerts
- รอจนถังขยะเต็ม >75%
- จะมี alert แสดงใน Active Alerts panel
- Bin card จะแสดง warning badge

### 3. ทดสอบ Collection Simulation
- Simulator จะ reset ถังขยะอัตโนมัติเมื่อเต็ม >85%
- Fill level จะกลับไปต่ำ

### 4. ทดสอบ API
เปิด http://localhost:8000/docs
- ทดลองเรียก API endpoints ต่างๆ
- ดู response data

### 5. ทดสอบ Database
```bash
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb

-- ดูสถานะปัจจุบัน
SELECT * FROM v_bin_current_status;

-- ดู readings ล่าสุด
SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 10;

-- ดู alerts
SELECT * FROM alerts WHERE status = 'open';
```

---

## ⏹️ หยุดระบบ

### วิธีหยุดแต่ละ component:

1. **Dashboard** (Terminal 3): กด `Ctrl+C`
2. **Simulator** (Terminal 2): กด `Ctrl+C`
3. **Backend Subscriber** (Terminal 1): กด `Ctrl+C`

### หยุด Docker services (ถ้าต้องการ):
```bash
sudo docker compose stop
```

---

## 🔄 Restart ระบบ

ไม่ต้องทำขั้นตอนที่ 1-2 อีก เริ่มจาก Terminal 1-3 เลย:

```bash
# Terminal 1
cd backend && python3 mqtt_subscriber.py

# Terminal 2
cd simulator && python3 iot_device_simulator.py

# Terminal 3
cd dashboard && ./start_dashboard.sh
```

---

## 🐛 Troubleshooting

### ปัญหา: Backend ไม่สามารถเชื่อมต่อ Database
```bash
# ตรวจสอบ PostgreSQL
sudo docker compose ps
sudo docker compose logs db

# ทดสอบ connection
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "SELECT 1"
```

### ปัญหา: Simulator ไม่สามารถเชื่อมต่อ MQTT
```bash
# ตรวจสอบ MQTT broker
sudo docker compose logs mqtt

# Restart broker
sudo docker compose restart mqtt
```

### ปัญหา: Dashboard ไม่แสดงข้อมูล
- ตรวจสอบว่า Backend Subscriber กำลังรันอยู่
- ตรวจสอบว่า Simulator กำลังส่งข้อมูล
- เปิด browser console (F12) เช็ค errors
- ตรวจสอบว่า API endpoint ถูกต้อง (http://localhost:8000/api/bins)

### ปัญหา: Port already in use
```bash
# หา process ที่ใช้ port
sudo lsof -i :8000  # Dashboard API
sudo lsof -i :8080  # Dashboard Frontend
sudo lsof -i :1883  # MQTT

# Kill process
kill -9 <PID>
```

### ปัญหา: Python dependencies หายไป
```bash
# ติดตั้งใหม่
pip install -r requirements.txt

# หรือใช้ virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📖 เอกสารเพิ่มเติม

- [Main README](README.md) - Overview ทั้งหมด
- [Dashboard README](dashboard/README.md) - Web dashboard
- [Backend README](backend/README.md) - MQTT subscriber
- [Simulator README](simulator/README.md) - IoT simulator
- [Database README](database/README.md) - Database schema
- [CLAUDE.md](CLAUDE.md) - สำหรับ AI assistants
- [DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md) - ประวัติการติดตั้ง

---

**Created**: 2025-12-19
**Status**: ✅ Ready for testing
