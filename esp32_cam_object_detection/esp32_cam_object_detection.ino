/*
 * ESP32-CAM moving-object detector (AI Thinker pinout)
 *
 * The detector compares two grayscale frames and reports the bounding box of
 * changed pixels. It runs entirely on the ESP32-CAM and requires no cloud
 * service or model download.
 */
#include <Arduino.h>
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

// Fill these in before flashing.
constexpr char WIFI_SSID[] = "";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";

// AI Thinker ESP32-CAM camera pins.
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

constexpr uint8_t PIXEL_DELTA = 28;       // 0-255; raise to ignore noise
constexpr uint16_t MIN_CHANGED_PIXELS = 90;
constexpr uint32_t DETECTION_COOLDOWN_MS = 180;

WebServer server(80);
uint8_t *previousFrame = nullptr;
size_t previousFrameLength = 0;
uint32_t lastDetectionAt = 0;

struct Detection {
  bool detected = false;
  uint16_t changedPixels = 0;
  uint16_t left = 0, top = 0, right = 0, bottom = 0;
};

const char INDEX_HTML[] PROGMEM = R"HTML(
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32-CAM Object Detector</title><style>body{font-family:system-ui;margin:2rem;background:#101418;color:#e8edf2}img{max-width:100%;border-radius:8px}#s{font-size:1.1rem}</style></head>
<body><h1>ESP32-CAM object detector</h1><img id="cam" src="/capture"><p id="s">Starting…</p>
<script>async function tick(){document.querySelector('#cam').src='/capture?t='+Date.now();let r=await fetch('/detect');let d=await r.json();document.querySelector('#s').textContent=d.detected?`Object movement: ${d.changedPixels} pixels, box (${d.left}, ${d.top})–(${d.right}, ${d.bottom})`:'No moving object';}setInterval(tick,700);tick();</script>
</body></html>
)HTML";

bool initCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM; c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_GRAYSCALE;
  c.frame_size = FRAMESIZE_QQVGA; // 160x120: fast enough for local analysis
  c.jpeg_quality = 12;
  c.fb_count = psramFound() ? 2 : 1;
  return esp_camera_init(&c) == ESP_OK;
}

Detection detectMovement(camera_fb_t *frame) {
  Detection result;
  if (!frame || frame->format != PIXFORMAT_GRAYSCALE) return result;

  const uint32_t now = millis();
  if (!previousFrame || previousFrameLength != frame->len) {
    free(previousFrame);
    previousFrame = static_cast<uint8_t *>(malloc(frame->len));
    if (!previousFrame) return result;
    previousFrameLength = frame->len;
    memcpy(previousFrame, frame->buf, frame->len);
    return result;
  }
  if (now - lastDetectionAt < DETECTION_COOLDOWN_MS) return result;
  lastDetectionAt = now;

  const uint16_t width = frame->width, height = frame->height;
  uint16_t minX = width, minY = height, maxX = 0, maxY = 0;
  uint32_t changed = 0;
  // Sample every second pixel. It cuts CPU use by 75% while retaining a usable box.
  for (uint16_t y = 1; y + 1 < height; y += 2) {
    for (uint16_t x = 1; x + 1 < width; x += 2) {
      const size_t i = y * width + x;
      const int delta = abs(int(frame->buf[i]) - int(previousFrame[i]));
      if (delta >= PIXEL_DELTA) {
        ++changed;
        minX = min(minX, x); minY = min(minY, y);
        maxX = max(maxX, x); maxY = max(maxY, y);
      }
    }
  }
  memcpy(previousFrame, frame->buf, frame->len);
  if (changed >= MIN_CHANGED_PIXELS) {
    result.detected = true;
    result.changedPixels = changed > UINT16_MAX ? UINT16_MAX : changed;
    result.left = minX; result.top = minY; result.right = maxX; result.bottom = maxY;
  }
  return result;
}

void handleCapture() {
  camera_fb_t *frame = esp_camera_fb_get();
  if (!frame) { server.send(503, "text/plain", "Camera capture failed"); return; }
  uint8_t *jpg = nullptr; size_t jpgLength = 0;
  const bool converted = frame2jpg(frame, 70, &jpg, &jpgLength);
  esp_camera_fb_return(frame);
  if (!converted) { server.send(500, "text/plain", "JPEG conversion failed"); return; }
  server.sendHeader("Cache-Control", "no-store");
  server.setContentLength(jpgLength);
  server.send(200, "image/jpeg", "");
  server.sendContent(reinterpret_cast<const char *>(jpg), jpgLength);
  free(jpg);
}

void handleDetect() {
  camera_fb_t *frame = esp_camera_fb_get();
  if (!frame) { server.send(503, "application/json", "{\"error\":\"capture failed\"}"); return; }
  Detection d = detectMovement(frame);
  esp_camera_fb_return(frame);
  char json[180];
  snprintf(json, sizeof(json), "{\"detected\":%s,\"changedPixels\":%u,\"left\":%u,\"top\":%u,\"right\":%u,\"bottom\":%u}", d.detected ? "true" : "false", d.changedPixels, d.left, d.top, d.right, d.bottom);
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", json);
}

void setup() {
  Serial.begin(115200);
  if (!initCamera()) { Serial.println("Camera initialization failed"); while (true) delay(1000); }
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print('.'); }
  Serial.printf("\nOpen http://%s\n", WiFi.localIP().toString().c_str());
  server.on("/", HTTP_GET, [] { server.send_P(200, "text/html", INDEX_HTML); });
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/detect", HTTP_GET, handleDetect);
  server.begin();
}

void loop() { server.handleClient(); }
