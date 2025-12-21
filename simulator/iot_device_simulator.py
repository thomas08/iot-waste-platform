#!/usr/bin/env python3
"""
IoT Waste Bin Device Simulator
Simulates waste bin sensors sending data to MQTT broker
"""

import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List
from pathlib import Path
import paho.mqtt.client as mqtt
import logging
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


class WasteBinSensor:
    """Simulates a single waste bin with sensors"""

    def __init__(self, bin_id: str, bin_code: str, location: str,
                 capacity: int, bin_type: str):
        self.bin_id = bin_id
        self.bin_code = bin_code
        self.location = location
        self.capacity = capacity  # in liters
        self.bin_type = bin_type

        # Sensor states
        self.fill_level = random.uniform(10, 40)  # Start between 10-40%
        self.temperature = random.uniform(20, 30)  # Celsius
        self.battery_level = random.uniform(80, 100)  # Percentage
        self.distance_cm = self._calculate_distance()

        # Simulation parameters
        self.fill_rate = random.uniform(0.5, 2.0)  # % per reading
        self.temp_variance = 0.5
        self.battery_drain = 0.01  # % per reading

    def _calculate_distance(self) -> float:
        """Calculate distance based on fill level"""
        # Assume bin height is proportional to capacity
        bin_height_cm = (self.capacity / 10) * 0.8  # rough estimate
        return bin_height_cm * (1 - self.fill_level / 100)

    def update_readings(self):
        """Update sensor readings to simulate real sensor behavior"""
        # Gradually fill up
        self.fill_level = min(100, self.fill_level + random.uniform(0, self.fill_rate))

        # Distance decreases as fill level increases
        self.distance_cm = self._calculate_distance()

        # Temperature fluctuates slightly
        self.temperature += random.uniform(-self.temp_variance, self.temp_variance)
        self.temperature = max(15, min(40, self.temperature))

        # Battery slowly drains
        self.battery_level = max(0, self.battery_level - self.battery_drain)

        # Simulate occasional collection (reset fill level)
        if self.fill_level > 85 and random.random() < 0.1:
            logger.info(f"🚛 Bin {self.bin_code} collected! Resetting...")
            self.fill_level = random.uniform(0, 10)

    def get_reading(self) -> Dict:
        """Get current sensor reading as dictionary"""
        return {
            "bin_id": self.bin_id,
            "bin_code": self.bin_code,
            "sensor_code": f"SENS{self.bin_id.zfill(3)}",
            "location": self.location,
            "bin_type": self.bin_type,
            "fill_level": round(self.fill_level, 2),
            "distance_cm": round(self.distance_cm, 2),
            "weight_kg": round(self.fill_level * self.capacity / 100 * 0.5, 2),  # estimate
            "temperature_c": round(self.temperature, 2),
            "humidity": round(random.uniform(40, 70), 2),
            "gas_level": round(random.uniform(0, 10), 2),
            "battery_level": round(self.battery_level, 2),
            "signal_strength": random.randint(-90, -30),  # RSSI
            "timestamp": datetime.now().isoformat(),
        }


