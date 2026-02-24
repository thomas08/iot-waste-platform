/**
 * ESP32-C3 — Multi-Department Waste Bin Test
 * ส่งข้อมูลครบทุก 10 แผนกเพื่อทดสอบ IoT Platform
 * Library required: WebSockets by Markus Sattler (links2004)
 * Version: 2.1 — ส่ง mac_address ใน payload สำหรับ Device Registration
 */
#define FW_VERSION "2.1"

#include <WiFi.h>
#include <time.h>
#include <WebSocketsClient.h>

// ─── WiFi ─────────────────────────────────────────────────────────────────
const char* WIFI_SSID = "MakerHub_2.4G";
const char* WIFI_PASS = "makerhubhome";

// ─── MQTT over WSS ────────────────────────────────────────────────────────
const char* WS_HOST   = "mqtt-tuh.maker-hub.net";
const int   WS_PORT   = 443;
const char* MQTT_USER = "iot_user";
const char* MQTT_PASS = "iotpassword";
const char* CLIENT_ID = "esp32c3-test-all";

// ─── NTP ──────────────────────────────────────────────────────────────────
const char* NTP_SERVER = "pool.ntp.org";
const long  GMT_OFFSET = 25200;  // UTC+7

// ─── แผนกทั้ง 10 (bin_id, bin_code, sensor_code, fill_level, weight_kg) ──
struct Bin {
  const char* bin_id;
  const char* bin_code;
  const char* sensor_code;
  float       fill_level;
  float       weight_kg;
  float       temperature_c;
};

const Bin BINS[] = {
  { "6",  "W-OT",   "SENS006",    15.0, 1.2, 36.0 },
  { "7",  "W-ER",   "SNS-W-ER",   72.0, 4.8, 38.0 },
  { "8",  "W-ICU",  "SNS-W-ICU",  45.0, 3.1, 24.0 },
  { "9",  "W-MED1", "SNS-W-MED1", 30.0, 2.2, 25.0 },
  { "10", "W-MED2", "SNS-W-MED2", 88.0, 5.9, 27.0 },
  { "11", "W-SUR1", "SNS-W-SUR1", 60.0, 4.1, 26.0 },
  { "12", "W-SUR2", "SENS012",    25.0, 1.8, 24.0 },
  { "13", "W-OB",   "SNS-W-OB",   50.0, 3.5, 25.0 },
  { "14", "W-PED",  "SNS-W-PED",  20.0, 1.4, 23.0 },
  { "15", "W-OPD",  "SNS-W-OPD",  95.0, 6.2, 28.0 },
};
const int BIN_COUNT = sizeof(BINS) / sizeof(BINS[0]);

// ─────────────────────────────────────────────────────────────────────────

WebSocketsClient webSocket;
bool          mqttReady   = false;
int           currentBin  = 0;      // index ที่กำลังจะส่ง
bool          allSent     = false;  // ส่งครบรอบแล้ว
unsigned long lastSend    = 0;
unsigned long lastPing    = 0;

// ─── MQTT Packet Helpers ──────────────────────────────────────────────────

size_t encodeLen(uint8_t* buf, size_t len) {
  size_t i = 0;
  do {
    buf[i] = len % 128;
    len /= 128;
    if (len > 0) buf[i] |= 0x80;
    i++;
  } while (len > 0);
  return i;
}

size_t buildConnect(uint8_t* buf) {
  uint8_t tmp[256]; size_t p = 0;
  tmp[p++]=0x00; tmp[p++]=0x04;
  tmp[p++]='M'; tmp[p++]='Q'; tmp[p++]='T'; tmp[p++]='T';
  tmp[p++] = 0x04;
  tmp[p++] = 0xC2;
  tmp[p++] = 0x00; tmp[p++] = 0x3C;
  size_t l;
  l = strlen(CLIENT_ID);
  tmp[p++]=0; tmp[p++]=l; memcpy(tmp+p, CLIENT_ID, l); p+=l;
  l = strlen(MQTT_USER);
  tmp[p++]=0; tmp[p++]=l; memcpy(tmp+p, MQTT_USER, l); p+=l;
  l = strlen(MQTT_PASS);
  tmp[p++]=0; tmp[p++]=l; memcpy(tmp+p, MQTT_PASS, l); p+=l;
  uint8_t lenBuf[4];
  size_t  lenSz = encodeLen(lenBuf, p);
  buf[0] = 0x10;
  memcpy(buf+1, lenBuf, lenSz);
  memcpy(buf+1+lenSz, tmp, p);
  return 1 + lenSz + p;
}

