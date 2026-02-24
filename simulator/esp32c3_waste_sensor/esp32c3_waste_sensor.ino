/**
 * Senses Scale — ESP32 Smart Scale Firmware
 * ─────────────────────────────────────────────────────────────────
 * หลักการทำงาน:
 *   1. เชื่อมต่อ WiFi และรับ MAC address
 *   2. เรียก API: GET /api/devices/lookup?mac={MAC}
 *      → ดึงข้อมูลแผนก (bin_code, bin_id, sensor_code, weight_offset)
 *   3. ถ้าไม่ได้ลงทะเบียน → แสดง Serial แล้ว restart ใน 30 วินาที
 *   4. ถ้าลงทะเบียนแล้ว → เชื่อมต่อ MQTT over WSS → ส่งน้ำหนัก demo
 *
 * Libraries (Arduino IDE Library Manager):
 *   - WebSockets  by Markus Sattler (links2004)  v2.x
 *   - ArduinoJson by Benoit Blanchon              v6.x or v7.x
 *
 * Board: ESP32C3 Dev Module (หรือ ESP32S3 Dev Module)
 * Version: 3.0
 */
#define FW_VERSION "3.0"

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <time.h>
#include <WebSocketsClient.h>

// ─── WiFi ──────────────────────────────────────────────────────────────────
const char* WIFI_SSID = "MakerHub_2.4G";
const char* WIFI_PASS = "makerhubhome";

// ─── API (device lookup) ───────────────────────────────────────────────────
const char* API_BASE  = "https://tuh.maker-hub.net";

// ─── MQTT over WSS ─────────────────────────────────────────────────────────
const char* WS_HOST   = "mqtt-tuh.maker-hub.net";
const int   WS_PORT   = 443;
const char* MQTT_USER = "iot_user";
const char* MQTT_PASS = "iotpassword";

// ─── NTP ───────────────────────────────────────────────────────────────────
const char* NTP_SERVER = "pool.ntp.org";
const long  GMT_OFFSET = 25200;  // UTC+7

// ─── Send interval ─────────────────────────────────────────────────────────
const unsigned long SEND_INTERVAL_MS = 30000;  // ส่งทุก 30 วินาที

// ─── Device info (populated from API lookup) ───────────────────────────────
String myMac;
String myBinId;
String myBinCode;
String mySensorCode;
String myLocation;
float  myWeightOffset = 0.0;

// ─── Runtime state ─────────────────────────────────────────────────────────
WebSocketsClient webSocket;
bool          mqttReady = false;
unsigned long lastSend  = 0;
unsigned long lastPing  = 0;

// ─── Demo weight simulation ────────────────────────────────────────────────
// จำลองน้ำหนักขยะติดเชื้อ 0.200 – 4.999 kg
float demoWeightKg() {
  return (float)random(200, 5000) / 1000.0f;
}

// ─── MQTT Packet Helpers ───────────────────────────────────────────────────

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
  // Client ID unique per device: "ss-AABBCCDDEEFF"
  String cid = "ss-" + myMac;
  cid.replace(":", "");

  uint8_t tmp[256]; size_t p = 0;
  tmp[p++] = 0x00; tmp[p++] = 0x04;
  tmp[p++] = 'M';  tmp[p++] = 'Q'; tmp[p++] = 'T'; tmp[p++] = 'T';
  tmp[p++] = 0x04;  // Protocol level MQTT 3.1.1
  tmp[p++] = 0xC2;  // Connect flags: username + password
  tmp[p++] = 0x00; tmp[p++] = 0x3C;  // Keepalive 60s

  size_t l;
  l = cid.length();
  tmp[p++] = 0; tmp[p++] = l; memcpy(tmp+p, cid.c_str(), l); p += l;

  l = strlen(MQTT_USER);
  tmp[p++] = 0; tmp[p++] = l; memcpy(tmp+p, MQTT_USER, l); p += l;

  l = strlen(MQTT_PASS);
  tmp[p++] = 0; tmp[p++] = l; memcpy(tmp+p, MQTT_PASS, l); p += l;

  uint8_t lenBuf[4];
  size_t  lenSz = encodeLen(lenBuf, p);
  buf[0] = 0x10;
  memcpy(buf+1, lenBuf, lenSz);
  memcpy(buf+1+lenSz, tmp, p);
  return 1 + lenSz + p;
}

