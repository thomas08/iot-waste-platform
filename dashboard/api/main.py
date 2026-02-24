#!/usr/bin/env python3
"""
FastAPI Backend for IoT Waste Platform Dashboard
Provides REST API endpoints for frontend dashboard
"""

import os
import hashlib
import secrets
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import re
from dotenv import load_dotenv
import time

# In-memory session store: {token: {username, role, display_name, expires}}
_sessions: dict = {}

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configure logging
log_level = logging.DEBUG if os.getenv('DEBUG', 'false').lower() == 'true' else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Application configuration from environment
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8000'))
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
CORS_ORIGINS = os.getenv('API_CORS_ORIGINS', 'http://localhost:8080,http://127.0.0.1:8080').split(',')

# Database configuration from environment
DB_CONFIG = {
    "host": os.getenv('POSTGRES_HOST', 'localhost'),
    "port": int(os.getenv('POSTGRES_PORT', '5432')),
    "database": os.getenv('POSTGRES_DB', 'wastedb'),
    "user": os.getenv('POSTGRES_USER', 'admin'),
    "password": os.getenv('POSTGRES_PASSWORD', 'rootpassword')
}

# Initialize FastAPI app
app = FastAPI(
    title="IoT Waste Platform API",
    description="REST API for IoT Waste Management System",
    version="1.0.0",
    docs_url="/docs" if ENVIRONMENT == 'development' else None,
    redoc_url="/redoc" if ENVIRONMENT == 'development' else None
)


# Security middleware: Add security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    return response


# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # Use environment variable
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)


def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")


def fix_ts(v):
    """Append +07:00 to naive datetime strings so JavaScript parses them correctly."""
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.isoformat() + '+07:00'
        return v.isoformat()
    if isinstance(v, str) and len(v) >= 19 and v[10] == 'T' and '+' not in v and v[-1] != 'Z':
        return v + '+07:00'
    return v


def normalize_row(row):
    """Convert RealDictRow to plain dict and fix naive timestamps."""
    if row is None:
        return None
    d = dict(row)
    TS_KEYS = {'timestamp', 'last_reading', 'triggered_at', 'resolved_at',
               'last_login', 'created_at', 'updated_at', 'installed_date',
               'last_reading_today', 'collection_time'}
    for k, v in d.items():
        if k in TS_KEYS:
            d[k] = fix_ts(v)
    return d


@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("=" * 60)
    logger.info("🗑️  IoT Waste Platform API - Starting")
    logger.info("=" * 60)
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"API Host: {API_HOST}")
    logger.info(f"API Port: {API_PORT}")
    logger.info(f"CORS Origins: {CORS_ORIGINS}")
    logger.info(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info(f"Debug Mode: {os.getenv('DEBUG', 'false')}")
    logger.info("=" * 60)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "IoT Waste Platform API",
        "version": "1.0.0",
        "environment": ENVIRONMENT,
        "endpoints": {
            "bins": "/api/bins",
            "sensors": "/api/sensors",
            "readings": "/api/readings",
            "alerts": "/api/alerts",
            "stats": "/api/stats",
            "health": "/health",
            "docs": "/docs" if ENVIRONMENT == 'development' else None
        }
    }


@app.get("/api/bins")
async def get_bins(status: Optional[str] = None):
    """Get all waste bins with current status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT
                bin_id,
                bin_code,
                location,
                latitude,
                longitude,
                capacity,
                bin_type,
                bin_status,
                fill_level,
                weight_kg,
                temperature_c,
                battery_level,
                signal_strength,
                last_reading,
                fill_status,
                open_alerts
            FROM v_bin_current_status
            WHERE bin_status = 'active'
        """

        if status:
            query += " AND bin_status = %s"
            cursor.execute(query, (status,))
        else:
            cursor.execute(query)

        bins = [normalize_row(b) for b in cursor.fetchall()]
        cursor.close()
        conn.close()

        return {"success": True, "count": len(bins), "data": bins}

    except Exception as e:
        logger.error(f"Error fetching bins: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bins/{bin_id}")