size_t buildPublish(uint8_t* buf, const char* topic, const char* payload) {
  uint8_t tmp[512]; size_t p = 0;
  size_t tl = strlen(topic), pl = strlen(payload);
  tmp[p++]=0; tmp[p++]=tl; memcpy(tmp+p, topic, tl); p+=tl;
  memcpy(tmp+p, payload, pl); p+=pl;
  uint8_t lenBuf[4];
  size_t  lenSz = encodeLen(lenBuf, p);
  buf[0] = 0x30;
  memcpy(buf+1, lenBuf, lenSz);
  memcpy(buf+1+lenSz, tmp, p);
  return 1 + lenSz + p;
}

// ─── WebSocket Event ──────────────────────────────────────────────────────

void wsEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.println("[WS] Connected → MQTT CONNECT");
      { uint8_t pkt[256]; webSocket.sendBIN(pkt, buildConnect(pkt)); }
      break;
    case WStype_BIN:
      if (length >= 4 && payload[0] == 0x20 && payload[3] == 0x00) {
        Serial.println("[MQTT] Connected OK! เริ่มส่งข้อมูลทุกแผนก...\n");
        mqttReady  = true;
        currentBin = 0;
        lastSend   = 0;
      }
      break;
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected");
      mqttReady = false;
      break;
    case WStype_ERROR:
      Serial.println("[WS] Error");
      break;
    default: break;
  }
}

// ─── Publish หนึ่งแผนก ────────────────────────────────────────────────────

void publishBin(int idx) {
  const Bin& b = BINS[idx];

  char topic[64];
  snprintf(topic, sizeof(topic), "waste/bins/%s/sensors", b.bin_code);

  struct tm t;
  char ts[32] = "1970-01-01T00:00:00+07:00";
  if (getLocalTime(&t)) strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S+07:00", &t);

  // Get MAC address for device registration
  String macStr = WiFi.macAddress();

  char msg[600];
  snprintf(msg, sizeof(msg),
    "{\"bin_id\":\"%s\",\"bin_code\":\"%s\","
    "\"sensor_code\":\"%s\","
    "\"mac_address\":\"%s\","
    "\"fill_level\":%.1f,\"weight_kg\":%.1f,"
    "\"temperature_c\":%.1f,\"battery_level\":85,"
    "\"signal_strength\":-65,\"timestamp\":\"%s\"}",
    b.bin_id, b.bin_code, b.sensor_code, macStr.c_str(),
    b.fill_level, b.weight_kg, b.temperature_c, ts);

  uint8_t pkt[600];
  webSocket.sendBIN(pkt, buildPublish(pkt, topic, msg));

  Serial.printf("[%d/%d] %-8s fill=%.0f%% weight=%.1fkg @ %s\n",
    idx+1, BIN_COUNT, b.bin_code, b.fill_level, b.weight_kg, ts);
}

// ─── Setup ────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Waste Bin Multi-Dept Test v" FW_VERSION " ===");
  Serial.printf("จำนวนแผนก: %d\n\n", BIN_COUNT);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - t0 > 30000) { Serial.println("\nTimeout — restart"); ESP.restart(); }
    delay(500); Serial.print(".");
  }
  Serial.println("\nWiFi OK: " + WiFi.localIP().toString());

  configTime(GMT_OFFSET, 0, NTP_SERVER);
  Serial.print("NTP sync");
  struct tm t;
  t0 = millis();
  while (!getLocalTime(&t)) {
    if (millis() - t0 > 15000) { Serial.println(" skipped"); break; }
    delay(500); Serial.print(".");
  }
  Serial.println(" OK");

  webSocket.beginSSL(WS_HOST, WS_PORT, "/", NULL, "mqtt");
  webSocket.onEvent(wsEvent);
  webSocket.setReconnectInterval(5000);
}

// ─── Loop ─────────────────────────────────────────────────────────────────

void loop() {
  webSocket.loop();
  if (!mqttReady) return;

  unsigned long now = millis();

  // ส่งทีละแผนก ห่างกัน 2 วินาที
  if (!allSent && (lastSend == 0 || now - lastSend > 2000)) {
    lastSend = now;
    publishBin(currentBin);
    currentBin++;
    if (currentBin >= BIN_COUNT) {
      allSent = true;
      Serial.println("\n✓ ส่งครบทุกแผนกแล้ว! ส่งซ้ำทุก 60 วินาที");
    }
  }

  // หลังครบรอบ ส่งซ้ำทุก 60 วินาที
  if (allSent && now - lastSend > 60000) {
    allSent    = false;
    currentBin = 0;
    Serial.println("\n--- รอบใหม่ ---");
  }

  // MQTT PING keepalive
  if (now - lastPing > 30000) {
    lastPing = now;
    uint8_t ping[2] = {0xC0, 0x00};
    webSocket.sendBIN(ping, 2);
  }
}
