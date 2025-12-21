# Web Dashboard - IoT Waste Management Platform

Web dashboard สำหรับแสดงผลและติดตามสถานะของระบบจัดการขยะแบบ real-time

## 🎯 Features

- ✅ **Real-time Monitoring**: แสดงสถานะถังขยะแบบ real-time (auto-refresh ทุก 10 วินาที)
- ✅ **Statistics Overview**: สถิติรวมของระบบ
- ✅ **Interactive Charts**: กราฟแสดง fill level timeline และ bin status distribution
- ✅ **Bins Grid View**: แสดงถังขยะทั้งหมดพร้อมสถานะ
- ✅ **Active Alerts**: รายการ alerts ที่ยังไม่ได้แก้ไข
- ✅ **Responsive Design**: รองรับทุกขนาดหน้าจอ

## 🏗️ Architecture

```
Frontend (HTML/CSS/JS)
    ↓ HTTP Request
Backend API (FastAPI)
    ↓ SQL Query
PostgreSQL Database
```

## 📁 Structure

```
dashboard/
├── api/
│   └── main.py          # FastAPI backend
└── frontend/
    ├── index.html       # Main HTML
    ├── style.css        # Custom styles
    └── app.js           # JavaScript logic
```

## 🚀 Quick Start

### 1. ติดตั้ง Dependencies

```bash
# จาก project root
pip install -r requirements.txt
```

### 2. เริ่มต้น Backend API

```bash
cd dashboard/api
python3 main.py
```

API จะรันที่ `http://localhost:8000`

### 3. เปิด Frontend Dashboard

```bash
cd dashboard/frontend

# เปิดด้วย simple HTTP server
python3 -m http.server 8080
```

Dashboard จะรันที่ `http://localhost:8080`

**หรือเปิดไฟล์ `index.html` ด้วย browser โดยตรง**

## 📡 API Endpoints

Backend API มี endpoints ดังนี้:

### General

- `GET /` - API information
- `GET /health` - Health check

### Bins

- `GET /api/bins` - Get all bins with current status
- `GET /api/bins/{bin_id}` - Get specific bin details

### Sensors

- `GET /api/sensors` - Get all sensors

### Readings

- `GET /api/readings` - Get sensor readings
  - Query params: `bin_id`, `hours` (default: 24)

### Alerts

- `GET /api/alerts` - Get alerts
  - Query params: `status` (default: "open")

### Statistics

- `GET /api/stats` - Get overall statistics
- `GET /api/stats/timeline` - Get timeline statistics for charts
  - Query params: `hours` (default: 24)

## 🖥️ Dashboard Sections

### 1. Statistics Cards

แสดงข้อมูลสถิติหลัก:
- Total Bins
- Bins Need Attention (>75% full)
- Active Alerts
- Average Fill Level

### 2. Charts

**Fill Level Timeline**
- กราฟเส้นแสดง average fill level ในช่วง 24 ชั่วโมงที่ผ่านมา
- Auto-update ทุก 10 วินาที

**Bin Status Distribution**
- Pie chart แสดงการกระจายสถานะของถังขยะ
- แบ่งเป็น: Low, Medium, High, Critical

### 3. Bins Grid

แสดงถังขยะทั้งหมดในรูปแบบ cards:
- Bin code และ location
- Progress bar แสดง fill level
- Temperature, battery level, bin type
- Status badge (color-coded)
- Active alerts count

### 4. Active Alerts Panel

แสดง alerts ที่ยังไม่ได้แก้ไข:
- Alert type และ message
- Severity level (low, medium, high, critical)
- Timestamp
- Bin code

## ⚙️ Configuration

### Frontend (`app.js`)

```javascript
const API_BASE_URL = 'http://localhost:8000/api';
const REFRESH_INTERVAL = 10000; // 10 seconds
```

