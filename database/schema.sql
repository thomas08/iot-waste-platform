-- IoT Waste Platform Database Schema
-- Created: 2025-12-19

-- ตาราง waste_bins: จัดเก็บข้อมูลถังขยะ
CREATE TABLE IF NOT EXISTS waste_bins (
    bin_id SERIAL PRIMARY KEY,
    bin_code VARCHAR(50) UNIQUE NOT NULL,
    location VARCHAR(255) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    capacity INTEGER NOT NULL,  -- ความจุในหน่วยลิตร
    bin_type VARCHAR(50) NOT NULL,  -- general, recycle, organic, hazardous
    status VARCHAR(20) DEFAULT 'active',  -- active, inactive, maintenance
    installed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_maintenance TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตาราง sensors: ข้อมูล sensor ที่ติดตั้งในถังขยะ
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id SERIAL PRIMARY KEY,
    sensor_code VARCHAR(50) UNIQUE NOT NULL,
    bin_id INTEGER REFERENCES waste_bins(bin_id) ON DELETE CASCADE,
    sensor_type VARCHAR(50) NOT NULL,  -- ultrasonic, weight, temperature, gas
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    firmware_version VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active',  -- active, inactive, faulty
    installed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_calibration TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตาราง sensor_readings: บันทึกข้อมูลจาก sensors
CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    sensor_id INTEGER REFERENCES sensors(sensor_id) ON DELETE CASCADE,
    bin_id INTEGER REFERENCES waste_bins(bin_id) ON DELETE CASCADE,
    fill_level DECIMAL(5, 2),  -- เปอร์เซ็นต์การเต็ม (0-100)
    distance_cm DECIMAL(6, 2),  -- ระยะห่างที่วัดได้ (สำหรับ ultrasonic)
    weight_kg DECIMAL(8, 2),  -- น้ำหนัก (สำหรับ weight sensor)
    temperature_c DECIMAL(5, 2),  -- อุณหภูมิ
    humidity DECIMAL(5, 2),  -- ความชื้น
    gas_level DECIMAL(5, 2),  -- ระดับก๊าซ
    battery_level DECIMAL(5, 2),  -- แบตเตอรี่เครื่องส่ง (0-100)
    signal_strength INTEGER,  -- ความแรงของสัญญาณ (RSSI)
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตาราง collections: บันทึกการเก็บขยะ
CREATE TABLE IF NOT EXISTS collections (
    collection_id SERIAL PRIMARY KEY,
    bin_id INTEGER REFERENCES waste_bins(bin_id) ON DELETE CASCADE,
    collected_by VARCHAR(100),  -- ชื่อผู้เก็บขยะ/รหัสพนักงาน
    vehicle_id VARCHAR(50),
    collection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fill_level_before DECIMAL(5, 2),  -- ระดับความเต็มก่อนเก็บ
    weight_collected DECIMAL(8, 2),  -- น้ำหนักที่เก็บได้
    duration_minutes INTEGER,  -- เวลาที่ใช้ในการเก็บ
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตาราง alerts: การแจ้งเตือน
CREATE TABLE IF NOT EXISTS alerts (
    alert_id SERIAL PRIMARY KEY,
    bin_id INTEGER REFERENCES waste_bins(bin_id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,  -- bin_full, sensor_fault, maintenance_required, unusual_activity
    severity VARCHAR(20) NOT NULL,  -- low, medium, high, critical
    message TEXT NOT NULL,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100),
    status VARCHAR(20) DEFAULT 'open',  -- open, acknowledged, resolved, false_alarm
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตาราง users: ผู้ใช้งานระบบ (สำหรับ authentication ในอนาคต)
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) NOT NULL,  -- admin, operator, viewer
    phone VARCHAR(20),
    status VARCHAR(20) DEFAULT 'active',  -- active, inactive, suspended
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตาราง collection_routes: เส้นทางการเก็บขยะ
CREATE TABLE IF NOT EXISTS collection_routes (
    route_id SERIAL PRIMARY KEY,
    route_name VARCHAR(100) NOT NULL,
    description TEXT,
    estimated_duration_minutes INTEGER,
    status VARCHAR(20) DEFAULT 'active',  -- active, inactive
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตาราง route_bins: ความสัมพันธ์ระหว่างเส้นทางและถังขยะ
CREATE TABLE IF NOT EXISTS route_bins (
    route_bin_id SERIAL PRIMARY KEY,
    route_id INTEGER REFERENCES collection_routes(route_id) ON DELETE CASCADE,
    bin_id INTEGER REFERENCES waste_bins(bin_id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL,  -- ลำดับการเก็บในเส้นทาง
    estimated_time_minutes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(route_id, bin_id)
);

-- Indexes สำหรับเพิ่มประสิทธิภาพการค้นหา
CREATE INDEX idx_sensor_readings_timestamp ON sensor_readings(timestamp DESC);
CREATE INDEX idx_sensor_readings_bin_id ON sensor_readings(bin_id);
CREATE INDEX idx_sensor_readings_sensor_id ON sensor_readings(sensor_id);
CREATE INDEX idx_collections_bin_id ON collections(bin_id);
CREATE INDEX idx_collections_time ON collections(collection_time DESC);
CREATE INDEX idx_alerts_bin_id ON alerts(bin_id);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_triggered ON alerts(triggered_at DESC);
CREATE INDEX idx_waste_bins_status ON waste_bins(status);
CREATE INDEX idx_waste_bins_type ON waste_bins(bin_type);

-- Function สำหรับอัพเดท updated_at timestamp อัตโนมัติ
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers สำหรับอัพเดท updated_at
CREATE TRIGGER update_waste_bins_updated_at BEFORE UPDATE ON waste_bins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sensors_updated_at BEFORE UPDATE ON sensors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alerts_updated_at BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_collection_routes_updated_at BEFORE UPDATE ON collection_routes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View: ภาพรวมสถานะถังขยะปัจจุบัน
CREATE OR REPLACE VIEW v_bin_current_status AS
SELECT
    wb.bin_id,
    wb.bin_code,
    wb.location,
    wb.bin_type,
    wb.capacity,
    wb.status as bin_status,
    sr.fill_level,
    sr.temperature_c,
    sr.battery_level,
    sr.timestamp as last_reading,
    CASE
        WHEN sr.fill_level >= 90 THEN 'critical'
        WHEN sr.fill_level >= 75 THEN 'high'
        WHEN sr.fill_level >= 50 THEN 'medium'
        ELSE 'low'
    END as fill_status,
    (SELECT COUNT(*) FROM alerts a
     WHERE a.bin_id = wb.bin_id AND a.status = 'open') as open_alerts
FROM waste_bins wb
LEFT JOIN LATERAL (
    SELECT * FROM sensor_readings
    WHERE bin_id = wb.bin_id
    ORDER BY timestamp DESC
    LIMIT 1
) sr ON true;

-- View: สถิติการเก็บขยะ
CREATE OR REPLACE VIEW v_collection_stats AS
SELECT
    wb.bin_id,
    wb.bin_code,
    wb.location,
    COUNT(c.collection_id) as total_collections,
    AVG(c.fill_level_before) as avg_fill_before_collection,
    SUM(c.weight_collected) as total_weight_collected,
    MAX(c.collection_time) as last_collection_time,
    AVG(c.duration_minutes) as avg_collection_duration
FROM waste_bins wb
LEFT JOIN collections c ON wb.bin_id = c.bin_id
GROUP BY wb.bin_id, wb.bin_code, wb.location;

-- ข้อมูลตัวอย่างสำหรับทดสอบ
INSERT INTO waste_bins (bin_code, location, latitude, longitude, capacity, bin_type) VALUES
    ('BIN001', 'Building A - Floor 1', 13.7563, 100.5018, 120, 'general'),
    ('BIN002', 'Building A - Floor 2', 13.7564, 100.5019, 120, 'recycle'),
    ('BIN003', 'Building B - Floor 1', 13.7565, 100.5020, 240, 'general'),
    ('BIN004', 'Parking Lot', 13.7566, 100.5021, 240, 'general'),
    ('BIN005', 'Cafeteria', 13.7567, 100.5022, 180, 'organic')
ON CONFLICT (bin_code) DO NOTHING;

-- เพิ่ม sensors สำหรับถังขยะ
INSERT INTO sensors (sensor_code, bin_id, sensor_type, manufacturer, model) VALUES
    ('SENS001', 1, 'ultrasonic', 'HC-SR04', 'v2.1'),
    ('SENS002', 2, 'ultrasonic', 'HC-SR04', 'v2.1'),
    ('SENS003', 3, 'ultrasonic', 'HC-SR04', 'v2.1'),
    ('SENS004', 4, 'ultrasonic', 'HC-SR04', 'v2.1'),
    ('SENS005', 5, 'ultrasonic', 'HC-SR04', 'v2.1')
ON CONFLICT (sensor_code) DO NOTHING;

-- สร้าง user admin
INSERT INTO users (username, email, password_hash, full_name, role) VALUES
    ('admin', 'admin@admin.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVr/qvWy6', 'System Administrator', 'admin')
ON CONFLICT (username) DO NOTHING;

COMMENT ON TABLE waste_bins IS 'ตารางเก็บข้อมูลถังขยะทั้งหมดในระบบ';
COMMENT ON TABLE sensors IS 'ตารางเก็บข้อมูล sensors ที่ติดตั้งในถังขยะ';
COMMENT ON TABLE sensor_readings IS 'ตารางเก็บข้อมูลการอ่านค่าจาก sensors (Time-series data)';
COMMENT ON TABLE collections IS 'ตารางบันทึกประวัติการเก็บขยะ';
COMMENT ON TABLE alerts IS 'ตารางการแจ้งเตือนเมื่อมีปัญหาหรือถังขยะเต็ม';