class IoTSimulator:
    """Main simulator managing multiple waste bins"""

    def __init__(self, mqtt_broker: str = None, mqtt_port: int = None,
                 mqtt_username: str = None, mqtt_password: str = None):
        # Use environment variables with fallback to defaults
        self.mqtt_broker = mqtt_broker or os.getenv('MQTT_HOST', 'localhost')
        self.mqtt_port = mqtt_port or int(os.getenv('MQTT_PORT', '1883'))
        self.mqtt_username = mqtt_username or os.getenv('MQTT_USERNAME')
        self.mqtt_password = mqtt_password or os.getenv('MQTT_PASSWORD')
        self.client = None
        self.bins: List[WasteBinSensor] = []
        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"✅ Connected to MQTT Broker at {self.mqtt_broker}:{self.mqtt_port}")
        else:
            logger.error(f"❌ Failed to connect, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        logger.warning(f"⚠️  Disconnected from MQTT Broker, return code {rc}")

    def on_publish(self, client, userdata, mid):
        """Callback when message is published"""
        logger.debug(f"Message {mid} published")

    def setup_mqtt(self):
        """Initialize MQTT client"""
        self.client = mqtt.Client(client_id="waste_bin_simulator")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish

        # Set username and password if provided
        if self.mqtt_username and self.mqtt_password:
            logger.info(f"🔐 Using MQTT authentication (user: {self.mqtt_username})")
            self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        else:
            logger.warning("⚠️  No MQTT authentication configured (not recommended for production)")

        try:
            logger.info(f"🔌 Connecting to MQTT broker {self.mqtt_broker}:{self.mqtt_port}...")
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.client.loop_start()

            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if not self.connected:
                logger.error("❌ Connection timeout!")
                return False

            return True
        except Exception as e:
            logger.error(f"❌ Error connecting to MQTT: {e}")
            return False

    def add_bin(self, bin_id: str, bin_code: str, location: str,
                capacity: int, bin_type: str):
        """Add a waste bin to simulate"""
        bin_sensor = WasteBinSensor(bin_id, bin_code, location, capacity, bin_type)
        self.bins.append(bin_sensor)
        logger.info(f"➕ Added bin: {bin_code} at {location}")

    def publish_reading(self, bin_sensor: WasteBinSensor):
        """Publish sensor reading to MQTT"""
        if not self.connected:
            logger.warning("⚠️  Not connected to MQTT broker")
            return

        reading = bin_sensor.get_reading()
        topic = f"waste/bins/{bin_sensor.bin_code}/sensors"

        # Publish to MQTT
        result = self.client.publish(topic, json.dumps(reading), qos=1)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            fill_icon = "🟢" if reading["fill_level"] < 50 else "🟡" if reading["fill_level"] < 75 else "🔴"
            logger.info(
                f"{fill_icon} {bin_sensor.bin_code}: "
                f"Fill={reading['fill_level']:.1f}% | "
                f"Temp={reading['temperature_c']:.1f}°C | "
                f"Battery={reading['battery_level']:.1f}%"
            )
        else:
            logger.error(f"❌ Failed to publish for {bin_sensor.bin_code}")

    def run(self, interval: int = 5, duration: int = None):
        """
        Run the simulator

        Args:
            interval: Time between readings in seconds
            duration: Total duration to run in seconds (None = infinite)
        """
        if not self.bins:
            logger.error("❌ No bins added to simulate!")
            return

        if not self.connected:
            logger.error("❌ Not connected to MQTT broker!")
            return

        logger.info(f"🚀 Starting simulation with {len(self.bins)} bins")
        logger.info(f"📊 Publishing interval: {interval} seconds")

        start_time = time.time()
        iteration = 0

        try:
            while True:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"Iteration {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*60}")

                # Update and publish readings for all bins
                for bin_sensor in self.bins:
                    bin_sensor.update_readings()
                    self.publish_reading(bin_sensor)
                    time.sleep(0.1)  # Small delay between bins

                # Check duration limit
                if duration and (time.time() - start_time) >= duration:
                    logger.info(f"\n⏱️  Duration limit reached ({duration}s)")
                    break

                # Wait for next iteration
                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Simulation stopped by user")
        except Exception as e:
            logger.error(f"\n❌ Error during simulation: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up...")
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        logger.info("✅ Cleanup complete")


def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🗑️  IoT Waste Bin Device Simulator")
    logger.info("=" * 60)
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"Debug mode: {os.getenv('DEBUG', 'false')}")
    logger.info("")

    # Create simulator (will use environment variables)
    simulator = IoTSimulator()

    # Setup MQTT connection
    if not simulator.setup_mqtt():
        logger.error("❌ Failed to setup MQTT connection. Exiting.")
        logger.error("💡 Check your MQTT credentials in .env file")
        return

    # Get configuration from environment
    num_bins = int(os.getenv('SIMULATOR_NUM_BINS', '5'))
    interval = int(os.getenv('SIMULATOR_INTERVAL', '10'))

    # Add waste bins to simulate (matching our database sample data)
    if num_bins >= 1:
        simulator.add_bin("1", "BIN001", "Building A - Floor 1", 120, "general")
    if num_bins >= 2:
        simulator.add_bin("2", "BIN002", "Building A - Floor 2", 120, "recycle")
    if num_bins >= 3:
        simulator.add_bin("3", "BIN003", "Building B - Floor 1", 240, "general")
    if num_bins >= 4:
        simulator.add_bin("4", "BIN004", "Parking Lot", 240, "general")
    if num_bins >= 5:
        simulator.add_bin("5", "BIN005", "Cafeteria", 180, "organic")

    logger.info("")
    logger.info(f"📊 Simulating {len(simulator.bins)} bins with {interval}s interval")
    logger.info("")

    # Run simulation
    # interval: seconds between readings (from env or default: 10)
    # duration: total seconds to run (None = run forever)
    simulator.run(interval=interval, duration=None)


if __name__ == "__main__":
    main()
