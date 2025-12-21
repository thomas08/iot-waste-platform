# IoT Waste Platform - System Test Guide

## 🧪 วิธีทดสอบระบบ

### วิธีที่ 1: ใช้ Test Script (แนะนำ)

```bash
cd /home/tossaporn/iot-waste-platform
./test_system.sh
```

Script นี้จะตรวจสอบ:
- ✅ Docker services (MQTT, PostgreSQL, pgAdmin)
- ✅ Database connection
- ✅ Database schema และ tables
- ✅ Sample data
- ✅ MQTT broker connectivity
- ✅ Python dependencies
- ✅ Project file structure
- ✅ Port availability

---

### วิธีที่ 2: ทดสอบแต่ละ Component แยก

#### 1. ทดสอบ Docker Services

```bash
sudo docker compose ps
```

**Expected Output:**
```
NAME            STATUS
waste_mqtt      Up
waste_db        Up
waste_pgadmin   Up
```

#### 2. ทดสอบ Database

```bash
# Test connection
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "SELECT 1"

# Check tables
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "\dt"

# Check sample data
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "SELECT * FROM waste_bins"
```

#### 3. ทดสอบ MQTT Broker

```bash
# Subscribe (Terminal 1)
mosquitto_sub -h localhost -t "test/#" -v

# Publish (Terminal 2)
mosquitto_pub -h localhost -t "test/message" -m "Hello MQTT"
```

#### 4. ทดสอบ Python Dependencies

```bash
python3 -c "import paho.mqtt; print('paho-mqtt: OK')"
python3 -c "import psycopg2; print('psycopg2: OK')"
python3 -c "import fastapi; print('fastapi: OK')"
python3 -c "import uvicorn; print('uvicorn: OK')"
```

---

## 🚀 ทดสอบ Full System Integration

### Step 1: เริ่ม Backend Subscriber

```bash
cd backend
python3 mqtt_subscriber.py
```

**Expected Output:**
```
✅ Connected to database at localhost
✅ Connected to MQTT Broker at localhost:1883
📡 Subscribed to topic: waste/bins/+/sensors
🚀 MQTT Subscriber service started
📊 Waiting for sensor data...
```

### Step 2: เริ่ม IoT Simulator

```bash
cd simulator
python3 iot_device_simulator.py
```

**Expected Output:**
```
✅ Connected to MQTT Broker
🚀 Starting simulation with 5 bins
🟢 BIN001: Fill=35.2% | Temp=25.3°C | Battery=95.2%
```

### Step 3: เริ่ม Dashboard

```bash
cd dashboard
./start_dashboard.sh
```

**Expected Output:**
```
✅ API backend started
✅ Frontend server started
🌐 Open your browser and navigate to:
   👉 http://localhost:8080
```

### Step 4: ตรวจสอบ Dashboard

เปิด browser: http://localhost:8080

**ตรวจสอบว่ามี:**
1. ✅ Statistics cards แสดงตัวเลข (ไม่ใช่ --)
2. ✅ Chart มีข้อมูล (ไม่ใช่ empty)
3. ✅ Bins grid แสดง 5 cards
4. ✅ ข้อมูล auto-refresh ทุก 10 วินาที
5. ✅ Fill level เพิ่มขึ้นเรื่อยๆ

---

## 📊 Expected Results Timeline

| Time | What Should Happen |
|------|-------------------|
| 0s | Dashboard loads, shows loading state |
| 10s | First data appears from simulator |
| 20s | Statistics cards update |
| 30s | Charts start showing data |
| 60s | Fill levels visibly increasing |
| 2-3 min | Some bins reach >50% (yellow) |
| 5-10 min | Some bins reach >75% (alerts appear) |
| 10-15 min | Some bins reach >85% (auto-collection simulated) |

---

## 🔍 Verification Checklist

### Infrastructure
- [ ] MQTT Broker running (port 1883, 9001)
- [ ] PostgreSQL running (port 5432)
- [ ] pgAdmin running (port 5050)