async def get_bin_detail(bin_id: int):
    """Get detailed information for a specific bin"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get bin info
        cursor.execute("""
            SELECT * FROM v_bin_current_status WHERE bin_id = %s
        """, (bin_id,))
        bin_info = cursor.fetchone()

        if not bin_info:
            raise HTTPException(status_code=404, detail="Bin not found")

        # Get recent readings
        cursor.execute("""
            SELECT * FROM sensor_readings
            WHERE bin_id = %s
            ORDER BY timestamp DESC
            LIMIT 10
        """, (bin_id,))
        recent_readings = cursor.fetchall()

        # Get collection history
        cursor.execute("""
            SELECT * FROM collections
            WHERE bin_id = %s
            ORDER BY collection_time DESC
            LIMIT 5
        """, (bin_id,))
        collections = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "success": True,
            "data": {
                "bin_info": normalize_row(bin_info),
                "recent_readings": [normalize_row(r) for r in recent_readings],
                "collections": [normalize_row(c) for c in collections]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching bin detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sensors")
async def get_sensors():
    """Get all sensors"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT s.*, wb.bin_code, wb.location
            FROM sensors s
            LEFT JOIN waste_bins wb ON s.bin_id = wb.bin_id
            ORDER BY s.sensor_id
        """)
        sensors = cursor.fetchall()

        cursor.close()
        conn.close()

        return {"success": True, "count": len(sensors), "data": sensors}

    except Exception as e:
        logger.error(f"Error fetching sensors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/readings")
async def get_readings(
    bin_id: Optional[int] = None,
    hours: int = Query(default=24, ge=1, le=168)
):
    """Get sensor readings for the last N hours"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        time_threshold = datetime.now() - timedelta(hours=hours)

        if bin_id:
            cursor.execute("""
                SELECT sr.*, wb.bin_code
                FROM sensor_readings sr
                LEFT JOIN waste_bins wb ON sr.bin_id = wb.bin_id
                WHERE sr.bin_id = %s AND sr.timestamp >= %s
                ORDER BY sr.timestamp DESC
            """, (bin_id, time_threshold))
        else:
            cursor.execute("""
                SELECT sr.*, wb.bin_code
                FROM sensor_readings sr
                LEFT JOIN waste_bins wb ON sr.bin_id = wb.bin_id
                WHERE sr.timestamp >= %s
                ORDER BY sr.timestamp DESC
                LIMIT 1000
            """, (time_threshold,))

        readings = cursor.fetchall()
        cursor.close()
        conn.close()

        return {"success": True, "count": len(readings), "data": readings}

    except Exception as e:
        logger.error(f"Error fetching readings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
async def get_alerts(status: str = Query(default="open")):
    """Get alerts"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT a.*, wb.bin_code, wb.location
            FROM alerts a
            LEFT JOIN waste_bins wb ON a.bin_id = wb.bin_id
            WHERE a.status = %s
            ORDER BY a.triggered_at DESC
            LIMIT 100
        """, (status,))

        alerts = [normalize_row(a) for a in cursor.fetchall()]
        cursor.close()
        conn.close()

        return {"success": True, "count": len(alerts), "data": alerts}

    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_statistics():
    """Get overall system statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Total bins
        cursor.execute("SELECT COUNT(*) as total_bins FROM waste_bins WHERE status = 'active'")
        total_bins = cursor.fetchone()['total_bins']

        # Bins by fill status
        cursor.execute("""
            SELECT fill_status, COUNT(*) as count
            FROM v_bin_current_status
            GROUP BY fill_status
        """)
        fill_status_counts = cursor.fetchall()

        # Active alerts
        cursor.execute("SELECT COUNT(*) as active_alerts FROM alerts WHERE status = 'open'")
        active_alerts = cursor.fetchone()['active_alerts']

        # Recent collections (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) as recent_collections
            FROM collections
            WHERE collection_time >= NOW() - INTERVAL '7 days'
        """)
        recent_collections = cursor.fetchone()['recent_collections']

        # Average fill level
        cursor.execute("""
            SELECT AVG(fill_level) as avg_fill_level
            FROM v_bin_current_status
            WHERE fill_level IS NOT NULL
        """)
        avg_fill = cursor.fetchone()['avg_fill_level']

        # Bins requiring attention (>75%)
        cursor.execute("""
            SELECT COUNT(*) as bins_need_attention
            FROM v_bin_current_status
            WHERE fill_level >= 75
        """)
        bins_need_attention = cursor.fetchone()['bins_need_attention']

        cursor.close()
        conn.close()

        return {
            "success": True,
            "data": {
                "total_bins": total_bins,
                "active_alerts": active_alerts,
                "recent_collections": recent_collections,
                "avg_fill_level": round(float(avg_fill or 0), 2),
                "bins_need_attention": bins_need_attention,
                "fill_status_distribution": fill_status_counts
            }
        }

    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/timeline")