size_t buildPublish(uint8_t* buf, const char* topic, const char* payload) {
  uint8_t tmp[600]; size_t p = 0;
  size_t tl = strlen(topic), pl = strlen(payload);
  tmp[p++] = 0; tmp[p++] = tl; memcpy(tmp+p, topic, tl); p += tl;
  memcpy(tmp+p, payload, pl);  p += pl;
  uint8_t lenBuf[4];
  size_t  lenSz = encodeLen(lenBuf, p);
  buf[0] = 0x30;
  memcpy(buf+1, lenBuf, lenSz);
  memcpy(buf+1+lenSz, tmp, p);
  return 1 + lenSz + p;
}

// ─── WebSocket / MQTT event ────────────────────────────────────────────────

void wsEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.println("[WS] Connected → MQTT CONNECT");
      { uint8_t pkt[300]; webSocket.sendBIN(pkt, buildConnect(pkt)); }
      break;

    case WStype_BIN:
      if (length >= 4 && payload[0] == 0x20 && payload[3] == 0x00) {
        Serial.println("[MQTT] Connected OK!");
        Serial.printf("📡 แผนก : %s\n", myBinCode.c_str());
        Serial.printf("📍 สถานที่: %s\n", myLocation.c_str());
        Serial.printf("⚖️  Offset : %.3f kg\n\n", myWeightOffset);
        mqttReady = true;
        lastSend  = 0;  // ส่งทันที
      }
      break;

    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected — reconnecting...");
      mqttReady = false;
      break;

    case WStype_ERROR:
      Serial.println("[WS] Error");
      break;

    default: break;
  }
}

// ─── API: ดึงข้อมูลแผนกด้วย MAC address ──────────────────────────────────

bool lookupDevice() {
  Serial.printf("🔍 ค้นหาการลงทะเบียน MAC: %s\n", myMac.c_str());

  WiFiClientSecure client;
  client.setInsecure();  // skip cert verify (ok for embedded)

  HTTPClient http;
  String url = String(API_BASE) + "/api/devices/lookup?mac=" + myMac;
  http.begin(client, url);
  http.setTimeout(10000);

  int httpCode = http.GET();
  if (httpCode != 200) {
    Serial.printf("  ❌ HTTP error: %d\n", httpCode);
    http.end();
    return false;
  }

  String body = http.getString();
  http.end();

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    Serial.printf("  ❌ JSON parse error: %s\n", err.c_str());
    return false;
  }

  if (!doc["registered"].as<bool>()) {
    Serial.println("  ⚠️  ยังไม่ได้ลงทะเบียน!");
    Serial.println("  → เปิด https://tuh.maker-hub.net/add-devices");
    Serial.printf("  → ใส่ MAC: %s และเลือกแผนก\n", myMac.c_str());
    return false;
  }

  myBinId        = doc["bin_id"].as<String>();
  myBinCode      = doc["bin_code"].as<String>();
  mySensorCode   = doc["sensor_code"].as<String>();
  myLocation     = doc["location"].as<String>();
  myWeightOffset = doc["weight_offset"] | 0.0f;

  Serial.printf("  ✅ ลงทะเบียนแล้ว: %s — %s\n", myBinCode.c_str(), myLocation.c_str());
  return true;
}

// ─── Publish ค่าน้ำหนัก ───────────────────────────────────────────────────

