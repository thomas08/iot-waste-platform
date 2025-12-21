# Database Schema - IoT Waste Platform

## ภาพรวม

Database ถูกออกแบบมาเพื่อรองรับระบบจัดการขยะอัจฉริยะด้วย IoT ประกอบด้วย:
- การติดตาม real-time ของระดับขยะในถังขยะ
- บันทึกประวัติการเก็บขยะ
- ระบบแจ้งเตือนอัตโนมัติ
- การจัดการเส้นทางการเก็บขยะ

## ตารางหลัก

### 1. waste_bins
เก็บข้อมูลถังขยะทั้งหมด
- `bin_id`: Primary key
- `bin_code`: รหัสถังขยะ (unique)
- `location`: ตำแหน่งที่ตั้ง
- `latitude`, `longitude`: พิกัด GPS
- `capacity`: ความจุ (ลิตร)
- `bin_type`: ประเภท (general, recycle, organic, hazardous)

### 2. sensors
ข้อมูล sensors ที่ติดตั้ง
- `sensor_id`: Primary key
- `sensor_code`: รหัส sensor (unique)
- `bin_id`: อ้างอิงถึงถังขยะ
- `sensor_type`: ประเภท sensor (ultrasonic, weight, temperature, gas)

### 3. sensor_readings
บันทึกค่าจาก sensors (Time-series data)
- `reading_id`: Primary key
- `sensor_id`, `bin_id`: Foreign keys
- `fill_level`: ระดับความเต็ม (%)
- `temperature_c`: อุณหภูมิ
- `battery_level`: แบตเตอรี่
- `timestamp`: เวลาที่อ่านค่า

### 4. collections
ประวัติการเก็บขยะ
- `collection_id`: Primary key
- `bin_id`: ถังขยะที่เก็บ
- `collected_by`: ผู้เก็บขยะ
- `fill_level_before`: ระดับก่อนเก็บ
- `weight_collected`: น้ำหนักที่เก็บได้

### 5. alerts
การแจ้งเตือน
- `alert_id`: Primary key
- `bin_id`: ถังขยะที่เกิดปัญหา
- `alert_type`: ประเภทการแจ้งเตือน
- `severity`: ความรุนแรง (low, medium, high, critical)
- `status`: สถานะ (open, acknowledged, resolved)

### 6. users
ผู้ใช้งานระบบ
- `user_id`: Primary key
- `username`, `email`: ข้อมูลล็อกอิน
- `role`: บทบาท (admin, operator, viewer)

### 7. collection_routes & route_bins
เส้นทางการเก็บขยะ และความสัมพันธ์กับถังขยะ

## Views

### v_bin_current_status
แสดงสถานะปัจจุบันของถังขยะทั้งหมด พร้อมข้อมูลการอ่านค่าล่าสุด

### v_collection_stats
สถิติการเก็บขยะของแต่ละถัง

## การติดตั้ง

### วิธีที่ 1: ผ่าน psql command line
```bash
# เชื่อมต่อ database
PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb < schema.sql
```

### วิธีที่ 2: ผ่าน Docker exec
```bash
# Copy schema file เข้า container
sudo docker cp schema.sql waste_db:/tmp/schema.sql

# รัน schema
sudo docker exec -it waste_db psql -U admin -d wastedb -f /tmp/schema.sql
```

### วิธีที่ 3: ผ่าน pgAdmin
1. เปิด http://localhost:5050
2. Login ด้วย admin@admin.com / rootpassword
3. Add Server:
   - Name: Waste DB
   - Host: db (หรือ waste_db)
   - Port: 5432
   - Username: admin
   - Password: rootpassword
4. เปิด Query Tool และรัน schema.sql

## ตรวจสอบการติดตั้ง

```sql
-- ตรวจสอบตาราง
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- ตรวจสอบข้อมูลตัวอย่าง
SELECT * FROM waste_bins;
SELECT * FROM sensors;

-- ดูสถานะถังขยะ
SELECT * FROM v_bin_current_status;
```

## ข้อมูลตัวอย่าง

Schema มีข้อมูลตัวอย่างดังนี้:
- 5 ถังขยะ (BIN001-BIN005)
- 5 sensors (SENS001-SENS005)
- 1 user admin (username: admin, password: admin)

## Indexes

ระบบมี indexes สำหรับเพิ่มประสิทธิภาพการค้นหา:
- sensor_readings: timestamp, bin_id, sensor_id
- collections: bin_id, collection_time
- alerts: bin_id, status, triggered_at

## Auto-update Timestamp

ตาราง waste_bins, sensors, alerts, users, และ collection_routes จะอัพเดท `updated_at` อัตโนมัติเมื่อมีการแก้ไขข้อมูล