### Backend (`main.py`)

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "wastedb",
    "user": "admin",
    "password": "rootpassword"
}
```

## 📊 Data Flow

1. Frontend JavaScript calls API endpoints every 10 seconds
2. FastAPI backend queries PostgreSQL database
3. Data is returned as JSON
4. Frontend updates UI with new data
5. Charts are redrawn with latest data

## 🎨 UI Components

### Technologies Used

- **Bootstrap 5.3**: CSS framework
- **Bootstrap Icons**: Icon library
- **Chart.js 4.4**: Charting library
- **Vanilla JavaScript**: No frameworks required

### Color Scheme

- **Success (Green)**: Low fill level (<50%)
- **Info (Blue)**: Medium fill level (50-75%)
- **Warning (Yellow)**: High fill level (75-90%)
- **Danger (Red)**: Critical fill level (>90%)

## 🧪 Testing

### ทดสอบ API

```bash
# Check health
curl http://localhost:8000/health

# Get bins
curl http://localhost:8000/api/bins

# Get statistics
curl http://localhost:8000/api/stats

# Get alerts
curl http://localhost:8000/api/alerts?status=open
```

### ทดสอบ Dashboard

1. เริ่ม infrastructure: `sudo docker compose up -d`
2. Apply database schema: `cd database && ./apply_schema.sh`
3. เริ่ม backend service: `cd backend && python3 mqtt_subscriber.py`
4. เริ่ม simulator: `cd simulator && python3 iot_device_simulator.py`
5. เริ่ม API: `cd dashboard/api && python3 main.py`
6. เปิด dashboard: `cd dashboard/frontend && python3 -m http.server 8080`
7. เข้า http://localhost:8080

## 🔧 Development

### เพิ่ม API Endpoint ใหม่

1. แก้ไข `dashboard/api/main.py`
2. เพิ่ม endpoint function ด้วย `@app.get()` หรือ `@app.post()`
3. Return JSON response

### เพิ่ม UI Component

1. แก้ไข `dashboard/frontend/index.html` - เพิ่ม HTML structure
2. แก้ไข `dashboard/frontend/style.css` - เพิ่ม styles
3. แก้ไข `dashboard/frontend/app.js` - เพิ่ม logic

## 📱 Responsive Design

Dashboard รองรับหน้าจอทุกขนาด:
- Desktop: แสดง 2 bins per row
- Tablet: แสดง 1 bin per row
- Mobile: Stack layout

## 🔒 Security Notes

⚠️ **สำคัญ**: Dashboard ปัจจุบันเป็นแบบ development

สำหรับ production:
- ✅ เพิ่ม authentication/authorization
- ✅ ตั้งค่า CORS อย่างเหมาะสม
- ✅ ใช้ environment variables สำหรับ credentials
- ✅ ใช้ HTTPS
- ✅ Rate limiting สำหรับ API
- ✅ Input validation

## 🚀 Production Deployment

### ใช้ Nginx + Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Run API with gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker dashboard.api.main:app --bind 0.0.0.0:8000

# Serve frontend with nginx
# Configure nginx to serve static files and proxy API
```

### ใช้ Docker

```bash
# สร้าง Docker image (TODO)
docker build -t waste-dashboard .

# Run container
docker run -d -p 8000:8000 waste-dashboard
```

## 📈 Future Enhancements

- [ ] User authentication & authorization
- [ ] WebSocket สำหรับ real-time updates
- [ ] Export data เป็น CSV/PDF
- [ ] Historical data comparison
- [ ] Map view สำหรับแสดงตำแหน่งถังขยะ
- [ ] Notification system (email, LINE, SMS)
- [ ] Collection route optimization
- [ ] Predictive analytics (ML)
- [ ] Mobile app version

## 🐛 Troubleshooting

### API ไม่สามารถเชื่อมต่อ Database

```bash
# ตรวจสอบว่า PostgreSQL ทำงานอยู่
sudo docker compose ps

# ตรวจสอบ connection string ใน main.py
```

### CORS Error

แก้ไข CORS settings ใน `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # ระบุ origin ที่ต้องการ
    ...
)
```

### Charts ไม่แสดง

- ตรวจสอบว่า Chart.js โหลดสำเร็จ
- เปิด browser console เช็ค JavaScript errors
- ตรวจสอบว่า API return ข้อมูลถูกต้อง

## 📚 Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Chart.js Documentation](https://www.chartjs.org/)
- [Bootstrap Documentation](https://getbootstrap.com/)

---

**Created:** 2025-12-19
**Status:** ✅ Ready for development/testing
