#!/usr/bin/env python3
"""
FastAPI Backend for IoT Waste Platform Dashboard
Provides REST API endpoints for frontend dashboard
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from typing import List, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from dotenv import load_dotenv
import time

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
                status as bin_status,
                fill_level,
                temperature_c,
                battery_level,
                last_reading,
                fill_status,
                open_alerts
            FROM v_bin_current_status
        """

        if status:
            query += " WHERE status = %s"
            cursor.execute(query, (status,))
        else:
            cursor.execute(query)

        bins = cursor.fetchall()
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
                "bin_info": bin_info,
                "recent_readings": recent_readings,
                "collections": collections
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

        alerts = cursor.fetchall()
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
