#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// ========== PIN DEFINE ==========
// Motor trái
#define M1_IN1 D1
#define M1_IN2 D2
#define M1_EN  D5   // PWM

// Motor phải
#define M2_IN1 D8
#define M2_IN2 D7
#define M2_EN  D6   // PWM

#define SPEED_LEFT   60
#define SPEED_RIGHT  60

// ========== WIFI ==========
const char* ssid = "ROBOT_ESP";
const char* password = "12345678";

ESP8266WebServer server(80);

// ========== MOTOR ==========
void motor_forward() {
  digitalWrite(M1_IN1, HIGH);
  digitalWrite(M1_IN2, LOW);
  digitalWrite(M2_IN1, HIGH);
  digitalWrite(M2_IN2, LOW);
  analogWrite(M1_EN, SPEED_LEFT);
  analogWrite(M2_EN, SPEED_RIGHT);
}

void motor_backward() {
  digitalWrite(M1_IN1, LOW);
  digitalWrite(M1_IN2, HIGH);
  digitalWrite(M2_IN1, LOW);
  digitalWrite(M2_IN2, HIGH);
  analogWrite(M1_EN, SPEED_LEFT);
  analogWrite(M2_EN, SPEED_RIGHT);
}

void motor_stop() {
  digitalWrite(M1_IN1, LOW);
  digitalWrite(M1_IN2, LOW);
  digitalWrite(M2_IN1, LOW);
  digitalWrite(M2_IN2, LOW);
  analogWrite(M1_EN, 0);
  analogWrite(M2_EN, 0);
}

// ========== WEB ==========
void handleRoot() {
  server.send(200, "text/html",
    "<h2>ESP8266 Robot Control</h2>"
    "<a href='/forward'>FORWARD</a><br>"
    "<a href='/back'>BACK</a><br>"
    "<a href='/stop'>STOP</a><br>"
  );
}

void setup() {
  pinMode(M1_IN1, OUTPUT);
  pinMode(M1_IN2, OUTPUT);
  pinMode(M1_EN, OUTPUT);
  pinMode(M2_IN1, OUTPUT);
  pinMode(M2_IN2, OUTPUT);
  pinMode(M2_EN, OUTPUT);

  motor_stop();

  // ===== WIFI AP MODE =====
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ssid, password);

  server.on("/", handleRoot);
  server.on("/forward", []() {
    motor_forward();
    server.send(200, "text/plain", "FORWARD");
  });
  server.on("/back", []() {
    motor_backward();
    server.send(200, "text/plain", "BACK");
  });
  server.on("/stop", []() {
    motor_stop();
    server.send(200, "text/plain", "STOP");
  });

  server.begin();
}

void loop() {
  server.handleClient();
}