async def get_timeline_stats(hours: int = Query(default=24, ge=1, le=168)):
    """Get timeline statistics for charts"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        time_threshold = datetime.now() - timedelta(hours=hours)

        # Average fill level over time (hourly)
        cursor.execute("""
            SELECT
                DATE_TRUNC('hour', timestamp) as hour,
                AVG(fill_level) as avg_fill_level,
                COUNT(*) as reading_count
            FROM sensor_readings
            WHERE timestamp >= %s
            GROUP BY DATE_TRUNC('hour', timestamp)
            ORDER BY hour
        """, (time_threshold,))
        fill_timeline = cursor.fetchall()

        # Alerts over time
        cursor.execute("""
            SELECT
                DATE_TRUNC('hour', triggered_at) as hour,
                COUNT(*) as alert_count,
                severity
            FROM alerts
            WHERE triggered_at >= %s
            GROUP BY DATE_TRUNC('hour', triggered_at), severity
            ORDER BY hour
        """, (time_threshold,))
        alert_timeline = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "success": True,
            "data": {
                "fill_level_timeline": fill_timeline,
                "alert_timeline": alert_timeline
            }
        }

    except Exception as e:
        logger.error(f"Error fetching timeline stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/daily-weight")
async def get_daily_weight():
    """Get today's total weight per bin (infectious waste weighing workflow)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                wb.bin_id,
                wb.bin_code,
                wb.location,
                COALESCE(SUM(sr.weight_kg), 0) as total_weight_today,
                COUNT(sr.reading_id) as reading_count_today,
                MAX(sr.timestamp) as last_reading_today
            FROM waste_bins wb
            LEFT JOIN sensor_readings sr
                ON wb.bin_id = sr.bin_id
                AND sr.timestamp >= NOW() - INTERVAL '24 hours'
                AND sr.weight_kg > 0
            WHERE wb.status = 'active'
            GROUP BY wb.bin_id, wb.bin_code, wb.location
            ORDER BY wb.bin_id
        """)

        daily = [normalize_row(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()

        total_today = sum(float(r['total_weight_today']) for r in daily)

        return {
            "success": True,
            "data": daily,
            "total_weight_today": round(total_today, 2)
        }

    except Exception as e:
        logger.error(f"Error fetching daily weight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/login")
async def login(request: Request):
    """Authenticate user and return session token"""
    try:
        body = await request.json()
        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not username or not password:
        raise HTTPException(status_code=400, detail="กรุณากรอก Username และ Password")

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT user_id, username, full_name, role, status
            FROM users
            WHERE username = %s AND password_hash = %s AND status = 'active'
        """, (username, password_hash))
        user = cursor.fetchone()

        if user:
            cursor.execute(
                "UPDATE users SET last_login = NOW() WHERE user_id = %s",
                (user["user_id"],)
            )
            conn.commit()

        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Auth DB error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not user:
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    token = secrets.token_hex(32)
    _sessions[token] = {
        "user_id":      user["user_id"],
        "username":     user["username"],
        "display_name": user["full_name"] or user["username"],
        "role":         user["role"],
        "expires":      datetime.now() + timedelta(hours=8),
    }

    logger.info(f"Login: {username} (role={user['role']})")
    return {
        "success":      True,
        "token":        token,
        "username":     user["username"],
        "display_name": user["full_name"] or user["username"],
        "role":         user["role"],
    }


