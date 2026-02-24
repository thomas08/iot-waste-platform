#!/usr/bin/env python3
"""
MQTT Subscriber Service for IoT Waste Platform
Subscribes to sensor data from MQTT broker and stores in PostgreSQL
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import RealDictCursor
import time
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configure logging
log_level = logging.DEBUG if os.getenv('DEBUG', 'false').lower() == 'true' else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Handles PostgreSQL database operations"""

    def __init__(self, host: str = None, port: int = None,
                 database: str = None, user: str = None,
                 password: str = None):
        # Use environment variables with fallback to defaults
        self.connection_params = {
            "host": host or os.getenv('POSTGRES_HOST', 'localhost'),
            "port": port or int(os.getenv('POSTGRES_PORT', '5432')),
            "database": database or os.getenv('POSTGRES_DB', 'wastedb'),
            "user": user or os.getenv('POSTGRES_USER', 'admin'),
            "password": password or os.getenv('POSTGRES_PASSWORD', 'rootpassword')
        }
        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(**self.connection_params)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info(f"✅ Connected to database at {self.connection_params['host']}")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from database"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("🔌 Disconnected from database")

    def insert_sensor_reading(self, data: Dict[str, Any]) -> bool:
        """Insert sensor reading into database"""
        try:
            sensor_result = None
            weight_offset = 0.0

            # 1. Try MAC address lookup first (registered device)
            mac = data.get('mac_address', '').strip().upper()
            if mac:
                self.cursor.execute(
                    "SELECT sensor_id, bin_id, weight_offset FROM sensors WHERE mac_address = %s",
                    (mac,)
                )
                sensor_result = self.cursor.fetchone()
                if sensor_result:
                    weight_offset = float(sensor_result.get('weight_offset') or 0.0)
                    # Override bin_id from registration (ignore payload's bin_id)
                    data = dict(data)
                    data['bin_id'] = str(sensor_result['bin_id'])
                    logger.debug(f"🔍 MAC match: {mac} → sensor_id={sensor_result['sensor_id']}")

            # 2. Fall back to sensor_code lookup
            if not sensor_result:
                self.cursor.execute(
                    "SELECT sensor_id, weight_offset FROM sensors WHERE sensor_code = %s",
                    (data.get('sensor_code'),)
                )
                sensor_result = self.cursor.fetchone()
                if sensor_result:
                    weight_offset = float(sensor_result.get('weight_offset') or 0.0)

            if not sensor_result:
                logger.warning(f"⚠️  Unknown device — MAC={mac or 'N/A'}, sensor_code={data.get('sensor_code', 'N/A')}")
                return False

            sensor_id = sensor_result['sensor_id']

            # Apply weight offset calibration
            raw_weight = data.get('weight_kg')
            if raw_weight is not None and weight_offset != 0.0:
                data = dict(data)
                data['weight_kg'] = float(raw_weight) + weight_offset

            # Insert reading
            insert_query = """
                INSERT INTO sensor_readings (
                    sensor_id, bin_id, fill_level, distance_cm, weight_kg,
                    temperature_c, humidity, gas_level, battery_level,
                    signal_strength, timestamp
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """

            values = (
                sensor_id,
                int(data.get('bin_id')),
                data.get('fill_level'),
                data.get('distance_cm'),
                data.get('weight_kg'),
                data.get('temperature_c'),
                data.get('humidity'),
                data.get('gas_level'),
                data.get('battery_level'),
                data.get('signal_strength'),
                data.get('timestamp') or datetime.now().astimezone().isoformat()
            )

            self.cursor.execute(insert_query, values)
            self.conn.commit()

            logger.debug(f"💾 Saved reading for {data.get('bin_code')}")
            return True

        except Exception as e:
            logger.error(f"❌ Error inserting sensor reading: {e}")
            self.conn.rollback()
            return False

    def check_and_create_alert(self, data: Dict[str, Any]):
        """Check sensor data and create alerts if necessary"""
        try:
            bin_id = int(data.get('bin_id'))
            bin_code = data.get('bin_code')
            fill_level = data.get('fill_level', 0)
            battery_level = data.get('battery_level', 100)
            temperature = data.get('temperature_c', 25)

            # Check for bin full alert
            if fill_level >= 90:
                self._create_alert(
                    bin_id, bin_code, 'bin_full', 'critical',
                    f'Bin {bin_code} is {fill_level:.1f}% full - requires immediate collection'
                )
            elif fill_level >= 75:
                self._create_alert(
                    bin_id, bin_code, 'bin_full', 'high',
                    f'Bin {bin_code} is {fill_level:.1f}% full - collection needed soon'
                )

            # Check for low battery
            if battery_level < 20:
                self._create_alert(
                    bin_id, bin_code, 'sensor_fault', 'medium',
                    f'Low battery warning for {bin_code}: {battery_level:.1f}%'
                )

            # Check for unusual temperature
            if temperature > 45:
                self._create_alert(
                    bin_id, bin_code, 'unusual_activity', 'high',
                    f'High temperature detected in {bin_code}: {temperature:.1f}°C'
                )

        except Exception as e:
            logger.error(f"❌ Error checking alerts: {e}")

    def _create_alert(self, bin_id: int, bin_code: str, alert_type: str,
                      severity: str, message: str):
        """Create an alert if it doesn't already exist"""
        try:
            # Check if similar alert already exists and is open
            self.cursor.execute(
                """
                SELECT alert_id FROM alerts
                WHERE bin_id = %s AND alert_type = %s AND status = 'open'
                """,
                (bin_id, alert_type)
            )

            if self.cursor.fetchone():
                return  # Alert already exists

            # Create new alert
            self.cursor.execute(
                """
                INSERT INTO alerts (bin_id, alert_type, severity, message, status)
                VALUES (%s, %s, %s, %s, 'open')
                """,
                (bin_id, alert_type, severity, message)
            )
            self.conn.commit()

            logger.warning(f"🚨 ALERT [{severity.upper()}]: {message}")

        except Exception as e:
            logger.error(f"❌ Error creating alert: {e}")
            self.conn.rollback()


