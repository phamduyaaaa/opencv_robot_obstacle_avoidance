#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// ========== PIN DEFINE ==========
#define M1_IN1 D1
#define M1_IN2 D2
#define M1_EN  D5   // PWM

#define M2_IN1 D8
#define M2_IN2 D7
#define M2_EN  D6   // PWM

#define BASE_SPEED   60
#define TURN_SPEED   30   // tốc độ khi rẽ

// ========== WIFI ==========
const char* ssid = "ROBOT_ESP";
const char* password = "12345678";

ESP8266WebServer server(80);

// ========== MOTOR CONTROL ==========
void setMotor(int leftSpeed, int rightSpeed, bool forward) {
  // LEFT
  digitalWrite(M1_IN1, forward ? HIGH : LOW);
  digitalWrite(M1_IN2, forward ? LOW : HIGH);

  // RIGHT
  digitalWrite(M2_IN1, forward ? HIGH : LOW);
  digitalWrite(M2_IN2, forward ? LOW : HIGH);

  analogWrite(M1_EN, leftSpeed);
  analogWrite(M2_EN, rightSpeed);
}

void stopMotor() {
  analogWrite(M1_EN, 0);
  analogWrite(M2_EN, 0);
  digitalWrite(M1_IN1, LOW);
  digitalWrite(M1_IN2, LOW);
  digitalWrite(M2_IN1, LOW);
  digitalWrite(M2_IN2, LOW);
}

// ========== WEB UI ==========
const char MAIN_page[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { text-align: center; font-family: Arial; }
    button {
      width: 120px; height: 60px;
      font-size: 18px; margin: 5px;
    }
  </style>
</head>
<body>
  <h2>ESP8266 Robot Control</h2>
  <div>
    <button onclick="send('forward')">▲</button>
  </div>
  <div>
    <button onclick="send('left')">◀</button>
    <button onclick="send('stop')">■</button>
    <button onclick="send('right')">▶</button>
  </div>
  <div>
    <button onclick="send('back')">▼</button>
  </div>

<script>
function send(cmd) {
  fetch('/' + cmd);
}
</script>
</body>
</html>
)rawliteral";

// ========== SETUP ==========
void setup() {
  pinMode(M1_IN1, OUTPUT);
  pinMode(M1_IN2, OUTPUT);
  pinMode(M1_EN, OUTPUT);
  pinMode(M2_IN1, OUTPUT);
  pinMode(M2_IN2, OUTPUT);
  pinMode(M2_EN, OUTPUT);

  stopMotor();

  WiFi.mode(WIFI_AP);
  WiFi.softAP(ssid, password);

  server.on("/", []() {
    server.send(200, "text/html", MAIN_page);
  });

  server.on("/forward", []() {
    setMotor(BASE_SPEED, BASE_SPEED, true);
    server.send(200, "text/plain", "FORWARD");
  });

  server.on("/back", []() {
    setMotor(BASE_SPEED, BASE_SPEED, false);
    server.send(200, "text/plain", "BACK");
  });

  server.on("/left", []() {
    setMotor(TURN_SPEED, BASE_SPEED, true);
    server.send(200, "text/plain", "LEFT");
  });

  server.on("/right", []() {
    setMotor(BASE_SPEED, TURN_SPEED, true);
    server.send(200, "text/plain", "RIGHT");
  });

  server.on("/stop", []() {
    stopMotor();
    server.send(200, "text/plain", "STOP");
  });

  server.begin();
}

// ========== LOOP ==========
void loop() {
  server.handleClient();
}