### Database
- [ ] Can connect to database
- [ ] All tables exist (waste_bins, sensors, sensor_readings, alerts, collections, users, collection_routes, route_bins)
- [ ] Sample data loaded (5 bins, 5 sensors)
- [ ] Views created (v_bin_current_status, v_collection_stats)

### Backend Services
- [ ] MQTT Subscriber can connect to MQTT broker
- [ ] MQTT Subscriber can connect to database
- [ ] MQTT Subscriber receiving messages
- [ ] Data being saved to sensor_readings table
- [ ] Alerts being generated when needed

### Simulator
- [ ] Simulator can connect to MQTT broker
- [ ] Publishing messages every 10 seconds
- [ ] Fill levels increasing gradually
- [ ] Auto-collection working (reset when >85%)

### Dashboard
- [ ] API backend running (port 8000)
- [ ] Frontend running (port 8080)
- [ ] Can access dashboard in browser
- [ ] Statistics cards showing data
- [ ] Charts rendering correctly
- [ ] Bins grid displaying all bins
- [ ] Auto-refresh working (every 10 seconds)
- [ ] Alerts panel showing when bins >75%

---

## 📈 Performance Metrics

### Expected Performance:

| Metric | Expected Value |
|--------|---------------|
| Dashboard Load Time | < 2 seconds |
| API Response Time | < 500ms |
| MQTT Message Latency | < 100ms |
| Database Write Speed | > 100 inserts/sec |
| Dashboard Refresh | Every 10 seconds |

### Monitor Performance:

```bash
# Database queries per second
watch -n 1 'PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "SELECT COUNT(*) FROM sensor_readings"'

# MQTT message count
sudo docker compose logs mqtt | grep -c "Received PUBLISH"

# API response time
curl -w "@-" -o /dev/null -s http://localhost:8000/api/bins <<'EOF'
    time_total:  %{time_total}\n
EOF
```

---

## 🐛 Common Issues & Solutions

### Issue: No data in dashboard

**Diagnosis:**
```bash
# Check if simulator is sending data
sudo docker compose logs mqtt | tail -20

# Check if backend is receiving data
# Look at backend terminal output

# Check database
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "SELECT COUNT(*) FROM sensor_readings"
```

**Solution:**
- Ensure all 3 services are running (backend, simulator, dashboard)
- Check that sensors exist in database
- Verify MQTT broker is running

### Issue: Dashboard shows errors in console

**Diagnosis:**
- Open browser console (F12)
- Look for network errors or CORS errors

**Solution:**
```bash
# Restart API backend
cd dashboard/api
python3 main.py

# Clear browser cache
# Hard refresh: Ctrl+Shift+R
```

### Issue: Database connection errors

**Diagnosis:**
```bash
sudo docker compose ps
sudo docker compose logs db
```

**Solution:**
```bash
sudo docker compose restart db
# Wait 10 seconds
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb -c "SELECT 1"
```

---

## 📝 Test Report Template

```
=== IoT Waste Platform - Test Report ===

Date: [DATE]
Tester: [NAME]

Infrastructure Tests:
[ ] Docker Services Running
[ ] Database Connected
[ ] MQTT Broker Accessible

Data Flow Tests:
[ ] Simulator → MQTT → Working
[ ] MQTT → Backend → Working
[ ] Backend → Database → Working
[ ] Database → API → Working
[ ] API → Dashboard → Working

Feature Tests:
[ ] Real-time monitoring
[ ] Auto-refresh
[ ] Charts rendering
[ ] Alerts generation
[ ] Data persistence

Performance:
- Dashboard load time: ____ seconds
- API response time: ____ ms
- MQTT latency: ____ ms

Issues Found:
[List any issues]

Status: ✅ Pass / ❌ Fail
```

---

## 📞 Support

หากพบปัญหา:
1. ตรวจสอบ logs ของแต่ละ component
2. ดู [DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md)
3. อ่าน README ในแต่ละ directory
4. รัน `./test_system.sh` เพื่อหาปัญหา

---

**Last Updated**: 2025-12-19
**Status**: Ready for testing