class MQTTSubscriber:
    """MQTT Subscriber that processes waste bin sensor data"""

    def __init__(self, mqtt_broker: str = None, mqtt_port: int = None,
                 mqtt_username: str = None, mqtt_password: str = None,
                 db_manager: DatabaseManager = None):
        # Use environment variables with fallback to defaults
        self.mqtt_broker = mqtt_broker or os.getenv('MQTT_HOST', 'localhost')
        self.mqtt_port = mqtt_port or int(os.getenv('MQTT_PORT', '1883'))
        self.mqtt_username = mqtt_username or os.getenv('MQTT_USERNAME')
        self.mqtt_password = mqtt_password or os.getenv('MQTT_PASSWORD')
        self.db_manager = db_manager
        self.client = None
        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"✅ Connected to MQTT Broker at {self.mqtt_broker}:{self.mqtt_port}")

            # Subscribe to all waste bin sensor topics
            topic = "waste/bins/+/sensors"
            client.subscribe(topic)
            logger.info(f"📡 Subscribed to topic: {topic}")
        else:
            logger.error(f"❌ Failed to connect, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠️  Unexpected disconnection, return code {rc}")

    def on_message(self, client, userdata, msg):
        """Callback when message is received"""
        try:
            # Parse JSON payload
            data = json.loads(msg.payload.decode())

            bin_code = data.get('bin_code', 'UNKNOWN')
            fill_level = data.get('fill_level', 0)
            temp = data.get('temperature_c', 0)
            battery = data.get('battery_level', 0)

            # Log received data
            fill_icon = "🟢" if fill_level < 50 else "🟡" if fill_level < 75 else "🔴"
            logger.info(
                f"{fill_icon} Received from {bin_code}: "
                f"Fill={fill_level:.1f}% | Temp={temp:.1f}°C | Battery={battery:.1f}%"
            )

            # Store in database
            if self.db_manager:
                success = self.db_manager.insert_sensor_reading(data)

                if success:
                    # Check for alerts
                    self.db_manager.check_and_create_alert(data)
            else:
                logger.warning("⚠️  No database manager configured")

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")

    def connect(self):
        """Connect to MQTT broker"""
        self.client = mqtt.Client(client_id="waste_backend_subscriber")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        # Set username and password if provided
        if self.mqtt_username and self.mqtt_password:
            logger.info(f"🔐 Using MQTT authentication (user: {self.mqtt_username})")
            self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        else:
            logger.warning("⚠️  No MQTT authentication configured (not recommended for production)")

        try:
            logger.info(f"🔌 Connecting to MQTT broker {self.mqtt_broker}:{self.mqtt_port}...")
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            return True
        except Exception as e:
            logger.error(f"❌ Error connecting to MQTT: {e}")
            return False

    def start(self):
        """Start the subscriber (blocking)"""
        logger.info("🚀 MQTT Subscriber service started")
        logger.info("📊 Waiting for sensor data...")
        logger.info("Press Ctrl+C to stop\n")

        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("\n⏹️  Service stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in subscriber loop: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up...")
        if self.client:
            self.client.disconnect()
        if self.db_manager:
            self.db_manager.disconnect()
        logger.info("✅ Cleanup complete")


def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🗑️  IoT Waste Management Platform - Backend Service")
    logger.info("=" * 60)
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"Debug mode: {os.getenv('DEBUG', 'false')}")
    logger.info("")

    # Create database manager (will use environment variables)
    db_manager = DatabaseManager()

    # Connect to database
    if not db_manager.connect():
        logger.error("❌ Failed to connect to database. Exiting.")
        logger.error("💡 Check your database credentials in .env file")
        return

    # Create MQTT subscriber (will use environment variables)
    subscriber = MQTTSubscriber(db_manager=db_manager)

    # Connect to MQTT broker
    if not subscriber.connect():
        logger.error("❌ Failed to connect to MQTT broker. Exiting.")
        logger.error("💡 Check your MQTT credentials in .env file")
        db_manager.disconnect()
        return

    # Start subscriber service
    subscriber.start()


if __name__ == "__main__":
    main()
