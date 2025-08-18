/***
 * Single Teensy recording Photodiode, sync signal, and controlling two water valves.
 * 
 * Inputs:
 *   - Analog sensor: A0  (change ANALOG_PIN if needed)
 *   - Digital sensor: 2  (change DIGITAL_PIN if needed)
 * 
 * Outputs:
 *   - Left water valve:  L_water (pin 0)
 *   - Right water valve: R_water (pin 2)
 *   - Speaker:           speaker (pin 1)
 * 
 * Commands (1-byte + optional 16-bit little-endian params):
 *   A = Start task
 *   Z = Stop task
 *   Y = Reboot (Teensy)
 *   L = Turn ON LEFT water for <int16 ms>   (<=0 turns OFF immediately)
 *   R = Turn ON RIGHT water for <int16 ms>  (<=0 turns OFF immediately)
 *   T = Tone: params = <int16 freq Hz>, <int16 dur ms>  (dur<0 => continuous)
 *   X = Clock sync: replies immediately with "SYNC <t_dev_us>"
 * 
 * Streaming (when task_on):
 *   CSV line each sample: micros,analog,digital,
 *   Example: 1234567,512,1
 ***/

// ---------- constants ----------
const long BAUD_RATE = 115200;
const int SAMPLE_RATE = 500;                 // Hz
const unsigned long SAMPLE_INTERVAL_US = 1000000UL / SAMPLE_RATE;

// Sensor pins (change as needed)
const int ANALOG_PIN  = A0;
const int DIGITAL_PIN = 2;

// Existing pins
const int R_water = 2;
const int L_water = 0;
const int speaker = 1;

// ---------- state ----------
bool task_on = false;

volatile bool L_on = false, R_on = false;
unsigned long L_start_ms = 0, R_start_ms = 0;
int L_dur_ms = 0, R_dur_ms = 0;

int tone_freq = 0, tone_dur_ms = 0;

unsigned long last_sample_us = 0;

// ---------- utils ----------
int read16i() {
  union U {
    byte b[2];
    int16_t v;
  } u;

  // Read two bytes (little-endian). If not available, zero-fill.
  for (int i = 0; i < 2; i++) {
    if (Serial.available() > 0) u.b[i] = Serial.read();
    else u.b[i] = 0;
  }
  return (int)u.v;
}


// ---------- setup ----------
void setup() {
  Serial.begin(BAUD_RATE);
  pinMode(R_water, OUTPUT);
  pinMode(L_water, OUTPUT);
  pinMode(speaker, OUTPUT);
  pinMode(DIGITAL_PIN, INPUT_PULLUP); // change to INPUT if external pull resistors
  digitalWrite(R_water, LOW);
  digitalWrite(L_water, LOW);

  // give host time to open port (optional)
  delay(1500);
}

// ---------- command handlers ----------
void handle_cmd(uint8_t cmd) {
  const unsigned long now_ms = millis();

  if (task_on) {
    if (cmd == 'Z') {
      task_on = false;
      // fail-safe: turn everything off
      L_on = R_on = false;
      digitalWrite(L_water, LOW);
      digitalWrite(R_water, LOW);
      noTone(speaker);
    } else if (cmd == 'L') {
      L_dur_ms = read16i();
      if (L_dur_ms <= 0) {
        L_on = false;
        digitalWrite(L_water, LOW);
      } else {
        L_start_ms = now_ms;
        L_on = true;
        digitalWrite(L_water, HIGH);
      }
    } else if (cmd == 'R') {
      R_dur_ms = read16i();
      if (R_dur_ms <= 0) {
        R_on = false;
        digitalWrite(R_water, LOW);
      } else {
        R_start_ms = now_ms;
        R_on = true;
        digitalWrite(R_water, HIGH);
      }
    } else if (cmd == 'T') {
      tone_freq = read16i();
      tone_dur_ms = read16i();
      if (tone_dur_ms >= 0) {
        tone(speaker, tone_freq, tone_dur_ms);
      } else {
        tone(speaker, tone_freq);
      }
    } else if (cmd == 'X') {
      // Clock sync: reply ASAP with device microsecond time
      unsigned long t_dev = micros();
      Serial.print("SYNC ");
      Serial.println(t_dev); // "SYNC <t_dev_us>\n"
    } else {
      // Unknown or not handled in task_on
    }

  } else { // !task_on
    if (cmd == 'A') {
      task_on = true;
      // reset timers on start
      L_on = R_on = false;
      digitalWrite(L_water, LOW);
      digitalWrite(R_water, LOW);
    } else if (cmd == 'Y') {
#ifdef ARDUINO_TEENSYDUINO
      _reboot_Teensyduino_();
#endif
    } else if (cmd == 'X') {
      // Allow sync even when task is off
      unsigned long t_dev = micros();
      Serial.print("SYNC ");
      Serial.println(t_dev);
    }
  }
}

// ---------- loop ----------
void loop() {
  // --- 1) Read serial commands (byte-oriented, as per your protocol) ---
  while (Serial.available() > 0) {
    uint8_t cmd = (uint8_t)Serial.read();
    handle_cmd(cmd);
  }

  // --- 2) Valve auto-off timers (millis, independent L/R) ---
  const unsigned long now_ms = millis();
  if (L_on && (L_dur_ms > 0) && (now_ms - L_start_ms >= (unsigned long)L_dur_ms)) {
    L_on = false;
    digitalWrite(L_water, LOW);
  }
  if (R_on && (R_dur_ms > 0) && (now_ms - R_start_ms >= (unsigned long)R_dur_ms)) {
    R_on = false;
    digitalWrite(R_water, LOW);
  }

  // --- 3) Periodic sampling + streaming (micros-based schedule) ---
  const unsigned long now_us = micros();
  if ((unsigned long)(now_us - last_sample_us) >= SAMPLE_INTERVAL_US) {
    last_sample_us = now_us;

    int a = analogRead(ANALOG_PIN);      // 0..1023 (typical)
    int d = digitalRead(DIGITAL_PIN);    // 0/1

    // CSV: micros,analog,digital,L_on,R_on
    Serial.print(now_us);
    Serial.print(',');
    Serial.print(a);
    Serial.print(',');
    Serial.println(d);
  }
}
