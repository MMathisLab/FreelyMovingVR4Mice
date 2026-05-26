
// Updated version which now also reads TTL state, only samples at given rate
// and uses micros() for more precise timing and sends its time 

const long BAUD_RATE = 9600;   // USB Serial ignores this on Teensy, but set high if using UART
const int SAMPLE_RATE = 1000;                 // Hz
const uint32_t SAMPLE_INTERVAL_MS = 1000UL / SAMPLE_RATE;


int photodiode_state = 0;
int ttl_state = 0;
const int PHOTODIODE_PIN = 14;
const int TTL_PIN = 2;    
elapsedMillis sinceLastSample;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(BAUD_RATE);
  pinMode(PHOTODIODE_PIN, INPUT);
  pinMode(TTL_PIN, INPUT_PULLDOWN);
  analogReadResolution(12);           // 0..4095
  analogReadAveraging(4);             // simple HW averaging for noise reduction

  sinceLastSample = 0;
}

// Extend micros() to 64-bit with rollover handling
static inline uint64_t micros64() {
  static uint32_t last_lo = 0;
  static uint64_t hi = 0;
  uint32_t lo = micros();                     // 32-bit, overflows ~71 min
  if (lo < last_lo) {
    // detected wrap: bump high bits by 2^32
    hi += (1ULL << 32);
  }
  last_lo = lo;
  return hi | lo;
}

void loop() {
  if (sinceLastSample >= SAMPLE_INTERVAL_MS) {
    // Decrement rather than reset to reduce long-term drift if we ever fall a bit behind
    sinceLastSample -= SAMPLE_INTERVAL_MS;

    uint32_t t_ms = millis();                       // timestamp first
    //uint64_t t_us = micros64();  
    int photodiode_adc = analogRead(PHOTODIODE_PIN);
    int ttl_state = digitalReadFast(TTL_PIN);       // fast I/O on Teensy cores

    Serial.print(photodiode_adc);
    Serial.print(",");
    Serial.print(ttl_state);
    Serial.print(",");    
    Serial.println(t_ms);
    // We send photodiode,ttl, teensytime
  }

}