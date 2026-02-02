#include "esp_camera.h"
#include <WiFi.h>

// ===== WIFI CONFIG =====
//const char* ssid = "I-robot Lab_5G";
//const char* password = "irobotlab";
const char* ssid = "Happy House";
const char* password = "66668888";

// ===== CAMERA PINS (AI Thinker) =====
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

// ===== STREAM SERVER =====
#include "esp_http_server.h"

httpd_handle_t stream_httpd = NULL;

static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  char * part_buf[64];

  res = httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=frame");
  if (res != ESP_OK) return res;

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      res = ESP_FAIL;
    } else {
      size_t hlen = snprintf((char *)part_buf, 64,
        "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
        fb->len);
      res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
      if (res == ESP_OK) {
        res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
      }
      if (res == ESP_OK) {
        res = httpd_resp_send_chunk(req, "\r\n", 2);
      }
      esp_camera_fb_return(fb);
    }
    if (res != ESP_OK) break;
  }
  return res;
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;

  httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;

  config.xclk_freq_hz = 21000000;
  
  // --- CẤU HÌNH QUAN TRỌNG ĐỂ STREAM MƯỢT ---
  config.pixel_format = PIXFORMAT_JPEG;
  
  // 1. Độ phân giải thấp (QVGA = 320x240)
  // Nếu vẫn lag, hãy đổi thành FRAMESIZE_QQVGA (160x120)
  config.frame_size   = FRAMESIZE_QQVGA; 

  // 2. Chất lượng ảnh (0-63). Số càng to ảnh càng xấu nhưng stream càng nhanh.
  // 10-15: Đẹp, nặng.
  // 60-63: Xấu (vỡ hạt), rất nhẹ, stream siêu nhanh.
  config.jpeg_quality = 25; 

  // 3. Số lượng bộ nhớ đệm frame. 
  // 2 là tốt để stream liên tục (1 cái đang gửi, 1 cái đang chụp)
  config.fb_count     = 2;
  config.grab_mode    = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_DRAM;
  // ------------------------------------------

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed");
    return;
  }

  WiFi.begin(ssid, password);
  WiFi.setSleep(false);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("Camera Stream: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/stream");

  startCameraServer();
}

void loop() {}