void publishWeight() {
  char topic[64];
  snprintf(topic, sizeof(topic), "waste/bins/%s/sensors", myBinCode.c_str());

  struct tm t;
  char ts[32] = "1970-01-01T00:00:00+07:00";
  if (getLocalTime(&t)) strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S+07:00", &t);

  // น้ำหนัก demo + offset
  float weight = demoWeightKg() + myWeightOffset;

  char msg[512];
  snprintf(msg, sizeof(msg),
    "{"
      "\"bin_id\":\"%s\","
      "\"bin_code\":\"%s\","
      "\"sensor_code\":\"%s\","
      "\"mac_address\":\"%s\","
      "\"fill_level\":0,"
      "\"weight_kg\":%.3f,"
      "\"temperature_c\":%.1f,"
      "\"battery_level\":85,"
      "\"signal_strength\":%d,"
      "\"timestamp\":\"%s\""
    "}",
    myBinId.c_str(),
    myBinCode.c_str(),
    mySensorCode.c_str(),
    myMac.c_str(),
    weight,
    23.0f + random(-10, 30) / 10.0f,  // 22.0 – 26.0 °C
    WiFi.RSSI(),
    ts
  );

  uint8_t pkt[600];
  webSocket.sendBIN(pkt, buildPublish(pkt, topic, msg));

  Serial.printf("[%s] weight=%.3f kg  RSSI=%d dBm  @ %s\n",
    myBinCode.c_str(), weight, WiFi.RSSI(), ts);
}

// ─── Setup ────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println();
  Serial.println("╔══════════════════════════════════╗");
  Serial.println("║   Senses Scale v" FW_VERSION "             ║");
  Serial.println("╚══════════════════════════════════╝");

  // ── WiFi ──────────────────────────────────────────────────────
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - t0 > 30000) {
      Serial.println("\nTimeout — restart");
      ESP.restart();
    }
    delay(500); Serial.print(".");
  }
  Serial.println("\nWiFi OK: " + WiFi.localIP().toString());

  myMac = WiFi.macAddress();
  Serial.println("MAC   : " + myMac);

  // ── NTP ───────────────────────────────────────────────────────
  configTime(GMT_OFFSET, 0, NTP_SERVER);
  Serial.print("NTP sync");
  struct tm t;
  t0 = millis();
  while (!getLocalTime(&t)) {
    if (millis() - t0 > 15000) { Serial.println(" skipped"); break; }
    delay(500); Serial.print(".");
  }
  Serial.println(" OK");
  Serial.println();

  // ── Device lookup (ลองสูงสุด 5 ครั้ง) ────────────────────────
  bool registered = false;
  for (int i = 1; i <= 5 && !registered; i++) {
    Serial.printf("[%d/5] ", i);
    registered = lookupDevice();
    if (!registered) delay(5000);
  }

  if (!registered) {
    Serial.println();
    Serial.println("════════════════════════════════════");
    Serial.println("  ไม่พบการลงทะเบียน — restart ใน 30s");
    Serial.println("════════════════════════════════════");
    delay(30000);
    ESP.restart();
  }

  Serial.println();

  // ── MQTT over WSS ─────────────────────────────────────────────
  randomSeed(analogRead(0) ^ millis());
  webSocket.beginSSL(WS_HOST, WS_PORT, "/", NULL, "mqtt");
  webSocket.onEvent(wsEvent);
  webSocket.setReconnectInterval(5000);
}

// ─── Loop ─────────────────────────────────────────────────────────────────

void loop() {
  webSocket.loop();
  if (!mqttReady) return;

  unsigned long now = millis();

  // ส่งน้ำหนักตาม interval
  if (lastSend == 0 || now - lastSend >= SEND_INTERVAL_MS) {
    lastSend = now;
    publishWeight();
  }

  // MQTT PING keepalive ทุก 30 วินาที
  if (now - lastPing >= 30000) {
    lastPing = now;
    uint8_t ping[2] = {0xC0, 0x00};
    webSocket.sendBIN(ping, 2);
  }
}