@app.post("/api/auth/logout")
async def logout(request: Request):
    """Invalidate session token"""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    _sessions.pop(token, None)
    return {"success": True}


@app.get("/api/auth/verify")
async def verify_token(request: Request):
    """Verify if a session token is still valid"""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    session = _sessions.get(token)
    if not session or datetime.now() > session["expires"]:
        _sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired")
    return {
        "success":      True,
        "username":     session["username"],
        "display_name": session["display_name"],
        "role":         session["role"],
    }


# ─── Device Management ──────────────────────────────────────────────────────

class DeviceItem(BaseModel):
    mac_address: str
    device_name: str
    bin_id: int
    weight_offset: float = 0.0

class DeviceRegisterRequest(BaseModel):
    devices: List[DeviceItem]


def _require_auth(request: Request) -> dict:
    """Check Bearer token and return session, raise 401 if invalid."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    session = _sessions.get(token)
    if not session or datetime.now() > session["expires"]:
        _sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อน")
    return session


def _normalize_mac(mac: str) -> str:
    """Uppercase and validate MAC address format AA:BB:CC:DD:EE:FF."""
    mac = mac.strip().upper()
    if not re.fullmatch(r'([0-9A-F]{2}:){5}[0-9A-F]{2}', mac):
        raise HTTPException(status_code=400, detail=f"MAC address ไม่ถูกต้อง: {mac}")
    return mac


@app.get("/api/devices/lookup")
async def lookup_device(mac: str = Query(..., description="MAC address AA:BB:CC:DD:EE:FF")):
    """Called by ESP32 on boot to find which department it is assigned to."""
    mac = mac.strip().upper()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT s.sensor_id, s.sensor_code, s.weight_offset,
                   s.bin_id, wb.bin_code, wb.location
            FROM sensors s
            JOIN waste_bins wb ON s.bin_id = wb.bin_id
            WHERE s.mac_address = %s AND s.status = 'active'
        """, (mac,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            logger.info(f"Device lookup: MAC {mac} not registered")
            return {"registered": False}

        logger.info(f"Device lookup: MAC {mac} → {row['bin_code']}")
        return {
            "registered":    True,
            "sensor_id":     row["sensor_id"],
            "sensor_code":   row["sensor_code"],
            "bin_id":        str(row["bin_id"]),
            "bin_code":      row["bin_code"],
            "location":      row["location"],
            "weight_offset": float(row["weight_offset"] or 0.0),
        }
    except Exception as e:
        logger.error(f"Device lookup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/devices")
async def get_devices():
    """List all registered devices with bin/department info."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT
                s.sensor_id,
                s.sensor_code,
                s.mac_address,
                s.manufacturer  AS device_name,
                s.weight_offset,
                s.status,
                s.bin_id,
                wb.bin_code,
                wb.location,
                MAX(sr.timestamp) AS last_seen
            FROM sensors s
            LEFT JOIN waste_bins wb ON s.bin_id = wb.bin_id
            LEFT JOIN sensor_readings sr ON s.sensor_id = sr.sensor_id
            GROUP BY s.sensor_id, wb.bin_code, wb.location
            ORDER BY s.sensor_id
        """)
        rows = [normalize_row(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return {"success": True, "count": len(rows), "data": rows}
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/devices/register")
async def register_devices(body: DeviceRegisterRequest, request: Request):
    """Register one or more ESP32 devices (MAC address → department)."""
    _require_auth(request)

    if not body.devices:
        raise HTTPException(status_code=400, detail="ไม่มีข้อมูลอุปกรณ์")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    registered = []
    errors = []

    try:
        for item in body.devices:
            mac = _normalize_mac(item.mac_address)
            device_name = item.device_name.strip() or mac
            bin_id = item.bin_id
            weight_offset = item.weight_offset

            # Verify bin exists
            cursor.execute("SELECT bin_id, bin_code FROM waste_bins WHERE bin_id = %s AND status = 'active'", (bin_id,))
            bin_row = cursor.fetchone()
            if not bin_row:
                errors.append({"mac": mac, "error": f"ไม่พบแผนก bin_id={bin_id}"})
                continue

            # Check if MAC already registered
            cursor.execute("SELECT sensor_id, bin_id FROM sensors WHERE mac_address = %s", (mac,))
            existing = cursor.fetchone()
            if existing:
                # Update existing registration
                cursor.execute("""
                    UPDATE sensors
                    SET bin_id = %s, manufacturer = %s, weight_offset = %s, updated_at = NOW()
                    WHERE mac_address = %s
                """, (bin_id, device_name, weight_offset, mac))
                conn.commit()
                registered.append({"mac": mac, "bin_code": bin_row["bin_code"], "action": "updated"})
                continue

            # Generate unique sensor_code from device_name
            base_code = re.sub(r'[^A-Za-z0-9\-_]', '-', device_name)[:40].strip('-')
            sensor_code = base_code or f"MAC-{mac.replace(':', '')[-6:]}"
            cursor.execute("SELECT sensor_id FROM sensors WHERE sensor_code = %s", (sensor_code,))
            if cursor.fetchone():
                sensor_code = f"{sensor_code[:36]}-{mac[-5:].replace(':', '')}"

            cursor.execute("""
                INSERT INTO sensors (sensor_code, bin_id, sensor_type, manufacturer, model, weight_offset, mac_address, status)
                VALUES (%s, %s, 'weight_scale', %s, 'Senses-Scale-v2', %s, %s, 'active')
            """, (sensor_code, bin_id, device_name, weight_offset, mac))
            conn.commit()
            registered.append({"mac": mac, "bin_code": bin_row["bin_code"], "sensor_code": sensor_code, "action": "created"})

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Register device error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

    return {"success": True, "registered": len(registered), "results": registered, "errors": errors}


@app.put("/api/devices/{sensor_id}")
async def update_device(sensor_id: int, body: DeviceItem, request: Request):
    """Update a registered device's MAC, department, or weight offset."""
    _require_auth(request)
    mac = _normalize_mac(body.mac_address)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT sensor_id FROM sensors WHERE sensor_id = %s", (sensor_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="ไม่พบอุปกรณ์")

        # Check MAC uniqueness (exclude self)
        cursor.execute("SELECT sensor_id FROM sensors WHERE mac_address = %s AND sensor_id != %s", (mac, sensor_id))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"MAC {mac} ถูกใช้งานแล้ว")

        cursor.execute("""
            UPDATE sensors
            SET mac_address = %s, bin_id = %s, manufacturer = %s, weight_offset = %s, updated_at = NOW()
            WHERE sensor_id = %s
        """, (mac, body.bin_id, body.device_name.strip(), body.weight_offset, sensor_id))
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "message": "อัปเดตอุปกรณ์แล้ว"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update device error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/devices/{sensor_id}")
async def delete_device(sensor_id: int, request: Request):
    """Unregister a device (clears MAC address). Keeps sensor record if it has readings."""
    _require_auth(request)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT sensor_id, sensor_code FROM sensors WHERE sensor_id = %s", (sensor_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="ไม่พบอุปกรณ์")

        # Check if it has readings — if yes, just clear MAC; if no, delete entirely
        cursor.execute("SELECT COUNT(*) as cnt FROM sensor_readings WHERE sensor_id = %s", (sensor_id,))
        cnt = cursor.fetchone()["cnt"]

        if cnt > 0:
            cursor.execute("UPDATE sensors SET mac_address = NULL, updated_at = NOW() WHERE sensor_id = %s", (sensor_id,))
            conn.commit()
            msg = "ยกเลิกการลงทะเบียน MAC แล้ว (ประวัติข้อมูลยังคงอยู่)"
        else:
            cursor.execute("DELETE FROM sensors WHERE sensor_id = %s", (sensor_id,))
            conn.commit()
            msg = "ลบอุปกรณ์แล้ว"

        cursor.close()
        conn.close()
        return {"success": True, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete device error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected", "error": str(e)}
        )


# Serve frontend static files — must be mounted LAST so API routes take priority
_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    # Run server with environment configuration
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="debug" if os.getenv('DEBUG', 'false').lower() == 'true' else "info",
        access_log=True
    )
