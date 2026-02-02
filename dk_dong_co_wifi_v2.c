#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// ========== WIFI CONFIG (SỬA LẠI CHO ĐÚNG) ==========
const char* ssid = "Happy House"; 
const char* password = "66668888";

// ========== PIN DEFINE (GIỮ NGUYÊN CỦA BẠN) ==========
#define M1_IN1 D1 // Bánh Trái
#define M1_IN2 D2
#define M1_EN  D5 // PWM

#define M2_IN1 D8 // Bánh Phải
#define M2_IN2 D7
#define M2_EN  D6 // PWM

// Tốc độ (0 - 255)
// Tăng lên nếu robot yếu, giảm đi nếu robot chạy quá nhanh
#define BASE_SPEED   70  // Tốc độ đi thẳng
#define TURN_SPEED   100 // Tốc độ khi rẽ (để quay xe nhanh hơn)

ESP8266WebServer server(80);

// ========== MOTOR CONTROL ==========
void stopMotor() {
  analogWrite(M1_EN, 0);
  analogWrite(M2_EN, 0);
  digitalWrite(M1_IN1, LOW); digitalWrite(M1_IN2, LOW);
  digitalWrite(M2_IN1, LOW); digitalWrite(M2_IN2, LOW);
}

// Hàm điều khiển bánh: speed (-255 đến 255)
// Dương là tiến, Âm là lùi
void setMotor(int speedL, int speedR) {
  // --- MOTOR 1 (LEFT) ---
  if (speedL >= 0) {
    digitalWrite(M1_IN1, HIGH); digitalWrite(M1_IN2, LOW);
    analogWrite(M1_EN, speedL);
  } else {
    digitalWrite(M1_IN1, LOW); digitalWrite(M1_IN2, HIGH);
    analogWrite(M1_EN, -speedL); // Lấy giá trị dương cho PWM
  }

  // --- MOTOR 2 (RIGHT) ---
  if (speedR >= 0) {
    digitalWrite(M2_IN1, HIGH); digitalWrite(M2_IN2, LOW);
    analogWrite(M2_EN, speedR);
  } else {
    digitalWrite(M2_IN1, LOW); digitalWrite(M2_IN2, HIGH);
    analogWrite(M2_EN, -speedR);
  }
}

// ========== SETUP ==========
void setup() {
  Serial.begin(115200);
  
  pinMode(M1_IN1, OUTPUT); pinMode(M1_IN2, OUTPUT); pinMode(M1_EN, OUTPUT);
  pinMode(M2_IN1, OUTPUT); pinMode(M2_IN2, OUTPUT); pinMode(M2_EN, OUTPUT);

  stopMotor();

  // KẾT NỐI WIFI
  WiFi.mode(WIFI_STA); // Chế độ Client
  WiFi.begin(ssid, password);
  
  Serial.println();
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.print("Connected! IP Address: ");
  Serial.println(WiFi.localIP()); // <--- NHỚ SỐ NÀY ĐỂ ĐIỀN VÀO PYTHON

  // CÁC LỆNH ĐIỀU KHIỂN
  server.on("/", []() { server.send(200, "text/plain", "ESP8266 Robot Ready"); });

  server.on("/forward", []() {
    setMotor(BASE_SPEED, BASE_SPEED); // Đi thẳng đều
    server.send(200, "text/plain", "OK");
  });

  server.on("/back", []() {
    setMotor(-BASE_SPEED, -BASE_SPEED); // Lùi lại
    server.send(200, "text/plain", "OK");
  });

  // Rẽ Trái tại chỗ (Xoay tank) để né vật cản tốt hơn
  server.on("/left", []() {
    setMotor(-TURN_SPEED, TURN_SPEED); // Trái lùi, Phải tiến -> Xoay trái tại chỗ
    server.send(200, "text/plain", "OK");
  });

  // Rẽ Phải tại chỗ
  server.on("/right", []() {
    setMotor(TURN_SPEED, -TURN_SPEED); // Trái tiến, Phải lùi -> Xoay phải tại chỗ
    server.send(200, "text/plain", "OK");
  });

  server.on("/stop", []() {
    stopMotor();
    server.send(200, "text/plain", "OK");
  });

  server.begin();
}

void loop() {
  server.handleClient();
}
