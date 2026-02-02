

// ========== PIN DEFINE (ESP8266 + L298) ==========

// Motor trái
#define M1_IN1 D1
#define M1_IN2 D2
#define M1_EN  D5   // PWM

// Motor phải
#define M2_IN1 D8
#define M2_IN2 D7
#define M2_EN  D6   // PWM OK


#define SPEED_LEFT   60   // chậm
#define SPEED_RIGHT  60   // chậm

// ================= MOTOR CONTROL =================

void motor_forward() {
  digitalWrite(M1_IN1, HIGH);
  digitalWrite(M1_IN2, LOW);

  digitalWrite(M2_IN1, HIGH);
  digitalWrite(M2_IN2, LOW);
}

void motor_backward() {
  digitalWrite(M1_IN1, LOW);
  digitalWrite(M1_IN2, HIGH);

  digitalWrite(M2_IN1, LOW);
  digitalWrite(M2_IN2, HIGH);
}

void motor_stop() {
  digitalWrite(M1_IN1, LOW);
  digitalWrite(M1_IN2, LOW);
  digitalWrite(M2_IN1, LOW);
  digitalWrite(M2_IN2, LOW);

  analogWrite(M1_EN, 0);
  analogWrite(M2_EN, 0);
}

// ================= SETUP =================

void setup() {
  pinMode(M1_IN1, OUTPUT);
  pinMode(M1_IN2, OUTPUT);
  pinMode(M1_EN, OUTPUT);

  pinMode(M2_IN1, OUTPUT);
  pinMode(M2_IN2, OUTPUT);
  pinMode(M2_EN, OUTPUT);

  motor_stop();
}

// ================= LOOP =================

void loop() {

  // ---- TIẾN CHẬM ----
  motor_forward();
  analogWrite(M1_EN, SPEED_LEFT);
  analogWrite(M2_EN, SPEED_RIGHT);
  delay(4000);
}

