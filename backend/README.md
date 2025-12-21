# Backend Service - MQTT Subscriber

บริการ backend ที่รับข้อมูลจาก MQTT broker และบันทึกลง PostgreSQL database

## คุณสมบัติ

- ✅ Subscribe ข้อมูล sensor จาก MQTT
- ✅ บันทึกข้อมูลลง PostgreSQL
- ✅ ตรวจจับและสร้าง alerts อัตโนมัติ
- ✅ Alert เมื่อถังขยะเต็ม (>75%, >90%)
- ✅ Alert เมื่อแบตเตอรี่ต่ำ (<20%)
- ✅ Alert เมื่ออุณหภูมิสูง (>45°C)
- ✅ ป้องกัน duplicate alerts

## การติดตั้ง

```bash
# ติดตั้ง dependencies
pip install -r ../requirements.txt

# หรือ
pip install paho-mqtt psycopg2-binary python-dotenv
```

## การใช้งาน

### เริ่มต้น Subscriber Service

```bash
python3 mqtt_subscriber.py
```

### Configuration

แก้ไขใน `mqtt_subscriber.py`:

```python
# Database Settings
db_manager = DatabaseManager(
    host="localhost",
    port=5432,
    database="wastedb",
    user="admin",
    password="rootpassword"
)

# MQTT Broker Settings
subscriber = MQTTSubscriber(
    mqtt_broker="localhost",
    mqtt_port=1883,
    db_manager=db_manager
)
```

## MQTT Topics

Subscribe ไปที่:
- `waste/bins/+/sensors` (wildcard สำหรับทุก bin)

## Database Tables ที่ใช้

### sensor_readings
บันทึกข้อมูลจาก sensors ทุกครั้งที่ได้รับ

### alerts
สร้าง alerts เมื่อตรวจพบสภาวะผิดปกติ:

| Alert Type | Severity | Condition |
|------------|----------|-----------|
| bin_full | critical | fill_level >= 90% |
| bin_full | high | fill_level >= 75% |
| sensor_fault | medium | battery < 20% |
| unusual_activity | high | temperature > 45°C |

## ตัวอย่าง Output

```
2025-12-19 10:30:00 - INFO - ✅ Connected to database at localhost
2025-12-19 10:30:00 - INFO - 🔌 Connecting to MQTT broker localhost:1883...
2025-12-19 10:30:00 - INFO - ✅ Connected to MQTT Broker
2025-12-19 10:30:00 - INFO - 📡 Subscribed to topic: waste/bins/+/sensors
2025-12-19 10:30:00 - INFO - 🚀 MQTT Subscriber service started
2025-12-19 10:30:00 - INFO - 📊 Waiting for sensor data...

🟢 Received from BIN001: Fill=35.2% | Temp=25.3°C | Battery=95.2%
🟡 Received from BIN003: Fill=68.5% | Temp=26.1°C | Battery=88.3%
🔴 Received from BIN004: Fill=89.2% | Temp=29.4°C | Battery=85.7%
🚨 ALERT [HIGH]: Bin BIN004 is 89.2% full - collection needed soon
```

## การตรวจสอบข้อมูล

### ดูข้อมูล sensor readings

```bash
# เชื่อมต่อ database
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb

# Query ข้อมูลล่าสุด
SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 10;

# ดูสถานะปัจจุบันของถังขยะ
SELECT * FROM v_bin_current_status;

# ดู alerts ที่ยังไม่ได้แก้ไข
SELECT * FROM alerts WHERE status = 'open' ORDER BY triggered_at DESC;
```

### ผ่าน pgAdmin

1. เปิด http://localhost:5050
2. Login: admin@admin.com / rootpassword
3. เชื่อมต่อ server "db"
4. เปิด Query Tool และรัน queries

## หยุดการทำงาน

กด `Ctrl+C` เพื่อหยุด service

## Troubleshooting

### ไม่สามารถเชื่อมต่อ Database

```bash
# ตรวจสอบว่า PostgreSQL ทำงานอยู่
sudo docker compose ps

# ดู logs
sudo docker compose logs db

# ตรวจสอบว่า schema ถูก apply แล้ว
cd ../database
./apply_schema.sh
```

### ไม่สามารถเชื่อมต่อ MQTT Broker

```bash
# ตรวจสอบ MQTT broker
sudo docker compose logs mqtt

# Restart broker
sudo docker compose restart mqtt
```

### Sensor not found in database

ตรวจสอบว่า sensor มีอยู่ใน database:

```sql
SELECT * FROM sensors;
```

ถ้าไม่มี ให้ insert:

```sql
INSERT INTO sensors (sensor_code, bin_id, sensor_type)
VALUES ('SENS001', 1, 'ultrasonic');
```

## Architecture Flow

```
IoT Devices (Simulator)
       |
       | MQTT Publish
       v
   MQTT Broker (Mosquitto)
       |
       | MQTT Subscribe
       v
MQTT Subscriber (this service)
       |
       | PostgreSQL INSERT
       v
   PostgreSQL Database
       |
       v
  Generate Alerts (if needed)
```
